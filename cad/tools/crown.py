import numpy as np, trimesh, json, os
from trimesh.creation import box, cylinder, icosphere
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U = lambda ms: trimesh.boolean.union(ms, engine='manifold')
D = lambda a, b: trimesh.boolean.difference([a, b], engine='manifold')
I = lambda a, b: trimesh.boolean.intersection([a, b], engine='manifold')


def bx(x0, x1, y0, y1, z0, z1):
    b = box(extents=[x1 - x0, y1 - y0, z1 - z0]); b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); return b


def zcyl(d, z0, z1, x=0.0, y=0.0, sec=48):
    c = cylinder(radius=d / 2, height=z1 - z0, sections=sec); c.apply_translation([x, y, (z0 + z1) / 2]); return c


def zcone(d0, d1, z0, z1, x, y, sec=48):
    """Frustum along +Z, dia d0 at z0 to d1 at z1."""
    th = np.linspace(0, 2 * np.pi, sec, endpoint=False)
    v = np.vstack([np.c_[x + d0 / 2 * np.cos(th), y + d0 / 2 * np.sin(th), np.full(sec, z0)],
                   np.c_[x + d1 / 2 * np.cos(th), y + d1 / 2 * np.sin(th), np.full(sec, z1)],
                   [[x, y, z0], [x, y, z1]]])
    f = []
    for i in range(sec):
        j = (i + 1) % sec
        f += [[i, j, sec + j], [i, sec + j, sec + i], [2 * sec, j, i], [2 * sec + 1, sec + i, sec + j]]
    m = trimesh.Trimesh(v, f, process=True)
    if m.volume < 0: m.invert()
    return m


def ball(c, r, sub=6):
    s = icosphere(subdivisions=sub, radius=r); s.apply_translation(c); return s


skull = trimesh.load(os.path.join(OUT, "GeneTop_v4_camslots.stl")); skull.apply_translation([-64.8, -61.4, -35.0])
shell = max(skull.split(only_watertight=False), key=lambda b: b.volume)
inner = json.load(open("sphere_inner.json")); IC, IR = np.array(inner["c"]), inner["r"]


def zin(x, y):
    """Inner dome surface Z (fitted sphere, rms 0.06 mm)."""
    return IC[2] + np.sqrt(IR ** 2 - (x - IC[0]) ** 2 - (y - IC[1]) ** 2)


# ---- slot outline (measured): vertical walls at X -12.26 / 14.76, shallow arced ends ----
XL, XR, CX = -12.26, 14.76, 1.25


def end_y(x, front):
    w = (XR - XL) / 2; u = (x - CX) / w
    return (-103.75 - 1.45 * (1 - u * u)) if front else (8.25 + 1.45 * (1 - u * u))


def outline(inset):
    xs = np.linspace(XL + inset, XR - inset, 41)
    return np.array([(x, end_y(x, True) + inset) for x in xs] + [(x, end_y(x, False) - inset) for x in xs[::-1]])


def prism(poly, z0, z1):
    """Vertical prism over a convex outline (the slot is convex)."""
    pts = np.vstack([np.c_[poly, np.full(len(poly), z0)], np.c_[poly, np.full(len(poly), z1)]])
    return trimesh.convex.convex_hull(pts)


# ---- flush top: heightfield built from the real rim heights along both walls ----
ray = trimesh.ray.ray_triangle.RayMeshIntersector(shell)
YS = np.arange(-110, 16.01, 1.0)


def rim(x):
    O = np.c_[np.full(len(YS), x), YS, np.full(len(YS), 160.0)]
    loc, idx, _ = ray.intersects_location(O, np.tile([0, 0, -1.0], (len(O), 1)), multiple_hits=False)
    z = np.full(len(YS), np.nan); z[idx] = loc[:, 2]; return z


XA, XB = XL - 0.25, XR + 0.25
zL = rim(XA); zR = rim(XB)
K = 1 / (2 * 88.4)          # curvature across the slot (outer dome radius)


