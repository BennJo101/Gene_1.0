# Post-step: the Pi/speaker shelf is lowered SHELF_DROP so its plate's underside is flush with the skull's bottom rim
# (Z -53.35), freeing that much headroom over the Pi; the speaker cradles hang 7 mm below the rim, over the jaw.
# The shelf carries 4 cubes on its wings, and they slide up into 4 divots in the skull's inner
# wall as the shelf goes in, then bolt in from outside. Replaces the old step that fused 4 nut posts to the skull.
# Cube: on top of each wing (Z -50.35..-44.35), 11 wide (Y) round the old wing hole (X +/-62, Y -49 / -21), from 5.5 mm
# inboard of the hole out to the wall and 2.25 mm into it. Divot: a groove in the inner wall (a vertical cylinder
# r 83.4-83.7 about X 0, Y -48, straight from the bottom rim Z -53.35 upwards) 2.5 deep and 11.6 wide, open at the rim
# so the cube can slide up it, with its roof 0.2 above the cube top: the roof is the stop that sets the shelf height.
# Bolt: M2 socket head along X at (Y, Z -47.35), in from outside through a counterbore (head flush with or just under
# the skin, as motor_mount_m2.py), through the wall and into the cube, onto an M2 nut dropped into a slot in the cube's
# top, 3 mm inboard of the wall. The old wing holes under each cube are filled.
# Run after motor_mount_m2.py. Old files kept as tools/retired/GeneTop_v7_before_shelf_divots.stl and
# tools/retired/pi_shelf_before_cubes.stl (and mocks/speakers.stl, also lowered, as speakers_before_drop.stl).
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RET=os.path.join(OUT,"tools","retired")
SHIFT=np.array([-64.8,-61.4,-35.0])
HOLES=[(sx*62.0,y) for sx in (-1,1) for y in (-49.0,-21.0)]   # old wing holes (shelf6.py)
SHELF_DROP=13.35                     # plate underside Z -40 -> -53.35, the bottom rim
WING_BOT,WING_TOP=-40.0-SHELF_DROP,-37.0-SHELF_DROP
CUBE_H,CUBE_W,INBOARD=6.0,11.0,5.5   # cube Z -37..-31, along Y, inboard face this far inboard of the hole centre
WALL_C,R_GROOVE=(0.0,-48.0),86.2     # groove outer radius about (0,-48): ~2.5 into the wall, ~5 left behind it
RIM_Z=-53.35                         # skull bottom rim
CLR_R,CLR_Y,CLR_TOP=0.25,0.3,0.2     # cube to groove clearances: radial, each side, roof
BOLT_Z=-34.0-SHELF_DROP
CLEAR=2.4                            # M2 clearance
HEAD_D,HEAD_H,SINK=4.3,2.0,0.2       # counterbore for an M2 socket head (3.8 x 2.0)
NUT_AF,NUT_T,NUT_SLOT=4.0,1.6,2.2    # M2 hex nut; slot 2.2 thick along X
NUT_IN=3.0                           # nut slot's outboard face this far inboard of the inner wall

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)
def prism(cs,z0,z1): return mf.Manifold.extrude(cs,z1-z0).translate([0,0,z0])
def rect(x0,x1,y0,y1): return mf.CrossSection.square([x1-x0,y1-y0]).translate([x0,y0])
def along_x(cs,x0,x1,y,z): return mf.Manifold.extrude(cs,x1-x0).transform([[0,0,1,x0],[1,0,0,y],[0,1,0,z]])
def ring(r0,r1,z0,z1): return prism(mf.CrossSection.circle(r1,256).translate(list(WALL_C))-mf.CrossSection.circle(r0,256).translate(list(WALL_C)),z0,z1)

def hits_x(m,sg,y,z):
    loc,_,_=m.ray.intersects_location(np.array([[0,y,z]]),np.array([[sg,0,0]]),multiple_hits=True)
    return np.sort(np.abs(loc[:,0]))

