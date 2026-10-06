> Design notes and history for the Gene head, kept as written while it was designed. File names refer to the
> model sources in `cad/` and scripts in `cad/tools/`; print-ready files are in `print/`. Parts marked retired or
> superseded are described for history only and are not included in this repo.

# Gene head - current build (start here)

Updated 2026-09-25. This section is the current state of the design. The
sections below it are the design history in the order it was built; where a
part or number there has since changed, it is marked **Superseded**.

All dimensions mm. Head frame: jaw pivot axis = X, origin on the axis, -Y is the
front (the face), +Z up. The robot faces -Y, so its own left is +X.

## What to print

Everything is in `print/`, oriented and laid out on six plates (each fits
250 x 250). `BOM.md` / `BOM.csv` have the full parts, hardware and electronics list.

| Part | Source file | Qty |
|---|---|---|
| Skull v7 | `GeneTop_v7_skull.stl` (built by `tools/skull_v7.py` from v6) | 1 |
| Jaw, twin D-shafts | `GeneBottom_v4_twindrive.stl` | 1 |
| Servo brackets v2 (with battery pads) | `GeneHead_xl330_bracket_v2.stl`, `GeneHead_xl330_bracket_R_v2.stl` | 1 + 1 |
| Jaw drive hub | `GeneHead_jaw_drive_hub.stl` | 2 |
| Eye display carrier v3 (wide top + bottom slots) / retainer | `GeneHead_eye_display_carrier.stl`, `GeneHead_eye_display_retainer.stl` | 2 + 2 |
| Camera bezel (black) / pupil ring (black) | `GeneHead_eye_camera_bezel.stl`, `GeneHead_pupil_ring.stl` | 2 + 2 |
| Pi 5 shelf v6 | `GeneHead_pi_shelf_v6.stl` | 1 |
| Battery tray / deck | `GeneHead_battery_tray.stl`, `GeneHead_battery_deck.stl` | 1 + 1 |
| Crown insert | `GeneHead_crown_insert.stl` | 1 |
| Bridge handle (optional) | `GeneHead_bridge_handle.stl` | 1 |
| GPIO flashlight (optional, instead of the handle) | `GeneHead_gpio_flashlight.stl` | 1 |
| GPIO cover (optional, for when nothing is plugged in) | `GeneHead_gpio_cover.stl` | 1 |
| Neck / neck base / clamp collar | `GeneHead_neck.stl`, `GeneHead_neck_base.stl`, `GeneHead_neck_collar.stl` | 1 each |

Retired, do not print: `GeneTop_v6_neck` (v7 is v6 + clearances), `GeneTop_v3_*`, `GeneTop_v4_camslots`, `GeneTop_v5_crownbay`,
`GeneBottom_v3_jawdrive`, `GeneHead_xl330_bracket(_R).stl` (v1), `GeneHead_pi_shelf_v4/v5`,
`GeneHead_top_handle.stl` (twist-lock), `GeneTop_v3_barrel_*` (the barrels are in the skull).

## Limits to set in software

| | |
|---|---|
| Jaw speaking range | 0 - 30 deg |
| Jaw servo limit, **neck fitted** | **33 deg** (chin reaches the neck base at 35.5) |
| Jaw servo limit, no neck | 50 deg (first skull contact at 53.25) |
| Twin XL330s | one of the pair **reversed** (Drive Mode bit or negated angle) |
| Neck rotation | no stop (slip ring) |
| Pi 5 on GPIO 5 V | `usb_max_current_enable=1` in `config.txt` |
| Jaw flapping speed, on the neck | up to ~4.4 swings/s of 0-20-0 deg stays within 80 % of servo torque |
| Jaw flapping speed, **head standing on its jaw** (no neck) | **under ~3 swings/s** of 0-20-0 deg; 4/s needs 109 % |
| Talking mouth opening, on the neck | **53 %** of full visemes (~12 deg on "ah", 14 max): servos never max out, 20 % reserve. Yelled ("!") x1.6 -> ~20 deg, brief strain OK |
| Talking mouth opening, head on its jaw | **28 %** (~6 deg on "ah", 7 max), same criterion. Yelled -> ~11 deg at 95 % of available torque |

Weight and servo load (estimate, `tools/mass.py` -> `tools/web/mass.json`, 2026-09-26):
about 1320 g / 2.9 lb as the sim shows it (flashlight, no handle, no neck); skull side
1046 g, jaw + hubs 274 g. Skull CoM 41 mm in front of the pivot and 11 mm above it; jaw
CoM 78 mm in front and 74 mm below. Holding torque against the pair's 1.04 N.m stall:
on the neck 0.21 N.m (20 %) with the jaw shut; standing on the jaw, 0.42 N.m (41 %) just
off closed, easing to 0.18 N.m at 50 deg. Printed parts are estimated from volume + area at
the BOM settings and bought parts from typical weights, so expect +/-15 %: weigh the real head
and rerun. Printing the jaw with 2 walls / 15 % instead of 4 / 22 % cuts it from ~268 to ~196 g.

## Assembly order

1. Eyes: glue the display carriers into the barrels from inside (they are a slip
   fit), fit the displays, glue the retainers behind them.
2. Cameras: fit each camera into its black bezel, press the ribbon into the
   slit on the back of the bezel's spoke (no threading - the camera stays on
   its cable) and through the barrel's inboard slot, push the bezel onto the ridge,
   and glue a black pupil ring round the lens. The right bezel is the left one
   turned 180 deg.
