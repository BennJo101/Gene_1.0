# Fit-check stand-in (not printed) for the TekGroAml display driver board: 57 mm round PCB behind each LCD,
# parts facing back, LCD flex connector at the bottom, so the mini-HDMI and micro-USB stand at the top edge.
# Plug bodies are modelled as a 90 deg mini-HDMI FPC plug and a right-angle micro-USB plug (each ~9 mm proud).
import trimesh, numpy as np, os
from trimesh.creation import cylinder, box
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXL,AXR,ZC=-60.96,60.95,-0.32
PCB_Y=-73            # PCB front face; set so the outboard plug clears the barrel skin
def bx(x0,x1,y0,y1,z0,z1):
    b=box(extents=[x1-x0,y1-y0,z1-z0]); b.apply_translation([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]); return b
def board(ax):
    pcb=cylinder(radius=28.5,height=1.6,sections=96); pcb.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
    pcb.apply_translation([ax,PCB_Y+0.8,ZC])
    chip=bx(ax-8,ax+8,PCB_Y+1.6,PCB_Y+3.0,ZC-8,ZC+8)
    y0=PCB_Y+1.6
    hdmi=bx(ax-5.9-5.75,ax-5.9+5.75,y0,y0+3.2,ZC+21.0,ZC+28.9)       # receptacle at the top edge
    hplug=bx(ax-5.9-6.25,ax-5.9+6.25,y0-0.9,y0+4.6,ZC+28.9,ZC+38.0)    # plug body above it
    usb=bx(ax+8.9-4.0,ax+8.9+4.0,y0,y0+3.0,ZC+23.0,ZC+28.9)
    uplug=bx(ax+8.9-5.25,ax+8.9+5.25,y0-0.9,y0+4.1,ZC+28.9,ZC+38.0)
    return trimesh.util.concatenate([pcb,chip,hdmi,hplug,usb,uplug])
m=trimesh.util.concatenate([board(AXL),board(AXR)])
m.export(os.path.join(OUT,"GeneHead_display_board_MOCK.stl"))
