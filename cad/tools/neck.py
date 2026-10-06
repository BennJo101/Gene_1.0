import numpy as np, trimesh, os
from trimesh.creation import box, cylinder
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U = lambda ms: trimesh.boolean.union(ms, engine='manifold')
D = lambda a, b: trimesh.boolean.difference([a, b], engine='manifold')
I = lambda a, b: trimesh.boolean.intersection([a, b], engine='manifold')


def zcyl(d, z0, z1, x=0.0, y=0.0, sec=96):
    c = cylinder(radius=d / 2, height=z1 - z0, sections=sec); c.apply_translation([x, y, (z0 + z1) / 2]); return c


def bx(x0, x1, y0, y1, z0, z1):
    b = box(extents=[x1 - x0, y1 - y0, z1 - z0]); b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); return b


def ring(od, idd, z0, z1, x=0.0, y=0.0):
    return D(zcyl(od, z0, z1, x, y), zcyl(idd, z0 - 1, z1 + 1, x, y))


# ---- measured skull: lower section is a vertical cylinder wall, r 84.0..91.5 about (0,-48), bottom face Z -53.35 ----
SC = np.array([0.0, -48.0]); R_IN, R_OUT, RIM_Z = 84.0, 91.5, -53.35
NX, NY = 0.0, 20.0                  # neck axis: behind the hinge, clear of the chin up to ~40 deg
YOKE_T = 6.0
YZ0, YZ1 = RIM_Z - YOKE_T, RIM_Z    # yoke sits against the rim's bottom face

# ---- neck (one part): yoke under the rear rim + tube ----
disc = zcyl(2 * (R_OUT - 0.5), YZ0, YZ1, SC[0], SC[1], sec=256)
yoke = I(disc, bx(-62, 62, NY - 30, 60, YZ0 - 1, YZ1 + 1))           # rear part of the rim footprint
yoke = D(yoke, D(zcyl(2 * (R_IN - 12), YZ0 - 2, YZ1 + 2, SC[0], SC[1], sec=256), zcyl(70, YZ0 - 3, YZ1 + 3, NX, NY)))   # open the middle, keep a hub round the neck
yoke = U([yoke, I(zcyl(70, YZ0, YZ1, NX, NY), disc)])                 # hub, trimmed to the skull outline
# stiffening ribs from the hub to the rim screws
ANG = [55.0, 72.5, 90.0, 107.5, 125.0]
RS = (R_IN + R_OUT) / 2
screws = [(SC[0] + RS * np.cos(np.radians(a)), SC[1] + RS * np.sin(np.radians(a))) for a in ANG]
ribs = []
for sx, sy in screws:
    v = np.array([sx - NX, sy - NY]); L = np.linalg.norm(v); u = v / L
    r = box(extents=[L, 8.0, 10.0]); ang = np.arctan2(u[1], u[0])
    r.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1])); r.apply_translation([NX + u[0] * L / 2, NY + u[1] * L / 2, YZ0 - 5.0 + 0.01])
    ribs.append(r)
yoke = U([yoke] + ribs)
# tube: OD 44 below the yoke, stepping to OD 40 for the bearings; the step sits on the top bearing's inner race
TUBE_OD, BRG_ID, BORE = 44.0, 40.0, 26.0
Z_STEP, Z_TUBE_BOT = -106.0, -139.0
tube = U([zcyl(TUBE_OD, Z_STEP, YZ0 + 0.5, NX, NY), zcyl(BRG_ID - 0.05, Z_TUBE_BOT, Z_STEP + 0.01, NX, NY)])
neck = U([yoke, tube])
cuts = [zcyl(BORE, Z_TUBE_BOT - 1, YZ1 + 1, NX, NY)]                      # cable bore, open into the head
for sx, sy in screws:
    cuts.append(zcyl(3.4, YZ0 - 12, YZ1 + 1, sx, sy))                  # M3 up into the rim
    cuts.append(zcyl(6.0, YZ0 - 12, YZ0 + 2.5, sx, sy))                # counterbore for M3 socket heads (5.5): 3.5 mm under each head
neck = D(neck, U(cuts))
neck = I(neck, U([zcyl(2 * (R_OUT - 0.5), YZ0 - 20, YZ1 + 1, SC[0], SC[1], sec=256), zcyl(TUBE_OD + 1, Z_TUBE_BOT - 1, YZ0, NX, NY)]))   # nothing past the back of the head
# skull v6: v5 + M3 pilots up into the rim for the neck yoke
sk = trimesh.load(os.path.join(OUT, "GeneTop_v5_crownbay.stl")); sk.apply_translation([-64.8, -61.4, -35.0])
sk = D(sk, U([zcyl(2.5, RIM_Z - 1, RIM_Z + 12, x, y, sec=32) for x, y in screws]))
sk = max(sk.split(only_watertight=False), key=lambda b: b.volume)
print(f"skull v6: watertight={sk.is_watertight} bodies={sk.body_count} vol={sk.volume / 1000:.1f} cm3")
sk.apply_translation([64.8, 61.4, 35.0]); sk.export(os.path.join(OUT, "GeneTop_v6_neck.stl"))
# collar clamp: radial M3 through the tube wall below the bottom bearing is done by the collar, not the tube
neck.export(os.path.join(OUT, "GeneHead_neck.stl"))
print(f"neck: watertight={neck.is_watertight} bodies={neck.body_count} vol={neck.volume / 1000:.1f} cm3 bounds {np.round(neck.bounds, 1).tolist()}")

