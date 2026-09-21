# QuantroTa_01 layout notes

Working notes for rebuilding the fabricated quantromon cell in Qiskit Metal and extracting a lumped capacitance matrix.

Source CAD:

- Original fab file: `quantromon/QuantroTa_01_726_22_finger_130nm_SJ_01_04_25.dwg`
- Converted file (readable): packaged DXF `src/quantromon/data/model_/QuantroTa_01_726_22_finger_130nm_SJ_01_04_25.dxf`
- Conversion: ODA File Converter, ASCII DXF 2013 (`AC1027`)
- Units: microns (`$INSUNITS = 13`)
- Extent of this cell: about 0.90 mm x 2.04 mm

This DXF is one device cell, not the full diced chip. The thesis quotes a typical diced chip of 8 mm x 2 mm holding several devices.

Related references:

- Kishor V. Salunkhe, *The Quantromon*, TIFR PhD thesis, 17 Oct 2025 (`/home/hm/IITB/Unacad/The_Quantromon__Thesis_signed.pdf`)
- Salunkhe et al., APL Quantum / Appl. Phys. Lett. 126, 254001 (2025)
- Existing SEM-based Metal reconstruction (paper Fig. 1, not this mask): `src/quantromon/paper/metal.py`
- Capacitance-extraction workflow to follow: `QDW2025/notebooks/beginner-track/Workshops/Murat/transmon_resonator.ipynb` (Palace via SQDMetal)

The paper/SEM reconstruction is a cousin of this chip, not a copy. This DXF is ground truth for *this* mask.

## Filename

`QuantroTa_01_726_22_finger_130nm_SJ_01_04_25`

| Piece | Meaning |
|---|---|
| QuantroTa_01 | Quantromon, tantalum pads, sample/design 01 |
| 726 | Matches the 0.726 um low-dose Dolan bridge on `L3D700` |
| 22_finger | 22-finger interdigitated capacitor (IDC), not 22 traces of 130 nm |
| 130nm | Shadow-junction finger width |
| SJ | Shadow / Dolan junction |
| 01_04_25 | Date stamp (1 Apr 2025) |

## What this file is

It is an e-beam write CAD layout, not a Qiskit Metal design and not a circuit netlist.

- 142 closed `LWPOLYLINE`s
- 9 CAD layers
- Layer names encode lithography pass and dose, not circuit inductors \(L_1\) / \(L_2\)

Pattern:

```text
L  2  D  2100
|  |  |    |
|  |  |    +-- dose (exposure)
|  |  +------- "dose"
|  +---------- write layer / pass
+------------- "layer"
```

So `L2D2100` means layer 2, dose 2100. `L2D2100` and `L2D2400` are the same write layer at two doses. Small 130 nm features get extra dose so they clear.

The labmate said the CAD `L0` / `L1` / `L2` names are not different physical metals. They were split for colour / dose in AutoCAD. Finished metals are Ta pads+IDC, Al meander+junctions.

## CAD layers in this cell

| Layer | Polys | What it is | Use in sim |
|---|---|---|---|
| `L2D2100` | 76 | Main 500 nm Al wiring / meander. Many 0.50 um traces, plus filleted 4 x 2.5 um pads | Yes: thin wiring |
| `L2D2400` | 4 | Extra dose on SJ fingers: two 0.13 x 2.10 um, two 0.43 x 2.10 um | Yes: same Al wiring, junction electrodes |
| `L3D700` | 6 | Low-dose Dolan / undercut. 0.40 um squares and 0.726 x 0.20 um bridges | No: process layer, not a conductor |
| `L6D1800` | 26 | IDC: **22 fingers, 5.00 um x 295.5 um**, plus 35 um squares and two 237 x 15 um bars | Yes: CR |
| `L7D1800` | 3 | Three large antenna pads (top, bottom, left), hundreds of microns | Yes: P1 / P2 / P3 |
| `L4D1800` | 11 | Alignment marks (~10 x 12.5 um and larger crosses) | Ignore |
| `L0D1800` | 9 | 20 x 20 um chip-corner marks near +/-320 um | Ignore |
| `L1D1000` | 3 | 2 x 2 um marks | Ignore |
| `L63D1000` | 4 | 10 x 10 um corner marks near +/-305 um | Ignore |

Dose in this file: 700 is gentle (junction undercut), 1800 medium (pads/marks), 2100 main wiring, 2400 extra on 130 nm fingers.

## Electrical islands from the polygons

