# Jaw v5: the pivot pins become separate screw-in parts.
# On v4 each arm carried a dia 13.74 pivot pin plus a dia 8 D-shaft, 42 mm long in all, which had to pass axially
# through the closed ring of the skull socket. Fitting the jaw meant springing the arms apart, and the pins snapped.
# Now the pins are cut off and the arms get a through bore, so the bare jaw slides on from below with no flexing,
# then each pin goes in from outside through its arm and the socket into the hub.
#   pin  : hex head (AF 15 x 5.9) + the original dia 13.74 bearing pin + the original D-shaft, printed separately.
#          The hex keys it to the arm (it carries the servo torque), the step under the head locates it inboard.
#   arm  : hex pocket AF 15.3 x 6.0 in the outboard face, dia 14.1 bore through the rest of the arm.
#   lock : 1 x M3 x 5 grub screw (as on the hubs) per side, radial from the back (+Y) edge of the arm into a groove round the hex head
#          (root r 5.8, so the grub ends flush with the arm edge, which is 10.9 from the axis).
# Writes jaw.stl (old file kept as tools/retired/jaw_v4_before_screw_pins.stl) and jaw_pin.stl (left pin, in the head
# frame; the right pin is the same part turned 180 deg about Z, as with the hubs).
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JAW_T=np.array([13.75,-61.0,-40.6])   # jaw frame -> head frame (as in parts.py)
HEX_AF,HEX_LEN=15.0,5.9               # pin head
POCKET_AF,POCKET_D=15.3,6.0           # arm pocket
PIN_R=6.87                            # bearing pin, as v4 (its facets run r 6.71-6.87)
BORE_D=14.1                           # bore through the arm for the pin
X_BEAR=78.0                           # |x| inboard of which the pin + D-shaft are taken from the v4 mesh as they are
GROOVE_AT,GROOVE_W,GROOVE_R=3.0,3.2,5.8   # grub groove: distance in from the outboard face, width, root radius
GRUB_D=2.5                            # M3 tapping hole, radial along +Y

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def xprism(x0,x1,r,n,yc,zc,rot=0.0):
    # n-sided prism (or cylinder for large n) along +X from x0 to x1, circumradius r, centred on (yc,zc)
    c=mf.Manifold.cylinder(x1-x0,r,r,n)
    if rot: c=c.rotate([0,0,rot])
    return c.transform([[0,0,1,x0],[0,1,0,yc],[-1,0,0,zc]])

def pin_circle(jaw,x):
    # centre and radius of the bearing pin, from its cross-section at x (least-squares circle through the outline)
    sec=jaw.section(plane_origin=[x,0,0],plane_normal=[1,0,0])
    pts=np.vstack([e for e in sec.discrete if np.hypot(e[:,1],e[:,2]).max()<10])[:,1:]
    A=np.c_[2*pts,np.ones(len(pts))]; b=(pts**2).sum(1)
    yc,zc,c=np.linalg.lstsq(A,b,rcond=None)[0]
    return yc,zc,np.sqrt(c+yc**2+zc**2)

def pin_and_cut(J,jaw,s):
    # s=-1 left (head frame -X), +1 right. Returns (pin, cut) manifolds in the head frame.
    yc,zc,r_pin=pin_circle(jaw,s*72.0)
    xo=jaw.bounds[0][0] if s<0 else jaw.bounds[1][0]               # outboard arm face
    hexr=lambda af: af/2/np.cos(np.pi/6)
    # hex with a flat facing +Y (the grub side): cylinder(n=6) puts a vertex on its local +X, which maps to head -Z
    def span(a,b): return tuple(sorted((xo-s*a,xo-s*b)))                # distances in from the face -> x range
    x0,x1=span(0.05,HEX_LEN+0.05); head=xprism(x0,x1,hexr(HEX_AF),6,yc,zc)
    x0,x1=span(HEX_LEN,s*xo-X_BEAR)                                      # dia 13.74 bearing pin up to |x|=X_BEAR
    bear=xprism(x0,x1,PIN_R,128,yc,zc)
    keep=xprism(min(s*X_BEAR,s*40.0)-0.01,max(s*X_BEAR,s*40.0)+0.01,7.3,128,yc,zc)
    shaft=J^keep                                                          # v4 pin + D-shaft, exactly as it was
    x0,x1=span(GROOVE_AT-GROOVE_W/2,GROOVE_AT+GROOVE_W/2)
    groove=xprism(x0,x1,hexr(HEX_AF)+1,6,yc,zc)-xprism(x0,x1,GROOVE_R,128,yc,zc)
    pin=(head+bear+shaft)-groove
    # cut in the jaw: pocket, bore (also removes the old pin and shaft), grub hole
    x0,x1=span(-1.0,POCKET_D); pocket=xprism(x0,x1,hexr(POCKET_AF),6,yc,zc)
    bore=xprism(min(xo-s,s*40.0),max(xo-s,s*40.0),BORE_D/2,128,yc,zc)
    xg=xo-s*GROOVE_AT
    grub=mf.Manifold.cylinder(30,GRUB_D/2,GRUB_D/2,48).transform([[1,0,0,xg],[0,0,1,yc+GROOVE_R],[0,-1,0,zc]])  # along +Y
    return pin, pocket+bore+grub, (yc,zc,r_pin,xo)

def build():
    fn=os.path.join(OUT,"jaw.stl")
    bak=os.path.join(OUT,"tools","retired","jaw_v4_before_screw_pins.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    jaw=trimesh.load(bak); jaw.apply_translation(JAW_T)                   # work in the head frame
    J=to_mf(jaw)
    pins={}; cut=None
    for s,nm in ((-1,"L"),(1,"R")):
        p,c,info=pin_and_cut(J,jaw,s); pins[nm]=p; cut=c if cut is None else cut+c
        print(f"{nm}: axis y {info[0]:+.3f} z {info[1]:+.3f}, fitted pin r {info[2]:.3f}, outboard face x {info[3]:+.2f}")
    new=J-cut
    comps=new.decompose(); assert len(comps)==1, sorted(c.volume() for c in comps)
    for nm,p in pins.items():
        assert len(p.decompose())==1, nm
        print(f"pin {nm}: {p.volume()/1000:.2f} cm3, overlap with new jaw {(p^new).volume():.4f} mm3")
    # the right pin should be the left one turned 180 deg about Z
    pr=pins["L"].rotate([0,0,180]).translate([0,2*info[0],0])   # same part, sitting on the right bore's axis
    d=(pr-pins["R"]).volume()+(pins["R"]-pr).volume()
    print(f"left pin turned 180 about Z vs right pin: {d:.2f} mm3 symmetric difference")
    t=to_tm(new); t.apply_translation(-JAW_T)
    p=to_tm(pins["L"])
    for m,f in ((t,fn),(p,os.path.join(OUT,"jaw_pin.stl"))):
        b=io.BytesIO(); m.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
        assert r.is_watertight and r.body_count==1, f
        m.export(f)
    print(f"jaw v5 {t.volume/1000:.2f} cm3 (v4 {jaw.volume/1000:.2f}), pin {p.volume/1000:.2f} cm3 x2")

if __name__=="__main__":
    build()
