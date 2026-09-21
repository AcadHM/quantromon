r"""Quantromon layout generator for Qiskit Metal.

Reproduces the device in the SEM of Salunkhe et al., "The quantromon: a
qubit-resonator system with orthogonal qubit and readout modes",
APL Quantum 2, 026123 (2025) / arXiv:2501.17439, Fig. 1(c) and its inset.

Circuit (paper, Sec. II)
------------------------
The linear resonator inductance L_R is a 500 nm wide meandering line split
into three sections in series::

    P1 pad --[ L1 ]-- A --[ L2 ]-- B --[ L1 ]-- P3 pad
                       \                 /
                        SQUID1 - P2 - SQUID2

L2 (the middle section, ``b = L2 / L_R``) is shunted by two Josephson
junctions in series with the floating centre pad P2 between them, so
``A -> SQUID1 -> P2 -> SQUID2 -> B -> L2 -> A`` closes the *quantromon loop*.
In this sample each junction is itself a small SQUID, which is what the two
red arrows in the SEM point at.

L2 is drawn as a *folded hairpin*: the line snakes out to the far end and
comes back alongside itself.  That is not decoration - it is what keeps the
quantromon loop area down to the narrow slot between the two strands, so the
loop stays flux-quiet while the wire stays long.  The two L1 sections use the
same generator with fewer rows, which is why one component builds all three.

Geometry provenance
-------------------
Every number in ``quantromon_geometry()`` was measured off the published SEM.
The scale bar there is 120 px = 20 um, i.e. 6.0 px/um, and the origin used
below is the centre of pad P2.  Two independent cross-checks come out right:
the meander line measures 500 nm, as the paper states, and the SQUID-to-
quantromon loop area ratio comes out at 6.9% against the 6.8% quoted there.

The one number that does not match the paper is ``b``: the drawn lengths give
``b = 0.503``, whereas the paper quotes ``b ~ 0.4`` for the three samples it
reports on.  Fig. 1(c) is evidently a different device from those; setting
``n_rows_l2=6`` gives ``b = 0.431`` if you want a b ~ 0.4 variant.

Usage
-----
    python -m quantromon.paper.metal      # figures + GDS into ./out/
    from quantromon.paper.metal import build_quantromon, quantromon_geometry
"""

from __future__ import annotations

import os

import numpy as np

import qiskit_metal as qm
from qiskit_metal import Dict, designs, draw
from qiskit_metal.qlibrary.core import QComponent

__all__ = [
    "quantromon_geometry",
    "HairpinMeander",
    "QuantromonCore",
    "PatchLead",
    "build_quantromon",
    "make_design",
    "section_lengths",
]


# --------------------------------------------------------------------------
# Measured geometry
# --------------------------------------------------------------------------
def quantromon_geometry(**overrides) -> Dict:
    """Measured quantromon dimensions, in micron, as a mutable ``Dict``.

    Pass keyword overrides to sweep a parameter, e.g.
    ``quantromon_geometry(n_rows_l2=6)`` shortens L2 and so lowers ``b``.
    """
    g = Dict(
        # --- the 500 nm line and its meander lattice -----------------------
        trace_width=0.50,  # paper: "a 500 nm wide meandering line"
        pitch=3.21,  # row-to-row pitch of the meander
        fillet=1.55,  # U-turn radius, just under pitch/2
        half_width=16.60,  # outer U-turns sit at +-half_width
        x_inner=2.30,  # inner U-turns sit at +-x_inner
        x_port=7.05,  # where a hairpin's two ends leave the pad line
        # --- the three inductor sections -----------------------------------
        n_rows_l2=8,  # middle section: 8 rows, folds upwards
        lead_l2=4.08,  # straight lead-in before the first L2 row
        n_rows_l1=4,  # outer sections: 4 rows each, fold downwards
        lead_l1=3.75,
        arm_centre=28.00,  # |x| of the centre of each L1 hairpin
        # --- central pads P1 / P2 / P3 -------------------------------------
        pad_line_width=0.60,
        pad_line_reach=21.00,  # P1/P3 line runs from |x| = pad_line_reach ...
        pad_line_tip=5.30,  # ... inwards to |x| = pad_line_tip
        p2_width=2.33,  # centre pad P2
        p2_height=7.45,
        p2_stem_width=1.00,  # narrow line leaving P2
        # --- the two SQUIDs bridging P1-P2 and P2-P3 -----------------------
        squid_height=1.95,  # vertical separation of the two SQUID arms
        squid_lead_width=0.30,
        jj_x=3.00,  # |x| of the junctions inside each SQUID
        jj_length=0.50,
        jj_width=0.30,
        # --- leads out to the (off-frame) antenna pads ---------------------
        lead_length=22.70,  # L1 leads, to the edge of the published frame
        p2_stem_length=41.00,
        patch_radius=46.70,  # all three overlap patches sit this far out
        patch_width=3.70,
        patch_height=2.50,
        # --- layers --------------------------------------------------------
        layer_base=1,  # base wiring layer
        layer_jj=2,  # junction layer
    )
    unknown = set(overrides) - set(g)
    if unknown:
        raise KeyError(f"unknown geometry key(s): {sorted(unknown)}")
    g.update(overrides)
    return g


