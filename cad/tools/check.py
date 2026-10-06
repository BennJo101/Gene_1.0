import numpy as np, json, itertools, trimesh, time
from parts import *
t0=time.time()
P=load_all()
M={k:to_mf(v) for k,v in P.items()}
bad=[k for k,m in M.items() if m.status()!=mf.Error.NoError or m.is_empty()]
print("non-manifold:",bad)
for k,v in P.items(): print(f"  {k:12s} vol {v.volume/1000:7.2f} cm3  wt={v.is_watertight}")
names=list(P)
def bbox_near(a,b,pad):
    A,B=P[a].bounds,P[b].bounds
    return np.all(A[0]-pad<=B[1]) and np.all(B[0]-pad<=A[1])
SEARCH=3.0
rows=[]
for a,b in itertools.combinations(names,2):
    if not bbox_near(a,b,SEARCH): continue
    ma,mb=M[a],M[b]
    inter=ma^mb
    vol=inter.volume()
    if vol>1e-3:
        tm=inter.to_mesh(); im=trimesh.Trimesh(tm.vert_properties[:,:3],tm.tri_verts)
        thick=2*vol/im.area
        rows.append(dict(a=a,b=b,overlap=round(vol,3),depth=round(thick,3),gap=0.0,
                         where=np.round(im.bounds.mean(0),1).tolist()))
    else:
        g=ma.min_gap(mb,SEARCH)
        rows.append(dict(a=a,b=b,overlap=0.0,depth=0.0,gap=round(g,3)))
rows.sort(key=lambda r:(-r["overlap"],r["gap"]))
print(f"\nSTATIC, jaw at 0 deg  ({len(rows)} neighbouring pairs of {len(names)*(len(names)-1)//2})")
for r in rows:
    s=f"OVERLAP {r['overlap']:9.3f} mm3  ~{r['depth']:.3f} mm thick  at {r['where']}" if r["overlap"] else f"gap {r['gap']:.3f}"+(" (>=3)" if r['gap']>=SEARCH else "")
    print(f"  {r['a']:11s} x {r['b']:11s} {s}")
json.dump(rows,open("static.json","w"),indent=1)
print(f"{time.time()-t0:.0f}s")
