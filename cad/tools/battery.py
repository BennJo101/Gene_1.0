import trimesh, numpy as np, os, itertools
from trimesh.creation import cylinder, box
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U=lambda ms: trimesh.boolean.union(ms,engine='manifold')
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
def bx(x0,x1,y0,y1,z0,z1):
    b=box(extents=[x1-x0,y1-y0,z1-z0]); b.apply_translation([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]); return b
def zcyl(d,z0,z1,x=0.0,y=0.0,sec=64):
    c=cylinder(radius=d/2,height=z1-z0,sections=sec); c.apply_translation([x,y,(z0+z1)/2]); return c
def ycyl(d,y0,y1,x=0.0,z=0.0,sec=64):
    c=cylinder(radius=d/2,height=y1-y0,sections=sec)
    c.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0])); c.apply_translation([x,(y0+y1)/2,z]); return c

# ---- pack: 2S2P 18650, four cells in a row across X, cell axes fore-aft (Y) ----
CELL_D, CELL_L = 18.5, 65.0
PITCH = 18.6
CX = [(-1.5+i)*PITCH for i in range(4)]
FLOOR_Z0, FLOOR_T = 14.0, 2.0              # tray sits on the bracket pads (top Z 14.0)
CELL_ZC = FLOOR_Z0+FLOOR_T+CELL_D/2+0.3    # 0.3 for wrap/heat-shrink
PY0, PY1 = -56.5, 11.0                     # pack incl. wrap, end caps and nickel
TX0, TX1, TY0, TY1 = -40.0, 40.0, -58.5, 13.0
WALL, WALL_TOP = 2.0, 27.0
DECK_Z = 38.5                              # deck underside, 1 mm over the wrapped pack
DECK_T = 2.5
HOLE_FRONT_Y, HOLE_REAR_Y, HOLE_X = -31.0, 14.0, 41.5
REAR_POST_X, REAR_POST_Y = 20.0, 15.5

tray=[bx(TX0,TX1,TY0,TY1,FLOOR_Z0,FLOOR_Z0+FLOOR_T)]
tray+= [bx(TX0,TX0+WALL,TY0,TY1,FLOOR_Z0,WALL_TOP), bx(TX1-WALL,TX1,TY0,TY1,FLOOR_Z0,WALL_TOP),
        bx(TX0,TX1,TY0,TY0+WALL,FLOOR_Z0,WALL_TOP), bx(TX0,TX1,TY1-WALL,TY1,FLOOR_Z0,WALL_TOP)]
# cradle ribs across the cells
ribs=[bx(TX0+WALL,TX1-WALL,y-1.5,y+1.5,FLOOR_Z0,CELL_ZC) for y in (-44.0,-22.0,0.0)]
tray+=ribs
# corner posts carrying the deck, and the two screw bosses per side that land on the bracket pads
for sx in (-1,1):
    tray.append(bx(min(sx*38.0,sx*44.5),max(sx*38.0,sx*44.5),TY0,TY0+8.0,FLOOR_Z0,DECK_Z))      # front deck posts
    tray.append(bx(min(sx*38.0,sx*44.5),max(sx*38.0,sx*44.5),10.0,18.0,FLOOR_Z0,FLOOR_Z0+10.0))  # rear screw boss (dome curves in above)
    tray.append(zcyl(7.0,FLOOR_Z0,DECK_Z,sx*REAR_POST_X,REAR_POST_Y))                             # rear deck posts, inboard
    tray.append(bx(sx*REAR_POST_X-2.0,sx*REAR_POST_X+2.0,TY1-WALL,REAR_POST_Y,FLOOR_Z0,DECK_Z))
    tray.append(zcyl(7.0,FLOOR_Z0,FLOOR_Z0+10.0,sx*HOLE_X,HOLE_FRONT_Y))
    tray.append(bx(min(sx*38.0,sx*HOLE_X),max(sx*38.0,sx*HOLE_X),HOLE_FRONT_Y-3.5,HOLE_FRONT_Y+3.5,FLOOR_Z0,FLOOR_Z0+10.0))
tray=U(tray)
cuts=[ycyl(CELL_D+0.6,PY0,PY1,x,CELL_ZC) for x in CX]                 # cell saddles in the ribs
for sx in (-1,1):
    for y in (HOLE_FRONT_Y,HOLE_REAR_Y):
        cuts.append(zcyl(2.5,FLOOR_Z0-1,FLOOR_Z0+9.0,sx*HOLE_X,y))     # M3 self-tap from below, 9 deep
    cuts.append(zcyl(2.5,DECK_Z-9.0,DECK_Z+1,sx*HOLE_X,TY0+4.0))       # deck screws from above
    cuts.append(zcyl(2.5,DECK_Z-9.0,DECK_Z+1,sx*REAR_POST_X,REAR_POST_Y))
# strap windows: two 22 mm hook-and-loop straps pass under the floor through these and over the pack
for y in (-33.0,-11.0):
    for sx in (-1,1):
        cuts.append(bx(sx*36.0-2.0,sx*36.0+2.0,y-11.5,y+11.5,FLOOR_Z0-1,FLOOR_Z0+FLOOR_T+1))
