"""Route every cable through the free space of the head and check it is viable.
Grid: 2 mm voxels from occ_all.npz. Each cable gets a clearance (its radius + 1 mm), is
routed with Dijkstra on the 26-connected free grid, string-pulled, then added to the
grid as an obstacle so later cables cannot overlap it."""
import numpy as np, json, trimesh
from scipy import ndimage, sparse
from scipy.sparse.csgraph import dijkstra
from trimesh.creation import box
from parts import OUT

d = np.load("occ_all.npz")
OCC, INSIDE, xs, ys, zs, st = d["occ"].copy(), d["inside"], d["xs"], d["ys"], d["zs"], float(d["step"])
shape = OCC.shape


def idx(p):
    return tuple(int(round((p[i] - (xs, ys, zs)[i][0]) / st)) for i in range(3))


def pos(ijk):
    return np.array([xs[ijk[0]], ys[ijk[1]], zs[ijk[2]]])


def mark_box(grid, x0, x1, y0, y1, z0, z1):
    i0, j0, k0 = idx((x0, y0, z0)); i1, j1, k1 = idx((x1, y1, z1))
    grid[max(i0, 0):i1 + 1, max(j0, 0):j1 + 1, max(k0, 0):k1 + 1] = True


NEW = {}   # TTL interface, I2S amp and GPIO splitter are now mock STLs in parts.py
# GPIO ribbon, already routed and checked
RIB = [(-15.4, 35.4, -60.9, -49.0, -1.7, -0.4), (-25.5, 25.5, -60.9, -59.6, -1.7, 58.0),        # leaves the IDC on top of the splitter
       (-25.5, 25.5, -60.9, -46.5, 58.0, 59.3), (0.6, 1.9, -74.5, -18.5, 59.3, 70.9)]
for b in RIB: mark_box(OCC, *b)

# ---- the cables: name, from, to, diameter (mm), kind ----
CABLES = [
    ("Pack leads (XT30 + balance)", (0, 17, 24), (0, -20, 58), 6.0, "power"),
    ("Slip-ring bundle to deck", (0, 20, -50), (0, 16, 50), 6.0, "power"),
    ("Pi buck -> Pi 5 USB-C", (-22, -6, 58), (31.3, 3.0, -29), 4.0, "power"),
    ("Servo buck -> servo R", (22, -6, 58), (18, -4, -2), 3.0, "power"),
    ("USB: Pi 5 -> TTL interface", (-47, -40, -24), (-60, -8, -30), 4.0, "data"),
    ("DYNAMIXEL: interface -> servo L", (-60, -6, -28), (-18, -8, 0), 3.0, "data"),
    ("DYNAMIXEL: servo L -> servo R", (-18, -9, -4), (18, -9, -4), 3.0, "data"),
    ("Camera L ribbon -> CAM/DISP 0", (-20, -103.6, 0), (-2.5, 3.0, -28), 4.0, "ribbon"),
    ("Camera R ribbon -> CAM/DISP 1", (20, -103.6, 0), (-15.5, 3.0, -28), 4.0, "ribbon"),
    ("Display L -> micro-HDMI 1", (-61, -79, -20), (3.3, 3.0, -29), 6.0, "video"),
    ("Display R -> micro-HDMI 0", (61, -79, -20), (16.7, 3.0, -29), 6.0, "video"),
    ("Speaker L -> amp", (-26, -88, -35), (-5, -82, -32), 2.5, "audio"),
    ("Speaker R -> amp", (26, -88, -35), (5, -82, -32), 2.5, "audio"),
    ("Amp (I2S) -> GPIO splitter", (0, -72, -32), (-12, -60, -16), 3.0, "audio"),
]

OFFS = np.array([(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)])


def free_grid(radius):
    it = int(np.ceil((radius + 2.0) / st))          # 2 mm margin: smoothing can shave corners the grid can't see
    blocked = ndimage.binary_dilation(OCC, iterations=it) | ~INSIDE
    return ~blocked


