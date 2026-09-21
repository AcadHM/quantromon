"""Parse the QuantroTa DXF and label the three Ta pad+IDC islands.

Phase 1 unions L6+L7 (Ta pads+IDC) with L2D2100 Al wiring (meander cut
at y = 0) and L2D2400 JJ fingers. L3 (Dolan mask) stays out so the
0.2 um junction gaps stay open. Alignment marks stay out.

DXF coordinates are microns. Qiskit Metal native units are millimetres.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.ops import unary_union

from quantromon.paths import default_dxf, outdir

PAD_LAYERS = ("L6D1800", "L7D1800")
AL_WIRE_LAYERS = ("L2D2100",)
JJ_FINGER_LAYERS = ("L2D2400",)
DEFAULT_DXF = default_dxf()
UM_TO_MM = 1e-3
MIN_AREA_UM2 = 1.0
AL_MIN_AREA_UM2 = 0.05
# Designed Ta/Al gaps: 0.55 um on P1/P3, 2.0 um on P2. Closing radius
# must be > 1.0 um so the P2 bar glues on.
AL_JOIN_UM = 1.2
# Half-width of the inductor cut. Removes |y| < this from the meander
# body so P1 Al and P3 Al do not meet. The P2 Al bar is a separate island.
INDUCTOR_CUT_UM = 0.6
# Designed P1-P2 and P3-P2 JJ openings on L2D2400. Do not close these.
JJ_GAP_MIN_UM = 0.05
JJ_GAP_MAX_UM = 0.50


def _lwpolyline_to_polygon(entity) -> Polygon:
    pts = [(x, y) for x, y in entity.get_points("xy")]
    if not pts:
        raise ValueError("LWPOLYLINE with no points")
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def load_dxf_polygons(dxf_path: Path | None = None, layers=PAD_LAYERS):
    """Return shapely polygons in DXF units (microns)."""
    path = Path(dxf_path) if dxf_path is not None else DEFAULT_DXF
    if not path.is_file():
        raise FileNotFoundError(path)
    doc = ezdxf.readfile(path)
    geoms = []
    for entity in doc.modelspace():
        if entity.dxftype() != "LWPOLYLINE":
            continue
        if entity.dxf.layer not in layers:
            continue
        geoms.append(_lwpolyline_to_polygon(entity))
    if not geoms:
        raise RuntimeError(f"no LWPOLYLINE on layers {layers} in {path}")
    return geoms


def _as_parts(geom, min_area=MIN_AREA_UM2):
    if geom is None or geom.is_empty:
        return []
    parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    return [g for g in parts if g.area >= min_area]


def _drop_holes(g):
    if g.is_empty:
        return g
    if g.geom_type == "Polygon":
        return Polygon(g.exterior) if g.interiors else g
    if g.geom_type == "MultiPolygon":
        return unary_union(
            [Polygon(p.exterior) if p.interiors else p for p in g.geoms]
        )
    return g


def label_pad_islands(parts):
    """Name three islands: leftmost P2, remaining upper P1, remaining lower P3."""
    if len(parts) != 3:
        summary = []
        for i, g in enumerate(sorted(parts, key=lambda p: -p.area)):
            x0, y0, x1, y1 = g.bounds
            c = g.centroid
            summary.append(
                f"  [{i}] area={g.area:.2f} um^2  "
                f"centroid=({c.x:.2f},{c.y:.2f})  "
                f"bbox=({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f})"
            )
        raise RuntimeError(
            f"expected 3 pad islands, got {len(parts)}:\n" + "\n".join(summary)
        )
    by_x = sorted(parts, key=lambda g: g.centroid.x)
    p2 = by_x[0]
    rest = sorted(by_x[1:], key=lambda g: g.centroid.y, reverse=True)
    p1, p3 = rest
    return {"P1": p1, "P2": p2, "P3": p3}


def load_al_wiring(dxf_path: Path | None = None):
    """All finished Al traces on L2D2100 (leads, meander, JJ-approach lines)."""
    return load_dxf_polygons(dxf_path, layers=AL_WIRE_LAYERS)


def split_al_for_lom(pads: dict, dxf_path: Path | None = None) -> dict:
    """Split L2D2100 so the meander does not DC-short P1 to P3.

    The Al island nearest P2 (2 um gap bar) stays on P2. The remaining
    meander body is clipped at y = +/- INDUCTOR_CUT_UM.
    """
    parts = _as_parts(unary_union(load_al_wiring(dxf_path)), min_area=AL_MIN_AREA_UM2)
    if not parts:
        raise RuntimeError("no L2D2100 Al wiring found")
    ranked = sorted(parts, key=lambda g: g.distance(pads["P2"]))
    p2_al = ranked[0]
    rest = unary_union(ranked[1:]) if len(ranked) > 1 else Polygon()
    world = 1.0e5
    cut = INDUCTOR_CUT_UM
    p1_al = rest.intersection(box(-world, cut, world, world))
    p3_al = rest.intersection(box(-world, -world, world, -cut))
    return {"P1": p1_al, "P2": p2_al, "P3": p3_al}


def attach_al_wiring(pads: dict, dxf_path: Path | None = None) -> dict:
    """Glue split L2D2100 Al onto the Ta islands. Still three islands."""
    pieces = split_al_for_lom(pads, dxf_path)
    join = AL_JOIN_UM
    out = {}
    for name, pad in pads.items():
        al = pieces[name]
        if al is None or al.is_empty:
            g = pad
        else:
            g = unary_union([pad, al]).buffer(join).buffer(-join)
        out[name] = _drop_holes(g)
    names = list(out)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if out[a].intersects(out[b]):
                raise RuntimeError(
                    f"Al wiring fused {a} to {b}. Inductor cut failed or a JJ was included."
                )
    for name in names:
        if out[name].distance(pads[name]) > 1e-6 and not out[name].intersects(pads[name]):
            raise RuntimeError(f"Al wiring did not glue onto {name}")
        extra = out[name].difference(pads[name].buffer(0.01))
        if extra.is_empty or extra.area < 1.0:
            raise RuntimeError(f"{name} has no Al wiring attached")
    return out


def attach_al_leads(pads: dict, dxf_path: Path | None = None) -> dict:
    """Back-compat alias: now attaches full L2D2100 wiring, not only 1 um stubs."""
    return attach_al_wiring(pads, dxf_path)


def load_jj_fingers(dxf_path: Path | None = None):
    """L2D2400 extra-dose SJ fingers. Not L3 (process mask)."""
    return load_dxf_polygons(dxf_path, layers=JJ_FINGER_LAYERS)


def attach_jj_fingers(islands: dict, dxf_path: Path | None = None) -> dict:
    """Glue each L2D2400 finger onto the nearest island. Keep the 0.2 um gaps.

    Do not morphological-close here: AL_JOIN_UM = 1.2 um would fill those
    gaps and DC-short the junctions. Do not union L3.
    """
    out = {name: g for name, g in islands.items()}
    for finger in load_jj_fingers(dxf_path):
        hits = [n for n in out if finger.distance(out[n]) < 1e-9]
        if len(hits) > 1:
            raise RuntimeError(
                f"JJ finger bbox {tuple(round(x, 3) for x in finger.bounds)} "
                f"touches {hits}; would fuse islands."
            )
        name = min(out, key=lambda n: finger.distance(out[n]))
        out[name] = _drop_holes(unary_union([out[name], finger]))
    names = ("P1", "P2", "P3")
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if out[a].intersects(out[b]):
                raise RuntimeError(f"JJ fingers fused {a} to {b}")
    d12 = out["P1"].distance(out["P2"])
    d32 = out["P3"].distance(out["P2"])
    if not (JJ_GAP_MIN_UM <= d12 <= JJ_GAP_MAX_UM):
        raise RuntimeError(f"P1-P2 JJ gap is {d12:.4f} um, expected ~0.2")
    if not (JJ_GAP_MIN_UM <= d32 <= JJ_GAP_MAX_UM):
        raise RuntimeError(f"P3-P2 JJ gap is {d32:.4f} um, expected ~0.2")
    return out


def load_pad_islands(
    dxf_path: Path | None = None,
    units: str = "um",
    include_al_leads: bool = True,
    include_jj_fingers: bool = True,
):
    """Union L6+L7, L2D2100 Al, and L2D2400 JJ fingers. Return P1/P2/P3.

    ``units`` is ``'um'`` (DXF native) or ``'mm'`` (Qiskit Metal).
    """
    geoms = load_dxf_polygons(dxf_path, layers=PAD_LAYERS)
    islands = label_pad_islands(_as_parts(unary_union(geoms)))
    if include_al_leads:
        islands = attach_al_wiring(islands, dxf_path)
        if include_jj_fingers:
            islands = attach_jj_fingers(islands, dxf_path)
    if units == "mm":
        return {name: _scale(g, UM_TO_MM) for name, g in islands.items()}
    if units == "um":
        return islands
    raise ValueError(f"units must be 'um' or 'mm', got {units!r}")


def _scale(geom, factor: float):
    from shapely.affinity import scale

    return scale(geom, xfact=factor, yfact=factor, origin=(0.0, 0.0))


def island_table(islands) -> str:
    lines = [
        f"{'name':<4} {'area_um2':>12} {'cx_um':>10} {'cy_um':>10} "
        f"{'xmin':>10} {'ymin':>10} {'xmax':>10} {'ymax':>10} {'holes':>6}"
    ]
    for name in ("P1", "P2", "P3"):
        g = islands[name]
        x0, y0, x1, y1 = g.bounds
        c = g.centroid
        n_holes = len(g.interiors) if g.geom_type == "Polygon" else 0
        lines.append(
            f"{name:<4} {g.area:12.2f} {c.x:10.2f} {c.y:10.2f} "
            f"{x0:10.2f} {y0:10.2f} {x1:10.2f} {y1:10.2f} {n_holes:6d}"
        )
    return "\n".join(lines) + "\n"


def plot_islands(islands, out_png: Path, dxf_path: Path | None = None):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes

    colors = {"P1": "#d62728", "P2": "#2ca02c", "P3": "#1f77b4"}
    fig, ax = plt.subplots(figsize=(7.5, 9.0))

    if dxf_path is not None:
        for g in load_dxf_polygons(dxf_path, layers=PAD_LAYERS):
            if g.geom_type == "Polygon":
                xs, ys = g.exterior.xy
                ax.plot(xs, ys, color="#bbbbbb", lw=0.4, zorder=0)

    def _draw_islands(target, lw=0.4, alpha=0.55):
        for name in ("P1", "P2", "P3"):
            g = islands[name]
            geoms = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
            for poly in geoms:
                patch = MplPoly(
                    list(poly.exterior.coords),
                    closed=True,
                    facecolor=colors[name],
                    edgecolor="black",
                    linewidth=lw,
                    alpha=alpha,
                    zorder=1,
                )
                target.add_patch(patch)

    _draw_islands(ax)
    for name in ("P1", "P2", "P3"):
        c = islands[name].centroid
        ax.text(
            c.x,
            c.y,
            name,
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color="black",
            zorder=2,
        )

    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("P1 / P2 / P3: Ta pads+IDC, L2D2100 Al, L2D2400 JJ fingers")
    ax.grid(True, alpha=0.25)

    axins = inset_axes(ax, width="42%", height="32%", loc="lower right", borderpad=1.2)
    _draw_islands(axins, lw=0.25, alpha=0.75)
    axins.set_xlim(-80, 40)
    axins.set_ylim(-80, 80)
    axins.set_aspect("equal")
    axins.set_title("Al meander zoom", fontsize=8)
    axins.tick_params(labelsize=7)
    axins.set_facecolor("#f7f7f7")

    fig.subplots_adjust(left=0.12, right=0.98, top=0.95, bottom=0.08)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    plt.close(fig)
    return out_png


def plot_al_zoom(islands, out_png: Path):
    """Close-up of the Al meander and JJ-approach lines (microns)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly

    colors = {"P1": "#d62728", "P2": "#2ca02c", "P3": "#1f77b4"}
    fig, ax = plt.subplots(figsize=(7.0, 7.5))
    for name in ("P1", "P2", "P3"):
        g = islands[name]
        geoms = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
        for poly in geoms:
            ax.add_patch(
                MplPoly(
                    list(poly.exterior.coords),
                    closed=True,
                    facecolor=colors[name],
                    edgecolor="black",
                    linewidth=0.3,
                    alpha=0.8,
                    zorder=1,
                )
            )
        extra = g.difference(
            label_pad_islands(
                _as_parts(unary_union(load_dxf_polygons(layers=PAD_LAYERS)))
            )[name].buffer(0.2)
        )
        if not extra.is_empty:
            c = extra.centroid
            ax.text(c.x, c.y, name + " Al", fontsize=8, color=colors[name], zorder=2)
    ax.set_xlim(-80, 40)
    ax.set_ylim(-80, 80)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("L2D2100 Al + L2D2400 JJ fingers (0.2 um gaps, L3 omitted)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)
    return out_png


def plot_jj_zoom(islands, out_png: Path):
    """Close-up of the 0.2 um P1-P2 and P3-P2 JJ gaps (microns)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly

    colors = {"P1": "#d62728", "P2": "#2ca02c", "P3": "#1f77b4"}
    fig, ax = plt.subplots(figsize=(4.5, 8.0))
    for name in ("P1", "P2", "P3"):
        g = islands[name]
        geoms = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
        for poly in geoms:
            ax.add_patch(
                MplPoly(
                    list(poly.exterior.coords),
                    closed=True,
                    facecolor=colors[name],
                    edgecolor="black",
                    linewidth=0.4,
                    alpha=0.85,
                    zorder=1,
                )
            )
    d12 = islands["P1"].distance(islands["P2"])
    d32 = islands["P3"].distance(islands["P2"])
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-7.0, 7.0)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(f"JJ fingers: P1-P2 {d12:.2f} um, P3-P2 {d32:.2f} um")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=220)
    plt.close(fig)
    return out_png


def main(dxf_path: Path | None = None, out: Path | str | None = None):
    dxf = Path(dxf_path) if dxf_path is not None else DEFAULT_DXF
    dest = outdir(out)

    islands = load_pad_islands(dxf, units="um")
    table = island_table(islands)
    table_path = dest / "phase1_islands.txt"
    png_path = dest / "phase1_islands.png"
    zoom_path = dest / "phase1_al_zoom.png"
    table_path.write_text(table)
    plot_islands(islands, png_path, dxf_path=dxf)
    plot_al_zoom(islands, zoom_path)
    jj_path = dest / "phase1_jj_zoom.png"
    plot_jj_zoom(islands, jj_path)

    print(f"dxf     : {dxf}")
    print(f"islands : {len(islands)}")
    print(table, end="")
    print("P1-P2 gap um", round(islands["P1"].distance(islands["P2"]), 4))
    print("P3-P2 gap um", round(islands["P3"].distance(islands["P2"]), 4))
    print("P1-P3 gap um", round(islands["P1"].distance(islands["P3"]), 4))
    print(f"wrote   : {table_path}")
    print(f"wrote   : {png_path}")
    print(f"wrote   : {zoom_path}")
    print(f"wrote   : {jj_path}")
    return islands


if __name__ == "__main__":
    main()