def _um(value) -> str:
    """Format a micron number as a Qiskit Metal option string."""
    return f"{value}um"


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------
def _hairpin_centreline(n_rows, pitch, half_width, x_inner, x_port, lead):
    """Centreline of a folded-hairpin meander, as a list of (x, y) corners.

    The line enters at ``(-x_port, 0)``, snakes upwards over ``n_rows`` rows
    alternating between the outer and inner turn columns, crosses over on the
    top row, then snakes back down as the mirror image and leaves at
    ``(+x_port, 0)``.  Both ends therefore sit on the same pad line, which is
    what makes the enclosed loop a narrow central slot.
    """
    rows = [lead + k * pitch for k in range(n_rows)]
    half = [(-x_port, 0.0), (-x_port, rows[0])]
    for k in range(n_rows - 1):
        x_turn = -half_width if k % 2 == 0 else -x_inner
        half += [(x_turn, rows[k]), (x_turn, rows[k + 1])]
    return half + [(-x, y) for x, y in reversed(half)]


class HairpinMeander(QComponent):
    """A folded-hairpin meander inductor: one L1 or L2 section.

    Both ends leave the structure on the same side, ``2 * x_port`` apart, so
    the component can be dropped straight onto a pad line.
    """

    default_options = Dict(
        n_rows="8",
        pitch="3.21um",
        half_width="16.6um",
        x_inner="2.3um",
        x_port="7.05um",
        lead_length="4.08um",
        trace_width="0.5um",
        fillet="1.55um",
        pos_x="0um",
        pos_y="0um",
        orientation="0",
        layer="1",
        chip="main",
    )
    component_metadata = Dict(short_name="meander")
    TOOLTIP = "Folded-hairpin meander inductor (quantromon L1 / L2 section)."

    def make(self):
        p = self.p
        pts = _hairpin_centreline(
            int(p.n_rows),
            p.pitch,
            p.half_width,
            p.x_inner,
            p.x_port,
            p.lead_length,
        )
        line = draw.LineString(pts)
        line = draw.rotate(line, p.orientation, origin=(0, 0))
        line = draw.translate(line, p.pos_x, p.pos_y)

        self.add_qgeometry(
            "path",
            {"trace": line},
            width=p.trace_width,
            fillet=p.fillet,
            layer=p.layer,
            chip=p.chip,
        )

        # Pins point back down the lead, i.e. at the pad line the hairpin
        # lands on.
        coords = np.asarray(line.coords)
        self.add_pin("a", coords[1::-1], p.trace_width, input_as_norm=True)
        self.add_pin("b", coords[-2:], p.trace_width, input_as_norm=True)


