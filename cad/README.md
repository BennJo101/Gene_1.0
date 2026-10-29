# CAD sources and build scripts

All STLs here are in their design frame. `cad/tools/parts.py` places each one in the **head frame**: the X axis is the jaw pivot, the origin is on that axis, -Y is the face (front), and +Z is up. The robot faces -Y, so Gene's own left is +X.

The print-ready copies in `../print/` are the same parts, reoriented flat side down.

## Files

| Kind | Files |
|---|---|
| Skull | `skull.stl` (v7). Its build scripts start from the v6 skull, `GeneTop_v6_neck.stl`, which is no longer in the folder (see below) |
| Jaw | `jaw.stl`, `jaw_pin.stl` (the two screw-in pivot pins; the right one is the same part turned 180° about Z) |
| Jaw drive | `servo_bracket_L.stl`, `servo_bracket_R.stl`, `jaw_drive_hub.stl` |
| Eyes | `eye_display_carrier.stl`, `eye_display_retainer.stl`, `camera_bezel.stl`, `pupil_ring.stl`; optional `eye_x_insert.stl` (`tools/eye_x_insert.py`) |
| Interior | `pi_shelf.stl`, `battery_tray.stl`, `battery_deck.stl` |
| Crown | `crown_insert.stl`, `bridge_handle.stl`, `gpio_flashlight.stl`, `gpio_cover.stl` |
| Neck | `neck.stl`, `neck_base.stl`, `neck_collar.stl` |
| Fit-check only | `mocks/`: stand-ins for the bought parts (Pi 5, displays, cameras, battery, boards, servos, speakers, slip ring and so on), used by the sim and the clearance checks. **Do not print these** |

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
| `export.py` → `build_local_sim.py` | Exports meshes and the jaw sweep to `web/`, then inlines `web/` into one self-contained `head_sim.html` |

The skull is built in eight steps. Run them in this order:

1. `skull_v7.py`: v6 plus the camera ribbon slots, the top display windows and the plug pockets
2. `skull_v7_mirror_eye.py`: makes the right eye's plug pocket an exact mirror of the left one
3. `skull_v7_seal_corners.py`: seals the small holes at the outboard bottom corners of the eye barrels
4. `skull_v7_barrel_taper.py`: blends the back end of each eye barrel into the skull
5. `skull_v7_open_inboard.py`: opens the inboard wall of each eye barrel above the camera slot, so the display ribbon can swing past when the screen is turned 180°
6. `skull_v7_usbc_port.py`: cuts the USB-C charge port (flange seat, opening and 2 x M3 holes) in the lower back wall (flange horizontal), and writes `mocks/usbc_panel.stl`
7. `motor_mount_m2.py`: M2 through-bolt holes (counterbore outside, clearance, hex nut pocket) through the skull wall into both servo bracket feet, and the dia 2.5 pilots for the bracket M3 self-tappers. It changes the two bracket files too

8. `skull_v7_shelf_divots.py`: 4 divots (grooves open at the bottom rim) in the inner wall, and 4 cubes on the Pi shelf wings that slide up into them; M2 x 12 in from outside the skull into a nut dropped into each cube. It changes `pi_shelf.stl` too

Steps 2–8 save a copy of their input in `tools/retired/` the first time they run, and read from it on later runs.

`skull.stl` is the only skull kept in the repo. Step 1 and `check_v7.py` read the v6 skull, which has been removed; to rebuild from step 1, restore it with `git checkout 8078433 -- cad/GeneTop_v6_neck.stl`. All old part versions in `tools/retired/` were deleted too (the skull, jaw and bracket copies), so rerunning a single step now starts from the finished part rather than its original input.

Part generators: `jaw_fill_pivot_holes.py` (filled the old pivot-screw holes in the jaw; already applied), `jaw_screw_pins.py` (jaw v5: cuts the pivot pins off the jaw into `jaw_pin.stl` and puts a hex pocket, bore and grub hole in each arm; reads `tools/retired/jaw_v4_before_screw_pins.stl`), `cam3_arducam.py` (camera bezel v3), `carrier_topslot.py` (display carrier v3; its input `retired/carrier_v1_before_topslot.stl` was removed, so restore it with `git checkout 8078433 -- cad/tools/retired/carrier_v1_before_topslot.stl` before rerunning), `pupil.py`, `gpio_flashlight.py`, `gpio_mocks.py`, `dboard_mock.py`.

`battery.py`, `crown.py`, `neck.py` and `shelf6.py` generated their parts at earlier stages of the skull (v4/v5). They are kept as the record of how those parts were made, but they need skull files that are not in this repo. Their output STLs are included and current.

`printprep.py` and `plates.py` write to `cad/print/`, which is ignored by git. Copy the results into `../print/parts` and `../print/plates` (the files there use numbered names) when you update the print files.
