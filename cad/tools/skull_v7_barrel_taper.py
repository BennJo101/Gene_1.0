# Skull v7 post-step: blend the back end of each eye barrel into the skull on the outside (far left / far right).
# The barrels end in a flat face at Y -61.5 that stands up to ~4.5 mm proud of the skull side, with a thin
# see-through crack along that face where it meets the skull. Each barrel's outer cylinder (r 34.25) is continued
# backwards as a cone that narrows into the skull side, which fills the crack and turns the step into a ramp.
# The cone is trimmed to outside the head cavity (inner sphere / lower cylinder, r 83.3), outside the bore and below the
# display-plug pocket, so nothing changes on the inside of the head.
# Run after skull_v7_seal_corners.py. Old file kept as tools/retired/GeneTop_v7_before_barrel_taper.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC=-60.96,60.95,-0.32
R_OUT,R_BORE=34.25,30.3
Y_END=-61.5                        # back face of the barrels
Y0=Y_END-0.5                       # a stub reaches 0.5 inside the barrel so the cone fuses
SLOPE=0.35                         # radius lost per mm going back (~19 deg ramp)
LEN=40.0
TOP_A=45.0
C_IN,R_IN=(0.0065,-47.684,0.173),83.3   # inner skull: sphere above the equator, vertical cylinder below

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)
def along_y(m,x,z,y0): return m.transform([[1,0,0,x],[0,0,1,y0],[0,1,0,z]])   # local +Z extrusion -> head +Y

def cavity():
    sph=mf.Manifold.sphere(R_IN,512).translate(list(C_IN))
    cyl=mf.Manifold.cylinder(150,R_IN,R_IN,512).translate([C_IN[0],C_IN[1],C_IN[2]-150])
    return sph+cyl

def taper(ax):
    L=LEN+0.5
    cone=along_y(mf.Manifold.cylinder(LEN,R_OUT,R_OUT-SLOPE*LEN,256),ax,ZC,Y_END)   # full radius right at the back face
    stub=along_y(mf.Manifold.cylinder(Y_END-Y0+0.01,R_OUT-0.1,R_OUT-0.1,256),ax,ZC,Y0)  # inside the faceted barrel, fuses
    cone=cone+stub
    bore=along_y(mf.Manifold.cylinder(Y_END-Y0+1.0,R_BORE,R_BORE,256),ax,ZC,Y0-1.0)
    # leave out the top +/-TOP_A deg: the plug pocket lives there (+/-37.5) and on top the barrel is buried in the skull anyway
    a=np.radians(TOP_A); w=[(0,0),(-80*np.sin(a),80*np.cos(a)),(0,80),(80*np.sin(a),80*np.cos(a))]
    top=along_y(mf.Manifold.extrude(mf.CrossSection([w[::-1]]),L+2),ax,ZC,Y0-1)
    return cone-bore-top

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_barrel_taper.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT); A=to_mf(sh)
    v6=trimesh.load(os.path.join(OUT,"GeneTop_v6_neck.stl")); v6.apply_translation(SHIFT)   # only to check the pockets stay open
    pockets=[p for p in (to_mf(v6)-A).decompose() if p.volume()>5000]       # the two display-plug pockets
    F=(taper(AXL)+taper(AXR))-cavity()
    for p in pockets: assert (F^p).volume()<1e-3, "taper reaches into a plug pocket"
    new=A+F
    comps=sorted([c for c in new.decompose() if c.volume()>0.01],key=lambda c:-c.volume())   # drop boolean specks
    assert len(comps)==1, [c.volume() for c in comps]
    def reloads_ok(t):
        b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
        return r.is_watertight and r.body_count==1
    # STL stores float32: near-duplicate vertices collapse on reload and pinch the mesh, so merge them (as printprep.py)
    for tol in (0,0.002,0.005,0.01,0.02):
        t=to_tm(comps[0] if tol==0 else comps[0].simplify(tol)); t.apply_translation(-SHIFT)
        if reloads_ok(t): break
    else: raise AssertionError("does not reload watertight")
    if tol: print(f"   merged near-duplicate vertices (tol {tol} mm)")
    t.export(fn)
    print(f"skull v7: barrel ends tapered into the skull, +{(new.volume()-A.volume())/1000:.2f} cm3, vol {t.volume/1000:.2f} cm3, watertight on reload")

if __name__=="__main__":
    build()
