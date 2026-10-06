# Skull v7 post-step: seal the small triangular holes at the outboard bottom corner of each eye barrel.
# The bottom flex window (+/-37.5 deg about straight down, Y -96 back to the barrel end) cuts the barrel wall where
# the skull's lower side wall (vertical cylinder r 83.5..91.5 about X 0, Y -48) meets it, leaving a 3-4 mm slot from
# the bore straight to the outside between Y -96 and about -85. The barrel wall is put back only where it lies
# outboard of the lower wall's inner face, so the window stays fully open on the inside of the head.
# Run after skull_v7_mirror_eye.py. Old file kept as tools/retired/GeneTop_v7_before_corner_seal.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC=-60.96,60.95,-0.32
R_BORE,R_OUT=30.3,34.25            # barrel wall (behind the display seat)
WIN_A=37.5                         # bottom window half-angle
Y0,Y1=-96.5,-61.5                  # window start (overlap 0.5 into the solid barrel) to the barrel end
LW_C,LW_R=(0.0,-48.0),83.5         # lower wall inner face

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def along_y(m, x, z, y0):
    """Manifold extruded along +Z with its XY profile -> head frame: profile X->X, profile Y->Z, extrusion->Y"""
    M=[[1,0,0,x],[0,0,1,y0],[0,1,0,z]]   # (px,py,pz) -> (px+x, pz+y0, py+z)
    return m.transform(M)

def filler(ax):
    out=-1 if ax<0 else 1                                   # outboard direction in X
    L=Y1-Y0
    ring=mf.Manifold.cylinder(L,R_OUT,R_OUT,256)-mf.Manifold.cylinder(L,R_BORE,R_BORE,256)
    # wedge: outboard half of the window, from straight down to WIN_A+2 deg, out past the barrel
    a=np.radians(np.linspace(0,WIN_A+2.0,40))
    pts=[(0.0,0.0)]+[(out*60*np.sin(t),-60*np.cos(t)) for t in a]
    if out<0: pts=pts[::-1]
    wedge=mf.Manifold.extrude(mf.CrossSection([pts]),L)
    sec=along_y(ring^wedge,ax,ZC,Y0)
    lw=mf.Manifold.cylinder(200,LW_R,LW_R,512).translate([LW_C[0],LW_C[1],-100])   # vertical, inside of the lower wall
    return sec-lw

def build():
    fn=os.path.join(OUT,"GeneTop_v7_skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_corner_seal.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT)
    A=to_mf(sh)
    F=filler(AXL)+filler(AXR)
    new=A+F
    comps=sorted(new.decompose(),key=lambda c:-c.volume())
    assert len(comps)==1, [c.volume() for c in comps]
    added=new.volume()-A.volume()
    t=to_tm(comps[0]); t.apply_translation(-SHIFT)
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight and r.body_count==1
    t.export(fn)
    print(f"skull v7: barrel corners sealed, +{added:.1f} mm3, vol {t.volume/1000:.2f} cm3, watertight on reload")
    return to_tm(F)

if __name__=="__main__":
    build()
