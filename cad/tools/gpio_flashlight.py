# Optional crown accessories that use the GPIO well in the crown insert:
#   gpio_flashlight.stl - saddle on the crown insert + strap over the brow + lamp pod on the forehead.
#                                  An inverted 2x20 female header in the saddle plugs onto the crown pins.
#   gpio_cover.stl      - flush plug for the well when nothing is fitted, with a pry notch.
# Head frame: pivot axis = X, -Y front, +Z up. Run with cwd = tools.
import numpy as np, trimesh, json, os
from trimesh.creation import box, cylinder
from parts import *

U = lambda ms: trimesh.boolean.union(ms, engine='manifold')
D = lambda a, b: trimesh.boolean.difference([a, b], engine='manifold')
I = lambda a, b: trimesh.boolean.intersection([a, b], engine='manifold')


def bx(x0, x1, y0, y1, z0, z1):
    b = box(extents=[x1 - x0, y1 - y0, z1 - z0]); b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); return b


def ycyl(d, y0, y1, x, z, sec=96):
    c = cylinder(radius=d / 2, height=abs(y1 - y0), sections=sec)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])); c.apply_translation([x, (y0 + y1) / 2, z]); return c


def zcyl_at(d, z0, z1, x, y, sec=48):
    c = cylinder(radius=d / 2, height=z1 - z0, sections=sec); c.apply_translation([x, y, (z0 + z1) / 2]); return c


P = load_all()
shell, insert = P["shell"], P["insert"]
meta = json.load(open("crown_meta.json"))
CX, GYC, BODY_TOP = meta["CX"], meta["GYC"], meta["BODY_TOP"]
SCREWS = meta["SCREWS"]
SC = np.array(json.load(open("sphere_outer.json"))["c"])           # dome centre, outer radius 88.4, wall ~4.9

# ---- outer surface along the centre band, in polar form about the dome centre (YZ plane) ----
# th = 0 straight up, positive toward the face. For each th take the outermost surface over the band's width.
def envelope(xs, ths):
    """(max, min) over the X samples of the outermost surface radius at each th."""
    per_x = []
    for x in xs:
        segs = []
        for m in (shell, insert):
            s = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
            if s is None: continue
            for e in s.entities:
                p = s.vertices[e.points][:, 1:]
                segs += list(zip(p[:-1], p[1:]))
        A = np.array([a for a, b in segs]) - SC[1:]; E = np.array([b for a, b in segs]) - SC[1:] - A
        row = []
        for t in ths:
            d = np.array([-np.sin(t), np.cos(t)])                      # (dY, dZ)
            den = E[:, 0] * d[1] - E[:, 1] * d[0]; ok = np.abs(den) > 1e-12
            u = np.full(len(A), -1.0); u[ok] = (A[ok, 1] * d[0] - A[ok, 0] * d[1]) / den[ok]
            hit = ok & (u >= 0) & (u <= 1)
            r = ((A + u[:, None] * E) @ d)[hit]; r = r[r > 60]
            row.append(r.max() if len(r) else np.nan)
        per_x.append(row)
    R = np.array(per_x)
    return np.nanmax(R, 0), np.nanmin(R, 0)


TH_REAR, TH_SADDLE, TH_END = np.radians(-22.0), np.radians(33.0), np.radians(57.0)   # front screws at th 28.7 (heads to ~31)
ths = np.radians(np.arange(-22.0, 57.01, 1.0))
ENV_S, ENV_S_MIN = envelope(np.linspace(-13.5, 16.0, 9), ths)         # saddle width
ENV_B, ENV_B_LO = envelope(np.linspace(-7.0, 7.0, 5), ths)            # strap width
ENV_B_MIN = np.minimum(ENV_S_MIN, ENV_B_LO) + 1.0                     # inner face starts 0.5 below the lowest surface (radii below use -1.5)
T_SAD, T_STRAP = 6.0, 5.0


def smooth_top(env, t):
    """Outer surface: running max over +/-8 deg, then a 7-point average, so dips in the skull (the slot's front end) don't show."""
    r = env + 0.3 + t; w = 8
    m = np.array([r[max(0, i - w):i + w + 1].max() for i in range(len(r))])
    k = np.ones(7) / 7; return np.convolve(np.pad(m, 3, mode="edge"), k, mode="valid")


TOP_S, TOP_B = smooth_top(ENV_S, T_SAD), smooth_top(ENV_B, T_STRAP)


def polar_pt(t, r, x):
    return np.array([x, SC[1] - np.sin(t) * r, SC[2] + np.cos(t) * r])


def band(t0, t1, x0, x1, r_in, r_out):
    """Solid between radii r_in(t) .. r_out(t), X x0..x1, swept th t0..t1 in 1 deg hulls."""
    k = [i for i, t in enumerate(ths) if t0 - 1e-9 <= t <= t1 + 1e-9]
    parts = []
    for i, j in zip(k[:-1], k[1:]):
        pts = [polar_pt(ths[q], rr, xx) for q in (i, j) for rr in (r_in(q), r_out(q)) for xx in (x0, x1)]
        parts.append(trimesh.convex.convex_hull(np.array(pts)))
    return U(parts)


