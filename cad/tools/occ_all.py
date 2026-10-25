"""Occupancy of the current assembly on a 2 mm grid, for cable routing.
Occupied = inside any fixed part, or inside the jaw/hubs anywhere in their 0..35 deg sweep.
Solids are voxelised by casting one +Z ray per grid column and filling between entry/exit hits
(far faster than point-in-mesh tests on the merged skull)."""
import numpy as np, time, trimesh
from parts import *
t0 = time.time()
P = load_all()
sh = P["shell"]
step = 2.0
mn = sh.bounds[0] - 2; mx = sh.bounds[1] + 2
xs = np.arange(mn[0], mx[0], step) + step / 2; ys = np.arange(mn[1], mx[1], step) + step / 2; zs = np.arange(mn[2], mx[2], step) + step / 2
shape = (len(xs), len(ys), len(zs))
X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
G = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
hull = sh.convex_hull
inside = np.all(G @ hull.face_normals.T - (hull.face_normals * hull.triangles[:, 0]).sum(1) < 0.0, axis=1).reshape(shape)
print("grid", shape, flush=True)


def column_fill(m):
    """Boolean grid of voxel centres inside mesh m, by ray parity along +Z per column."""
    out = np.zeros(shape, bool)
    lo, hi = m.bounds
    ii = np.where((xs >= lo[0] - step) & (xs <= hi[0] + step))[0]
    jj = np.where((ys >= lo[1] - step) & (ys <= hi[1] + step))[0]
    if not len(ii) or not len(jj): return out
    I, J = np.meshgrid(ii, jj, indexing='ij'); I = I.ravel(); J = J.ravel()
    # tiny offsets keep rays off shared edges/vertices
    O = np.c_[xs[I] + 1.37e-3, ys[J] + 2.11e-3, np.full(len(I), lo[2] - 5.0)]
    ray = trimesh.ray.ray_triangle.RayMeshIntersector(m)
    loc, ridx, _ = ray.intersects_location(O, np.tile([0, 0, 1.0], (len(O), 1)), multiple_hits=True)
    order = np.lexsort((loc[:, 2], ridx))
    loc, ridx = loc[order], ridx[order]
    starts = np.searchsorted(ridx, np.arange(len(O)))
    ends = np.searchsorted(ridx, np.arange(len(O)), side='right')
    for r in range(len(O)):
        zz = np.unique(np.round(loc[starts[r]:ends[r], 2], 4))
        for a, b in zip(zz[0::2], zz[1::2]):
            k = (zs > a) & (zs < b)
            out[I[r], J[r], k] = True
    return out


occ = np.zeros(shape, bool)
ROUTE_THROUGH = {"gpio_plug"}          # an endpoint, not an obstacle
for k, m in P.items():
    if k in MOVING or k in ROUTE_THROUGH: continue
    occ |= column_fill(m)
    print(f" - {k:12s} {time.time() - t0:5.0f}s", flush=True)
cand = np.where(inside.ravel())[0]
for k in MOVING:
    v = P[k].voxelized(1.0).fill(); Mv = v.matrix; T = np.linalg.inv(v.transform)
    flat = occ.ravel()
    for a in np.arange(-3, 36.1, 1.5):
        R = trimesh.transformations.rotation_matrix(np.radians(-a), [1, 0, 0])
        q = np.round(trimesh.transform_points(G[cand], T @ R)).astype(int)
        ok = np.all((q >= 0) & (q < np.array(Mv.shape)), 1)
        hit = np.zeros(len(cand), bool); hit[ok] = Mv[q[ok, 0], q[ok, 1], q[ok, 2]]
        flat[cand[hit]] = True
    occ = flat.reshape(shape)
    print(f" - sweep {k} {time.time() - t0:5.0f}s", flush=True)
# sanity: compare the skull's voxel volume with its true volume
sk = column_fill(sh).sum() * step ** 3 / 1000
print(f"skull voxel volume {sk:.0f} cm3 vs mesh {sh.volume / 1000:.0f} cm3", flush=True)
np.savez_compressed("occ_all_pb.npz" if POWER == "powerbank" else "occ_all.npz",occ=occ, inside=inside, xs=xs, ys=ys, zs=zs, step=step)
print("done", f"{time.time() - t0:.0f}s", flush=True)
