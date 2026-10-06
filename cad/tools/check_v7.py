# Verifies skull v7 against v6: outer skin left by the new pockets, ribbon slot opening, and the free
# height above the display driver board's top edge (where the HDMI / USB plugs stand).
import trimesh, numpy as np, os
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0]); AXL,AXR,ZC=-60.96,60.95,-0.32
def Lh(n): m=trimesh.load(os.path.join(OUT,n)); m.apply_translation(SHIFT); return m
v6=Lh("GeneTop_v6_neck.stl"); v7=Lh("GeneTop_v7_skull.stl")   # v7 here includes the fused carriers
# 1. skin: points on v7 surface that are not on v6 surface = new pocket faces
pts,fi=trimesh.sample.sample_surface_even(v7,60000)
d6=np.abs(trimesh.proximity.signed_distance(v6,pts))
sd=trimesh.proximity.signed_distance(v6,pts)
sel=(sd>0.05)&(pts[:,2]>ZC+20)                                # pocket faces: inside the old solid (seam fill is outside it; the slot is a through-cut on purpose)
newp=pts[sel]
# exterior faces of v6: a ray along the face normal escapes to infinity. The head's open bottom is capped
# with a slab first, so faces inside the cavity / bores can't "escape" down through it.
slab=trimesh.creation.box(extents=[400,400,6]); slab.apply_translation([0,0,-56.0])
# the crown slot is filled by the insert in the real head and the eye bores by the displays: block those too
crown=trimesh.creation.box(extents=[34,130,30]); crown.apply_translation([1.25,-48,80])
caps=[]
for ax in (AXL,AXR):
    cc=trimesh.creation.cylinder(radius=30.0,height=4,sections=64)
    cc.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])); cc.apply_translation([ax,-95.0,ZC]); caps.append(cc)
probe=trimesh.util.concatenate([v6,slab,crown]+caps)
c=v6.triangles_center+v6.face_normals*0.02
hit=probe.ray.intersects_any(c,v6.face_normals)
ext=v6.submesh([np.where(~hit)[0]],append=True)
_,dext,_=trimesh.proximity.closest_point(ext,newp)
print(f"new pocket surface points: {len(newp)}; min distance to the outside of the head {dext.min():.2f} mm (5th pct {np.percentile(dext,5):.2f})")
# 2. slot: probe open area at mid-wall
for side,ax,sg in (("L",AXL,1),("R",AXR,-1)):
    Ys=np.arange(-125,-80,0.25); Zs=np.arange(-8,8,0.25)
    G=np.array([[ax+sg*32.2,y,z] for y in Ys for z in Zs])
    s=np.concatenate([v7.contains(G[k:k+400]) for k in range(0,len(G),400)]).reshape(len(Ys),len(Zs))
    op=np.argwhere(~s); print(f"{side} ribbon slot open Y {Ys[op[:,0]].min():.2f}..{Ys[op[:,0]].max():.2f}  Z {Zs[op[:,1]].min():.2f}..{Zs[op[:,1]].max():.2f}")
# 3. free height above the board edge (r=28.5 from the eye axis), straight up, for lateral offsets
for side,ax in (("L",AXL),("R",AXR)):
    print(f"{side} eye: free height (mm) above board edge, v6 -> v7   [columns: X offset from eye axis, + = towards +X]")
    offs=[-15,-10,-5,0,5,10,15]
    print("        "+" ".join(f"{o:>11d}" for o in offs))
    for Y in (-84,-80,-76,-72,-66):
        row=[]
        for o in offs:
            z0=ZC+np.sqrt(max(28.5**2-o**2,0)) if abs(o)<28.5 else ZC
            o_=np.array([[ax+o,Y,z0]]); dd=np.array([[0,0,1.0]])
            r=[]
            for m in (v6,v7):
                loc,_,_=m.ray.intersects_location(o_,dd)
                h=np.sort(loc[:,2]-z0); h=h[h>0.01]
                r.append(h[0] if len(h) else np.inf)
            row.append(f"{r[0]:5.1f}->{r[1]:5.1f}")
        print(f"  Y{Y:4d} "+" ".join(row))
if __name__=="__main__" and os.environ.get("DBG"):
    cp,dd,tid=trimesh.proximity.closest_point(ext,newp)
    o=np.argsort(dext)[:25]
    for k in o: print(np.round(newp[k],2), "->", np.round(cp[k],2), f"{dext[k]:.2f}", "ext normal", np.round(ext.face_normals[tid[k]],2))
