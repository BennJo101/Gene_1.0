# Optional Halloween part: a cap for one eye barrel with a raised X on it, for while an eye is out of action.
# A solid plug slips into the barrel's dia 59.00 front bore (the bezel sits 38 mm further in, so nothing clashes), a
# flange sits on the barrel's front face (r 29.5..34.25, Y -137.6 in the head frame) and the X stands proud of it.
# Same part for either eye: it's symmetric about the barrel axis. Pull it out and the eye is back as it was.
# Writes eye_x_insert.stl (barrel frame: axis along +Y into the barrel, origin on the axis at the front face) and
# print/parts/20_eye_x_insert_OPTIONAL_x1.stl (plug down on the bed, X up). Swap filament at the top of the flange
# (Z 8.0 on the print) for a two-colour X.
import trimesh, numpy as np, os, io, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT=os.path.dirname(OUT)
SHIFT=np.array([-64.8,-61.4,-35.0])
AXL,AXR,ZC,FRONT=-60.96,60.95,-0.32,-137.6   # eye axes and barrel front face (parts.py: ridge front -99.6, 38 mm in)

PLUG_D,PLUG_L=58.70,6.0            # bore 59.00: 0.15 radial clearance, a light push fit (a wrap of tape tightens it)
FLANGE_D,FLANGE_T,CHAMF=66.0,2.0,0.8   # barrel OD 68.5, so the flange stays inside the barrel's outline
X_LEN,X_W,X_H=52.0,8.0,3.0         # each bar of the X, round-ended
SEC=128

def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def build():
    # built Z-up as printed: plug Z 0..6, flange 6..8, X 8..11; then turned so the front faces -Y
    plug=mf.Manifold.cylinder(PLUG_L,PLUG_D/2,PLUG_D/2,SEC)
    flange=(mf.Manifold.cylinder(FLANGE_T-CHAMF,FLANGE_D/2,FLANGE_D/2,SEC)
            +mf.Manifold.cylinder(CHAMF,FLANGE_D/2,FLANGE_D/2-CHAMF,SEC).translate([0,0,FLANGE_T-CHAMF])).translate([0,0,PLUG_L])
    bar=mf.CrossSection.square([X_LEN-X_W,X_W],center=True)
    bar=bar+mf.CrossSection.circle(X_W/2,48).translate([-(X_LEN-X_W)/2,0])+mf.CrossSection.circle(X_W/2,48).translate([(X_LEN-X_W)/2,0])
    xs=bar.rotate(45)+bar.rotate(-45)
    x=mf.Manifold.extrude(xs,X_H).translate([0,0,PLUG_L+FLANGE_T])
    part=plug+flange+x
    assert len(part.decompose())==1
    pr=to_tm(part)
    pr.export(os.path.join(ROOT,"print","parts","20_eye_x_insert_OPTIONAL_x1.stl"))
    # barrel frame: print Z -> -Y (front face at Y 0, plug runs into +Y)
    bf=pr.copy(); bf.apply_translation([0,0,-(PLUG_L)])
    bf.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
    bf.export(os.path.join(OUT,"eye_x_insert.stl"))
    print(f"eye X insert: {pr.volume/1000:.1f} cm3, {pr.bounds[1][2]:.1f} mm tall, watertight {pr.is_watertight}")
    return bf

def check(bf):
    sk=trimesh.load(os.path.join(OUT,"skull.stl")); sk.apply_translation(SHIFT)
    S=mf.Manifold(mf.Mesh(vert_properties=np.asarray(sk.vertices,np.float32),tri_verts=np.asarray(sk.faces,np.uint32)))
    for s,ax in (("L",AXL),("R",AXR)):
        k=bf.copy(); k.apply_translation([ax,FRONT,ZC])
        K=mf.Manifold(mf.Mesh(vert_properties=np.asarray(k.vertices,np.float32),tri_verts=np.asarray(k.faces,np.uint32)))
        print(f"  {s} eye: overlap with skull {(S^K).volume():.3f} mm3")

if __name__=="__main__":
    check(build())
