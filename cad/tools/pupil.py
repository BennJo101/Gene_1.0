import trimesh, numpy as np, os
from trimesh.creation import cylinder
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
# Pupil ring: glues onto the front face of the bezel hub (local frame: bezel front face at y=-6, axis on Y).
# Its bore is a cone that opens forward, so the lens reads as a deep pupil and the camera is never vignetted.
FACE_Y   = -6.0      # bezel front face
H        = 2.0       # ring height, forward of the face
OD       = 18.0
BORE0    = 7.5       # matches the bezel's lens aperture at the face
CONE     = 60.0      # bore half-angle (deg)
N=128
r0=BORE0/2; r1=r0+H*np.tan(np.radians(CONE)); R=OD/2
# revolve a closed profile (r, y) about the Y axis
prof=[(r0,FACE_Y),(R,FACE_Y),(R,FACE_Y-H+0.4),(R-0.4,FACE_Y-H),(r1,FACE_Y-H)]   # 0.4 chamfer on the outer lip
th=np.linspace(0,2*np.pi,N,endpoint=False)
V=[];F=[]
P=len(prof)
for t in th:
    for r,y in prof: V.append([r*np.cos(t),y,r*np.sin(t)])
for i in range(N):
    j=(i+1)%N
    for k in range(P):
        a=i*P+k; b=i*P+(k+1)%P; c=j*P+(k+1)%P; d=j*P+k
        F+= [[a,b,c],[a,c,d]]
ring=trimesh.Trimesh(V,F,process=True)
if ring.volume<0: ring.invert()
ring.export(os.path.join(OUT,"pupil_ring.stl"))
print(f"pupil ring: watertight={ring.is_watertight} vol={ring.volume:.1f} mm3 bounds={np.round(ring.bounds,2).tolist()}")
print(f"   bore {BORE0:.2f} at the face -> {2*r1:.2f} at the lip, wall at lip {R-0.4-r1:.2f} mm")
# field-of-view check: rays from the lens entrance pupil (r ~1.0 mm, at the lens front y=-6.5)
cam=trimesh.load(os.path.join(OUT,"mocks/camera.stl"))
lens_front=cam.bounds[0][1]
ep=1.0
lip_y=FACE_Y-H
tan_max=(r1-ep)/(lens_front-lip_y)
print(f"   lens front y={lens_front:.2f}; clear half-angle from the entrance pupil = {np.degrees(np.arctan(tan_max)):.1f} deg  (full FOV {2*np.degrees(np.arctan(tan_max)):.0f} deg)")
