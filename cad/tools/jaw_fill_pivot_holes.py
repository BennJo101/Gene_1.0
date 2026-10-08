# Jaw v4 post-step: fill the old pivot-screw holes.
# Each jaw arm had a stepped blind hole on the pivot axis, opening on the arm's outboard face: dia ~5.4 for 14 mm,
# then dia ~2.9 down to the start of the D-shaft (30.4 mm deep in all). They were for a screw through the pivot,
# but the pins are now D-shafts clamped by the drive hubs and nothing screws into the jaw, so the holes are filled
# solid with a coaxial cylinder that ends flush with the outboard face. Outer shape unchanged.
# Old file kept as tools/retired/GeneBottom_v4_before_hole_fill.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YC,ZC=60.76,40.29                  # pivot axis in the jaw's own frame (fitted to the hole walls)
R_FILL=3.3                         # covers the dia 5.4 bore; pin around it is dia 13.76
X_SHAFT_L,X_SHAFT_R=-82.38,54.80   # hole bottoms, where the D-shafts start; the holes run out to the arm faces

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def plug(x0,x1):
    c=mf.Manifold.cylinder(x1-x0,R_FILL,R_FILL,96)          # along +Z from 0
    return c.transform([[0,0,1,x0],[0,1,0,YC],[-1,0,0,ZC]])  # Z -> +X, centred on the pivot axis

def build():
    fn=os.path.join(OUT,"jaw.stl")
    bak=os.path.join(OUT,"tools","retired","GeneBottom_v4_before_hole_fill.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    old=trimesh.load(bak)
    A=to_mf(old)
    xl,xr=old.bounds[:,0]                                 # outboard arm faces are the jaw's X extremes
    new=A+plug(xl,X_SHAFT_L)+plug(X_SHAFT_R,xr)
    comps=new.decompose()
    assert len(comps)==1, [c.volume() for c in comps]
    t=to_tm(new)
    assert np.allclose(t.bounds,old.bounds,atol=1e-3), (t.bounds,old.bounds)
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight and r.body_count==1
    t.export(fn)
    print(f"jaw v4: pivot holes filled, +{new.volume()-A.volume():.1f} mm3, vol {t.volume/1000:.2f} cm3, watertight on reload")

if __name__=="__main__":
    build()