Boolean union of overlapping polys (micron units):

**`L2` only (2100 + 2400), two islands**

1. 44.00 x 129.00 um, area 372 um^2, centroid near (2.8, 0). Main device body.
2. 67.50 x 6.50 um, area 70 um^2, centroid near (-32, 0). Horizontal bar toward the left pad.

If `L3` is unioned with `L2`, those two islands short into **one** piece with a hole. That is the Dolan *mask*, not finished metal. For electrostatics, **keep the `L2` gap and drop `L3`**. The two islands are the Al electrodes coupled by the AlOx junctions.

**`L7`: three large pads**

- Top: 250 x 957.5 um
- Bottom: 250 x 957.5 um
- Left: 486.5 x 250 um

This matches the three-antenna quantromon (P1, P2, P3). Geometry suggests the left `L7` pad is the P2 stem side; top/bottom are P1/P3 antennas. Confirm if a figure is ever labeled.

**`L6` IDC** sits on the large-pad side, not on the 500 nm meander. `L6` touches `L7`. `L6` does **not** touch `L2` (gap ~110 um).

**`L2` to `L7` nearest gap is 0.55 um.** Treat as a designed join/gap at the Ta/Al overlap (thesis: notch + ion mill for galvanic Ta/Al contact). For a first C-matrix, treat pads as galvanically attached to their Al leads unless a sim of the overlap is needed.

## Mapping onto the thesis circuit

The chip is a hybrid 2D-3D cQED sample: planar circuit on sapphire, measured in a 3D rectangular waveguide. There is **no on-chip ground plane**.

Thesis Fig. 5.1 / 5.2:

- Three superconducting islands P1, P2, P3
- Qubit (transmon-like) mode: dipole between P2 and (P1 + P3)
- P1 and P3 also act as antennas for the linear / readout mode, setting coupling to the waveguide
- \(C_J\): capacitance between pads (P1, P2) and (P3, P2)
- \(C_R\): capacitance of the IDC
- Meander: 500 nm line split into L1, L2. Central L2 closes the quantromon loop with the two junctions / SQUIDs
- IDC fingers: 5 um wide, 5 um gap (matches `L6`)

Sample types in the thesis: non-tunable, tunable (each JJ replaced by a SQUID), asymmetry-tunable. This filename (`SJ`, 130 nm fingers) is a shadow-junction variant of that family.

## Stack (labmate + thesis)

Labmate (17 Sep 2026):

- Pads and IDC: tantalum, about **160 nm**
- Junctions: aluminium
- Meander thickness: she guessed about 0.7 um
- Substrate: sapphire, **0.43 mm**
- CAD layer names: not a metal stack, split for colour

Thesis Sec. 4.4 (Ta process, more reliable for thicknesses):

- Commercial Ta-sputtered sapphire
- Large features P1, P2, P3 patterned in Ta (negative resist ARN7520, SF6 etch)
- Small features (JJs and IDC in the Al process description; on the Ta device the IDC is Ta with the pads) written in a second e-beam step
- Alignment marks in Ta
- Ta film **200 nm**
- Al **70 nm** combined (first evaporation 20 nm at \(+\theta_1\), second 50 nm at \(-\theta_2\))
- Dolan bilayer: AR6200 / EL-9, in-situ oxidation 6 mbar / 10 min, capping oxidation 18 mbar / 30 min
- Ta/Al step is 200 nm vs 70 nm: notch + in-situ ion mill so the contact is galvanic
- Small Al probing patches on Ta pads for room-temperature resistance

Use thesis Al thickness (70 nm), not the 0.7 um guess. Ta 160 nm vs 200 nm is a small difference for C; pick one and record it.

Junction overlap (Dolan):

\[
\mathrm{Overlap} = h(\tan\theta_1 + \tan\theta_2) - B
\]

where \(h\) is the bottom-layer thickness, \(\theta_{1,2}\) the evaporation angles, and \(B\) the bridge width. Linewidth \(W\) is varied to set area / \(I_c\).

## 3D waveguide (not part of the mask)

Thesis Sec. 5.3:

- Rectangular waveguide **1.75 cm x 3.5 cm x 8.2 cm**
- Cutoff \(f_C \sim 4.3\) GHz, useful band roughly 4.3 to 9.5 GHz
- Two sections: Al 6061 (low loss) and OFHC copper (thermalization + flux coil)
- Chip **12 mm from the copper end** for max coupling near 7.0 to 7.5 GHz
- E field in the waveguide is parallel to the readout mode and orthogonal to the qubit mode
- Several devices can sit on a sapphire platform; they need different resonator frequencies
- Devices should be at least about 2.5 to 3.0 mm apart to avoid qubit-qubit coupling