def ztop(x, y):
    a = np.interp(y, YS, zL); b = np.interp(y, YS, zR); t = (x - XA) / (XB - XA)
    return a + (b - a) * t + K * (x - XA) * (XB - x)


def heightfield(fz, x0, x1, y0, y1, zb, n=(40, 160)):
    gx = np.linspace(x0, x1, n[0]); gy = np.linspace(y0, y1, n[1]); X, Y = np.meshgrid(gx, gy, indexing='ij'); Z = fz(X, Y)
    nx, ny = X.shape; idx = lambda i, j: i * ny + j
    V = np.vstack([np.c_[X.ravel(), Y.ravel(), Z.ravel()], np.c_[X.ravel(), Y.ravel(), np.full(X.size, zb)]]); off = X.size; F = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            F += [[a, b, c], [a, c, d], [off + a, off + c, off + b], [off + a, off + d, off + c]]
    for i in range(nx - 1):
        for j in (0, ny - 1):
            a, b = idx(i, j), idx(i + 1, j)
            F += [[a, off + a, off + b], [a, off + b, b]] if j == 0 else [[a, b, off + b], [a, off + b, off + a]]
    for j in range(ny - 1):
        for i in (0, nx - 1):
            a, b = idx(i, j), idx(i, j + 1)
            F += [[a, b, off + b], [a, off + b, off + a]] if i == 0 else [[a, off + a, off + b], [a, off + b, b]]
    m = trimesh.Trimesh(V, F, process=True)
    if m.volume < 0: m.invert()
    return m


below_top = heightfield(ztop, XL - 3.0, XR + 3.0, -108, 13, 40.0)

# ---- skull v5: 4 mm ledge round the underside of the slot + 4 screw bosses ----
LEDGE_W, LEDGE_T, BOSS_D, BOSS_H = 4.0, 3.0, 7.0, 6.0
band = D(prism(outline(-0.3), 40, 100), prism(outline(LEDGE_W), 39, 101))
ledge = I(band, D(ball(IC, IR + LEDGE_T), ball(IC, IR)))
SCREWS = [(XL + LEDGE_W / 2, -90.0), (XR - LEDGE_W / 2, -90.0), (XL + LEDGE_W / 2, -6.0), (XR - LEDGE_W / 2, -6.0)]
bosses = []
for x, y in SCREWS:
    z = zin(x, y)
    bosses.append(zcyl(BOSS_D, z - BOSS_H, z + 0.5, x, y))        # hangs below the ledge, merges into the slot wall
skull5 = U(skull.split(only_watertight=False) + [ledge] + bosses)     # shell, brow and barrels fused into one solid
skull5 = D(skull5, U([zcyl(2.5, zin(x, y) - BOSS_H + 0.8, zin(x, y) + LEDGE_T + 0.5, x, y) for x, y in SCREWS]))   # M3 self-tap pilots
skull5 = max(skull5.split(only_watertight=False), key=lambda b: b.volume)   # drop zero-volume slivers from the merge
print(f"skull v5: watertight={skull5.is_watertight} bodies={skull5.body_count} vol={skull5.volume / 1000:.1f} cm3 (v4 {skull.volume / 1000:.1f})")

