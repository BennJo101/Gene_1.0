# Camera bezel v3, sized for the camera actually bought: Arducam B0066 mini OV5647 (Amazon B012QRGUCQ).
# Measured from the seller's photos (300 mm cable as scale): 8.5 mm square head, ~12 mm long including the
# crystal / flex joint behind it, 6.0 mm wide flex leaving along the spoke, rigid 16 x 30 mm 15-pin end.
#  * pocket keeps the lens on the eye axis and grows only towards the cable: 8.6 x 12.4 (was 8.6 x 8.6)
#  * the 3.6 x 1.8 tunnel at mid-thickness is replaced by a 6.8 mm lane cut from the rear face, level with
#    the camera board, so the flex runs straight out of the module without a jog; small lips on the outer
#    part of the lane snap the flex in
#  * spoke widened 7.0 -> 11.5 so the lane and the longer pocket keep >= 1.3 mm walls
import trimesh, numpy as np, os
from trimesh.creation import cylinder, box
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U=lambda ms: trimesh.boolean.union(ms,engine='manifold')
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
def ycyl(d,y0,y1,x=0.0,z=0.0,sec=128):
    c=cylinder(radius=d/2.0,height=abs(y1-y0),sections=sec)
    c.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    c.apply_translation([x,(y0+y1)/2.0,z]); return c
def bx(x0,x1,y0,y1,z0,z1):
    b=box(extents=[x1-x0,y1-y0,z1-z0]); b.apply_translation([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]); return b
BEZ_OD, BEZ_ID, BEZ_T = 58.60, 51.60, 6.00
HUB_D   = 16.00
SPOKE_W = 11.50
CAM_W, CAM_L, LENS = 8.60, 12.40, 7.50     # pocket across the spoke, pocket along the spoke, lens hole
POCKET_FRONT = -4.60                       # 1.4 mm front wall in front of the module, as before
LANE_W, LANE_D = 6.80, 2.20                # flex is 6.0 wide; lane floor 2.2 below the rear face
LIP, LIP_T, LIP_X0 = 0.60, 0.50, 16.0      # 5.6 mm mouth on the outer part of the lane only
SL_L = BEZ_OD/2.0+6.0                      # run the lane out past the ring OD (no skin at the exit)
# local frame: axis along Y, rear face at y=0 (seats on the ridge), front face at y=-BEZ_T; spoke along +X
ring = D(ycyl(BEZ_OD,-BEZ_T,0.0), ycyl(BEZ_ID,-BEZ_T-1,1.0))
hub  = ycyl(HUB_D,-BEZ_T,0.0)
spoke= trimesh.boolean.intersection([bx(0.0,BEZ_OD/2.0, -BEZ_T,0.0, -SPOKE_W/2,SPOKE_W/2), ycyl(BEZ_OD,-BEZ_T-1,1.0)],engine="manifold")   # square corners trimmed to the ring OD
bez=U([ring,hub,spoke])
cuts=[ycyl(LENS,-BEZ_T-1,1.0)]                                                   # lens aperture
cuts.append(bx(-CAM_W/2, -CAM_W/2+CAM_L, POCKET_FRONT, 1.0, -CAM_W/2, CAM_W/2))  # module pocket, open at the back
lane_x0=-CAM_W/2+CAM_L-0.5                                                        # overlaps the pocket 0.5 mm
cuts.append(bx(lane_x0, SL_L, -LANE_D, -LIP_T, -LANE_W/2, LANE_W/2))             # lane below the lips
cuts.append(bx(lane_x0, LIP_X0, -LIP_T-0.1, 1.0, -LANE_W/2, LANE_W/2))           # inner part: fully open (flex leaves the board here)
cuts.append(bx(LIP_X0-0.1, SL_L, -LIP_T-0.1, 1.0, -LANE_W/2+LIP, LANE_W/2-LIP))  # outer part: 5.6 mouth between lips
bez=D(bez,U(cuts))
bodies=[b for b in bez.split(only_watertight=False) if b.volume>50]
bez=U(bodies) if len(bodies)>1 else bodies[0]
bez.export(os.path.join(OUT,"camera_bezel.stl"))
print(f"bezel v3 (Arducam): pocket {CAM_W} x {CAM_L} (lens on axis, extra length towards the cable), spoke {SPOKE_W} wide")
print(f"   lane {LANE_W} wide x {LANE_D} deep from the rear face, {LANE_W-2*LIP:.1f} mm mouth from r={LIP_X0} outwards")
print(f"   walls: pocket {(SPOKE_W-CAM_W)/2:.2f} each side, lane {(SPOKE_W-LANE_W)/2:.2f} each side, {BEZ_T-LANE_D:.2f} in front of the lane")
print(f"   watertight={bez.is_watertight} bodies={bez.body_count} vol={bez.volume/1000:.2f}cm3 extents={np.round(bez.extents,2)}")

# fit-check stand-in for the Arducam module (not printed): head + lens like the old mock, plus the board tail
cam=trimesh.load(os.path.join(OUT,"mocks/camera.stl"))
y1=cam.bounds[1][1]
tail=bx(4.25, -CAM_W/2+CAM_L-0.2, y1-1.0, y1, -4.25, 4.25)
flex=bx(-CAM_W/2+CAM_L-0.2, SL_L+4.0, y1-1.0, y1-0.7, -3.0, 3.0)   # lies in the lane under the lips
cam=U([cam,tail,flex])
cam.export(os.path.join(OUT,"mocks/camera.stl"))
print(f"   camera MOCK now includes the board tail and 6 mm flex: extents {np.round(cam.extents,2)}")
