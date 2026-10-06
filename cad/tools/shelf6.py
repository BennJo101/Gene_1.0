import trimesh, numpy as np, os
from trimesh.creation import cylinder, box
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U=lambda ms: trimesh.boolean.union(ms,engine='manifold')
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
def zcyl(d,z0,z1,x=0.0,y=0.0,sec=96):
    c=cylinder(radius=d/2.0,height=abs(z1-z0),sections=sec); c.apply_translation([x,y,(z0+z1)/2.0]); return c
skull=trimesh.load(os.path.join(OUT,"GeneTop_v4_camslots.stl")); skull.apply_translation([-64.8,-61.4,-35.0])

PZ0,PZ1 = -40.0,-37.0          # plate, 3 mm, clears barrel undersides (-34.7) by 2.3
HX,HY   = 58.0,49.0            # Pi 5 hole pattern
CX,CY   = 0.0,-29.0            # board centre
SO_H    = 4.0                  # standoff height (was 6: real USB/Ethernet jacks need the room under the brackets)
SPK_D, SPK_T = 28.0, 5.0       # small speaker, dia 28 x 5 deep
SPK_AT  = [(-26.0,-88.0),(26.0,-88.0)]

plate=box(extents=[92.0,108.0,PZ1-PZ0]); plate.apply_translation([0,-51.0,(PZ0+PZ1)/2])
wings=[]
for sx in (-1,1):
    w=box(extents=[46.0,54.0,PZ1-PZ0]); w.apply_translation([sx*66.0,-35.0,(PZ0+PZ1)/2]); wings.append(w)
parts=[plate]+wings
for sx in (-1,1):
    for sy in (-1,1):
        parts.append(zcyl(7.0,PZ1,PZ1+SO_H,CX+sx*HX/2,CY+sy*HY/2))
for (sx,sy) in SPK_AT:
    parts.append(zcyl(SPK_D+6.0, PZ0-SPK_T-2.0, PZ1, sx, sy))   # speaker cradle hangs below
shelf=U(parts)

cuts=[]
for sx in (-1,1):
    for sy in (-1,1):
        cuts.append(zcyl(2.70,PZ1-1,PZ1+SO_H+1,CX+sx*HX/2,CY+sy*HY/2))
for (sx,sy) in SPK_AT:
    cuts.append(zcyl(SPK_D+0.4, PZ0-SPK_T-2.0-1, PZ0, sx, sy))  # speaker pocket, opens downward
    cuts.append(zcyl(SPK_D-5.0, PZ0-1, PZ1+1, sx, sy))          # sound hole through the plate
cuts.append(box(extents=[26.0,14.0,20.0]).apply_transform(np.eye(4)) or None)
cuts=[c for c in cuts if c is not None]
cable=box(extents=[26.0,14.0,20.0]); cable.apply_translation([0,-6.0,(PZ0+PZ1)/2]); cuts.append(cable)
for sx in (-1,1):
    for dy in (-14.0,14.0):
        cuts.append(zcyl(2.50,PZ0-1,PZ1+1,sx*62.0,-35.0+dy))    # M3 self-tappers into the shell
shelf=D(shelf,U(cuts))
shelf=D(shelf,skull)                                            # conform the wings to the inner wall
bodies=[b for b in shelf.split(only_watertight=False) if b.volume>200]
print("bodies kept:",len(bodies),[round(b.volume/1000,2) for b in bodies])
shelf=U(bodies) if len(bodies)>1 else bodies[0]
shelf.export(os.path.join(OUT,"GeneHead_pi_shelf_v6.stl"))
print(f"shelf v6: watertight={shelf.is_watertight} bodies={shelf.body_count} vol={shelf.volume/1000:.2f}cm3 extents={np.round(shelf.extents,1)}")
# mock Pi 5 and speakers for fit checking
pi=box(extents=[85.0,56.0,1.6]); pi.apply_translation([CX,CY,PZ1+SO_H+0.8])
stack=box(extents=[85.0,56.0,14.0]); stack.apply_translation([CX,CY,PZ1+SO_H+1.6+7.0])
# USB/Ethernet block: 16 tall above the PCB and 2.5 past the board edge (the part the brackets care about)
ports=box(extents=[21.5,53.0,16.0]); ports.apply_translation([CX+42.5+2.5-21.5/2,CY,PZ1+SO_H+1.6+8.0])
U([pi,stack,ports]).export(os.path.join(OUT,"GeneHead_pi5_MOCK.stl"))
spk=[zcyl(SPK_D,PZ0-SPK_T,PZ0,sx,sy) for sx,sy in SPK_AT]
U(spk).export(os.path.join(OUT,"GeneHead_speaker_MOCK.stl"))
print("mocks written (Pi 5 board+stack, 2x dia28 speakers)")
