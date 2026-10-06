import numpy as np, json, base64, os
from parts import *
P=load_all()
def b64(m, dec=None):
    tri=np.asarray(m.vertices,np.float32)[m.faces].reshape(-1)
    return base64.b64encode(tri.tobytes()).decode()
# real servo meshes for display (checks used the solid envelope)
sL=L("XL330_M288_from_STEP.stl"); sL.apply_transform(ML)
sR=L("XL330_R_placed_MOCK.stl")
groups={
 "skull":[P["shell"]], "jaw":[P["jaw"]], "insert":[P["insert"]], "gpio":[P["gpio_plug"]], "pupil":[P["pupil_L"],P["pupil_R"]],
 "hub":[P["hub_L"],P["hub_R"]], "bracket":[P["bracket_L"],P["bracket_R"]], 
 "carrier":[P["carrier_L"],P["carrier_R"]], "retainer":[P["retainer_L"],P["retainer_R"]],
 "display":[P["display_L"],P["display_R"]], "bezel":[P["bezel_L"],P["bezel_R"]],
 "camera":[P["camera_L"],P["camera_R"]], "shelf":[P["shelf"]], "pi5":[P["pi5"]],
 "speaker":[P["speakers"]], "handle":[P["handle"]],
 "tray":[P["tray"]], "deck":[P["deck"]], "battery":[P["battery"]], "boards":[P["boards"]],
 "neck":[P["neck"]], "neckbase":[P["neck_base"]], "collar":[P["neck_collar"]], "bearings":[P["bearings"]], "slipring":[P["slip_ring"]],
 "splitter":[P["splitter"]], "ttl":[P["ttl"]], "amps":[P["amps"]]}
for k,ms in groups.items():
    m=trimesh.util.concatenate(ms)
    json.dump({"b64":b64(m)},open(f"web/{k}.json","w"))
    print(f"{k:9s} {len(m.faces):7d} tris")
# interference vs angle: overlap volume and the deepest blob (2V/A thickness), per side; blobs under 0.01 mm3 are facet noise
M={k:to_mf(v) for k,v in P.items()}
angles=sorted(set(np.round(np.r_[np.arange(0,60.5,0.5),np.arange(52,58,0.25)],2)))
curve=[]; contacts={}
for a in angles:
    R=trimesh.transformations.rotation_matrix(np.radians(a),[1,0,0])
    jr=M["jaw"].transform(R[:3,:].tolist())
    nk=[jr^M[n] for n in ("neck","neck_base","neck_collar","bearings","slip_ring")]
    nv=sum(x.volume() for x in nk)
    inter=jr^M["shell"]; ov=inter.volume()
    rec={"a":float(a),"ov":round(ov+nv,3),"L":0.0,"R":0.0,"N":0.0}
    if nv>0.01:
        nm=[trimesh.Trimesh(x.to_mesh().vert_properties[:,:3],x.to_mesh().tri_verts) for x in nk if x.volume()>0.01]
        nm=trimesh.util.concatenate(nm); rec["N"]=round(2*nv/nm.area,3)
        inter=inter+trimesh.boolean.union([],engine='manifold') if False else inter
        nmr=nm.copy(); nmr.apply_transform(np.linalg.inv(R)); contacts["n"+str(float(a))]=b64(nmr)
    if ov>1e-3:
        t=inter.to_mesh(); im=trimesh.Trimesh(t.vert_properties[:,:3],t.tri_verts)
        for bl in im.split(only_watertight=False):
            v=abs(bl.volume)
            if v<0.01: continue
            d=round(2*v/bl.area,3); side="L" if bl.bounds.mean(0)[0]<0 else "R"
            rec[side]=max(rec[side],d)
        if rec["L"] or rec["R"]:
            im.apply_transform(np.linalg.inv(R)); contacts[str(float(a))]=b64(im)
    curve.append(rec)
print([c for c in curve if c["ov"]>0.01])
json.dump({"curve":curve,"contacts":contacts},open("web/sweep.json","w"))
