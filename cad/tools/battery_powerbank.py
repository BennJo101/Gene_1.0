# Secondary power setup: a bought power bank (INIU Pocket Rocket P50, 10000 mAh, 45 W) instead of the 2S2P pack.
# Bank lies across the head (long axis X) on the same bracket pads as the pack tray; its ports face +X (Gene's left),
# where there is a plug zone. One USB-C output -> 15 V PD trigger board -> switch -> fuse -> the two D36V50F5 bucks, as before.
# The charge-port extension plugs into the bank's in/out USB-C. No cells, BMS, charger board, XT30 or balance lead.
# Writes battery_tray_pb.stl, battery_deck_pb.stl, mocks/powerbank_P50.stl, mocks/power_boards_pb.stl (head frame).
import trimesh, numpy as np, os, itertools
from trimesh.creation import cylinder, box
from parts import load_all, to_mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U=lambda ms: trimesh.boolean.union(ms,engine='manifold')
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
def bx(x0,x1,y0,y1,z0,z1):
    b=box(extents=[x1-x0,y1-y0,z1-z0]); b.apply_translation([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]); return b
def zcyl(d,z0,z1,x=0.0,y=0.0,sec=64):
    c=cylinder(radius=d/2,height=z1-z0,sections=sec); c.apply_translation([x,y,(z0+z1)/2]); return c

# ---- bank: INIU P50, 83.6 x 53.1 x 25.4 (spec 3.29 x 2.09 x 1.0 in); check your unit, the bay has 0.5 mm per side ----
BANK_L, BANK_W, BANK_H = 83.6, 53.1, 25.4
FLOOR_Z0, FLOOR_T = 14.0, 6.0               # on the bracket pads (top Z 14); 6 mm so the front M3s have something to bite
BZ0 = FLOOR_Z0+FLOOR_T                      # bank underside
BX0, BX1 = -48.3, -48.3+BANK_L              # ports at the +X end (BX1 = 35.3)
BY0, BY1 = -54.05, -54.05+BANK_W
GAP, WALL, WALL_TOP = 0.5, 2.0, 32.0
TX0, TY0, TY1 = BX0-GAP-WALL, BY0-GAP-WALL, BY1+GAP+WALL
PLUG_X1 = 52.0                              # floor runs on under the plugs (right-angle USB-C, ~12 mm)
DECK_Z = BZ0+BANK_H+0.6                     # deck underside; 0.6 for a 1 mm foam pad squashed on the bank top
DECK_T = 2.5
HOLE_FRONT_Y, HOLE_REAR_Y, HOLE_X = -31.0, 14.0, 41.5      # bracket pad holes, unchanged
POSTS = [(-18.0,TY0-2.5),(-44.0,TY1+2.0),(18.0,TY0-2.5),(30.0,TY1+2.0)]   # deck posts outside the front/rear walls; front pair
                                                                          # at X +/-18, where the lift-in path clears the inner face over the eyes

tray=[bx(TX0,PLUG_X1,TY0,TY1,FLOOR_Z0,BZ0)]
tray+=[bx(TX0,TX0+WALL,TY0,TY1,FLOOR_Z0,WALL_TOP),                       # -X end wall
       bx(TX0,BX1+GAP,TY0,TY0+WALL,FLOOR_Z0,WALL_TOP), bx(TX0,BX1+GAP,TY1-WALL,TY1,FLOOR_Z0,WALL_TOP)]
for x,y in POSTS:
    tray.append(zcyl(7.0,FLOOR_Z0,DECK_Z,x,y))
    tray.append(bx(x-2.0,x+2.0,min(y,TY0+WALL/2) if y<0 else TY1-WALL/2,max(y,TY0+WALL/2) if y<0 else y,FLOOR_Z0,DECK_Z))
for sx in (-1,1):                                                        # rear arms out to the rear pads, low (the dome curves in)
    tray.append(bx(min(sx*37.0,sx*45.0),max(sx*37.0,sx*45.0),TY1-WALL,HOLE_REAR_Y+4.0,FLOOR_Z0,FLOOR_Z0+10.0))
tray=U(tray)
cuts=[]
for sx in (-1,1):
    cuts.append(zcyl(2.5,FLOOR_Z0-1,FLOOR_Z0+9.0,sx*HOLE_X,HOLE_REAR_Y))      # M3 x 12 self-tap from below, 9 deep
    cuts.append(zcyl(2.5,FLOOR_Z0-1,FLOOR_Z0+5.0,sx*HOLE_X,HOLE_FRONT_Y))     # M3 x 10 self-tap from below, 5 deep (floor only)
for x,y in POSTS:
    cuts.append(zcyl(2.5,DECK_Z-9.0,DECK_Z+1,x,y))                          # deck screws from above
cuts.append(bx(-30,20,TY0+WALL+4,TY1-WALL-4,FLOOR_Z0+2.0,BZ0+1))   # lightening pocket from the top (the bank sits on the rim round it)
tray=D(tray,U(cuts))