# saddle: X -13.5..16 (over the front screw pair), strap: X -7..7 centred on the face; 3 deg taper between
SX0, SX1, BX = -13.5, 16.0, 7.0
sad = band(TH_REAR, TH_SADDLE, SX0, SX1, lambda q: ENV_B_MIN[q] - 1.5, lambda q: TOP_S[q])
strap = band(TH_SADDLE - np.radians(3), TH_END, -BX, BX, lambda q: ENV_B_MIN[q] - 1.5, lambda q: TOP_B[q])
# taper from the saddle's width to the strap's over 12 deg in front of the front screws
TAPER = np.radians(12.0)
tq = [i for i, t in enumerate(ths) if TH_SADDLE - 1e-9 <= t <= TH_SADDLE + TAPER + 1e-9]
tp = []
for i, j in zip(tq[:-1], tq[1:]):
    pts = []
    for q in (i, j):
        u = (ths[q] - TH_SADDLE) / TAPER; x0 = SX0 + (-BX - SX0) * u; x1 = SX1 + (BX - SX1) * u
        top = TOP_S[q] + (TOP_B[q] - TOP_S[q]) * u
        pts += [polar_pt(ths[q], rr, xx) for rr in (ENV_B_MIN[q] - 1.5, top) for xx in (x0, x1)]
    tp.append(trimesh.convex.convex_hull(np.array(pts)))
taper = U(tp)

# ---- lamp pod on the forehead: 20 mm LED star + 20 mm optic, driver behind, pointing straight ahead (-Y) ----
POD_Z, POD_D, POD_FRONT = 40.0, 27.0, -155.0
LENS_D, LENS_L, STAR_L, CAV_D, CAV_L = 20.4, 12.5, 2.0, 16.0, 7.0
pod = ycyl(POD_D, POD_FRONT, -108.0, 0.0, POD_Z)
# fairing from the strap end down onto the pod top, so the two read as one piece
te = len(ths) - 1
fair = trimesh.convex.convex_hull(np.array(
    [polar_pt(ths[te], TOP_B[te], x) for x in (-BX, BX)] +
    [polar_pt(ths[te], ENV_B_MIN[te] - 1.5, x) for x in (-BX, BX)] +
    [[x, y, POD_Z + POD_D / 2 - 0.8] for x in (-BX, BX) for y in (-150.0, -118.0)]))

mount = U([sad, strap, taper, pod, fair])

# ---- tongue into the well: the crown bulges ~3 mm above the header's top in the middle, so the saddle reaches down to it ----
HDR_L, HDR_W, HDR_H, TAIL_H = 50.8, 5.08, 8.5, 3.0                    # standard 2x20 female header, 2.54 pitch, fitted upside down
HDR_TOP = BODY_TOP + HDR_H                                            # sits on the ribbon plug's body, fully on the pins
tongue = bx(CX - 3.0, CX + 3.0, GYC - 26.0, GYC + 26.0, HDR_TOP + 0.3, HDR_TOP + 4.0)
mount = U([mount, tongue])

# ---- skull and insert side: exact conformal underside with 0.3 mm radial clearance ----
Sscale = trimesh.transformations.scale_matrix(1.0 + 0.3 / 88.4, SC)
body = U([shell, insert]); grown = body.copy(); grown.apply_transform(Sscale)
mount = D(mount, U([body, grown, bx(CX - 3.4, CX + 3.4, GYC - 26.3, GYC + 26.3, 60.0, HDR_TOP + 0.3)]))   # the well stays clear below the tongue
mount = max(mount.split(only_watertight=False), key=lambda b: b.volume)     # drop anything that fell inside the wall
# fill the 0.2 mm gaps round the crown insert (slot side walls and ends) so nothing hangs down into them:
# the insert's top is convex, so its hull stretched 4 % across and 1 % along covers the gaps up to its own top
hv = insert.vertices.copy(); ic = insert.bounds.mean(0)
hv[:, 0] = ic[0] + (hv[:, 0] - ic[0]) * 1.04; hv[:, 1] = ic[1] + (hv[:, 1] - ic[1]) * 1.01
hv = SC + (hv - SC) * (1.0 + 0.3 / 88.4)                            # and 0.3 mm up, like the rest of the underside
mount = D(mount, D(trimesh.convex.convex_hull(hv), tongue))       # the hull covers the well too: only the tongue goes in
mount = max(mount.split(only_watertight=False), key=lambda b: b.volume)

# ---- cuts: header tails, wire channel, screw bores, pod bores ----
cuts = [bx(CX - 2.0, CX + 2.0, GYC - 25.9, GYC + 25.9, HDR_TOP - 0.5, HDR_TOP + TAIL_H + 1.2),   # solder-tail cavity (tails up)
        bx(CX - 2.0, CX + 2.0, GYC - 30.0, GYC - 24.0, 84.0, HDR_TOP + TAIL_H + 1.2)]            # tails cavity out to the wire channel
