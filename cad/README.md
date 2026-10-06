# CAD sources and build scripts

All STLs here are in their design frame. `cad/tools/parts.py` places each one in the **head frame**: the X axis is the jaw pivot, the origin is on that axis, -Y is the face (front), and +Z is up. The robot faces -Y, so Gene's own left is +X.

The print-ready copies in `../print/` are the same parts, reoriented flat side down.

## Files

| Kind | Files |
|---|---|
| Skull | `GeneTop_v7_skull.stl` (current). `GeneTop_v6_neck.stl` is the base that `skull_v7.py` builds v7 from, and the reference for `check_v7.py` |
| Jaw | `GeneBottom_v4_twindrive.stl` |
| Jaw drive | `GeneHead_xl330_bracket_v2.stl`, `GeneHead_xl330_bracket_R_v2.stl`, `GeneHead_jaw_drive_hub.stl` |
| Eyes | `GeneHead_eye_display_carrier.stl`, `GeneHead_eye_display_retainer.stl`, `GeneHead_eye_camera_bezel.stl`, `GeneHead_pupil_ring.stl` |
| Interior | `GeneHead_pi_shelf_v6.stl`, `GeneHead_battery_tray.stl`, `GeneHead_battery_deck.stl` |
| Crown | `GeneHead_crown_insert.stl`, `GeneHead_bridge_handle.stl`, `GeneHead_gpio_flashlight.stl`, `GeneHead_gpio_cover.stl` |
| Neck | `GeneHead_neck.stl`, `GeneHead_neck_base.stl`, `GeneHead_neck_collar.stl` |
| Fit-check only | `*_MOCK.stl`: stand-ins for the bought parts (Pi 5, displays, cameras, battery, boards, servos, slip ring and so on). **Do not print these** |
| Sim only | `XL330_M288_from_STEP.stl`: the servo model used for display |

## Setup

```
pip install -r tools/requirements.txt
```

Run every script from inside `cad/tools/`, because several open their data files by relative path:

```
cd cad/tools
python check.py
```

## Scripts

| Script | What it does |
|---|---|
| `parts.py` | Loads every current part and places it in the head frame (imported by the others) |
| `check.py`, `sweep.py` | Pairwise interference check of the assembly; jaw sweep against every part |
| `check_v7.py` | Skin left over the v7 eye pockets, ribbon-slot opening, and free height above the display boards |
| `mass.py` | Mass, centre of mass and jaw-servo torque estimate |
| `occ_all.py`, `route.py` | Occupancy grid of the assembly, then a cable routing check for every run in `cables.json` |
| `printprep.py` → `plates.py` | Orients every part for printing (writes `printparts.pkl` and `cad/print/`), then lays out the `.3mf` plates |
| `export.py` → `build_local_sim.py` | Exports meshes and the jaw sweep to `web/`, then inlines `web/` into one self-contained `GeneHead_sim.html` |

The skull is built in five steps. Run them in this order:

1. `skull_v7.py`: v6 plus the camera ribbon slots, the top display windows and the plug pockets
2. `skull_v7_mirror_eye.py`: makes the right eye's plug pocket an exact mirror of the left one
3. `skull_v7_seal_corners.py`: seals the small holes at the outboard bottom corners of the eye barrels
4. `skull_v7_barrel_taper.py`: blends the back end of each eye barrel into the skull
5. `skull_v7_open_inboard.py`: opens the inboard wall of each eye barrel above the camera slot, so the display ribbon can swing past when the screen is turned 180°

Steps 2–5 keep a copy of their input in `tools/retired/` the first time they run. If you rebuild from step 1, delete those `GeneTop_v7_before_*.stl` copies first, so each step starts from the new file.

Part generators: `cam3_arducam.py` (camera bezel v3), `carrier_topslot.py` (display carrier v3, built from `retired/carrier_v1_before_topslot.stl`), `pupil.py`, `gpio_flashlight.py`, `gpio_mocks.py`, `dboard_mock.py`.

`battery.py`, `crown.py`, `neck.py` and `shelf6.py` generated their parts at earlier stages of the skull (v4/v5). They are kept as the record of how those parts were made, but they need skull files that are not in this repo. Their output STLs are included and current.

`printprep.py` and `plates.py` write to `cad/print/`, which is ignored by git. Copy the results into `../print/parts` and `../print/plates` (the files there use numbered names) when you update the print files.
