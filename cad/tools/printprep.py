import numpy as np, trimesh, os, json
from parts import *
from trimesh.transformations import rotation_matrix as rot
OUTP=os.path.join(OUT,"print"); os.makedirs(OUTP,exist_ok=True)
Uu=lambda ms: trimesh.boolean.union(ms,engine='manifold')
def Lraw(n): return trimesh.load(os.path.join(OUT,n))
X,Y,Z=[1,0,0],[0,1,0],[0,0,1]
skull=Lraw("skull.stl")
skull=Uu(skull.split(only_watertight=False))
skull=[b for b in skull.split(only_watertight=False) if abs(b.volume)>1.0][0]   # drop zero-volume slivers from the merge
hub=Lraw("jaw_drive_hub.stl")
# name, mesh, qty, rotations (list of (angle_deg, axis)) to put the best flat face on the bed
PARTS=[
 ("skull",        skull,                                  1, []),                      # open bottom rim on the bed, crown up
 ("jaw",          Lraw("jaw.stl"),    1, []),
 ("hub",          hub,                                    2, [(90,Y)]),                # axis vertical, flat end down
 ("bracket_L",    Lraw("servo_bracket_L.stl"),  1, []),                      # upright, as installed
 ("bracket_R",    Lraw("servo_bracket_R.stl"),1, []),
 ("carrier",      Lraw("eye_display_carrier.stl"),2,[(90,X)]),                # front lip down
 ("retainer",     Lraw("eye_display_retainer.stl"),2,[(90,X)]),
 ("bezel",        Lraw("camera_bezel.stl"),  2, [(90,X)]),                # front face down
 ("pupil_ring",   Lraw("pupil_ring.stl"),        2, [(-90,X)]),               # glue face down, cone opens up
 ("pi_shelf",     Lraw("pi_shelf.stl"),       1, []),
 ("bridge_handle",Lraw("bridge_handle.stl"),    1, [(-90,Y)]),               # on its side, flat post faces down (optional part)
 ("crown_insert", Lraw("crown_insert.stl"),     1, [(-90,Y)]),               # on its side so the visible top prints smooth
 ("neck",         Lraw("neck.stl"),              1, [(180,X)]),               # yoke plate on the bed, tube up
 ("neck_base",    Lraw("neck_base.stl"),         1, []),                      # flange down, bearing seats vertical
 ("neck_collar",  Lraw("neck_collar.stl"),       1, []),
 ("battery_tray", Lraw("battery_tray.stl"),      1, []),
 ("battery_deck", Lraw("battery_deck.stl"),      1, []),
 ("gpio_flashlight",Lraw("gpio_flashlight.stl"),1, [(-90,Y)]),              # on its side, saddle side down; supports under the strap and pod (optional part)
 ("gpio_cover",   Lraw("gpio_cover.stl"),        1, []),                      # upright, skirts down (optional part)
]
out={}
for name,m,q,rs in PARTS:
    m=m.copy()
    for a,ax in rs: m.apply_transform(rot(np.radians(a),ax))
    m.apply_translation(-m.bounds[0])                         # on the bed at the origin
    # STL stores float32: vertices closer than that collapse on reload and pinch the mesh.
    # Merge near-duplicates with Manifold.simplify, and keep the version that reloads watertight.
    import io, manifold3d as mf3
    def reloads_ok(mm):
        b=io.BytesIO(); mm.export(b,file_type="stl"); b.seek(0)
        return trimesh.load(b,file_type="stl").is_watertight
    if not reloads_ok(m):
        for tol in (0.002,0.005,0.01,0.02):
            man=mf3.Manifold(mf3.Mesh(vert_properties=np.asarray(m.vertices,np.float32),tri_verts=np.asarray(m.faces,np.uint32))).simplify(tol)
            t=man.to_mesh(); cand=trimesh.Trimesh(t.vert_properties[:,:3],t.tri_verts)
            if reloads_ok(cand):
                print(f"   {name}: merged near-duplicate vertices (tol {tol} mm), volume change {cand.volume-m.volume:+.3f} mm3")
                m=cand; break
    zmin=m.bounds[0][2]
    bed=m.area_faces[(np.abs(m.triangles[:,:,2]-zmin).max(1)<0.05)&(m.face_normals[:,2]<-0.99)].sum()
    out[name]=(m,q)
    print(f"{name:13s} x{q}  {np.round(m.extents,1)}  body={m.body_count} wt={m.is_watertight}  vol {m.volume/1000:6.2f} cm3  bed contact {bed:7.1f} mm2")
import pickle; pickle.dump({k:(v[0].vertices,v[0].faces,v[1]) for k,v in out.items()},open("printparts.pkl","wb"))
