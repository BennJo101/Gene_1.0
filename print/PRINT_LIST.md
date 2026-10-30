# Gene head - print list

27 pieces in total (23 without the optional parts: fit the bridge handle **or** the GPIO flashlight, the GPIO cover is for when neither is plugged in, and the eye X insert is a Halloween cap for one eye). Tick them off as they come off the bed.

| # | Part | Qty | File (in `parts/`) | Plate | Notes |
|---|---|---|---|---|---|
| 1 | skull | **1** | `01_skull_x1.stl` | 1 | tree supports. **Updated 2026-10-04 (v7):** camera ribbon slots 26.5 x 7.5 (were 14 x 4) for the Arducam's rigid 16 mm cable end and 6 mm flex; top window in each eye barrel plus a pocket in the skull above it for the display board's HDMI and USB plugs. **Updated 2026-10-06:** the plug pocket above the right eye is now a mirror of the left one (it had a ragged edge). The small triangular holes at the outboard bottom corner of each eye barrel are sealed. The back end of each eye barrel now tapers smoothly into the skull side (closes a thin crack there). The inboard wall of each eye barrel is open from the camera slot up to the top window, so the display ribbon can swing past when the screen is turned. **Updated 2026-10-30:** the flat plate between the eye barrels is cut to a U (6 mm strips along both barrels and the face, open at the back), so there are far fewer supports under it. The inboard tabs of the eye barrels behind the camera slots are half as long (they end 13 mm behind the slot). The inside of each barrel's top is relieved for the LCD's flex ledge (1.1 mm of wall left under the skin), so the screens aren't pushed on. Plate 1 was printed as v6 - reprint Plate 1 |
| 2 | jaw | **1** | `02_jaw_x1.stl` | 2 | tree supports; 4 walls, 20-25% infill. **Updated 2026-10-29 (v5):** the pivot pins are no longer part of the jaw (they snapped when the arms were sprung over the skull). Each arm now has a hex pocket in its outer face and a bore through it for the screw-in pin (23) - reprint the jaw |
| 3 | pi shelf | **1** | `03_pi_shelf_x1.stl` | 3 | tree supports. **Updated 2026-10-16:** 4 cubes on the wings that slide into divots in the skull (replaces the skull's nut posts); the shelf now sits 13.35 mm lower, flush with the skull's bottom rim - reprint Plate 3 (or Plate 8, which has the skull, shelf and eye X insert together for a 350 mm bed) |
| 4 | battery tray | **1** | `04_battery_tray_x1.stl` | 3 | PETG; tree supports |
| 5 | battery deck | **1** | `05_battery_deck_x1.stl` | 3 | PETG; tree supports |
| 6 | servo bracket L | **1** | `06_servo_bracket_L_x1.stl` | 4 | PETG; 4 walls, 20-25% infill |
| 7 | servo bracket R | **1** | `07_servo_bracket_R_x1.stl` | 4 | PETG; 4 walls, 20-25% infill |
| 8 | jaw drive hub | **2** | `08_jaw_drive_hub_x2.stl` | 4 | 4 walls, 20-25% infill |
| 9 | eye display carrier | **2** | `09_eye_display_carrier_x2.stl` | 4 | **Updated 2026-10-06 (v3):** top and bottom slots widened to +/-74.25 deg, so behind the front lip only a 31.5 deg wall is left on each side. **Updated 2026-10-30:** display seat 56.60 (was 56.00), and the top/bottom slots run up to the lip so the glass's flex ledge isn't pushed on: the screen isn't squeezed. Plate 4 was printed before this - reprint the two carriers from `09_eye_display_carrier_x2.stl`, or Plate 10 (just the two carriers, lip down, no supports) |
| 10 | eye display retainer | **2** | `10_eye_display_retainer_x2.stl` | 4 |  |
| 11 | camera bezel | **2** | `11_camera_bezel_x2.stl` | 4 | BLACK. **Updated 2026-10-04 (v3):** sized for the Arducam mini camera: pocket 12.4 mm long (was 8.6) for the crystal behind the lens, 6.8 mm cable lane level with the camera board (was a 3.6 mm tunnel), spoke 11.5 wide. Plate 4 was printed before this - reprint the two bezels from `11_camera_bezel_x2.stl` |
| 12 | pupil ring | **2** | `12_pupil_ring_x2.stl` | 4 | BLACK |
| 13 | crown insert | **1** | `13_crown_insert_x1.stl` | 5 | support the lower step |
| 14 | neck | **1** | `14_neck_x1.stl` | 6 | yoke down, no supports |
| 15 | neck base | **1** | `15_neck_base_x1.stl` | 6 | no supports |
| 16 | neck collar | **1** | `16_neck_collar_x1.stl` | 6 | no supports |
| 17 | bridge handle OPTIONAL | **1** | `17_bridge_handle_OPTIONAL_x1.stl` | 5 | optional; support the grip span; 4 walls |
| 18 | GPIO flashlight OPTIONAL | **1** | `18_gpio_flashlight_OPTIONAL_x1.stl` | 7 | optional; PETG (the LED gets warm); lies on its side, tree supports under the strap and lamp pod; 4 walls |
| 19 | GPIO cover OPTIONAL | **1** | `19_gpio_cover_OPTIONAL_x1.stl` | 7 | optional; upright, no supports |
| 20 | eye X insert OPTIONAL | **1** | `20_eye_x_insert_OPTIONAL_x1.stl` | - | optional; plug down, X up, no supports; for a two-colour X, swap filament at Z 8.0 (top of the flange) |
| 23 | jaw pivot pin | **2** | `23_jaw_pin_x2.stl` | 2 | **New 2026-10-29.** **Tough filament: PETG at least, nylon (PA / PA-CF) or PC better, not PLA** (they carry the jaw's weight and the servo torque). Hex head down, no supports; **100% infill**. Plate 2 has them next to the jaw: print them on their own in the tough filament, or give them that filament in Creality Print. Same part both sides. Push in from outside through the arm and skull socket, lock with an M3x5 grub screw in the back edge of the arm |

## Every piece, one by one

- [ ] 1. skull
  - [ ] reprint: skull v7 with shelf divots and bracket M3 pilots - Plate 1
- [ ] 2. jaw
  - [ ] reprint: jaw v5 for the screw-in pins - Plate 2
- [ ] jaw pivot pin (1 of 2) - Plate 2
- [ ] jaw pivot pin (2 of 2) - Plate 2
- [ ] 3. pi shelf
  - [ ] reprint: shelf with cubes - Plate 3
- [ ] 4. battery tray
- [ ] 5. battery deck
- [ ] 6. servo bracket L
- [ ] 7. servo bracket R
- [ ] 8. jaw drive hub (1 of 2)
- [ ] 9. jaw drive hub (2 of 2)
- [ ] 10. eye display carrier (1 of 2)
- [ ] 11. eye display carrier (2 of 2)
  - [ ] reprint: carrier v3 with wide slots and eased 56.60 seat (1 of 2) - `09_eye_display_carrier_x2.stl`
  - [ ] reprint: carrier v3 with wide slots and eased 56.60 seat (2 of 2) - `09_eye_display_carrier_x2.stl`
- [ ] 12. eye display retainer (1 of 2)
- [ ] 13. eye display retainer (2 of 2)
- [ ] 14. camera bezel (1 of 2)
- [ ] 15. camera bezel (2 of 2)
  - [ ] reprint: camera bezel v3 (1 of 2) - `11_camera_bezel_x2.stl`
  - [ ] reprint: camera bezel v3 (2 of 2) - `11_camera_bezel_x2.stl`
- [ ] 16. pupil ring (1 of 2)
- [ ] 17. pupil ring (2 of 2)
- [ ] 18. crown insert
- [ ] 19. neck
- [ ] 20. neck base
- [ ] 21. neck collar
- [ ] 22. bridge handle OPTIONAL
- [ ] 23. GPIO flashlight OPTIONAL
- [ ] 24. GPIO cover OPTIONAL
- [ ] 25. eye X insert OPTIONAL

## Settings

- **Material:** the two jaw pivot pins in a tough filament: PETG at least, nylon (PA / PA-CF) or PC if your printer can do it, not PLA. PETG for the battery tray, deck, both servo brackets and the GPIO flashlight. PLA or PETG for everything else.
- **Colour:** camera bezels and pupil rings in **black**.
- **Strength:** 4 walls, 20-25 % infill for the jaw, hubs, brackets, handle and flashlight; 100 % infill for the two jaw pins. Defaults for the rest.
- **Filament:** about 1.3 kg on hand.
- **Tree supports, already set (optional):** `plates/tree_supports/` has copies of plates 1, 2, 3, 5, 7 and 8 with Creality Print's organic tree supports switched on for the parts that need them (skull, jaw, Pi shelf, battery tray and deck, crown insert, handle, flashlight) and off for the rest of each plate (the jaw pins, the GPIO cover, the eye X insert). Open one as a project; each supported object shows the support settings in its object list. They're tuned to come off easily at 0.2 mm layers: a one-layer (0.2 mm) gap above and below the supports, 0.6 mm from side walls, a sparse two-layer interface under the part and no interface where a branch lands on the part, so the branches snap off cleanly. The PETG parts get a sparser interface and 0.8 mm from walls, because PETG welds to itself. If a plate opens without them (older slicer), use the plain plate and set Support > Tree (auto), style Organic, with those values. Remake them with `cad/tools/support_plates.py`.
- `plates/` has the same parts pre-laid-out on seven 250 x 250 plates (`.3mf`, Creality Print). Plate 7 is only the optional GPIO flashlight and cover. If parts don't land centred, press **Arrange**.
- The two parts of each pair are identical: the right camera bezel is the left one turned 180 deg, both jaw hubs are the same, and so are both jaw pins.
- **Camera bezel lane (v3):** the Arducam's 6 mm flex lies in a 6.8 mm wide, 2.2 mm deep lane cut into the back of the spoke, level with the camera board, so it leaves the module straight. From 16 mm out from the centre the lane narrows to a 5.6 mm mouth (0.6 mm lips): bow the flex slightly to press it past them. Print front face down (as on the plates) so the lane faces up and needs no supports. Seat the camera in its pocket from behind with the crystal end towards the spoke.
- **Skull v7, threading the camera cable:** push the rigid 16 mm wide end down the eye barrel and out through the inboard slot with its width along the barrel (front to back), then let the flex settle at the front of the slot, level with the bezel spoke. 17.9 mm of the slot is still open with the display carrier glued in, but it's easier to thread the cameras before gluing the carriers.
