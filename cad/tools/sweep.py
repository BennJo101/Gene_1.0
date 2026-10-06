import numpy as np, json
from parts import *
P=load_all(); M={k:to_mf(v) for k,v in P.items()}
static=[k for k in P if k not in MOVING]
# near-field statics only (bbox of the jaw's full sweep, padded)
angles=np.arange(0,60.01,0.5)
res={k:[] for k in static}; hubres={k:[] for k in static}
for a in angles:
    R=trimesh.transformations.rotation_matrix(np.radians(a),[1,0,0])
    mv={k:M[k].transform(R[:3,:].tolist()) for k in MOVING}
    for s in static:
        best_ov=0; best_gap=9
        for k in MOVING:
            if k.startswith("hub") and s.startswith("servo"): continue   # hub is bolted to the horn and turns with it
            if k.startswith("hub") and s.startswith("bracket") and False: pass
            ov=(mv[k]^M[s]).volume()
            if ov>1e-3: best_ov=max(best_ov,ov); best_gap=0
            else: best_gap=min(best_gap,mv[k].min_gap(M[s],9))
        res[s].append((round(best_ov,3),round(best_gap,3)))
out={"angles":angles.tolist(),"pairs":{s:v for s,v in res.items() if min(g for _,g in v)<9}}
json.dump(out,open("sweep.json","w"))
for s,v in out["pairs"].items():
    first=next((angles[i] for i,(o,_) in enumerate(v) if o>0),None)
    mg=min(g for o,g in v[:61] if o==0) if any(o==0 for o,_ in v[:61]) else 0
    print(f"{s:11s} min gap 0-30: {min(g for _,g in v[:61]):.3f}  0-55: {min(g for _,g in v[:111]):.3f}  first overlap at {first}  max ov@60 {v[-1][0]}")