# ---- base housing: 2 x 6808 (40x52x7), slip ring below; bolts to the body/stand ----
BRG_OD, BRG_W = 52.0, 7.0
H_TOP = Z_STEP                                  # top face level with the step
TOP_SEAT = (H_TOP - BRG_W, H_TOP)
BOT_SEAT = (H_TOP - 27.0, H_TOP - 27.0 + BRG_W)  # 20 mm between the bearings
CAV_BOT, PLATE_T, FL_D = -150.0, 5.0, 100.0
body = zcyl(66.0, CAV_BOT - PLATE_T, H_TOP, NX, NY)
flange = I(zcyl(FL_D, CAV_BOT - PLATE_T, CAV_BOT, NX, NY), bx(-60, 60, NY - 33.0, NY + 60, CAV_BOT - PLATE_T - 1, CAV_BOT + 1))   # D-shaped: flat front, clear of the chin's arc
base = U([body, flange])
bc = [zcyl(BRG_OD + 0.15, TOP_SEAT[0], H_TOP + 1, NX, NY),             # top bearing seat, from above
      zcyl(47.0, BOT_SEAT[1] - 0.01, TOP_SEAT[0] + 0.01, NX, NY),       # lip region between the bearings (clears the inner races)
      zcyl(BRG_OD + 0.15, BOT_SEAT[0], BOT_SEAT[1], NX, NY),            # bottom bearing seat
      zcyl(50.0, CAV_BOT, BOT_SEAT[0] + 0.01, NX, NY),                  # cavity for the collar and slip ring (bottom bearing goes in from below)
      zcyl(12.0, CAV_BOT - PLATE_T - 1, CAV_BOT + 1, NX, NY)]            # stator wire exit
# slip-ring flange: 3 x M3 on PCD 35 (assumed); body Ø22 rises into the tube bore
SR_FL, SR_PCD, SR_BODY, SR_LEN = 44.0, 35.0, 22.2, 30.0
for k in range(3):
    a = np.radians(90 + k * 120)
    bc.append(zcyl(2.5, CAV_BOT - PLATE_T - 1, CAV_BOT + 1, NX + SR_PCD / 2 * np.cos(a), NY + SR_PCD / 2 * np.sin(a)))
for bx_, by_ in ((-38.0, 5.0), (38.0, 5.0), (-38.0, 50.0), (38.0, 50.0)):
    bc.append(zcyl(4.5, CAV_BOT - PLATE_T - 1, CAV_BOT + 1, NX + bx_, by_))   # 4 x M4 to the body, 76 x 45 rectangle
# side window so the collar screw and slip-ring wires can be reached
bc.append(bx(NX - 8, NX + 8, NY - 40, NY, CAV_BOT + 1, BOT_SEAT[0] - 2))
base = D(base, U(bc))
base.export(os.path.join(OUT, "GeneHead_neck_base.stl"))
print(f"base: watertight={base.is_watertight} bodies={base.body_count} vol={base.volume / 1000:.1f} cm3 bounds {np.round(base.bounds, 1).tolist()}")

# ---- clamp collar under the bottom bearing's inner race: M3 grub through a captive nut ----
C_Z0, C_Z1 = Z_TUBE_BOT, BOT_SEAT[0]
collar = ring(45.0, BRG_ID + 0.2, C_Z0, C_Z1, NX, NY)
nut = bx(NX - 3.1, NX + 3.1, NY - 22.5 + 1.2, NY - 22.5 + 3.8, C_Z0 - 1, C_Z1 + 1)        # M3 nut slot (5.5 AF, 2.4 thick)
grub = cylinder(radius=1.7, height=10, sections=32); grub.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
grub.apply_translation([NX, NY - 21.0, (C_Z0 + C_Z1) / 2])
collar = D(collar, U([nut, grub]))
collar.export(os.path.join(OUT, "GeneHead_neck_collar.stl"))
print(f"collar: watertight={collar.is_watertight} vol={collar.volume / 1000:.2f} cm3 Z {C_Z0}..{C_Z1}")

# ---- mocks: bearings and slip ring ----
brgs = U([ring(BRG_OD, BRG_ID, TOP_SEAT[0], TOP_SEAT[1], NX, NY), ring(BRG_OD, BRG_ID, BOT_SEAT[0], BOT_SEAT[1], NX, NY)])
brgs.export(os.path.join(OUT, "GeneHead_neck_bearings_MOCK.stl"))
sr = U([zcyl(SR_FL, CAV_BOT, CAV_BOT + 2.0, NX, NY), zcyl(SR_BODY, CAV_BOT + 2.0, CAV_BOT + 2.0 + SR_LEN, NX, NY)])
sr.export(os.path.join(OUT, "GeneHead_slip_ring_MOCK.stl"))
print(f"slip ring mock: flange Z {CAV_BOT}..{CAV_BOT + 2}, body to Z {CAV_BOT + 2 + SR_LEN:.1f} (tube bore bottom at {Z_TUBE_BOT})")
print("screws into the rim at", [(round(x, 1), round(y, 1)) for x, y in screws])
