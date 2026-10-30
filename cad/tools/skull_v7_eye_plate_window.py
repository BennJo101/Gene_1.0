# Skull v7 post-step: cut the middle out of the flat plate between the eye barrels (Z 2.5..5.1, 2.6 mm thick,
# X -27..27, Y -130..-82), leaving a U: a strip along each barrel wall and one along the face, open at the back, so the
# plate still ties the barrels to each other through the face. Nothing mounts on the middle, and printed rim-down it is a
# roof 57 mm above the bed that needs tree supports under all of it; a bar across the free back edge would span 54 mm.
# The plate is found as the material in neither the Z 1.5 nor the Z 6.1 section (grown 1.5 mm) and outside both barrel
# tubes (r 34.45); the cut is that outline inset by FRAME (corners rounded R_CORNER), run out through the back edge.
# Run after skull_v7_shelf_divots.py. Old file kept as tools/retired/GeneTop_v7_before_eye_plate_window.stl.
# Also replaces the skull in print/parts/01_skull_x1.stl and in Plates 1 and 8, in the same place on the bed.
import trimesh, numpy as np, os, io, re, shutil, zipfile, manifold3d as mf
from threemf import write_3mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PR=os.path.join(os.path.dirname(OUT),"print")
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC=-60.96,60.95,-0.32
Z0,Z1=1.9,5.7                      # band round the plate's 2.5..5.1
R_TUBE=34.45                       # barrel outer radius 34.4 + 0.05
FRAME,R_CORNER=6.0,5.0             # strip width from the walls and the face, corner radius at the face

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def section(m,z,outer_only=False):
    p,_=m.section(plane_origin=[0,0,z],plane_normal=[0,0,1]).to_2D(to_2D=np.eye(4)); loops=[]
    for g in p.polygons_full:
        loops+=[np.asarray(g.exterior.coords)[:-1]]+([] if outer_only else [np.asarray(i.coords)[:-1] for i in g.interiors])
    return mf.CrossSection(loops,mf.FillRule.EvenOdd)

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_eye_plate_window.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT); A=to_mf(sh)
    walls=(section(sh,Z0-0.4)+section(sh,Z1+0.4)).offset(1.5,mf.JoinType.Round).extrude(Z1-Z0+2).translate([0,0,Z0-1])
    tube=lambda ax: mf.Manifold.cylinder(120,R_TUBE,R_TUBE,256).transform([[1,0,0,ax],[0,0,1,-140],[0,1,0,ZC]])
    plate=A^(mf.Manifold.cube([60,62,Z1-Z0]).translate([-30,-142,Z0])-(walls+tube(AXL)+tube(AXR)))
    outline=section(to_tm(plate),(2.5+5.1)/2,outer_only=True)
    win=outline.offset(-FRAME-R_CORNER,mf.JoinType.Round).offset(R_CORNER,mf.JoinType.Round)
    x0,y0,x1,y1=win.bounds()
    win=win+mf.CrossSection.square([x1-x0,40]).translate([x0,(y0+y1)/2])   # out through the back edge: no bar across
    cut=win.extrude(Z1-Z0+2).translate([0,0,Z0-1])
    new=A-cut
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
    print(f"skull v7: eye plate U, cut {np.round(gone.extents[:2],1).tolist()} mm, -{(A.volume()-comps[0].volume())/1000:.2f} cm3 "
          f"(plate was {plate.volume()/1000:.2f}), vol {t.volume/1000:.2f} cm3, window bounds {np.round(gone.bounds,1).tolist()}, watertight on reload (tol {tol})")
    return t

def reprint(t):
    # print orientation is the skull as modelled, rim on the bed: same bounds before and after, so it drops into place
    old=trimesh.load(os.path.join(PR,"parts","01_skull_x1.stl")); p=t.copy(); p.apply_translation(-p.bounds[0])
    assert np.allclose(old.extents,p.extents,atol=0.05), (old.extents,p.extents)
    p.export(os.path.join(PR,"parts","01_skull_x1.stl"))
    for plate in ("Plate1_skull.3mf","Plate8_changes_2026-10-16.3mf"):
        fn=os.path.join(PR,"plates",plate); x=zipfile.ZipFile(fn).read("3D/3dmodel.model").decode(); objs=[]
        for name,body in re.findall(r'<object id="\d+" name="([^"]*)"[^>]*>(.*?)</object>',x,re.S):
            v=np.array(re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"',body),float)
            f=np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"',body),int)
            m=trimesh.Trimesh(v,f,process=False)
            if name.startswith("skull"):
                m2=p.copy(); m2.apply_translation(m.bounds[0]); m=m2
            objs.append((name,m))
        write_3mf(fn,objs); print(f"  {plate}: skull replaced in place")

if __name__=="__main__":
    reprint(build())