# ---- crown insert: drops in from above, sits on the ledge, flush on top ----
CLR = 0.20
upper = D(I(prism(outline(CLR), 40, 100), below_top), ball(IC, IR + LEDGE_T))
lower = D(I(prism(outline(LEDGE_W + CLR), 40, 100), below_top), ball(IC, IR))
insert = U([upper, lower])
# GPIO riser: the male IDC plug of a 40-pin male-to-female GPIO extension ribbon, pins up, in a recessed well
IDC_L, IDC_W, IDC_H, PIN_H = 56.0, 8.9, 7.6, 6.0      # assumed plug body and pin length - check yours
GY0, GY1 = -74.5, -18.5; GYC = (GY0 + GY1) / 2
zs = [ztop(CX, y) for y in np.linspace(GY0, GY1, 60)]
BODY_TOP = min(zs) - 1.0 - PIN_H                     # pin tips 1 mm below the lowest surface over the well
BODY_BOT = BODY_TOP - IDC_H
PW, PL = IDC_W + 0.6, IDC_L + 0.6
sleeve = bx(CX - PW / 2 - 1.6, CX + PW / 2 + 1.6, GYC - PL / 2 - 1.6, GYC + PL / 2 + 1.6, BODY_BOT - 1.0, zin(CX, GYC) + 1.0)
insert = U([insert, sleeve])
cuts = [bx(CX - PW / 2, CX + PW / 2, GYC - PL / 2, GYC + PL / 2, BODY_BOT - 2, BODY_TOP),    # plug pocket, open below, stops on the body
        bx(CX - 3.2, CX + 3.2, GYC - 26.1, GYC + 26.1, BODY_TOP - 0.5, 110)]                   # pin well, open above (fits a 2x20 female header)
for x, y in SCREWS:
    zt = ztop(x, y)
    cuts += [zcyl(3.4, 40, 110, x, y), zcone(3.4, 7.4, zt - 2.0, zt + 0.01, x, y)]          # M3 countersunk
insert = D(insert, U(cuts))
print(f"insert: watertight={insert.is_watertight} bodies={insert.body_count} vol={insert.volume / 1000:.2f} cm3 bounds {np.round(insert.bounds, 1).tolist()}")
print(f"   IDC body Z {BODY_BOT:.1f}..{BODY_TOP:.1f}, pin tips {BODY_TOP + PIN_H:.1f}; surface over the well {min(zs):.1f}..{max(zs):.1f}")

# ---- bridge handle (optional): two feet on the insert, grip bar over the GPIO well ----
GRIP_D, GRIP_Z = 16.0, 124.0
posts = [bx(XL - 1.2, XR + 1.2, y - 9, y + 9, 60, GRIP_Z) for y in (-90.0, -6.0)]
grip = cylinder(radius=GRIP_D / 2, height=102.0, sections=64)
grip.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])); grip.apply_translation([CX, -48.0, GRIP_Z])
handle = D(U(posts + [grip]), below_top)             # feet follow the insert's top exactly
hc = []
for x, y in SCREWS:
    zt = ztop(x, y)
    hc += [zcyl(3.4, zt - 1, zt + 5.5, x, y), zcyl(6.6, zt + 5.0, GRIP_Z + 20, x, y)]   # 5 mm of foot under each screw head, driver bore above
handle = D(handle, U(hc))
print(f"handle: watertight={handle.is_watertight} bodies={handle.body_count} vol={handle.volume / 1000:.2f} cm3 bounds {np.round(handle.bounds, 1).tolist()}")
print(f"   grip underside Z {GRIP_Z - GRIP_D / 2:.1f}; highest crown surface {max(ztop(CX, y) for y in np.linspace(-100, 5, 200)):.1f}")
for x, y in SCREWS:
    zt = ztop(x, y); zi = zin(x, y)
    print(f"   screw ({x:6.2f},{y:6.1f}): insert top {zt:.1f}, ledge top {zi + LEDGE_T:.1f}, insert over ledge {zt - (zi + LEDGE_T):.1f} mm, thread engagement {LEDGE_T + BOSS_H - 0.8:.1f} mm")

for m, fn in ((skull5, "GeneTop_v5_crownbay.stl"), (insert, "GeneHead_crown_insert.stl"), (handle, "GeneHead_bridge_handle.stl")):
    e = m.copy(); e.apply_translation([64.8, 61.4, 35.0]) if fn.startswith("GeneTop") else None; e.export(os.path.join(OUT, fn))
json.dump({"SCREWS": SCREWS, "BODY_TOP": BODY_TOP, "BODY_BOT": BODY_BOT, "GYC": GYC, "CX": CX, "IDC": [IDC_L, IDC_W, IDC_H, PIN_H]}, open("crown_meta.json", "w"))
