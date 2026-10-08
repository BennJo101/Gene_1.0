# Skull v7 post-step: USB-C charge port through the lower back wall.
# Part: Poyiccot USB-C male-to-female panel-mount extension, 30 cm, right-angle male (Amazon B086W2R8Z6). Its female end
# has a 25 x 8 mm flange with two M3 holes 16.6 mm apart, 34.5 mm long overall. The flange sits INSIDE the skull with its
# face on a flat seat, and 2 x M3 go in from outside through the wall into the flange (as on a PCI bracket).
# The lower skull is a vertical cylinder wall (r 84.0..91.6 about X 0, Y -48). The flange's long axis runs horizontal
# (along X, screws side by side; turned 90 deg from the first, vertical layout on 2026-10-07). The seat is a flat plane, so
# the wall in front of the flange thins from 3.0 mm at the centre to 2.1 at its ends (the cylinder's 0.9 mm sagitta).
# Port centred on the back (X 0) at Z -14: clear of the neck-yoke screw pilots (top Z -41) and, with the connector
# body modelled straight inward, >= 1.6 mm from every part, the jaw sweep and every routed cable.
# Run after skull_v7_open_inboard.py. Old file kept as tools/retired/GeneTop_v7_before_usbc_port.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])
SC_Y,R_OUT=-48.0,91.63             # wall axis (X 0, Y -48) and outer radius
ZC=-14.0                           # port centre height
PANEL=3.0                          # wall left in front of the flange; the supplied 11 mm screws then reach 8 mm into it
FLANGE=(25.6,8.6)                  # seat pocket X x Z: 25 x 8 flange + 0.3 a side
OPEN=(13.8,7.6,2.5)                # opening X x Z, corner radius: passes a max-size USB-C overmold (6.5 x 12.35).
                                   # Its ends run 0.3 into the screw holes (a hairline web there would not print); the M3 heads
                                   # still bear on the wall outboard of that
SCREW_DX,SCREW_D=8.3,3.4           # M3 clearance, 16.6 apart along X

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

Y_SEAT=SC_Y+R_OUT-PANEL           # flange face plane

def along_y(cs,y0,y1):
    """CrossSection in (X, Z) extruded along +Y from y0 to y1, centred on X 0, Z ZC"""
    return mf.Manifold.extrude(cs,y1-y0).transform([[1,0,0,0],[0,0,1,y0],[0,1,0,ZC]])

def rrect(w,h,r):
    return mf.CrossSection.square([w-2*r,h-2*r],center=True).offset(r,mf.JoinType.Round,2.0,64)

def cutter():
    pocket=along_y(mf.CrossSection.square(list(FLANGE),center=True),Y_SEAT-12.0,Y_SEAT)       # from inside the head out to the seat
    hole=along_y(rrect(*OPEN),Y_SEAT-1.0,SC_Y+R_OUT+3.0)
    screws=[mf.Manifold.cylinder(PANEL+6.0,SCREW_D/2,SCREW_D/2,48).transform([[1,0,0,s*SCREW_DX],[0,0,1,Y_SEAT-1.0],[0,1,0,ZC]]) for s in (-1,1)]
    return pocket+hole+screws[0]+screws[1]

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_usbc_port.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT)
    A=to_mf(sh)
    new=A-cutter()
    comps=sorted(new.decompose(),key=lambda c:-c.volume())
    n_before=len(A.decompose())
    assert len(comps)==n_before, (len(comps),n_before)
    t=to_tm(new); t.apply_translation(-SHIFT)
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight
    t.export(fn)
    print(f"skull v7: USB-C port cut, {new.volume()-A.volume():.1f} mm3, vol {t.volume/1000:.2f} cm3, bodies {len(comps)}, watertight on reload")

def mock():
    """Fit-check stand-in for the female end, in the head frame: flange 25 x 8 x 4 (assumed thickness), body 12 x 6.5 x 18
    (assumed), strain relief dia 6 to 34.5 overall, all pointing straight into the head from the seat"""
    f=along_y(mf.CrossSection.square([25.0,8.0],center=True),Y_SEAT-4.0,Y_SEAT)
    b=along_y(mf.CrossSection.square([12.0,6.5],center=True),Y_SEAT-22.0,Y_SEAT-4.0)
    s=along_y(mf.CrossSection.circle(3.0,48),Y_SEAT-34.5,Y_SEAT-22.0)
    t=to_tm(f+b+s); t.export(os.path.join(OUT,"mocks/usbc_panel.stl")); return t

if __name__=="__main__":
    build()
    mock()