def build_parts(sk,sh):
    shell=max(sk.split(only_watertight=False),key=lambda b:b.volume)
    top=WING_TOP+CUBE_H
    clip=prism(mf.CrossSection.circle(R_GROOVE-CLR_R,256).translate(list(WALL_C)),WING_BOT-1,top+1)
    add=[]; skcut=[]; shcut=[]; report=[]
    for x,y in HOLES:
        sg=np.sign(x); xi=x-sg*INBOARD
        x_wall=hits_x(shell,sg,y,BOLT_Z)[0]                     # inner wall on the bolt axis
        lo,hi=sorted([xi,sg*100.0])
        add.append(prism(rect(lo,hi,y-CUBE_W/2,y+CUBE_W/2),WING_TOP-0.5,top)^clip)   # sunk 0.5 into the wing: no knife edge where the cube overhangs the wing's wall edge
        add.append(prism(mf.CrossSection.circle(1.5,32).translate([x,y]),WING_BOT,WING_TOP+0.5))   # fill the old wing hole
        # divot: groove up the inner wall from below the rim to just over the cube top
        skcut.append(prism(rect(lo,hi,y-CUBE_W/2-CLR_Y,y+CUBE_W/2+CLR_Y),RIM_Z-1,top+CLR_TOP)^ring(70.0,R_GROOVE,RIM_Z-1,top+CLR_TOP))
        # bolt: counterbore from the skin, clearance through wall and cube, nut slot from the cube top
        rim=[hits_x(shell,sg,y+HEAD_D/2*np.cos(a),BOLT_Z+HEAD_D/2*np.sin(a))[-1] for a in np.linspace(0,2*np.pi,24,endpoint=False)]
        x_floor=min(rim)-HEAD_H-SINK
        x_nut=x_wall-NUT_IN                                      # slot's outboard face; the bolt pulls the nut onto it
        lo,hi=sorted([sg*(x_nut-NUT_SLOT-6.0),sg*(max(rim)+2.0)])
        hole=along_x(mf.CrossSection.circle(CLEAR/2,32),lo,hi,y,BOLT_Z)
        lo,hi=sorted([sg*x_floor,sg*(max(rim)+2.0)])
        skcut.append(hole+along_x(mf.CrossSection.circle(HEAD_D/2,48),lo,hi,y,BOLT_Z))
        corner=NUT_AF/np.sqrt(3)                                 # flats top and bottom, so it seats on the slot floor
        lo,hi=sorted([sg*(x_nut-NUT_SLOT),sg*x_nut])
        shcut.append(hole+prism(rect(lo,hi,y-corner-0.1,y+corner+0.1),BOLT_Z-NUT_AF/2-0.05,top+1))
        report.append((x,y,x_floor-(x_nut-NUT_T)))   # head underside to the far face of the seated nut
    U=lambda L: L[0] if len(L)==1 else L[0]+U(L[1:])
    S=to_mf(sk)-U(skcut); P=(to_mf(sh)+U(add))-U(shcut)
    return S,P,report

def save(t,fn):
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight and r.body_count==1, fn
    t.export(fn)

def build():
    sk_fn,sh_fn=os.path.join(OUT,"skull.stl"),os.path.join(OUT,"pi_shelf.stl")
    sk_bak,sh_bak=os.path.join(RET,"GeneTop_v7_before_shelf_divots.stl"),os.path.join(RET,"pi_shelf_before_cubes.stl")
    for f,b in ((sk_fn,sk_bak),(sh_fn,sh_bak)):
        if not os.path.exists(b): shutil.copy(f,b)
    sk=trimesh.load(sk_bak); sk.apply_translation(SHIFT); sh=trimesh.load(sh_bak); sh.apply_translation([0,0,-SHELF_DROP])
    spk_fn,spk_bak=os.path.join(OUT,"mocks","speakers.stl"),os.path.join(RET,"speakers_before_drop.stl")
    if not os.path.exists(spk_bak): shutil.copy(spk_fn,spk_bak)
    spk=trimesh.load(spk_bak); spk.apply_translation([0,0,-SHELF_DROP]); spk.export(spk_fn)
    S,P,report=build_parts(sk,sh)
    assert len(S.decompose())==1 and len(P.decompose())==1
    t=to_tm(S); t.apply_translation(-SHIFT); save(t,sk_fn)
    p=to_tm(P); save(p,sh_fn)
    for x,y,grip in report:
        print(f"  cube X {x:+.0f} Y {y:.0f}: head to nut far face {grip:.1f} mm")
    print(f"skull v7: 4 shelf divots, {sk.volume/1000:.2f} -> {t.volume/1000:.2f} cm3; shelf {sh.volume/1000:.2f} -> {p.volume/1000:.2f} cm3")

if __name__=="__main__":
    build()