class QuantromonCore(QComponent):
    """Pads P1, P2, P3 and the two SQUIDs that bridge them.

    P1 and P3 each reach in as a thin line that turns down into a short tab;
    that tab, the centre pad P2 and two thin arms enclose the small SQUID
    loop.  Each arm carries one junction, so each bridge is a SQUID and the
    pair of bridges closes the quantromon loop through L2.
    """

    default_options = Dict(
        pad_line_width="0.6um",
        pad_line_reach="21um",
        pad_line_tip="5.3um",
        p2_width="2.33um",
        p2_height="7.45um",
        squid_height="1.95um",
        squid_lead_width="0.3um",
        jj_x="3um",
        jj_length="0.5um",
        jj_width="0.3um",
        l2_port="7.05um",
        pos_x="0um",
        pos_y="0um",
        orientation="0",
        layer="1",
        layer_jj="2",
        junction_qgeometry=False,
        chip="main",
    )
    component_metadata = Dict(short_name="quantromon")
    TOOLTIP = "Quantromon centre: pads P1/P2/P3 plus the two SQUIDs."

    def make(self):
        p = self.p
        half_p2 = p.p2_width / 2.0
        y_lo = -p.squid_height

        # P2 sits with its top edge flush with the P1/P3 lines and hangs down
        # past the lower SQUID arm.
        p2 = draw.rectangle(p.p2_width, p.p2_height)
        p2 = draw.translate(p2, 0.0, p.pad_line_width / 2.0 - p.p2_height / 2.0)

        pad_lines, squid_leads, junctions = {}, {}, {}
        for sgn, pad in ((-1.0, "p1"), (+1.0, "p3")):
            # L-shaped approach: thin line inwards, then a tab down to the
            # lower SQUID arm.
            pad_lines[pad] = draw.LineString(
                [
                    (sgn * p.pad_line_reach, 0.0),
                    (sgn * p.pad_line_tip, 0.0),
                    (sgn * p.pad_line_tip, y_lo),
                ]
            )
            # Two arms across the gap to P2, each broken by a junction.
            for arm, y in (("top", 0.0), ("bot", y_lo)):
                x_pad = sgn * (p.pad_line_tip - p.pad_line_width / 2.0)
                x_jj_out = sgn * (p.jj_x + p.jj_length / 2.0)
                x_jj_in = sgn * (p.jj_x - p.jj_length / 2.0)
                squid_leads[f"{pad}_{arm}_outer"] = draw.LineString(
                    [(x_pad, y), (x_jj_out, y)]
                )
                squid_leads[f"{pad}_{arm}_inner"] = draw.LineString(
                    [(x_jj_in, y), (sgn * half_p2, y)]
                )
                junctions[f"jj_{pad}_{arm}"] = draw.LineString(
                    [(x_jj_out, y), (x_jj_in, y)]
                )

        names = ["p2", *pad_lines, *squid_leads, *junctions]
        shapes = [p2, *pad_lines.values(), *squid_leads.values(), *junctions.values()]
        shapes = draw.rotate(shapes, p.orientation, origin=(0, 0))
        shapes = draw.translate(shapes, p.pos_x, p.pos_y)
        shapes = dict(zip(names, shapes))

        self.add_qgeometry(
            "poly", {"p2": shapes["p2"]}, layer=p.layer, chip=p.chip
        )
        self.add_qgeometry(
            "path",
            {k: shapes[k] for k in pad_lines},
            width=p.pad_line_width,
            layer=p.layer,
            chip=p.chip,
        )
        self.add_qgeometry(
            "path",
            {k: shapes[k] for k in squid_leads},
            width=p.squid_lead_width,
            layer=p.layer_jj,
            chip=p.chip,
        )
        # Junctions as drawn metal by default so that the GDS is fabricable
        # as-is; flip ``junction_qgeometry`` to put them in Metal's junction
        # table instead, which is what LOM / Ansys renderers want.
        self.add_qgeometry(
            "junction" if p.junction_qgeometry else "path",
            {k: shapes[k] for k in junctions},
            width=p.jj_width,
            layer=p.layer_jj,
            chip=p.chip,
        )

        # Pins: the two outer ends of the pad lines, the two spots where L2
        # lands, and the bottom of P2 where its stem leaves.
        rot = np.deg2rad(p.orientation)
        rmat = np.array([[np.cos(rot), -np.sin(rot)], [np.sin(rot), np.cos(rot)]])
        offset = np.array([p.pos_x, p.pos_y])

        def place(pts):
            return np.asarray(pts) @ rmat.T + offset

        for sgn, pad in ((-1.0, "p1"), (+1.0, "p3")):
            self.add_pin(
                f"{pad}_out",
                place([(sgn * (p.pad_line_reach - p.pad_line_width), 0.0),
                       (sgn * p.pad_line_reach, 0.0)]),
                p.pad_line_width,
                input_as_norm=True,
            )
            self.add_pin(
                f"l2_{pad}",
                place([(sgn * p.l2_port, -p.pad_line_width),
                       (sgn * p.l2_port, 0.0)]),
                p.pad_line_width,
                input_as_norm=True,
            )
        y_bot = p.pad_line_width / 2.0 - p.p2_height
        self.add_pin(
            "p2_out",
            place([(0.0, y_bot + p.pad_line_width), (0.0, y_bot)]),
            p.p2_width,
            input_as_norm=True,
        )