3. Battery unit on the bench: pack in the tray (2 straps), deck on (4 x M3x10),
   bucks, BMS and charger on the deck. Lift the whole unit straight up through the
   open bottom of the skull into the dome.
4. Drive: servos onto the v2 brackets (4 x M2x8 each), brackets onto the skull
   walls (2 x M3x16 each). Lower the tray onto the bracket pads, 4 x M3x12 up
   through the pads.
5. Pi: GPIO ribbon's female end onto the header, Pi onto the v6 shelf with the
   header along the front edge (4 x M2.5x12 + nuts). Route the ribbon up in front
   of the battery tray. Shelf into the skull (4 x M3x10 through the wings).
6. Crown: push the ribbon's male plug up into the crown insert's pocket, drop the
   insert into the slot, 4 x M2x12 hex bolts. With the handle: bridge handle on
   top, 4 x M3x16 socket heads instead.
   Optional, after the crown: either press the GPIO cover into the well (notch to the
   rear), or fit the GPIO flashlight (see *GPIO flashlight and GPIO cover* below).
7. Jaw: pins in through the sockets, hubs onto the D-shafts (grub screws), hubs
   bolted to the horns (4 x M2x12 each).
8. Neck: yoke up under the rear rim, 5 x M3x16. Feed the slip ring's rotating
   wires up the tube bore. Bearings into the base, tube into the bearings, collar
   on underneath (M3 set screw), slip ring onto the base floor (3 x M3x8). Base to
   the body with 4 x M4.

## Still open

- Charge port and power switch holes in the skull.
- Wiring for the charge port and power switch once their holes exist.
- A drive for the neck rotation, and the body/stand the neck base bolts to.
- Assumed sizes to check against real parts: 2.1" round LCDs, eye cameras,
  speakers, the GPIO ribbon's male plug, the slip ring.

## Verified (last full check)

41 parts assembled, 129 neighbouring pairs measured, 15 cable runs routed and checked with exact solid
intersection; no overlaps except seating contacts. The jaw swept 0-60 deg in
0.25-0.5 deg steps against every part. All print files are single watertight
solids on reload.

Interactive sim with every part, the jaw sweep, head turn, eye expressions and
the two camera views: `sim/GeneHead_sim.html` (open it in a browser)

---

## v7 skull and v3 camera bezel - sized to the parts bought (2026-10-04)

Built from the Amazon order of 2026-09-30. Scripts: `tools/skull_v7.py`, `tools/cam3_arducam.py`, check with `tools/check_v7.py`.

| Part bought | Real size | Change |
|---|---|---|
| Arducam B0066 mini OV5647 | 8.5 mm head, ~12 mm with the crystal; 6.0 mm flex; rigid 16 x 30 mm 15-pin tail | Barrel ribbon slots 14 x 4 -> **26.5 x 7.5** (Y -114..-87.5, Z +/-3.75). Bezel pocket 8.6 x 8.6 -> **8.6 x 12.4** (grows towards the cable only, lens stays on axis); 3.6 mm mid-depth tunnel -> **6.8 x 2.2 lane from the rear face**, level with the camera board, 5.6 mm lipped mouth from r=16; spoke 7.0 -> 11.5 |
| TekGroAml 2.1" LCD + driver | LCD 56.18 x 59.71 x 2.3, 26.9 mm flex down; **round 57 mm board**, mini-HDMI + micro-USB on the edge opposite the flex | Top window in each barrel mirroring the bottom one (+/-37.5 deg, Y -96 to the barrel end) and a pocket in the skull above it from Y -88 back, up to 54 mm from the eye axis, never closer than 3 mm to the outside (measured min **3.45 mm**) |

Free height above the board's top edge went from ~2 mm to 17-29 mm over the middle of the eye at Y -84,
and 16-40 mm from Y -76 back. The exception is the **outboard** side (more than ~8 mm out from the eye
axis, in front of Y -76), where the barrel itself is the outside of the head: that's still ~2 mm. So mount
each driver board far enough back (PCB front face at Y -73 or further, about 19 mm behind the back of the LCD - checked with `GeneHead_display_board_MOCK.stl`, 0 overlap) that the
outboard plug clears; the LCD flex is long enough to run straight back rather than folding. With the
flex at the bottom and the board's parts facing back, the HDMI plug sits 6 mm outboard of the axis on the
left eye and the USB 9 mm outboard on the right.

Verified: skull single watertight solid (589.9 cm3); bezels, cameras, carriers, displays, retainers, pupil
rings, shelf, Pi, battery unit, brackets, servos, speakers, amps, TTL vs v7: 0 overlap (insert 7.4 mm3 and
neck 1.4 mm3 are the same seating contacts as v6).

Still assumed: display MOCK is still the old 55.4 x 5.2 shape (the real LCD is thinner, so the retainer
sits ~2.9 mm further forward - it's glued, so that's fine). Note the real LCD is 56.18 +/- 0.15 against the
56.00 display seat - test-fit and ease the seat if it's tight.

**Display carrier v2** (`tools/carrier_topslot.py`): still a separate glued-in cup (the barrels are part of the skull, the carriers are not). It gains a flex slot at the top matching the bottom one (+/-15.75 deg, Y -92.5 to the back face), for the driver board's HDMI/USB side. Original carrier kept as `tools/retired/carrier_v1_before_topslot.stl`.

**Display carrier v3** (same script): both slots widened to +/-74.25 deg (Y -92.55 to the back face), so behind the front lip only two side walls are left, each 31.5 deg wide (the width of the old v2 slot). The front lip ring is untouched and still frames the display. Volume 2.45 cm3, down from 4.7. The retainer now has only the two side walls to glue to. v2 kept as `tools/retired/carrier_v2_before_wide_slots.stl`.

