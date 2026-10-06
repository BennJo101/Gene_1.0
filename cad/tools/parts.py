# Loads every current part and places it in the head frame (pivot axis = X, origin on the axis).
import trimesh, numpy as np, os
from trimesh.creation import cylinder, box
import manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: trimesh.load(os.path.join(OUT,n))
AXL,AXR,ZC = -60.96,60.95,-0.32
DISP_Y, RIDGE_FRONT = -94.10, -99.60

def zcyl(d,z0,z1,sec=96):
    c=cylinder(radius=d/2,height=z1-z0,sections=sec); c.apply_translation([0,0,(z0+z1)/2]); return c

def servo_envelope():
    # solid stand-in for the STEP mesh (which is not watertight): case + output horn + idler disc
    case=box(extents=[20,34,23]); case.apply_translation([0,-7.5,-8.0])
    return trimesh.boolean.union([case,zcyl(16,0.9,6.5),zcyl(16,-22.5,-18.4)],engine='manifold')

ML=np.eye(4); ML[:3,:3]=[[0,0,-1],[0,1,0],[1,0,0]]; ML[:3,3]=[-39.5,0,0]
MR=np.eye(4); MR[:3,:3]=[[0,0,1],[0,1,0],[-1,0,0]]; MR[:3,3]=[39.5,0,0]
RY180=trimesh.transformations.rotation_matrix(np.pi,[0,1,0])

def load_all():
    P={}   # name -> (mesh, group, moves_with_jaw)
    top=L("GeneTop_v7_skull.stl"); top.apply_translation([-64.8,-61.4,-35.0])
    for b in top.split(only_watertight=False):
        v=b.volume/1000
        if v>400: P["shell"]=b
        elif v<20: P["brow"]=b
        elif b.bounds[0][0]<0: P["barrel_L"]=b
        else: P["barrel_R"]=b
    jaw=L("GeneBottom_v4_twindrive.stl"); jaw.apply_translation([13.75,-61.0,-40.6]); P["jaw"]=jaw
    P["hub_L"]=L("GeneHead_jaw_drive_hub.stl")
    P["hub_R"]=L("GeneHead_jaw_drive_hub_R_placed_MOCK.stl")
    env=servo_envelope()
    a=env.copy(); a.apply_transform(ML); P["servo_L"]=a
    b=env.copy(); b.apply_transform(MR); P["servo_R"]=b
    P["bracket_L"]=L("GeneHead_xl330_bracket_v2.stl"); P["bracket_R"]=L("GeneHead_xl330_bracket_R_v2.stl")
    car=L("GeneHead_eye_display_carrier.stl"); ret=L("GeneHead_eye_display_retainer.stl")
    dsp=L("GeneHead_eye_display_MOCK.stl"); bez=L("GeneHead_eye_camera_bezel.stl"); cam=L("GeneHead_eye_camera_MOCK.stl")
    pup=L("GeneHead_pupil_ring.stl")
    for s,ax in (("L",AXL),("R",AXR)):
        c=car.copy(); c.apply_translation([ax,0,ZC]); P["carrier_"+s]=c
        d=dsp.copy(); d.apply_translation([ax,DISP_Y,ZC]); P["display_"+s]=d
        r=ret.copy(); r.apply_translation([ax,DISP_Y+5.2,ZC]); P["retainer_"+s]=r   # directly behind the module
        for nm,m in (("bezel_",bez),("camera_",cam),("pupil_",pup)):
            k=m.copy()
            if s=="R": k.apply_transform(RY180)          # same part turned 180 deg about the barrel axis
            k.apply_translation([ax,RIDGE_FRONT,ZC]); P[nm+s]=k
    P["shelf"]=L("GeneHead_pi_shelf_v6.stl"); P["pi5"]=L("GeneHead_pi5_MOCK.stl")
    P["speakers"]=L("GeneHead_speaker_MOCK.stl"); P["handle"]=L("GeneHead_bridge_handle.stl"); P["insert"]=L("GeneHead_crown_insert.stl"); P["gpio_plug"]=L("GeneHead_gpio_plug_MOCK.stl")
    P["neck"]=L("GeneHead_neck.stl"); P["neck_base"]=L("GeneHead_neck_base.stl"); P["neck_collar"]=L("GeneHead_neck_collar.stl")
    P["bearings"]=L("GeneHead_neck_bearings_MOCK.stl"); P["slip_ring"]=L("GeneHead_slip_ring_MOCK.stl")
    P["splitter"]=L("GeneHead_gpio_splitter_MOCK.stl"); P["ttl"]=L("GeneHead_ttl_interface_MOCK.stl"); P["amps"]=L("GeneHead_i2s_amps_MOCK.stl")
    P["tray"]=L("GeneHead_battery_tray.stl"); P["deck"]=L("GeneHead_battery_deck.stl")
    P["battery"]=L("GeneHead_battery_2S2P_MOCK.stl"); P["boards"]=L("GeneHead_power_boards_MOCK.stl")
    # optional crown accessories (alternatives: the flashlight replaces the handle; the cover is for when nothing is plugged in)
    P["flashlight"]=L("GeneHead_gpio_flashlight.stl"); P["gpio_header"]=L("GeneHead_gpio_header_MOCK.stl"); P["gpio_cover"]=L("GeneHead_gpio_cover.stl")
    return P

MOVING={"jaw","hub_L","hub_R"}

def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices,np.float32),tri_verts=np.asarray(m.faces,np.uint32)))