class PatchLead(QComponent):
    """Straight lead out to an antenna pad, with the inter-layer patch.

    The little rectangles sitting on the long straight runs in the SEM are
    where the thin high-inductance line overlaps the base metal; they are
    drawn here so the lead reads the same way as the micrograph.
    """

    default_options = Dict(
        trace_width="0.5um",
        length="22.7um",
        patch_at="11.65um",
        patch_width="3.7um",
        patch_height="2.5um",
        pos_x="0um",
        pos_y="0um",
        orientation="0",
        layer="1",
        chip="main",
    )
    component_metadata = Dict(short_name="lead")
    TOOLTIP = "Straight lead with an inter-layer overlap patch."

    def make(self):
        p = self.p
        line = draw.LineString([(0.0, 0.0), (p.length, 0.0)])
        shapes = {"line": line}
        if 0.0 < p.patch_at < p.length:
            patch = draw.rectangle(p.patch_width, p.patch_height)
            shapes["patch"] = draw.translate(patch, p.patch_at, 0.0)

        names = list(shapes)
        moved = draw.rotate(list(shapes.values()), p.orientation, origin=(0, 0))
        moved = draw.translate(moved, p.pos_x, p.pos_y)
        shapes = dict(zip(names, moved))

        self.add_qgeometry(
            "path",
            {"line": shapes["line"]},
            width=p.trace_width,
            layer=p.layer,
            chip=p.chip,
        )
        if "patch" in shapes:
            self.add_qgeometry(
                "poly", {"patch": shapes["patch"]}, layer=p.layer, chip=p.chip
            )

        coords = np.asarray(shapes["line"].coords)
        self.add_pin("start", coords[1::-1], p.trace_width, input_as_norm=True)
        self.add_pin("end", coords[-2:], p.trace_width, input_as_norm=True)


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------
def build_quantromon(design, name: str = "Q", geom: Dict | None = None) -> Dict:
    """Place a whole quantromon on ``design`` and return its components."""
    g = geom if geom is not None else quantromon_geometry()

    core = QuantromonCore(
        design,
        f"{name}_core",
        options=dict(
            pad_line_width=_um(g.pad_line_width),
            pad_line_reach=_um(g.pad_line_reach),
            pad_line_tip=_um(g.pad_line_tip),
            p2_width=_um(g.p2_width),
            p2_height=_um(g.p2_height),
            squid_height=_um(g.squid_height),
            squid_lead_width=_um(g.squid_lead_width),
            jj_x=_um(g.jj_x),
            jj_length=_um(g.jj_length),
            jj_width=_um(g.jj_width),
            l2_port=_um(g.x_port),
            layer=str(g.layer_base),
            layer_jj=str(g.layer_jj),
        ),
    )

    hairpin = dict(
        pitch=_um(g.pitch),
        half_width=_um(g.half_width),
        x_inner=_um(g.x_inner),
        x_port=_um(g.x_port),
        trace_width=_um(g.trace_width),
        fillet=_um(g.fillet),
        layer=str(g.layer_base),
    )

    # L2: folds upwards off the P1/P3 pad lines, closing the quantromon loop.
    l2 = HairpinMeander(
        design,
        f"{name}_L2",
        options=dict(
            n_rows=str(g.n_rows_l2),
            lead_length=_um(g.lead_l2),
            pos_x="0um",
            pos_y="0um",
            orientation="0",
            **hairpin,
        ),
    )

    # L1: same generator, four rows, folded downwards on either side.  Its
    # inner end lands where the P1/P3 pad line starts, its outer end feeds
    # the lead to the antenna pad.
    arms, leads = {}, {}
    lead_start = g.arm_centre + g.x_port  # |x| where an L1 lead begins
    p2_stem_start = g.p2_height - g.pad_line_width / 2.0  # |y| for P2's stem
    for sgn, side in ((-1.0, "left"), (+1.0, "right")):
        arms[side] = HairpinMeander(
            design,
            f"{name}_L1_{side}",
            options=dict(
                n_rows=str(g.n_rows_l1),
                lead_length=_um(g.lead_l1),
                pos_x=_um(sgn * g.arm_centre),
                pos_y="0um",
                orientation="180",
                **hairpin,
            ),
        )
        leads[side] = PatchLead(
            design,
            f"{name}_lead_{side}",
            options=dict(
                trace_width=_um(g.trace_width),
                length=_um(g.lead_length),
                patch_at=_um(g.patch_radius - lead_start),
                patch_width=_um(g.patch_width),
                patch_height=_um(g.patch_height),
                pos_x=_um(sgn * lead_start),
                pos_y="0um",
                orientation="0" if sgn > 0 else "180",
                layer=str(g.layer_base),
            ),
        )

    # P2's stem runs the other way, to the third antenna pad.
    leads["p2"] = PatchLead(
        design,
        f"{name}_lead_p2",
        options=dict(
            trace_width=_um(g.p2_stem_width),
            length=_um(g.p2_stem_length),
            patch_at=_um(g.patch_radius - p2_stem_start),
            patch_width=_um(g.patch_width),
            patch_height=_um(g.patch_height),
            pos_x="0um",
            pos_y=_um(-p2_stem_start),
            orientation="270",
            layer=str(g.layer_base),
        ),
    )

    return Dict(core=core, l2=l2, arms=Dict(arms), leads=Dict(leads))


