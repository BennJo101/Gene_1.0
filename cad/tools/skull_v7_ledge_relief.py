# Skull v7 post-step: relief inside the top of each eye barrel for the LCD's flex ledge, never through the skin.
# The glass is not round (Tailor Pixels TTC021XRS-02 drawing): a R28.09 circle plus a ledge on the flex side, 31.40 wide,
# flat edge 31.62 from the centre. Mounted flex up, the ledge sits at Y -94.1..-91.8 and spans +/-34 deg about the top,
# where the outboard barrel wall (bore r 30.3, outside r 34.4, which is the head's outer skin there) was solid and pushed on
# it. The ledge outline grown CLEAR is cut into the wall only out to R1, so WALL of the barrel wall is always left under
# the skin (a full-depth cut opened the skin above the barrels; with the conservative rectangle outline the ledge corners
# reach r 35.3, so the real ledge must be rounder for the screens to have gone in at all). Inside the head, behind the
# display: nothing changes from outside. Run after skull_v7_shorten_tabs.py.
# Old file kept as tools/retired/GeneTop_v7_before_ledge_relief.stl. Also updates print/parts/01 and Plates 1 and 8.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
from skull_v7_eye_plate_window import reprint
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC=-60.96,60.95,-0.32
LEDGE_W,LEDGE_R=31.40,31.62        # ledge width, flat edge from the panel centre
CLEAR=0.4
R_OUT,WALL=34.4,1.2                # barrel outside (the skin here) and the wall always left under it
R0,R1=29.9,34.4-1.2                # bore is r 30.3
Y0,Y1=-94.5,-60.0                  # glass front face is Y -94.1; barrel ends at -61.4

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def cutter(ax):
    w=LEDGE_W/2+CLEAR
    sec=(mf.CrossSection.square([2*w,LEDGE_R+CLEAR]).translate([-w,0])
         ^(mf.CrossSection.circle(R1,256)-mf.CrossSection.circle(R0,256)))      # local x = X, local y = up (Z)
    return sec.extrude(Y1-Y0).transform([[1,0,0,ax],[0,0,1,Y0],[0,1,0,ZC]])

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_ledge_relief.stl")
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
    print(f"skull v7: ledge relief, -{(A.volume()-comps[0].volume())/1000:.2f} cm3, vol {t.volume/1000:.2f} cm3, "
          f"cut bounds {np.round(gone.bounds,1).tolist()}, watertight on reload (tol {tol})")
    return t

if __name__=="__main__":
    reprint(build())