**Skull v7 eye pockets made symmetric (2026-10-06)** (`tools/skull_v7_mirror_eye.py`, run after `skull_v7.py`): the plug pocket above Gene's right eye (-X) had a ragged outboard edge, because v6 has leftover internal weld faces at that barrel/skull crease that confused the skin check. The -X eye region (X -100..-33, Y -109..-49, Z 20..75) is now the exact mirror of the clean +X (left) eye. Still one watertight solid (589.5 cm3), min skin 3.34 mm (right) / 3.41 mm (left), part overlaps unchanged (only the insert/neck/handle seating contacts). The +X side is untouched. Old file kept as `tools/retired/GeneTop_v7_before_eye_mirror.stl`. `print/skull_x1.stl`, `3D print/01_skull_x1.stl`, Plates 1 and 9 and the sim have been regenerated.

**Skull v7 barrel corners sealed (2026-10-06)** (`tools/skull_v7_seal_corners.py`, run after `skull_v7_mirror_eye.py`): the bottom flex window cut through the barrel wall where the lower side wall meets it, leaving a small triangular hole to the outside at the outboard bottom corner of each eye (Y -96 to about -85). The barrel wall is restored there only outboard of the lower wall's inner face (r 83.5 about X 0, Y -48), so the inside of the window is unchanged. +1.39 cm3 (590.9 cm3), one watertight solid, part overlaps and the 0-60 deg jaw sweep unchanged. Previous file kept as `tools/retired/GeneTop_v7_before_corner_seal.stl`.

**Skull v7 barrel ends blended into the skull (2026-10-06)** (`tools/skull_v7_barrel_taper.py`, run after `skull_v7_seal_corners.py`): each eye barrel ended in a flat face at Y -61.5 standing up to 4.5 mm proud of the skull side, with a thin see-through crack along it. The barrel's outer cylinder (r 34.25) now carries on backwards as a cone (0.35 mm radius per mm, about 19 deg) that runs into the skull side, which closes the crack. The cone is trimmed outside the head cavity (r 83.3), outside the bore and out of the top +/-45 deg where the plug pocket is, so nothing changes inside. +2.07 cm3 (592.9 cm3), one watertight solid, part overlaps and the 0-60 deg jaw sweep unchanged. Previous file kept as `tools/retired/GeneTop_v7_before_barrel_taper.stl`.

