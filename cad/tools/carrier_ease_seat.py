# Display carrier v3 post-step: ease the display seat. The real TekGroAml 2.1" LCD is 56.18 +/- 0.15 across and the seat
# was 56.00, so the glass was squeezed round its edge (visible as pressure marks on the screen). The seat is opened to
# SEAT_D from the lip's rear face (Y -94.1) to the back face: 0.21 mm a side on a nominal panel, 0.13 on the largest,
# which a printed hole (usually ~0.1 undersize) still leaves free. The front lip (aperture 53.80) and the OD are
# untouched, so the screen is framed and the carrier fits the barrel as before. Side walls go 2.25 -> 1.95 mm.
# The glass is not round (Tailor Pixels TTC021XRS-02 drawing): a R28.09 circle plus a flat-ended ledge on the flex side,
# 31.40 wide, its flat edge 31.62 from the centre (59.71 overall). The top and bottom slots started at Y -92.55, so for the
# first 1.55 mm of the 2.3 mm glass the ledge hit a full ring of wall and the panel could not sit flat on the lip. Both
# slots (+/-74.25 deg, so the ledge's +/-34 deg is well inside, flex up or down) now run forward to the lip's rear face.
# All of this is behind the lip, so the eye looks the same from outside.
# Old file kept as tools/retired/carrier_v3_before_seat_ease.stl. Also writes print/parts/09 and the carriers on Plate 4.
import trimesh, numpy as np, os, re, shutil, zipfile, manifold3d as mf
from trimesh.transformations import rotation_matrix as rot
from threemf import write_3mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PR=os.path.join(os.path.dirname(OUT),"print")
SEAT_D=56.60                       # was 56.00
SLOT_HALF=74.25                    # v3 slot half-angle about +Z and -Z (side walls 31.5 deg wide at +/-X)
SLOT_Y0=-92.55                     # where the v3 slots started
LIP_BACK,BACK=-94.1,-84.1          # seat runs from the lip's rear face to the carrier's back face (carrier frame, axis Y)

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def build():
    fn=os.path.join(OUT,"eye_display_carrier.stl")
    bak=os.path.join(OUT,"tools","retired","carrier_v3_before_seat_ease.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    A=to_mf(trimesh.load(bak))
    L=BACK+1-LIP_BACK
    cut=mf.Manifold.cylinder(L,SEAT_D/2,SEAT_D/2,256).transform([[1,0,0,0],[0,0,1,LIP_BACK],[0,1,0,0]])
    a=np.radians(np.linspace(-SLOT_HALF,SLOT_HALF,64)); pie=np.vstack([[0,0],np.c_[31*np.sin(a),31*np.cos(a)]])
    for sgn in (1,-1):                                   # top and bottom slots, forward to the lip
        cs=mf.CrossSection([pie*[1,sgn]],mf.FillRule.EvenOdd)
        cut=cut+cs.extrude(SLOT_Y0+0.3-LIP_BACK).transform([[1,0,0,0],[0,0,1,LIP_BACK],[0,1,0,0]])
    new=A-cut; comps=new.decompose(); assert len(comps)==1
    t=to_tm(new); assert t.is_watertight
    t.export(fn)
    loc,_,_=t.ray.intersects_location([[0,-90,0],[0,-95,0],[0,-93.5,0],[0,-95,0]],[[1,0,0],[1,0,0],[0,0,1],[0,0,1]])
    print(f"carrier: seat {SEAT_D:.2f} (was 56.00), slots from Y {LIP_BACK} (were {SLOT_Y0}), vol {A.volume()/1000:.2f} -> {t.volume/1000:.2f} cm3")
    for o,d in (([0,-90,0],[1,0,0]),([0,-93.5,0],[0,0,1]),([0,-95.5,0],[0,0,1])):
        h,_,_=t.ray.intersects_location([o],[d]); print(f"  ray from {o} along {d}: hits {sorted(np.round(h[:,0 if d[0] else 2],2).tolist())}")
    return t

def reprint(t):
    p=t.copy(); p.apply_transform(rot(np.radians(90),[1,0,0])); p.apply_translation(-p.bounds[0])   # front lip down, as printprep
    old=trimesh.load(os.path.join(PR,"parts","09_eye_display_carrier_x2.stl")); assert np.allclose(old.extents,p.extents,atol=0.02)
    p.export(os.path.join(PR,"parts","09_eye_display_carrier_x2.stl"))
    fn=os.path.join(PR,"plates","Plate4_small_parts.3mf"); x=zipfile.ZipFile(fn).read("3D/3dmodel.model").decode(); objs=[]
    for name,body in re.findall(r'<object id="\d+" name="([^"]*)"[^>]*>(.*?)</object>',x,re.S):
        v=np.array(re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"',body),float)
        f=np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"',body),int)
        m=trimesh.Trimesh(v,f,process=False)
        if name.startswith("carrier"): m2=p.copy(); m2.apply_translation(m.bounds[0]); m=m2
        objs.append((name,m))
    write_3mf(fn,objs); print("  print/parts/09 and both carriers on Plate 4 replaced in place")

if __name__=="__main__":
    reprint(build())
