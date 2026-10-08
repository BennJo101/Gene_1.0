# Post-step: M2 through-bolts from the outside of the skull into each servo bracket's foot, alongside the 2 x M3
# self-tappers (Y +20, Z +/-10). The foot is the bracket's rear end, cut conformal to the inside of the skull wall; its
# inner face is the flat plane X = -/+43. Per bracket, 2 x M2 socket-head bolts at Y 19, Z +/-4.5, parallel to the M3s
# (along X): counterbored from outside so the head sits flush with or just under the skin, clearance through the wall
# and the foot, and an M2 hex nut captured in a hex pocket in the foot's inner face.
# Run after skull_v7_usbc_port.py. Old files kept in tools/retired/ (GeneTop_v7_before_m2_bolts.stl, *_v2_before_m2_bolts.stl).
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RET=os.path.join(OUT,"tools","retired")
SHIFT=np.array([-64.8,-61.4,-35.0])
BOLTS=[(19.0,-4.5),(19.0,4.5)]     # (Y, Z), same on both sides
X_FOOT=43.0                        # foot inner face, |X|
CLEAR=2.4                          # M2 clearance
HEAD_D,HEAD_H=4.3,2.0              # counterbore for an M2 socket head (3.8 x 2.0)
NUT_AF,NUT_DEPTH=4.3,2.2           # M2 hex nut 4.0 AF x 1.6, pocket with clearance
SINK=0.2                           # head top this far under the skin at the shallowest point of the counterbore

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def along_x(cs,x0,x1,y,z):
    """CrossSection in (Y, Z) extruded along +X from x0 to x1, centred on (y, z)"""
    return mf.Manifold.extrude(cs,x1-x0).transform([[0,0,1,x0],[1,0,0,y],[0,1,0,z]])

def skin_x(shell,sg,y,z):
    """|X| of the skull's outer skin on a ray along +/-X at (y, z)"""
    loc,_,_=shell.ray.intersects_location(np.array([[0,y,z]]),np.array([[sg,0,0]]))
    return np.abs(loc[:,0]).max()

def cuts(shell,sg):
    """cutters for one side (sg -1 left, +1 right) in the head frame, and the bolt length needed per bolt"""
    C=[]; lengths=[]
    for y,z in BOLTS:
        rim=[skin_x(shell,sg,y+HEAD_D/2*np.cos(a),z+HEAD_D/2*np.sin(a)) for a in np.linspace(0,2*np.pi,24,endpoint=False)]
        x_floor=min(rim)-HEAD_H-SINK                          # counterbore floor, |X|
        lo,hi=sorted([sg*(X_FOOT-1.0),sg*(max(rim)+2.0)])          # through the foot and the wall
        C.append(along_x(mf.CrossSection.circle(CLEAR/2,32),lo,hi,y,z))
        lo,hi=sorted([sg*x_floor,sg*(max(rim)+2.0)])
        C.append(along_x(mf.CrossSection.circle(HEAD_D/2,48),lo,hi,y,z))
        hexa=mf.CrossSection([[(NUT_AF/np.sqrt(3)*np.cos(a),NUT_AF/np.sqrt(3)*np.sin(a)) for a in np.radians(np.arange(0,360,60)+30)]])
        lo,hi=sorted([sg*(X_FOOT-1.0),sg*(X_FOOT+NUT_DEPTH)])      # into the foot from its inner face
        C.append(along_x(hexa,lo,hi,y,z))
        lengths.append(x_floor-(X_FOOT+NUT_DEPTH-1.6))        # head underside to the far face of the seated nut
    U=C[0]
    for c in C[1:]: U=U+c
    return U,lengths

def save(t,fn):
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight and r.body_count==1, fn
    t.export(fn)

def build():
    files={"skull":"skull.stl","L":"servo_bracket_L.stl","R":"servo_bracket_R.stl"}
    bakname=lambda f: "GeneTop_v7_before_m2_bolts.stl" if f=="skull.stl" else f.replace(".stl","_before_m2_bolts.stl")
    for k,f in files.items():
        bak=os.path.join(RET,bakname(f))
        if not os.path.exists(bak): shutil.copy(os.path.join(OUT,f),bak)
    load=lambda f: trimesh.load(os.path.join(RET,bakname(f)))
    sk=load(files["skull"]); sk.apply_translation(SHIFT)
    shell=max(sk.split(only_watertight=False),key=lambda b:b.volume)
    S=to_mf(sk)
    for side,sg in (("L",-1),("R",1)):
        U,lengths=cuts(shell,sg)
        S=S-U
        br=load(files[side]); B=to_mf(br)-U
        assert len(B.decompose())==1
        save(to_tm(B),os.path.join(OUT,files[side]))
        print(f"bracket {side}: {to_tm(B).volume/1000:.2f} cm3; bolt grip to nut far face {', '.join(f'{l:.1f}' for l in lengths)} mm -> M2 x 16")
    assert len(S.decompose())==1
    t=to_tm(S); t.apply_translation(-SHIFT); save(t,os.path.join(OUT,files["skull"]))
    print(f"skull v7: 4 x M2 bolt holes, vol {t.volume/1000:.2f} cm3")

if __name__=="__main__":
    build()
