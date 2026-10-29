# Loads every current part and places it in the head frame (pivot axis = X, origin on the axis).
import trimesh, numpy as np, os
from trimesh.creation import cylinder, box
import manifold3d as mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: trimesh.load(os.path.join(OUT,n))
AXL,AXR,ZC = -60.96,60.95,-0.32
DISP_Y, RIDGE_FRONT = -94.10, -99.60
POWER=os.environ.get("GENE_POWER","pack")   # "pack" (2S2P, default) or "powerbank"

def zcyl(d,z0,z1,sec=96):
    c=cylinder(radius=d/2,height=z1-z0,sections=sec); c.apply_translation([0,0,(z0+z1)/2]); return c

def servo_envelope():
    # solid stand-in for the STEP mesh (which is not watertight): case + output horn + idler disc
    case=box(extents=[20,34,23]); case.apply_translation([0,-7.5,-8.0])
    return trimesh.boolean.union([case,zcyl(16,0.9,6.5),zcyl(16,-22.5,-18.4)],engine='manifold')

ML=np.eye(4); ML[:3,:3]=[[0,0,-1],[0,1,0],[1,0,0]]; ML[:3,3]=[-39.5,0,0]
MR=np.eye(4); MR[:3,:3]=[[0,0,1],[0,1,0],[-1,0,0]]; MR[:3,3]=[39.5,0,0]
RY180=trimesh.transformations.rotation_matrix(np.pi,[0,1,0])
RZ180=trimesh.transformations.rotation_matrix(np.pi,[0,0,1])

def load_all():
    P={}   # name -> (mesh, group, moves_with_jaw)
    top=L("skull.stl"); top.apply_translation([-64.8,-61.4,-35.0])
    for b in top.split(only_watertight=False):
        v=b.volume/1000
        if v>400: P["shell"]=b
        elif v<20: P["brow"]=b
        elif b.bounds[0][0]<0: P["barrel_L"]=b
        else: P["barrel_R"]=b
    jaw=L("jaw.stl"); jaw.apply_translation([13.75,-61.0,-40.6]); P["jaw"]=jaw
    P["hub_L"]=L("jaw_drive_hub.stl")
    P["hub_R"]=L("mocks/jaw_drive_hub_R_placed.stl")
    # screw-in pivot pins (jaw_screw_pins.py): the right one is the same part turned 180 deg about Z, on the right bore's axis
    P["pin_L"]=L("jaw_pin.stl"); pr=P["pin_L"].copy(); pr.apply_transform(RZ180); pr.apply_translation([0,-0.076,0]); P["pin_R"]=pr
    env=servo_envelope()
    a=env.copy(); a.apply_transform(ML); P["servo_L"]=a
    b=env.copy(); b.apply_transform(MR); P["servo_R"]=b
    P["bracket_L"]=L("servo_bracket_L.stl"); P["bracket_R"]=L("servo_bracket_R.stl")
    car=L("eye_display_carrier.stl"); ret=L("eye_display_retainer.stl")
    dsp=L("mocks/display.stl"); bez=L("camera_bezel.stl"); cam=L("mocks/camera.stl")
    pup=L("pupil_ring.stl")
    for s,ax in (("L",AXL),("R",AXR)):
        c=car.copy(); c.apply_translation([ax,0,ZC]); P["carrier_"+s]=c
        d=dsp.copy(); d.apply_translation([ax,DISP_Y,ZC]); P["display_"+s]=d
        r=ret.copy(); r.apply_translation([ax,DISP_Y+5.2,ZC]); P["retainer_"+s]=r   # directly behind the module
        for nm,m in (("bezel_",bez),("camera_",cam),("pupil_",pup)):
            k=m.copy()
            if s=="R": k.apply_transform(RY180)          # same part turned 180 deg about the barrel axis
            k.apply_translation([ax,RIDGE_FRONT,ZC]); P[nm+s]=k
    P["shelf"]=L("pi_shelf.stl"); P["pi5"]=L("mocks/pi5.stl")
    P["speakers"]=L("mocks/speakers.stl"); P["handle"]=L("bridge_handle.stl"); P["insert"]=L("crown_insert.stl"); P["gpio_plug"]=L("mocks/gpio_plug.stl")
    P["neck"]=L("neck.stl"); P["neck_base"]=L("neck_base.stl"); P["neck_collar"]=L("neck_collar.stl")
    P["bearings"]=L("mocks/neck_bearings.stl"); P["slip_ring"]=L("mocks/slip_ring.stl")
    P["splitter"]=L("mocks/gpio_splitter.stl"); P["ttl"]=L("mocks/ttl_interface.stl"); P["amps"]=L("mocks/i2s_amp.stl")
    if POWER=="powerbank":   # secondary setup, battery_powerbank.py
        P["tray"]=L("battery_tray_pb.stl"); P["deck"]=L("battery_deck_pb.stl")
        P["battery"]=L("mocks/powerbank_P50.stl"); P["boards"]=L("mocks/power_boards_pb.stl")
    else:
        P["tray"]=L("battery_tray.stl"); P["deck"]=L("battery_deck.stl")
        P["battery"]=L("mocks/battery_2S2P.stl"); P["boards"]=L("mocks/power_boards.stl")
    P["usbc_port"]=L("mocks/usbc_panel.stl")
    # optional crown accessories (alternatives: the flashlight replaces the handle; the cover is for when nothing is plugged in)
    P["flashlight"]=L("gpio_flashlight.stl"); P["gpio_header"]=L("mocks/gpio_header.stl"); P["gpio_cover"]=L("gpio_cover.stl")
    return P

MOVING={"jaw","hub_L","hub_R","pin_L","pin_R"}

def to_mf(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices,np.float32),tri_verts=np.asarray(m.faces,np.uint32)))