# ---- deck: two D36V50F5 bucks (25.4 x 25.4 x 9.5) and the PD trigger board, clamps the bank down ----
DX0, DX1 = TX0, BX1+GAP                     # stops at the port end, so the plug zone stays open above
deck=U([bx(DX0,DX1,TY0,TY1,DECK_Z,DECK_Z+DECK_T)]+[zcyl(7.0,DECK_Z,DECK_Z+DECK_T,x,y) for x,y in POSTS]
       +[bx(x-2.0,x+2.0,min(y,TY0) if y<0 else TY1,max(y,TY0) if y<0 else y,DECK_Z,DECK_Z+DECK_T) for x,y in POSTS])
bays={"buck_pi":(-14.5,-38.0),"buck_servo":(14.5,-38.0),"trigger":(0.0,-12.0)}
BAY={"buck_pi":(26.4,26.4),"buck_servo":(26.4,26.4),"trigger":(33.0,15.0)}   # trigger bay fits boards up to 32 x 14
rims=[]
for k,(x,y) in bays.items():
    w,l=BAY[k]
    rims.append(D(bx(x-w/2-1.5,x+w/2+1.5,y-l/2-1.5,y+l/2+1.5,DECK_Z+DECK_T,DECK_Z+DECK_T+1.5),
                  bx(x-w/2,x+w/2,y-l/2,y+l/2,DECK_Z,DECK_Z+DECK_T+3)))
deck=U([deck]+rims)
dc=[]
for k,(x,y) in bays.items():
    w,l=BAY[k]
    for dy in ((-l/2+8,l/2-8) if l>20 else (0.0,)):                         # zip-tie slots either side of each bay
        for sx in (-1,1):
            dc.append(bx(x+sx*(w/2+4.5)-1.0,x+sx*(w/2+4.5)+1.0,y+dy-2.5,y+dy+2.5,DECK_Z-1,DECK_Z+DECK_T+3))
for x,y in POSTS:
    dc.append(zcyl(3.4,DECK_Z-1,DECK_Z+DECK_T+3,x,y))
deck=D(deck,U(dc))

# ---- keep tray and deck 1.5 mm off the skull (shell swept over a 1.5 mm ball, approximately) ----
sk=trimesh.boolean.intersection([load_all()["shell"],bx(-70,70,-75,40,5,75)],engine='manifold')
dirs=[np.array(v,float) for v in itertools.product((-1,0,1),repeat=3) if any(v)]
grow=U([sk]+[sk.copy().apply_translation(1.5*d/np.linalg.norm(d)) for d in dirs])
tray=D(tray,grow); deck=D(deck,grow)

# mocks
bank=bx(BX0,BX1,BY0,BY1,BZ0,BZ0+BANK_H)
plugs=bx(BX1,BX1+14.0,BY0+8.0,BY1-8.0,BZ0+3.0,BZ0+BANK_H-3.0)               # right-angle plugs, positions not known: whole end face
bucks=U([bx(x-12.7,x+12.7,y-12.7,y+12.7,DECK_Z+DECK_T,DECK_Z+DECK_T+9.5) for k,(x,y) in bays.items() if k.startswith("buck")])
trig=bx(-16,16,-12-7,-12+7,DECK_Z+DECK_T,DECK_Z+DECK_T+5.0)

if __name__=="__main__":
    for nm,m in (("battery_tray_pb.stl",tray),("battery_deck_pb.stl",deck),
                 ("mocks/powerbank_P50.stl",U([bank,plugs])),("mocks/power_boards_pb.stl",U([bucks,trig]))):
        m.export(os.path.join(OUT,nm))
        print(f"{nm:30s} watertight={m.is_watertight} bodies={m.body_count} vol={m.volume/1000:6.2f}cm3 bounds {np.round(m.bounds,1).tolist()}")
    # print copies: both print as installed (tray floor down, deck plate down), no supports
    PP=os.path.join(os.path.dirname(OUT),"print","parts")
    for nm,m in (("21_battery_tray_POWERBANK_x1.stl",tray),("22_battery_deck_POWERBANK_x1.stl",deck)):
        p=m.copy(); p.apply_translation(-p.bounds[0]); p.export(os.path.join(PP,nm))
        r=trimesh.load(os.path.join(PP,nm))
        for tol in (0.002,0.005,0.01,0.02):        # STL is float32: merge near-duplicate vertices, as printprep.py does
            if r.is_watertight: break
            t=to_mf(p).simplify(tol).to_mesh(); trimesh.Trimesh(t.vert_properties[:,:3],t.tri_verts).export(os.path.join(PP,nm))
            r=trimesh.load(os.path.join(PP,nm))
        print(f"print/parts/{nm:34s} {np.round(r.extents,1).tolist()}  reloads watertight={r.is_watertight}")