cuts.append(bx(-8,8,TY1-WALL-1,TY1+1,FLOOR_Z0+FLOOR_T,WALL_TOP+1))   # lead exit, rear wall
tray=D(tray,U(cuts))

# ---- deck: carries two 5 V buck converters (Pololu D36V50F5, 25.4 x 25.4 x 9.5), the HW-391 2S 20 A BMS (48 x 20 x 3) and the charger ----
deck=bx(-44.5,44.5,TY0,18.0,DECK_Z,DECK_Z+DECK_T)
bays={"buck_pi":(-24.0,-43.8),"buck_servo":(24.0,-43.8),"bms":(0.0,-18.6),"charger":(0.0,3.5)}
BAY={"buck_pi":(26.4,26.4),"buck_servo":(26.4,26.4),"bms":(49.0,21.0),"charger":(40.0,20.0)}   # 0.5 mm per side; 1.5 mm rim walls between bays
rims=[]
for k,(x,y) in bays.items():
    w,l=BAY[k]
    r=D(bx(x-w/2-1.5,x+w/2+1.5,y-l/2-1.5,y+l/2+1.5,DECK_Z+DECK_T,DECK_Z+DECK_T+1.5),
        bx(x-w/2,x+w/2,y-l/2,y+l/2,DECK_Z,DECK_Z+DECK_T+3))
    rims.append(r)
deck=U([deck]+rims)
dc=[]
for k,(x,y) in bays.items():
    w,l=BAY[k]
    for dy in (-l/2+8,l/2-8):                                        # zip-tie slot pairs either side of each bay
        for sx in (-1,1):
            dc.append(bx(x+sx*(w/2+4.5)-1.0,x+sx*(w/2+4.5)+1.0,y+dy-2.5,y+dy+2.5,DECK_Z-1,DECK_Z+DECK_T+3))
dc.append(bx(-3.5,3.5,-42,-32,DECK_Z-1,DECK_Z+DECK_T+1))               # pack leads up through the deck, between the buck bays, in front of the BMS
for sx in (-1,1):
    dc.append(zcyl(3.4,DECK_Z-1,DECK_Z+DECK_T+3,sx*HOLE_X,TY0+4.0))
    dc.append(zcyl(3.4,DECK_Z-1,DECK_Z+DECK_T+3,sx*REAR_POST_X,REAR_POST_Y))
deck=D(deck,U(dc))

# ---- keep tray and deck at least 1.5 mm off the skull (approximate offset: shell swept over a 1.5 mm ball) ----
skull=trimesh.load(os.path.join(OUT,"GeneTop_v4_camslots.stl")); skull.apply_translation([-64.8,-61.4,-35.0])
near=bx(-60,60,-70,40,5,60); sk=trimesh.boolean.intersection([skull,near],engine='manifold')
dirs=[np.array(v,float) for v in itertools.product((-1,0,1),repeat=3) if any(v)]
grow=U([sk]+[sk.copy().apply_translation(1.5*d/np.linalg.norm(d)) for d in dirs])
tray=D(tray,grow); deck=D(deck,grow)
# ---- bracket pads: fused to the top of each drive bracket, screw from below ----
def pads(sx):
    ps=[]
    for (y0,y1) in ((HOLE_FRONT_Y-5.0,HOLE_FRONT_Y+5.0),(HOLE_REAR_Y-3.5,HOLE_REAR_Y+3.5)):
        ps.append(bx(min(sx*37.0,sx*47.0),max(sx*37.0,sx*47.0),y0,y1,8.0,14.0))
    return ps
out={}
for s,sx,fn in (("L",-1,"GeneHead_xl330_bracket.stl"),("R",1,"GeneHead_xl330_bracket_R.stl")):
    b=trimesh.load(os.path.join(OUT,fn))
    nb=U([b]+pads(sx))
    nb=D(nb,U([zcyl(3.4,7.0,15.0,sx*HOLE_X,y) for y in (HOLE_FRONT_Y,HOLE_REAR_Y)]))
    out[s]=nb

# mocks
cells=U([ycyl(CELL_D,-55.0,10.0,x,CELL_ZC) for x in CX])
bucks=U([bx(x-12.7,x+12.7,y-12.7,y+12.7,DECK_Z+DECK_T,DECK_Z+DECK_T+9.5) for k,(x,y) in bays.items() if k.startswith("buck")])
bms=bx(-24.0,24.0,-18.6-10.0,-18.6+10.0,DECK_Z+DECK_T,DECK_Z+DECK_T+3.0)
chg=bx(-18,18,3.5-9,3.5+9,DECK_Z+DECK_T,DECK_Z+DECK_T+6)

if __name__=="__main__":
    for nm,m in (("GeneHead_battery_tray.stl",tray),("GeneHead_battery_deck.stl",deck),
                 ("GeneHead_xl330_bracket_v2.stl",out["L"]),("GeneHead_xl330_bracket_R_v2.stl",out["R"]),
                 ("GeneHead_battery_2S2P_MOCK.stl",cells),("GeneHead_power_boards_MOCK.stl",U([bucks,bms,chg]))):
        m.export(os.path.join(OUT,nm))
        print(f"{nm:34s} watertight={m.is_watertight} bodies={m.body_count} vol={m.volume/1000:6.2f}cm3 bounds {np.round(m.bounds,1).tolist()}")