def make_design(geom: Dict | None = None, margin: float = 8.0):
    """Build a ``DesignPlanar`` holding a single quantromon, chip sized to fit.

    The real device has no ground plane - it is a hybrid 2D-3D sample where
    bare wires sit on the substrate and the pads act as the antenna for a 3D
    waveguide.  So every shape here is additive metal (``subtract=False``) and
    the ground plane is switched off on export.
    """
    g = geom if geom is not None else quantromon_geometry()

    design = designs.DesignPlanar({}, overwrite_enabled=True)
    parts = build_quantromon(design, "Q", g)

    bounds = np.array(
        [c.qgeometry_bounds() for c in design.components.values()]
    )  # mm
    x0, y0 = bounds[:, 0].min(), bounds[:, 1].min()
    x1, y1 = bounds[:, 2].max(), bounds[:, 3].max()
    design.chips.main.size.update(
        size_x=f"{(x1 - x0) * 1e3 + 2 * margin}um",
        size_y=f"{(y1 - y0) * 1e3 + 2 * margin}um",
        center_x=f"{(x0 + x1) * 0.5e3}um",
        center_y=f"{(y0 + y1) * 0.5e3}um",
    )
    design.rebuild()
    return design, parts


# --------------------------------------------------------------------------
# Bookkeeping: how long is each inductor section?
# --------------------------------------------------------------------------
def section_lengths(geom: Dict | None = None) -> Dict:
    """Drawn length of each inductor section, in micron.

    Reported both as the raw polyline and with the fillets taken out: a 90
    degree corner of radius r replaces ``2r`` of straight line with a quarter
    arc, so each corner is ``(2 - pi/2) * r`` shorter than it looks.
    """
    g = geom if geom is not None else quantromon_geometry()
    out = Dict()
    for tag, n_rows, lead in (
        ("L2", g.n_rows_l2, g.lead_l2),
        ("L1", g.n_rows_l1, g.lead_l1),
    ):
        pts = np.asarray(
            _hairpin_centreline(
                n_rows, g.pitch, g.half_width, g.x_inner, g.x_port, lead
            )
        )
        raw = np.abs(np.diff(pts, axis=0)).sum()
        corners = len(pts) - 2
        out[tag] = Dict(
            polyline=raw,
            filleted=raw - corners * (2.0 - np.pi / 2.0) * g.fillet,
            corners=corners,
        )

    l_r = out.L2.filleted + 2 * out.L1.filleted
    out.L_R = l_r
    out.b = out.L2.filleted / l_r

    # Flux-enclosing (inner-edge) loop areas.  The quantromon loop is the
    # slot between the two strands of the L2 hairpin; each SQUID loop is the
    # little rectangle between a pad tab and P2.
    out.area_quantromon = (2 * g.x_inner - g.trace_width) * (
        (g.n_rows_l2 - 1) * g.pitch
    )
    out.area_squid = (
        g.pad_line_tip - g.pad_line_width / 2.0 - g.p2_width / 2.0
    ) * (g.squid_height - g.squid_lead_width)
    out.area_ratio = out.area_squid / out.area_quantromon
    return out


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------
# The published inset spans this window in device coordinates (micron),
# origin at the centre of P2.
SEM_WINDOW = (-57.5, 54.8, -31.8, 39.9)


