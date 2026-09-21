"""Phase 1 Qiskit Metal design: three Ta pad+IDC islands plus Al and JJ fingers.

Al meander is cut at y = 0 so P1 and P3 stay open. L2D2400 fingers keep
the 0.2 um JJ gaps. No L3 Dolan mask, no alignment marks, no ground.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from qiskit_metal import Dict, designs
from qiskit_metal.qlibrary.core import QComponent
from qiskit_metal.toolbox_metal.parsing import is_true

from quantromon.geometry.dxf import DEFAULT_DXF, island_table, load_pad_islands
from quantromon.paths import outdir

__all__ = ["QuantroTaPad", "make_design", "export_gds"]


class QuantroTaPad(QComponent):
    """One named island (P1, P2, or P3): Ta pad+IDC, split Al, JJ fingers."""

    default_options = Dict(
        island="P1",
        dxf_path=str(DEFAULT_DXF),
        layer="1",
        chip="main",
        include_al_leads=True,
        include_jj_fingers=True,
    )
    component_metadata = Dict(
        short_name="pad",
        _qgeometry_table_poly="True",
    )
    TOOLTIP = "QuantroTa pad+IDC island imported from the fab DXF."

    def make(self):
        p = self.p
        name = str(p.island)
        islands = load_pad_islands(
            Path(p.dxf_path),
            units="mm",
            include_al_leads=is_true(p.include_al_leads),
            include_jj_fingers=is_true(p.include_jj_fingers),
        )
        if name not in islands:
            raise KeyError(f"island {name!r} not in {sorted(islands)}")
        self.add_qgeometry(
            "poly",
            {name: islands[name]},
            layer=p.layer,
            chip=p.chip,
            subtract=False,
        )


def make_design(
    dxf_path: Path | None = None,
    margin_um: float = 200.0,
    size_z: str = "430um",
    include_al_leads: bool = True,
    include_jj_fingers: bool = True,
    material: str = "sapphire",
):
    """Build a DesignPlanar with components P1, P2, P3. Coordinates in mm.

    ``size_z`` is the sapphire thickness (labmate: 0.43 mm).
    """
    dxf = Path(dxf_path) if dxf_path is not None else DEFAULT_DXF
    design = designs.DesignPlanar({}, overwrite_enabled=True)
    for name in ("P1", "P2", "P3"):
        QuantroTaPad(
            design,
            name,
            options=dict(
                island=name,
                dxf_path=str(dxf),
                layer="1",
                include_al_leads=include_al_leads,
                include_jj_fingers=include_jj_fingers,
            ),
        )

    bounds = np.array(
        [c.qgeometry_bounds() for c in design.components.values()]
    )
    x0, y0 = bounds[:, 0].min(), bounds[:, 1].min()
    x1, y1 = bounds[:, 2].max(), bounds[:, 3].max()
    design.chips.main.size.update(
        size_x=f"{(x1 - x0) * 1e3 + 2 * margin_um}um",
        size_y=f"{(y1 - y0) * 1e3 + 2 * margin_um}um",
        size_z=size_z,
        center_x=f"{(x0 + x1) * 0.5e3}um",
        center_y=f"{(y0 + y1) * 0.5e3}um",
        center_z="0um",
    )
    design.chips.main.material = material
    design.rebuild()
    return design


def export_gds(design, path: str):
    gds = design.renderers.gds
    gds.options["fabricate"] = "False"
    gds.options["max_points"] = "8191"
    for key in ("cheese", "no_cheese"):
        gds.options[key]["view_in_file"]["main"] = {1: False}
    gds.export_to_gds(path)
    return path


def plot_metal(design, out_png: Path, show: bool = False):
    """Draw the Metal qgeometry with matplotlib (no MetalGUI).

    ``show=True`` leaves the figure open so a notebook can display it.
    Scripts keep ``show=False`` (headless save and close).
    """
    import matplotlib.pyplot as plt
    import qiskit_metal as qm

    fig = qm.view(
        design,
        figsize=(7.5, 9.0),
        title="Phase 1: P1 P2 P3 + L2D2100 Al (cut at y=0)",
    )
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    if not show:
        plt.close(fig)
        return out_png
    return fig


def main(out: Path | str | None = None):
    dest = outdir(out)
    islands_um = load_pad_islands(units="um")
    print("DXF islands (um)")
    print(island_table(islands_um), end="")

    design = make_design()
    print(f"components : {list(design.components)}")
    for name, comp in design.components.items():
        b = comp.qgeometry_bounds()
        print(
            f"  {name}: bounds mm "
            f"({b[0]:.4f},{b[1]:.4f})-({b[2]:.4f},{b[3]:.4f})"
        )

    png = plot_metal(design, dest / "phase1_metal.png")
    gds_path = export_gds(design, str(dest / "phase1_pads.gds"))
    print(f"wrote {png}")
    print(f"wrote {gds_path}")
    return design


if __name__ == "__main__":
    main()