def snap(free, p, maxr=12):
    ijk = np.array(idx(p))
    if free[tuple(ijk)]: return ijk, 0.0
    best = None
    for r in range(1, maxr + 1):
        rng = range(-r, r + 1)
        for a in rng:
            for b in rng:
                for c in rng:
                    q = ijk + (a, b, c)
                    if np.any(q < 0) or np.any(q >= shape): continue
                    if free[tuple(q)]:
                        dd = np.linalg.norm((a, b, c)) * st
                        if best is None or dd < best[1]: best = (q, dd)
        if best: return best
    return None, None


def route(free, s, e):
    ids = -np.ones(shape, np.int64); fi = np.argwhere(free); ids[tuple(fi.T)] = np.arange(len(fi))
    rows, cols, w = [], [], []
    for o in OFFS[:13]:                                    # half the neighbours, graph is undirected
        q = fi + o; ok = np.all((q >= 0) & (q < shape), 1)
        a = ids[tuple(fi[ok].T)]; b = ids[tuple(q[ok].T)]; m = b >= 0
        rows.append(a[m]); cols.append(b[m]); w.append(np.full(m.sum(), np.linalg.norm(o) * st))
    G = sparse.coo_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), shape=(len(fi), len(fi))).tocsr()
    si, ei = ids[tuple(s)], ids[tuple(e)]
    dist, pred = dijkstra(G, directed=False, indices=si, return_predecessors=True)
    if not np.isfinite(dist[ei]): return None
    path = [ei]
    while path[-1] != si: path.append(pred[path[-1]])
    return fi[path[::-1]]


def los(free, a, b):
    n = int(np.ceil(np.linalg.norm(b - a) / (st * 0.5))) + 1
    for t in np.linspace(0, 1, n):
        q = np.round(a + (b - a) * t).astype(int)
        if not free[tuple(q)]: return False
    return True


def pull(free, path):
    out = [path[0]]; i = 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not los(free, path[i], path[j]): j -= 1
        out.append(path[j]); i = j
    return np.array(out)


def clearance(pts, radius):
    """Smallest gap from the cable surface to any part, sampled along the polyline."""
    dt = ndimage.distance_transform_edt(~OCC) * st
    g = []
    for a, b in zip(pts[:-1], pts[1:]):
        for t in np.linspace(0, 1, max(2, int(np.linalg.norm(b - a) / 1.0))):
            q = np.round(a + (b - a) * t).astype(int); g.append(dt[tuple(q)])
    return min(g) - radius


def std_len(mm):
    for L in (50, 75, 100, 150, 200, 250, 300, 400, 500):
        if mm <= L: return L
    return int(np.ceil(mm / 100) * 100)


results = []
for name, a, b, dia, kind in CABLES:
    free = free_grid(dia / 2)
    s, sd = snap(free, a); e, ed = snap(free, b)
    if s is None or e is None:
        results.append(dict(name=name, kind=kind, ok=False, why="endpoint boxed in")); print(f"{name:34s} ENDPOINT BOXED IN"); continue
    p = route(free, s, e)
    if p is None:
        results.append(dict(name=name, kind=kind, ok=False, why="no path")); print(f"{name:34s} NO PATH"); continue
    pp = pull(free, p)
    pts = np.vstack([np.array(a, float), [pos(q) for q in pp], np.array(b, float)])
    L = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
    cl = clearance(pp, dia / 2)
    need = L * 1.15 + 30                                      # 15 % slack for bends plus 30 mm at the connectors
    results.append(dict(name=name, kind=kind, ok=True, dia=dia, length=round(L), need=round(need), buy=std_len(need),
                        clear=round(float(cl), 1), snap=round(max(sd, ed), 1), pts=np.round(pts, 1).tolist()))
    print(f"{name:34s} ok  route {L:6.0f} mm  -> buy {std_len(need):4d} mm   min gap to parts {cl:4.1f} mm  (endpoint snap {max(sd, ed):.1f})")
    # the cable now occupies space; later cables route round it
    for q0, q1 in zip(pp[:-1], pp[1:]):
        for t in np.linspace(0, 1, max(2, int(np.linalg.norm(q1 - q0) * 2))):
            q = np.round(q0 + (q1 - q0) * t).astype(int)
            r = int(np.ceil(dia / 2 / st))
            OCC[max(q[0] - r, 0):q[0] + r + 1, max(q[1] - r, 0):q[1] + r + 1, max(q[2] - r, 0):q[2] + r + 1] = True
