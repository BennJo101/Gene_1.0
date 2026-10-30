# Skull v7 post-step: shorten the inboard "tabs" of the eye barrels. Behind the camera ribbon slots (rear edge Y -87.5)
# each barrel's inboard wall is only a lower arc (from the slot's height down to about Z -25, the part left by
# skull_v7_open_inboard.py), running back to the barrel end at Y -61.4. Nothing mounts on it behind the display
# carrier (which ends at Y -84.1). It is cut back to half its length past the slot: Y_END = -87.5 + 26.1/2 = -74.45.
# Only the inboard half of the barrel wall (r 29.5..34.9 about the eye axis) below the open part is cut.
# Run after skull_v7_eye_plate_window.py. Old file kept as tools/retired/GeneTop_v7_before_shorten_tabs.stl.
# Also replaces the skull in print/parts/01_skull_x1.stl and in Plates 1 and 8, in the same place on the bed.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
from skull_v7_eye_plate_window import reprint
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC=-60.96,60.95,-0.32
SLOT_Y,END_Y=-87.5,-61.4
Y_END=SLOT_Y+(END_Y-SLOT_Y)/2      # -74.45
R0,R1=29.5,34.9                    # a little past both barrel faces
Z_TOP=ZC+4.5                       # above the tab top (ZC + 3.75); the wall above is already open

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def cutter(ax):
    L=END_Y+5-Y_END
    ring=(mf.Manifold.cylinder(L,R1,R1,256)-mf.Manifold.cylinder(L,R0,R0,256)).transform([[1,0,0,ax],[0,0,1,Y_END],[0,1,0,ZC]])
    x0,x1=(ax,ax+R1+1) if ax<0 else (ax-R1-1,ax)                         # inboard half
    return ring^mf.Manifold.cube([x1-x0,L,Z_TOP-(ZC-R1-1)]).translate([x0,Y_END,ZC-R1-1])

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_shorten_tabs.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT); A=to_mf(sh)
    cut=cutter(AXL)+cutter(AXR); new=A-cut
    comps=sorted([c for c in new.decompose() if c.volume()>0.01],key=lambda c:-c.volume())
    assert len(comps)==1, [round(c.volume(),2) for c in comps]
    gone=to_tm(A^cut)
    def reloads_ok(t):
        b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
        return r.is_watertight and r.body_count==1
    for tol in (0,0.002,0.005,0.01,0.02):      # STL is float32: merge near-duplicate vertices if the reload pinches
        t=to_tm(comps[0] if tol==0 else comps[0].simplify(tol)); t.apply_translation(-SHIFT)
        if reloads_ok(t): break
    else: raise AssertionError("does not reload watertight")
    t.export(fn)
    print(f"skull v7: barrel tabs cut back to Y {Y_END:.2f}, -{(A.volume()-comps[0].volume())/1000:.2f} cm3, vol {t.volume/1000:.2f} cm3, "
          f"cut bounds {np.round(gone.bounds,1).tolist()}, watertight on reload (tol {tol})")
    return t

if __name__=="__main__":
    reprint(build())