# wire channel on the underside, 4 wide x 2.5 deep, from the front of the header to the pod
TH_CH0 = np.arctan2(-(GYC - 28.0 - SC[1]), 88.0 - SC[2])
cuts.append(band(TH_CH0, TH_END, -2.0, 2.0, lambda q: ENV_B_MIN[q] - 1.0, lambda q: ENV_B[q] + 0.3 + 2.5))
p_end = polar_pt(ths[te], ENV_B[te] + 1.5, 0.0); p_cav = np.array([0.0, POD_FRONT + LENS_L + STAR_L + CAV_L / 2, POD_Z])
seg = cylinder(radius=1.9, segment=[p_end, p_cav], sections=24); cuts.append(seg)                # channel into the pod's driver cavity
for x, y in SCREWS[:2]:                                                                           # front screw pair, M3x20 socket heads
    cuts += [zcyl_at(3.4, 60.0, 110.0, x, y), zcyl_at(8.0, 60.0, 83.0, x, y)]   # bore + leave the insert's (now unused) countersink empty
Y_LENS = POD_FRONT + LENS_L + STAR_L
cuts += [ycyl(LENS_D, POD_FRONT - 1.0, Y_LENS, 0.0, POD_Z),                                      # optic + star, loaded from the front
         ycyl(CAV_D, Y_LENS - 0.1, Y_LENS + CAV_L, 0.0, POD_Z)]                                  # driver board cavity; star seats on the step
mount = D(mount, U(cuts))
mount = max(mount.split(only_watertight=False), key=lambda b: b.volume)
print(f"flashlight mount: watertight={mount.is_watertight} bodies={mount.body_count} vol={mount.volume / 1000:.2f} cm3 bounds {np.round(mount.bounds, 1).tolist()}")

# ---- GPIO cover: flush plug with side skirts either side of the pins, crush ribs, pry notch at the rear end ----
WL, WW = 52.2, 6.4                                                    # well in the insert
PIN_TIP = BODY_TOP + 6.0
cov = bx(CX - 3.1, CX + 3.1, GYC - 25.95, GYC + 25.95, BODY_TOP + 0.6, 100.0)
for sx in (-1, 1):                                                    # 0.3 mm crush ribs, two per long side
    for yy in (GYC - 14, GYC + 14):
        cov = U([cov, bx(min(CX + sx * 2.9, CX + sx * 3.3), max(CX + sx * 2.9, CX + sx * 3.3), yy - 0.5, yy + 0.5, BODY_TOP + 1.5, 86.0)])
ys_top = np.linspace(GYC - 27, GYC + 27, 109)
def ins_top(y):
    s1 = insert.section(plane_origin=[CX - 4.2, 0, 0], plane_normal=[1, 0, 0]).vertices
    s2 = insert.section(plane_origin=[CX + 4.2, 0, 0], plane_normal=[1, 0, 0]).vertices
    f = lambda v: np.array([v[np.abs(v[:, 1] - yy) < 0.8][:, 2].max() for yy in y])
    return (f(s1) + f(s2)) / 2
ZT = ins_top(ys_top)
above = []
for i in range(len(ys_top) - 1):
    y0, y1, z0, z1 = ys_top[i], ys_top[i + 1], ZT[i], ZT[i + 1]
    above.append(trimesh.convex.convex_hull(np.array([[x, y, z] for x in (CX - 4, CX + 4) for y, z in ((y0, z0), (y1, z1))] +
                                                     [[x, y, 150.0] for x in (CX - 4, CX + 4) for y in (y0, y1)])))
cov = D(cov, U(above))
cov = D(cov, bx(CX - 2.0, CX + 2.0, GYC - 24.8, GYC + 24.8, 0, PIN_TIP + 0.5))        # pocket over the pins (rows at +/-1.27, 0.64 square: +/-1.59)
notch = trimesh.convex.convex_hull(np.array(
    [[x, y, z] for x in (CX - 1.8, CX + 1.8) for y, z in ((GYC + 26.5, ZT[-1] + 1.0), (GYC + 26.5, ZT[-1] - 2.0), (GYC + 22.5, ZT[-1] + 1.0))]))
cov = D(cov, notch)                                                   # pry notch at the rear end: fingernail or small screwdriver
cov = max(cov.split(only_watertight=False), key=lambda b: b.volume)
print(f"gpio cover: watertight={cov.is_watertight} bodies={cov.body_count} vol={cov.volume / 1000:.3f} cm3 bounds {np.round(cov.bounds, 1).tolist()}")
print(f"   header top {HDR_TOP:.1f}, pin tips {PIN_TIP:.1f}, insert top over the well {ZT.min():.1f}..{ZT.max():.1f}")

# header mock for fit checks (body only)
hdr = bx(CX - HDR_W / 2, CX + HDR_W / 2, GYC - HDR_L / 2, GYC + HDR_L / 2, BODY_TOP, HDR_TOP)
for m, fn in ((mount, "gpio_flashlight.stl"), (cov, "gpio_cover.stl"), (hdr, "mocks/gpio_header.stl")):
    m.export(os.path.join(OUT, fn))
json.dump({"pod": [0.0, POD_FRONT, POD_Z], "pod_d": POD_D, "lens_d": LENS_D}, open("flashlight_meta.json", "w"))