# ---- exact validation: each cable as a solid tube, intersected with every part and every other cable ----
import manifold3d as mf
from parts import load_all, to_mf
P = load_all(); PM = {k: to_mf(v) for k, v in P.items()}
def tube(pts, r, trim=6.0):
    pts = np.asarray(pts, float)
    # trim the last few mm at each end: that is where the cable plugs into its part
    def cut(p, from_start):
        seq = p if from_start else p[::-1]; left = trim; out = [seq[0]]
        for a_, b_ in zip(seq[:-1], seq[1:]):
            L_ = np.linalg.norm(b_ - a_)
            if left >= L_: left -= L_; out = [b_]; continue
            out = [a_ + (b_ - a_) * (left / L_)] + list(seq[list(map(tuple, seq)).index(tuple(b_)):]); break
        return np.array(out) if from_start else np.array(out)[::-1]
    pts = cut(cut(pts, True), False)
    parts_ = []
    for a_, b_ in zip(pts[:-1], pts[1:]):
        L_ = np.linalg.norm(b_ - a_)
        if L_ < 1e-3: continue
        c = mf.Manifold.cylinder(L_, r, r, 20)
        dvec = (b_ - a_) / L_; z = np.array([0, 0, 1.0]); ax = np.cross(z, dvec); s_ = np.linalg.norm(ax)
        R = np.eye(3) if s_ < 1e-9 else trimesh.transformations.rotation_matrix(np.arctan2(s_, dvec @ z), ax / s_)[:3, :3]
        if s_ < 1e-9 and dvec[2] < 0: R = np.diag([1, -1, -1])
        M = np.c_[R, a_]; parts_.append(c.transform(M.tolist()))
    for p_ in pts[1:-1]: parts_.append(mf.Manifold.sphere(r, 20).translate(p_.tolist()))
    return mf.Manifold.batch_boolean(parts_, mf.OpType.Add) if parts_ else None
TUBES = {}
for r_ in results:
    if r_["ok"]: TUBES[r_["name"]] = tube(r_["pts"], r_["dia"] / 2)
for i, b_ in enumerate(RIB):
    TUBES[f"GPIO ribbon leg {i + 1}"] = mf.Manifold.cube([b_[1] - b_[0], b_[3] - b_[2], b_[5] - b_[4]]).translate([b_[0], b_[2], b_[4]])
print()
print("exact check (cable ends trimmed 6 mm where they plug in):")
names = list(TUBES)
for r_ in results:
    if not r_["ok"]: continue
    T = TUBES[r_["name"]]; worst = []; gap = 99.0
    for k, m in PM.items():
        v = (T ^ m).volume()
        if v > 0.01: worst.append((k, round(v, 1)))
        else: gap = min(gap, T.min_gap(m, 10))
    for n2 in names:
        if n2 == r_["name"]: continue
        v = (T ^ TUBES[n2]).volume()
        if v > 0.01: worst.append((n2, round(v, 1)))
    r_["exact_gap"] = round(float(gap), 2); r_["hits"] = worst
    print(f"  {r_['name']:34s} gap {gap:5.2f} mm  " + ("OVERLAPS " + str(worst) if worst else "clear"))
json.dump({"cables": results, "new_parts": NEW, "ribbon": RIB}, open("cables.json", "w"), indent=1)
print(f"\n{sum(r['ok'] for r in results)}/{len(results)} cables routed")
