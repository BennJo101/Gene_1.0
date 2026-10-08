# Skull v7 post-step: open the inboard wall of each eye barrel, from the top of the camera ribbon slot up to the top
# window, so the round LCD's ribbon (31.4 mm wide at the panel, 20.5 at the board) can swing past it when the display
# + driver board are turned in the barrel (e.g. flipped 180 deg). Only the barrel wall (r 30.3..34.25 about the eye
# axis) is cut; beyond it on the inboard side is open head cavity. The outboard wall stays: there it is the outside.
# Run after skull_v7_barrel_taper.py. Old file kept as tools/retired/GeneTop_v7_before_open_inboard.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC=-60.96,60.95,-0.32
R0,R1=29.8,34.4                    # a little past both barrel faces so no skin of wall is left
Y0,Y1=-96.0,-61.0                  # top window front to just past the barrel end (-61.5)
Z_SLOT=3.5                         # camera ribbon slot is ZC +/- 3.75; cut from 0.25 below its top edge (overlap, no shared face)

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def cutter(ax):
    inb=1 if ax<0 else -1
    L=Y1-Y0
    ring=(mf.Manifold.cylinder(L,R1,R1,256)-mf.Manifold.cylinder(L,R0,R0,256)).transform([[1,0,0,ax],[0,0,1,Y0],[0,1,0,ZC]])
    x0=ax if inb>0 else ax-R1-1; x1=ax+R1+1 if inb>0 else ax
    box=mf.Manifold.cube([x1-x0,L,R1+1-Z_SLOT]).translate([x0,Y0,ZC+Z_SLOT])     # inboard half, above the slot
    return ring^box

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_open_inboard.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT); A=to_mf(sh)
    new=A-(cutter(AXL)+cutter(AXR))
    comps=sorted([c for c in new.decompose() if c.volume()>0.01],key=lambda c:-c.volume())
    assert len(comps)==1, [round(c.volume(),2) for c in comps]
    def reloads_ok(t):
        b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
        return r.is_watertight and r.body_count==1
    for tol in (0,0.002,0.005,0.01,0.02):      # STL is float32: merge near-duplicate vertices if the reload pinches
        t=to_tm(comps[0] if tol==0 else comps[0].simplify(tol)); t.apply_translation(-SHIFT)
        if reloads_ok(t): break
    else: raise AssertionError("does not reload watertight")
    t.export(fn)
    print(f"skull v7: inboard barrel walls opened above the camera slot, -{(A.volume()-comps[0].volume())/1000:.2f} cm3, vol {t.volume/1000:.2f} cm3, watertight on reload (tol {tol})")

if __name__=="__main__":
    build()