def plot_sem_style(design, window=SEM_WINDOW, figsize=(9.0, 5.7), scale_bar=20.0):
    """Render the design the way the micrograph shows it: metal on substrate."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize)
    qm.view(design, ax=ax, chip_outline=False)

    ax.set_facecolor("#8d8d8d")
    for artist in list(ax.collections) + list(ax.patches):
        artist.set_facecolor("#f4f4f4")
        artist.set_edgecolor("none")
        artist.set_linewidth(0.0)
        artist.set_alpha(1.0)

    x0, x1, y0, y1 = window
    ax.set_xlim(x0 * 1e-3, x1 * 1e-3)
    ax.set_ylim(y0 * 1e-3, y1 * 1e-3)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    if scale_bar:
        bar_x = (x1 - 0.10 * (x1 - x0) - scale_bar) * 1e-3
        bar_y = (y0 + 0.09 * (y1 - y0)) * 1e-3
        ax.plot(
            [bar_x, bar_x + scale_bar * 1e-3],
            [bar_y, bar_y],
            lw=4,
            color="white",
            solid_capstyle="butt",
        )
        ax.text(
            bar_x + scale_bar * 0.5e-3,
            bar_y + 0.012 * (y1 - y0) * 1e-3,
            f"{scale_bar:.0f} um",
            color="white",
            ha="center",
            va="bottom",
            fontsize=13,
        )
    fig.tight_layout(pad=0.2)
    return fig


def export_gds(design, path: str, geom: Dict | None = None):
    """Write a GDS of the drawn metal.

    Nothing here is ``subtract=True``, so Metal emits no ground-plane
    polygon and the file ends up holding only the wires and pads - which is
    what this maskless sample needs.  Leave ``ground_plane`` alone: setting
    it to ``'False'`` drops the chip cell and with it the geometry.
    """
    g = geom if geom is not None else quantromon_geometry()
    layers = {int(g.layer_base): False, int(g.layer_jj): False}

    gds = design.renderers.gds
    gds.options["fabricate"] = "False"
    gds.options["max_points"] = "8191"
    # No ground plane, so there is nothing to cheese or to keep clear of.
    for key in ("cheese", "no_cheese"):
        gds.options[key]["view_in_file"]["main"] = dict(layers)
    gds.export_to_gds(path)
    return path


# --------------------------------------------------------------------------
def main(outdir: str = "out"):
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    geom = quantromon_geometry()
    design, _ = make_design(geom)

    lens = section_lengths(geom)
    print(f"components      : {len(design.components)}")
    print(f"L1 (each outer) : {lens.L1.filleted:7.1f} um "
          f"({lens.L1.corners} corners, {lens.L1.polyline:.1f} um unfilleted)")
    print(f"L2 (middle)     : {lens.L2.filleted:7.1f} um "
          f"({lens.L2.corners} corners, {lens.L2.polyline:.1f} um unfilleted)")
    print(f"L_R total       : {lens.L_R:7.1f} um")
    print(f"b = L2 / L_R    : {lens.b:7.3f}")
    print(f"quantromon loop : {lens.area_quantromon:7.1f} um^2")
    print(f"SQUID loop      : {lens.area_squid:7.1f} um^2  "
          f"(ratio {lens.area_ratio:.1%}, paper quotes 6.8%)")

    fig = plot_sem_style(design)
    fig.savefig(f"{outdir}/quantromon_sem_style.png", dpi=200)
    plt.close(fig)

    fig = qm.view(design, figsize=(9, 7), title="Quantromon (Qiskit Metal)")
    fig.savefig(f"{outdir}/quantromon_metal_view.png", dpi=170,
                bbox_inches="tight")
    plt.close(fig)

    gds_path = export_gds(design, f"{outdir}/quantromon.gds", geom)
    print(f"wrote {outdir}/quantromon_sem_style.png, "
          f"{outdir}/quantromon_metal_view.png, {gds_path}")
    return design


if __name__ == "__main__":
    # Only force a headless backend when run as a script; importing this
    # module from a notebook must leave the inline backend alone.
    import matplotlib

    matplotlib.use("Agg")
    main()