**Skull v7 inboard barrel walls opened (2026-10-06)** (`tools/skull_v7_open_inboard.py`, run after `skull_v7_barrel_taper.py`): the real TekGroAml driver board (seller's drawing: 57 mm round, 4 x M2.5 at (0,0) (0,33.4) (35,33.4) (38.69,0), mini-HDMI 11.5 wide at (-9.27,22.6) and micro-USB 8.0 wide at (-9.37,7.83), both angled 15 deg and splaying apart, 40-pin FPC connector 26.8 long on the opposite edge) puts the outboard plug of each eye - mini-HDMI on Gene's right, micro-USB on his left - only 8-10 mm from the barrel skin when mounted flex-down. The plan is to turn each LCD + board 180 deg in its barrel (flex up, plugs down; the Pi flips the picture with a standard 180 deg display rotation). To let the LCD ribbon swing past while turning it, the inboard wall of each barrel is removed from the top of the camera ribbon slot (Z +3.43) up to the top window, Y -96 to the barrel end, barrel wall only (r 29.8..34.4); beyond it is open head cavity. The bridge between the eyes and the outboard walls are untouched. -7.6 cm3 (585.4 cm3), one watertight solid. With the boards flipped (mock rotated 180 deg) there is no overlap with the skull, Pi shelf, speakers or anything else; the inboard plug then has about 11-12 mm to the Pi shelf's top plate, the outboard one 12-17 mm to the lower side wall. Previous file kept as `tools/retired/GeneTop_v7_before_open_inboard.stl`.

---

# Design history

## Jaw drive (XL330-M288-T), first version

**Superseded:** this section describes the single-servo v3 drive. The build now uses
the twin drive (jaw v4, v2 brackets) - see *Twin motors* and the current build above.

All dimensions mm. Reference frame: pivot axis = X, origin on the axis,
+X inboard (toward head centre), left side is -X. The drive is on the LEFT.
Jaw rest angle = 0 deg in this frame.

## Parts

| File | What | Print |
|---|---|---|
| `GeneBottom_v3_jawdrive.stl` | The jaw, with the left pivot pin extended into a dia 8.0 D-shaft | 1 |
| `GeneHead_jaw_drive_hub.stl` | Drive hub: dia 18 OD x 15 long, D-bore, 4 x M2 on dia 12 to the horn, radial M3 grub | 1 |
| `GeneHead_xl330_bracket.stl` | Servo bracket, 4 x M2 to the servo, 2 x M3 into the skull wall | 1 |
| `GeneTop_v3_thrustpad.stl` | The skull, with a conformal thrust pad added at each pivot | 1 |
| `GeneHead_jawdrive_assembly.stl` | Whole thing assembled, for viewing only | - |
| `render_jaw_drive.png` | Hub, bracket, and the drive train | - |

Hardware: 4 x M2 x 12 (hub to horn), 4 x M2 x 8 (servo to bracket),
2 x M3 x 16 self-tapping (bracket to skull), 1 x M3 grub (hub to shaft).

## How it goes together

1. Jaw pin passes outside-in through the skull socket as before. The new
   dia 8.0 D-shaft continues past the socket into the head.
2. Hub slides onto the D-shaft, flat-to-flat, grub screw from the side.
3. Servo bolts to the bracket (4 x M2), horn facing outboard.
4. Bracket screws to the skull's inner wall (2 x M3 at Y=+20, Z=+/-10).
   The bracket foot was cut with a boolean against the skull, so it is an
   exact conformal match to the inner surface, not a flat pad on a sphere.
5. Hub bolts to the horn, 4 x M2 on the dia 12 bolt circle.

## Verified numerically

- Every part watertight and a single body.
- Zero interference: hub/servo/jaw vs skull and bracket, 0 of 8000 sample
  points in all six pairings.
- Bracket vs skull max penetration 0.0000 mm (conformal by construction).
- Bracket screws pass through 8 mm of bracket into 11 mm of skull wall
  (wall measures 7.5-11 mm thick all round the pivot).
- Jaw sweep clear 0-53 deg; first contact (left arm) at 53.25 deg, right arm at 57.25 deg.
  Set the servo limit to 50 deg or less - **or 33 deg with the neck fitted**.
- Axial play 8.5 mm bare -> 4.75 mm with the hub -> **0.30 mm** with the
  thrust pads (free range dx -0.10 .. +0.20).
- Thrust pads: annulus r 7.30-11.00 at each pivot, shaped as the complement
  of the jaw's swept volume over -5..60 deg with 0.10 mm clearance, so the
  pad face matches the jaw arm exactly instead of being a flat ring on a
  curved shell. Both pads fuse into the skull body (body count stays 4).
- Skull + pads re-welded after export: watertight, 4 bodies, 603.9 cm3.

## Known limits

- A pivot sleeve and a thrust washer were both tried and dropped: measured
  on the real faceted meshes, the socket's usable bore is dia 14.28 and the
  pin is dia 13.76, leaving 0.26 mm radial - no room for a sleeve, and the
  annulus at the socket mouth is already occupied by skull material.
  The bare pivot fit is 0.52 mm diametral, which is a workable running fit.
- The socket still only wraps the pin over ~56% of its circumference.
- Horn screws: the ROBOTIS STEP models the horn holes at dia 1.60. The hub
  is drilled dia 2.20 for M2. Check your actual horn before final print.
- The right-hand pivot is undriven and runs as a plain bearing, but it does
  get a thrust pad, so both sides locate axially.
- The pads are cut for the jaw travelling -5 to 60 deg. Widening the travel
  later means recutting them.
- **Superseded:** print the skull from `GeneTop_v6_neck.stl` (it contains these thrust pads).

---

# Eye displays (2.1 inch round)

Measured bore of each eye barrel, along its axis from the front face:

| Depth | Diameter | Role |
|---|---|---|
| 0 - 38 mm | 59.00 | front tube |
| 38 - 40 mm | **56.80** | the inner circle - the ridge you see down the barrel |
| 40 mm - rear | 60.60 | rear cavity, opens into the head |

The monitor loads from **inside the head** and seats against the rear face
of the 56.80 ridge, so the ridge frames the screen.

| File | What | Print |
|---|---|---|
| `GeneHead_eye_display_carrier.stl` | Cup, OD 60.50 x 12 long. Aperture 53.80, pocket 56.00 x 10.0, cable slot at the bottom | 2 |
| `GeneHead_eye_display_retainer.stl` | Ring OD 55.80 ID 46.0 x 3.0, traps the module in the cup | 2 |
| `GeneHead_eye_display_MOCK.stl` | The module itself, for fit checking only - do not print | - |

Verified: carrier and module clear both barrels and the skull, 0 of 6000
sample points in every pairing. Active area clears the ridge by 1.73 mm all
round and the carrier lip by 0.23 mm.

**Module dimensions are assumed** - active area dia 53.34 (2.1 in) with a
55.4 mm body. Real 2.1 in round LCD modules vary. The two numbers to change
for your part are the pocket diameter (56.00) and pocket depth (10.0) in
`eyebuild.py`; everything else follows.

The carrier is a slip fit, not an interference fit: 0.106-0.109 mm radial
clearance to the bore at its tightest (full-assembly check). Glue it with CA;
the ridge takes the forward load. Glue the retainer too - nothing holds it axially.

---

# Pi 5, speakers, and eye cameras

## Where things fit

The cavity is 2721 cm3, but two things constrain it: the eye barrels pinch
the front to a **46 mm channel** between them, and the XL330 sits mid-cavity
at X -46..-17, Y -24.5..9.5, Z -10..10. An 85 mm Pi 5 cannot go where the
original shelf was.

The barrels bottom out at Z -34.67 and the cavity floor is at Z -53. That
band runs the full width of the head, so the shelf passes *under* the eyes.

| File | What | Print |
|---|---|---|
| `GeneHead_pi_shelf_v5.stl` | **Superseded by v6** (4 mm standoffs). Shelf, plate Z -40..-37, 92 x 108 with conformal side wings, Pi 5 standoffs, 2 speaker cradles, cable slot | 1 |
| `GeneHead_pi5_MOCK.stl` | Pi 5 board + 14 mm component stack, fit check only | - |
| `GeneHead_speaker_MOCK.stl` | 2 x dia 28 x 5 speakers, fit check only | - |

Pi 5 sits on standoffs (6 mm in v5, **4 mm in v6**), holes 58 x 49, board centred at (0, -29).
In the current build the board is turned so its GPIO header runs along the front edge.
Speakers drop into dia 28.4 cradles at (+/-26, -88) facing down, each with a
dia 23 sound hole through the plate. Shelf screws to the shell with 4 x M3
self-tappers through the wings, which were cut against the skull so they
match the curved inner wall exactly.

Verified clearances:

| | |
|---|---|
| Pi 5 component top to servo underside | 5.4 mm (v5); **7.4 mm with the v6 shelf** |
| Shelf top to eye barrel underside | 2.33 mm |
| Headroom under the shelf | 18.5 mm |
| Speaker underside to cavity floor | 6 mm |
| Shelf / Pi / speakers vs shell, servo, bracket, hub, carriers | 0 of 8000 pts |
| Jaw sweep 0-55 deg vs shelf | clear |

## Eye cameras

A micro camera sits at the centre of each eye, in front of the display, so
it reads as the pupil. Its ribbon leaves through a slot cut in the **inboard**
wall of each barrel and into the central channel between the eyes - the
display is never crossed by the cable.

| File | What | Print |
|---|---|---|
| `GeneTop_v4_camslots.stl` | Skull with thrust pads **and** the two 14 x 4 mm ribbon slots. **Superseded by v6**, which keeps these slots | 1 |
| `GeneHead_eye_camera_bezel.stl` | Print in black. Bezel OD 58.6 x 6, **one spoke**, 8.6 mm square camera pocket, dia 7.5 lens aperture, cable channel open to the rear face (slit) so the ribbon drops in with the camera attached. Rotate 180 deg about the barrel axis for the second eye | 2 |
| `GeneHead_eye_camera_MOCK.stl` | 8.5 mm camera + lens barrel, fit check only | - |

The bezel slips into the dia 59.00 front bore and seats on the front face of
the dia 56.80 ridge, 38 mm down the barrel.

**Single spoke.** The bezel has one arm, not three, and it points inboard
straight at the ribbon slot. The cable runs *inside* it in a 3.6 mm channel
that opens to the rear face through a 2.6 mm slit with 0.5 x 0.8 mm retaining
lips (added 2026-09-27, because the camera
module can't be unplugged from its ribbon to thread a closed tunnel) - walls
1.70 mm either side, 2.10 mm in front - so no cable is visible from the front and only one arm crosses the display.
Because the spoke has to point inboard on both sides the part is handed, but
rotating it 180 deg about the barrel axis hands it the other way: one file,
printed twice, same trick as the drive hub.

Verified: spoke points +X on the left eye and -X on the right (both inboard),
tunnel hollow at its centre with solid spoke around it, and the exit line
through the barrel slot is clear on both sides. Camera and bezel clear the shell
and the display carrier, 0 of 3000 points each, both sides. Both ribbon slots
probe fully open.

**Camera module is assumed** at 8.5 mm square with a 6 mm lens barrel (the
common OV5647 / IMX219 mini modules). Change `CAM` and `LENS` in `cam.py` for
a different part.

## Print list at this stage

**Superseded** - see *What to print* at the top of this file.

---

# Twin motors

Two XL330-M288-T, one per pivot, in tandem: **1.04 N.m** combined stall
torque at 5 V (0.52 each).

| File | What | Print |
|---|---|---|
| `GeneBottom_v4_twindrive.stl` | Jaw with **both** pins extended into dia 8 D-shafts. Use this, not v3 | 1 |
| `GeneHead_xl330_bracket.stl` | Left bracket (**superseded by** `_v2`, which adds the battery pads) | 1 |
| `GeneHead_xl330_bracket_R.stl` | Right bracket (**superseded by** `_R_v2`) | 1 |
| `GeneHead_jaw_drive_hub.stl` | Hub - the right one is the SAME part rotated 180 deg about Z | 2 |

The right side was probed before being trusted rather than assumed
symmetric: shell measures 12.0 mm thick at the anchor on both sides, and
the right pin geometry mirrors the left. The right bracket is the left's
construction mirrored in X and then re-cut against the actual right-hand
skull; it came out at 6.45 cm3, identical to the left.

Rotating the hub 180 deg about Z puts its counterbores outboard on the right
while leaving the D-flat on the same face, so one hub file serves both sides.

Verified: servo R, hub R and jaw v4 all 0/4000 against the shell; bracket R
penetration into the skull 0.0000 mm (conformal, by construction); right
pilots pass through 8 mm of bracket into ~12 mm of shell; jaw sweep clear
to 53 deg with both drives fitted (the later full-assembly check refined 55 to 53).

## Wiring - important

The two servos face opposite directions, so one jaw motion turns them in
**opposite senses**. Invert one of the pair, either with the Drive Mode
reverse bit in its control table or a negated angle in software. Sending
both the same command makes them fight each other and stall.

## Travel

| | |
|---|---|
| Speaking range | **0 - 30 deg** |
| Mechanical limit | 53 deg (skull); **35.5 deg with the neck** - set 50 / 33 |

The viewer's Cycle button now animates 0-30 deg only; the slider still
reaches 55 so the limit stays visible. The remaining travel is headroom,
not working range.

Hardware, doubled on the drive: 8 x M2x12 hub to horn, 8 x M2x8 servo to
bracket, 4 x M3x16 self-tapping bracket to shell, 2 x M3 grub hub to shaft.

---

# Top carry handle (retired)

**Superseded:** the crown slot is now filled by the crown insert, and the optional
bridge handle bolts on top of it. Do not print `GeneHead_top_handle.stl`. Kept here
for the slot measurements.

The crown slot measures **26.5 mm wide** (X -12.0 .. +14.5, centred X=+1.25,
so it is 1.25 mm off the dome's centreline) and runs about 100 mm fore-aft
through a shell 7.0-7.5 mm thick. The rim is flattest over Y -58 .. -38
(top Z 89.5-90.0, underside 82.0-82.5); the handle seats there, centred
at Y = -48.

**Quarter-turn twist lock.** Drop it in with the foot aligned along the
slot, turn 90 degrees, done. No flexing legs, no screws, no reaching inside
the head. To remove, turn back and lift.

| Feature | Value |
|---|---|
| Foot | 34 x 22 x 4, obround, top face at Z 80.80 |
| Insert clearance | 2.25 mm each side of the 22 mm foot in the 26.5 slot |
| Locked overhang | 3.75 mm onto the rim each side |
| Stem | dia 20, turns freely in the 26.5 slot |
| Shoulder underside | Z 90.70 (rim high points measure 90.47) |
| Grip | cross bar 90 long, 45 mm above the rim, 28 mm finger gap |
| Detents | 2 x dia 5 x 1.0 on the foot top, engage only in the last ~10 deg |

Verified: 0.000 mm interference at every step of the turn from 90 to 10
degrees, 0.096 mm at locked - that last figure is the detent bumps, which
is the click.

The foot sits 1.6-2.0 mm below the rim underside, so the handle lifts that
far before taking load. Deliberate, to keep the turn easy.

The foot is obround rather than rectangular so it has no corners to catch
the dome's curved underside as it sweeps.

---

# Full-assembly fit check (2026-09-25)

All 25 parts at that stage placed together, 88 neighbouring pairs measured with exact solid
intersection (Manifold), jaw + hubs swept 0-60 deg in 0.25-0.5 deg steps.
Servos checked as a solid envelope (the STEP mesh is not watertight).

- **No clashes anywhere in the 0-30 deg speaking range.**
- First jaw-to-skull contact at **53.25 deg** (left arm), not 55. Limit the servo to <= 50 deg
  (33 deg once the neck is fitted).
- **Fixed:** `GeneHead_eye_camera_bezel.stl` had its camera pocket cut flush with
  the rear face, leaving a zero-thickness skin that some kernels/slicers fill in.
  Pocket now runs 1 mm through; geometry and volume (5.03 cm3) unchanged,
  camera clears by 0.05 mm. Re-slice this part.
- **Fixed:** Pi standoffs 6 -> 4 mm (`GeneHead_pi_shelf_v6.stl`). Pi mock now includes a
  16 mm USB/Ethernet block overhanging the board edge 2.5 mm; clears the bracket by 1.4 mm.
- **Fixed (handle since retired):** handle -X detent 1.00 -> 1.35 mm. That rim is nearly flat, so 1.45 would rub
  through the whole turn; 1.35 stays clear until the last ~15 deg and seats 0.12 mm
  (+X seats 0.22). Both sides click.
- **Check:** display carriers and retainers are slip fits - glue both.
- By design: D-shaft ends sit flush on the horn faces at X +/-46 (turn together);
  jaw to thrust pads 0.08 mm at rest; hub to skull 0.40, hub to bracket 0.50.

---

# Battery (2S2P 18650)

Budget at 5 V: Pi 5 + cameras 7.5 W typ / 12.5 peak, 2 x XL330 3 / 14.7 (stall
1.47 A each), 2 LCDs 1.2, audio 1 / 4. From the pack at 90 % conversion:
**~14 W talking, ~36 W peak**. 2S2P 18650 (3000-3500 mAh, >=10 A cells such as
Samsung 30Q or Molicel P28A) = 43-50 Wh -> **about 3 h**. Peak 6.2 A at 6.4 V.
2S 20 A balancing BMS (HW-391), on the deck. Two 5 V 5 A bucks: Pi rail (5.1 V) and servo+audio rail.

| File | What | Print |
|---|---|---|
| `GeneHead_battery_tray.stl` | Tub, 3 cradle ribs, 2 strap windows (22 mm hook-and-loop), rear lead exit, trimmed >=1.4 mm off the dome | 1 |
| `GeneHead_battery_deck.stl` | Lid plate: 2 x 26.4x26.4 buck bays (Pololu D36V50F5) + 49x21 BMS bay (HW-391) + 40x20 charger bay, zip-tie slots, lead hole | 1 |
| `GeneHead_xl330_bracket_v2.stl` / `_R_v2.stl` | Brackets with 2 screw pads on top. **Use these instead of the v1 brackets** | 1 each |
| `GeneHead_pi_shelf_v6.stl` | Shelf with 4 mm standoffs. **Use instead of v5** | 1 |
| `GeneHead_battery_2S2P_MOCK.stl`, `GeneHead_power_boards_MOCK.stl` | Fit check only | - |

Pack sits in the dome over the servos: tray X -45..45, Y -58.5..19, Z 14..38.5;
deck to Z 42.5, boards to ~51. Tray floor rests on the bracket pads (Z 14).

**Fit order:** pack + tray + deck + boards as one bench unit -> lift straight up
through the open skull bottom into the dome (checked, no contact) -> fit both
brackets with servos -> lower tray onto pads -> 4 x M3x12 self-tappers up through
the pads (at X +/-41.5, Y -31 and +14) -> Pi shelf -> crown insert -> jaw -> neck. Deck screws 4 x M3x10
from above into the tray posts (X +/-41.5 Y -54.5, X +/-20 Y 15.5).

Verified: tray, deck, pack and boards clear everything else (skull >= 1.4 mm,
eye barrels 2.9 mm); jaw sweep unchanged.

Not done yet: a charge port through the skull. The pack is meant to stay in the head.

---

# Camera pupils

`GeneHead_pupil_ring.stl` (print 2, black): OD 18 x 2 mm, glued to the front face
of each bezel hub. Bore is a 60 deg cone from dia 7.5 at the face to 14.4 at the
lip, so the lens reads as a deep pupil. Clear field of view from the lens: 153 deg
(no vignetting for any normal lens); lens clears the bore by 0.75 mm. Print the
bezels black as well, so the ribbon spoke vanishes against the dark screen.

Screen graphics treat the lens as the fixed pupil: an aperture-blade iris around
it opens and closes per expression; gaze turns the focus ring and nudges the lids
rather than moving the pupil off the lens.

---

# GPIO flashlight and GPIO cover (optional)

Built by `tools/gpio_flashlight.py` (run with cwd = tools). Both use the crown insert's
GPIO well (pins in a 52.2 x 6.4 well centred X 1.25, Y -46.5; pin tips Z 85.5).

| File | What | Print |
|---|---|---|
| `GeneHead_gpio_flashlight.stl` | Saddle on the crown insert (X -13.5..16, Y -99..-12), a strap 14 wide over the brow, and a lamp pod dia 27 centred X 0, Z 40 on the forehead, pointing straight ahead (-Y). Front of the pod at Y -155 | 1, PETG |
| `GeneHead_gpio_cover.stl` | Flush plug for the well: skirts straddle the pins on all four sides, 4 crush ribs, pry notch at the rear end | 1 |
| `GeneHead_gpio_header_MOCK.stl` | The flashlight's 2x20 female header, fit check only | - |

**Flashlight mount.** A standard 2x20 female header (8.5 mm body) goes upside down onto
the crown pins and sits on the ribbon plug's body (Z 79.5..88.0). The crown bulges up to
3 mm above the header in the middle of the well, so the saddle has a tongue (6.0 wide in
the 6.4 well) that reaches down to the header's top with a 0.3 mm glue gap. The header's
solder tails point up into a 4 mm cavity in the tongue. A 4 x 2.5 mm channel under the
strap carries 3 wires from there to a 16 dia x 7 mm driver cavity behind the LED star.
The pod has a 20.4 mm bore, 14.5 deep, for a 20 mm optic in front of a 20 mm star, and
the star sits on the step into the cavity.

The saddle is screwed down through the front pair of crown screw holes with
**M3x20 socket heads** instead of the M2x12 hex bolts (7.3 mm under the head, 6.8 mm of
thread in the ledge + boss, which have 8.2). That keeps knocks off the pins. It also
means the flashlight and the bridge handle are either/or. The rear pair stay M2x12
hex bolts; the saddle ends 2.5 mm short of their heads. The underside follows the real
crown and brow with 0.2 mm clearance. The strap's top is smoothed where the dome dips in
front of the slot. Nothing is inside either camera's 62 x 49 deg view.

Fitting: solder the 3 wires to the header's tails first, then push the header onto the
crown pins on its own. Put a bead of CA or epoxy on its top, lay the wires in the channel,
lower the saddle onto it and screw it down. Leave it to cure in place so the header sets
exactly where the pins want it.

**Electrics.** It uses 3 pins: 5 V, GND and GPIO 12 (PWM0, pin 32; not used by the I2S
amps). The circuit: 5 V -> LED -> 10 ohm 1 W -> AO3400A drain, source to GND; gate from
GPIO 12 through 100 ohm, with 10 k to GND. That gives about 200 mA (0.6 W in the LED,
0.4 W in the resistor, 60-70 lm). Through a 30 deg optic that's roughly 250 lux at 1 m,
against about 2 lux from both eye screens at full white. Dim it with PWM, e.g.
`gpiozero.PWMLED(12)`. **Which crown pin is which depends on how the ribbon was folded
under the crown**, so find 5 V and GND with a meter on the powered head before soldering.

**Cover.** 6.2 x 51.9 mm, top trimmed flush to the crown. Its skirts (1.1-1.4 mm) go down
either side of the pins, clearing the real pin field (rows at +/-1.27, 0.64 square) by
0.35 mm, and stop 0.6 mm above the ribbon plug. Four 1 mm crush ribs give 0.1 mm
interference per side. The notch at the rear end (Y -20.5) takes a fingernail or a small
flat screwdriver.

Verified: the flashlight clears the skull by 0.20 mm, the insert by 0.20, the ribbon plug
by 2.05 and its header by 0.30. The cover clears the real pins by 0.35. Both are single
watertight solids and reload watertight. The pair check lists handle x flashlight and
cover x flashlight/header as overlaps, but those are alternatives, not a fit.

---

# Crown feature bay (replaces the twist-lock handle)

The top slot (measured: vertical walls at X -12.26 / +14.76, 27.0 wide, Y -105.2..+9.7
with shallow arced ends) is now a feature bay.

| File | What | Print |
|---|---|---|
| `GeneTop_v5_crownbay.stl` | Skull v4 + a 4 mm x 3 mm ledge round the underside of the slot + 4 screw bosses (dia 7 x 6, M3 pilots). **Superseded by v6**, which keeps the ledge | 1 |
| `GeneHead_crown_insert.stl` | Fills the slot flush (top built from the real rim heights both sides + across-slot curvature), sits on the ledge, 4 x M2x12 hex bolts from above | 1 |
| `GeneHead_bridge_handle.stl` | Optional. Two feet conformal to the insert, 16 mm grip 25 mm above the crown, M3x16 socket heads through bores in the posts | 1 |
| `GeneHead_gpio_plug_MOCK.stl` | Male IDC plug of the ribbon, fit check only | - |

Screw positions (X,Y): (-10.26,-90) (12.76,-90) (-10.26,-6) (12.76,-6). Insert over the
ledge 5.9 mm; 8.2 mm of thread engagement in ledge + boss.

**GPIO riser:** 40-pin female-to-male extension ribbon (20 cm). Female end on the Pi
header; the male IDC plug (assumed body 56 x 8.9 x 7.6, pins 6 mm) pushes up into a
pocket in the insert, centred Y -46.5, pins in a 52.2 x 6.4 well with tips 1 mm below
the lowest surface over the well. Add-ons plug in from the top with a 2x20 female header.
The Pi is now mounted with its GPIO along the FRONT edge (USB/Ethernet at -X). Ribbon
route: forward off the header, straight up in front of the battery tray (X +/-25.5,
Y -61..-59.6; 1.1 mm to the tray, 1.2 mm to the eye barrels), twisted on edge under the
crown into the plug. Checked clear all the way.

Verified: insert and handle clear everything (seating contacts only, 13 um and 5 um),
all new parts single watertight bodies.

The old `GeneHead_top_handle.stl` (twist-lock) is retired.

---

# Neck on a slip ring

The skull's lower section is a vertical cylinder wall (r 84.0..91.5 about X 0, Y -48,
bottom face Z -53.35). The neck axis is X 0, Y +20, just behind the hinge.

| File | What | Print |
|---|---|---|
| `GeneTop_v6_neck.stl` | Skull v5 + 5 M3 pilots up into the rear rim. **Print this skull** | 1 |
| `GeneHead_neck.stl` | Yoke under the rear rim (5 x M3x16 up into the wall) + tube OD 44, bore 26 (cable hole), stepping to OD 40 for the bearings | 1 |
| `GeneHead_neck_base.stl` | Bearing housing: 2 x 6808 (40x52x7) 20 mm apart, slip-ring floor, D-shaped flange with 4 x M4 on a 76 x 45 rectangle | 1 |
| `GeneHead_neck_collar.stl` | Clamps under the bottom bearing (M3 set screw + captive nut) | 1 |
| `GeneHead_neck_bearings_MOCK.stl`, `GeneHead_slip_ring_MOCK.stl` | Fit check only | - |

Load path: head weight -> tube step -> top bearing inner race -> housing. The collar
stops lift-off. The slip ring (assumed: 22 mm body, 30 mm tall, 44 mm flange, 3 holes on
PCD 35) bolts to the base floor and reaches up into the tube bore; fixed wires leave
through the 12 mm hole in the floor, rotating wires run up the bore into the head.

**Jaw limit with the neck fitted: 33 deg.** The chin swings back under the head as the
mouth opens; it clears the neck by 12 mm at 30 deg and first touches the front of the
base at 35.5 deg (the base flange is flat at the front to get that far).

---

# Sim additions (no printed parts)

- Eye screens: nine expressions (neutral, happy, sad, angry, surprised, sleepy,
  love, wink, loading), blink and look-around. The lens is always the pupil; an
  aperture-blade iris surrounds it. Baseline colour is green (hue 140). Loading
  spins the blades, chases a string of dots round the iris and fills a progress
  arc that restarts.
- Camera POV: live views from both lens positions (62 x 49 deg, IMX219-class),
  stereo baseline 121.9 mm, shown as a stereo pair with the robot's own left eye
  on the left. The lenses sit 31.5 mm inside the barrels (bore 59), so anything
  wider than ~86 deg horizontal would see the barrel wall.
- Head turn on the neck, with a Spin control.

---

# Wiring (all runs routed and checked)

Script: `tools/occ_all.py` builds a 2 mm occupancy grid of the whole assembly (fixed
parts + the jaw's 0-35 deg sweep; column ray-fill, ~20 s), `tools/route.py` routes each
cable (Dijkstra on the free grid, radius + 2 mm margin, string-pulled), adds it as an
obstacle for the next, then rebuilds every cable as a solid tube and intersects it
exactly with every part and every other cable (ends trimmed 6 mm where they plug in).
Results in `tools/cables.json`; lengths to buy are in `BOM.md` section 5.

All 14 runs plus the GPIO ribbon fit. Tightest: left display cable 0.19 mm, pack leads
0.25 mm (both at the full 6 mm envelope). The right camera ribbon wraps behind the Pi
shelf's rear edge and just touches it.

Added so the wiring works:
- `GeneHead_gpio_splitter_MOCK.stl`: 1-to-2 GPIO splitter on the Pi header. The crown
  ribbon's plug moves up 12 mm onto it; the amps use the second header.
- `GeneHead_ttl_interface_MOCK.stl`: DYNAMIXEL TTL interface on the left shelf wing.
- `GeneHead_i2s_amps_MOCK.stl`: one MAX98357A amp centred on the shelf between the speakers (mono, speakers in parallel);
  speaker leads (26-28 mm) come up through each speaker's vent hole.
- Pi 5 connector positions used (USB/Ethernet at -X, GPIO at the front): USB-C power
  X 31.3, micro-HDMI X 16.7 and 3.3 on the rear edge; camera connectors near X -2.5 and
  -15.5 at the rear.
