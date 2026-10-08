# Skull v7 post-step: make the -X eye's display-plug pocket (Gene's RIGHT eye) an exact mirror of the +X one.
# skull_v7.py builds each pocket from a ray/skin heightfield; on the -X side, v6 has leftover internal weld faces at
# the barrel/skull crease (up to 4 mm off the mirror), which made that pocket's outboard edge ragged. The outside of
# the head is symmetric, so the -X eye region is replaced with the mirrored +X region inside a box around the pocket.
# Run after skull_v7.py. Old file kept as tools/retired/GeneTop_v7_before_eye_mirror.stl.
import trimesh, numpy as np, os, io, shutil, manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])                          # file frame -> head frame
LO,HI=np.array([-100.0,-109.0,20.0]),np.array([-33.0,-49.0,75.0])   # -X pocket region (pocket spans X -84..-36, Y -105..-52, Z 22..59)
EPS=0.3                                                      # mirrored piece overlaps the kept skull so the seams fuse

def to_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices,np.float32),tri_verts=np.asarray(t.faces,np.uint32)))
def to_tm(m): g=m.to_mesh(); return trimesh.Trimesh(g.vert_properties[:,:3],g.tri_verts)

def build():
    fn=os.path.join(OUT,"skull.stl")
    bak=os.path.join(OUT,"tools","retired","GeneTop_v7_before_eye_mirror.stl")
    if not os.path.exists(bak): shutil.copy(fn,bak)
    sh=trimesh.load(bak); sh.apply_translation(SHIFT)
    A=to_mf(sh)
    box=mf.Manifold.cube((HI-LO).tolist()).translate(LO.tolist())
    big=mf.Manifold.cube((HI-LO+2*EPS).tolist()).translate((LO-EPS).tolist())
    new=(A-box)+(A.mirror([1,0,0])^big)
    comps=sorted(new.decompose(),key=lambda c:-c.volume())
    assert len(comps)==1, [c.volume() for c in comps]
    t=to_tm(comps[0]); t.apply_translation(-SHIFT)
    b=io.BytesIO(); t.export(b,file_type="stl"); b.seek(0); r=trimesh.load(b,file_type="stl")
    assert r.is_watertight and r.body_count==1
    t.export(fn)
    print(f"skull v7: -X eye pocket mirrored from +X; vol {sh.volume/1000:.2f} -> {t.volume/1000:.2f} cm3, watertight on reload")

if __name__=="__main__":
    build()
