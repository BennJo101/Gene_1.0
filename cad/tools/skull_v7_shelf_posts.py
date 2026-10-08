# Post-step: 4 nut posts on the inside of the skull wall for the Pi shelf wings. The wing holes (dia 2.5 at X +/-62,
# Y -49 / -21, vertical) used to open onto empty cavity: the wall is 17-22 mm outboard of them. Each post is a block
# hanging off the wall whose flat underside is the wing's top face (Z -37), running from 5.5 mm inboard of the hole out
# to the wall (the inner wall here is a vertical cylinder r 83.7 about X 0, Y -48; the post is fused 2.3 mm into it and
# stops at r 86, so the skin outside is untouched). An M2 x 8 socket head goes up from under the wing, through the wing
# and the post, into an M2 hex nut slid sideways into a slot from the post's inboard face. Wings unchanged.
# The left posts sit under the TTL interface, which now rests on their tops (mock raised by POST_H in gpio_mocks.py).
# Run after motor_mount_m2.py. Old file kept as tools/retired/GeneTop_v7_before_shelf_posts.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RET=os.path.join(OUT,"tools","retired")
SHIFT=np.array([-64.8,-61.4,-35.0])
HOLES=[(sx*62.0,y) for sx in (-1,1) for y in (-49.0,-21.0)]   # wing holes (shelf6.py)
WING_TOP=-37.0
POST_H=6.0                         # post Z -37..-31
POST_W=11.0                        # along Y
INBOARD=5.5                        # post's inboard face this far inboard of the hole centre
WALL_C,R_OUT=(0.0,-48.0),86.0      # post clipped to r <= 86 about (0,-48); inner wall r 83.6-83.9, outer 91.3-91.5
CLEAR=2.4                          # M2 clearance (the wing hole is 2.5)
NUT_AF,NUT_Z0,NUT_Z1=4.3,-35.0,-33.0   # M2 nut 4.0 AF x 1.6; slot 2.0 tall, 2.0 of post under it, 2.0 over it

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)
def prism(cs,z0,z1): return mf.Manifold.extrude(cs,z1-z0).translate([0,0,z0])
def rect(x0,x1,y0,y1): return mf.CrossSection.square([x1-x0,y1-y0]).translate([x0,y0])

def posts():
    clip=prism(mf.CrossSection.circle(R_OUT,256).translate(list(WALL_C)),WING_TOP-1,WING_TOP+POST_H+1)
    add=[]; cut=[]
    for x,y in HOLES:
        sg=np.sign(x); xi=x-sg*INBOARD
        lo,hi=sorted([xi,sg*100.0])
        add.append(prism(rect(lo,hi,y-POST_W/2,y+POST_W/2),WING_TOP,WING_TOP+POST_H)^clip)
        cut.append(prism(mf.CrossSection.circle(CLEAR/2,32).translate([x,y]),WING_TOP-1,WING_TOP+POST_H+1))
        hexa=mf.CrossSection([[(x+NUT_AF/np.sqrt(3)*np.cos(a),y+NUT_AF/np.sqrt(3)*np.sin(a)) for a in np.radians(np.arange(0,360,60))]])  # flats facing +/-Y
        lo,hi=sorted([x,xi-sg*1.0])
        cut.append(prism(hexa+rect(lo,hi,y-NUT_AF/2,y+NUT_AF/2),NUT_Z0,NUT_Z1))   # slot open to the inboard face
    A=add[0]
    for a in add[1:]: A=A+a
    C=cut[0]
    for c in cut[1:]: C=C+c
    return A,C

def save(t,fn):
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight and r.body_count==1, fn
    t.export(fn)

def build():
    fn=os.path.join(OUT,"skull.stl"); bak=os.path.join(RET,"GeneTop_v7_before_shelf_posts.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sk=trimesh.load(bak); sk.apply_translation(SHIFT)
    A,C=posts()
    S=(to_mf(sk)+A)-C
    assert len(S.decompose())==1
    t=to_tm(S); t.apply_translation(-SHIFT); save(t,fn)
    grip=(NUT_Z0+1.6)-(WING_TOP-3.0)                    # head underside (wing bottom) to the top of the seated nut
    print(f"skull v7: 4 shelf nut posts, vol {sk.volume/1000:.2f} -> {t.volume/1000:.2f} cm3; nut top {grip:.1f} mm above the head -> M2 x 8 ({8-grip:.1f} mm past the nut)")

if __name__=="__main__":
    build()