This sets boundary conditions. It is **not** extra 2D geometry.

## What \(C_J \approx 56\) fF actually is

Kishor / paper Table I: \(C_J\) fit 56.88 fF, HFSS 50.23 fF. That number is **not** the big Ta pad-to-pad capacitor.

In this mask, each \(C_J\) is the capacitance across one shadow junction: two Al fingers on `L2D2400` that face each other across a **0.20 um** opening (Al / AlOx / Al). Close metal, tiny gap, large C. There is one such gap P1-P2 and one P3-P2.

`L2D2100` only gets you to a ~4 um Al gap (the meander / P2 bar). Palace then reports \(C_J \approx 33\) fF (pads + wiring). The remaining ~20 fF is those 0.20 um fingers.

`L3` is the Dolan process mask, not finished metal. Unioning `L3` shorts the fingers. Leave `L3` out.

**Why the fingers were omitted at first**

1. The request was to add the visible Al lines (meander and JJ-approach traces) **without** inductor shorts or JJ devices.
2. A 0.2 um feature is easy to turn into an OOM if you put a fine size field on a large box (2 um on the whole meander wrote a 3 GB mesh here).
3. Morphological join used to glue Ta/Al (`buffer(1.2).buffer(-1.2)`) would fill a 0.2 um gap. Fingers must be unioned **after** that join, with no close.

They are now on the islands (`include_jj_fingers=True`). Mesh only a ~6 x 16 um box at the origin, not the whole meander.

## Capacitance extraction: what we can and cannot get

**Can get (lumped Maxwell C of the planar circuit)**

Named conductors: P1, P2, P3 (Ta pads + IDC fingers assigned to the pad they touch). Palace electrostatics on sapphire, no on-chip ground, box walls standing in for the waveguide. That yields \(C_J\) (pad-pad) and \(C_R\) (IDC).

This is the same loop as Murat's Qiskit Metal + SQDMetal + Palace notebook, different device.

**Cannot get from that C-matrix**

Waveguide coupling \(\kappa\), radiation, and the antenna-to-mode overlap. That needs an eigenmode or driven sim of the 1.75 x 3.5 x 8.2 cm box.

## Assumptions for the first Metal / Palace run

Unless changed later:

1. Rebuild from the DXF polygons, not from `quantromon.paper.metal` SEM numbers.
2. Keep `L2D2100` as Al wiring (cut the meander at y = 0). Keep `L2D2400` as JJ fingers with the 0.2 um gaps. Drop `L3` as a conductor.
3. Keep `L6` + `L7` as Ta pads and IDC. Ignore `L0`, `L1`, `L4`, `L63`.
4. Three conductors: P1, P2, P3. No on-chip ground. Sim box approximates waveguide walls.
5. Sapphire 0.43 mm, \(\varepsilon_r \approx 10\) (or anisotropic 9.3 / 11.5 if we refine).
6. Ta pads + IDC: 160 nm (labmate) or 200 nm (thesis). Record which.
7. Al meander + JJ electrodes: 70 nm.
8. Treat the 0.55 um `L2`--`L7` approach as galvanic Ta/Al contact (thesis notch), not a capacitor, unless we specifically study that overlap.
9. Palace/Q3D \(C_J\) is pad+wiring coplanar C. AlOx overlap \(C_J\) is a lumped element later, not a 0.2 um mesh.

## Practical CAD notes

- FreeCAD Snap cannot run host `/usr/bin/ODAFileConverter`. Convert DWG to DXF with the ODA GUI, then parse DXF.
- Preferred import for us: ASCII DXF 2013 (the "ASCII 2013 DXF" entry in ODA). Binary DXF is worse.
- Qiskit Metal does not ingest DWG. Path is: parse DXF -> named Metal components -> Palace C-matrix.

## Status

- DXF is parsed. Pads, IDC, split meander, and L2D2400 JJ fingers are on P1/P2/P3.
- `L3` is still not a conductor.
- Palace C without JJ fingers: \(C_J \approx 33\) fF, \(C_R \approx 600\) fF (`out/phase2_C_fF_al_meander.csv`).
- Next: `devnotes/status_and_next.md` (Q3D on the Windows box, then lumped AlOx \(C_J\)). Do not remesh the 0.2 um gap on this box.
