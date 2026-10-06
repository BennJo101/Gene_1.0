# Display carrier v3: wide top + bottom slots, leaving only a side wall on the left and right, each as wide as the
# old v2 slot (2 x +/-15.75 deg). Front lip ring untouched, so the display is still framed all round.
# v2 (narrow top slot) kept as retired/carrier_v2_before_wide_slots.stl.
# Display carrier v2: the original cup (aperture 53.80 lip, 56.00 x 10 pocket, OD 60.50 x 12) with a flex slot
# cut at the TOP to mirror the one at the bottom, so the driver board's HDMI/USB side has the same room as the
# LCD flex side. Same part both eyes. Source: retired/carrier_v1_before_topslot.stl (carrier frame: axis on Y,
# centred on X 0 / Z 0 before placement).
import trimesh, numpy as np, os
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
car=trimesh.load(os.path.join(OUT,"tools","retired","carrier_v1_before_topslot.stl"))
y0,y1=car.bounds[0][1],car.bounds[1][1]                 # -96.1 .. -84.1
# measure the bottom slot: angular half-width at the wall and where it starts along Y
r=29.2
def solid(p): return car.contains(np.atleast_2d(p))
ang=[a for a in np.arange(150,210.01,0.5) if not solid([r*np.sin(np.radians(a)),y1-2,r*np.cos(np.radians(a))])[0]]
ys=np.arange(y0+0.05,y1-0.05,0.1); ins=solid(np.stack([np.zeros_like(ys),ys,np.full_like(ys,-r)],1)); ystart=ys[~ins].min()
half=(max(ang)-min(ang))/2+0.25
print(f"bottom slot: +/-{half:.2f} deg, from Y {ystart:.2f} to the back face {y1:.2f}")
# top slot = the bottom slot's cutter mirrored: the carrier minus its mirror image's material gives the bottom slot,
# so cut the same sector at the top
n=32; As=np.radians(np.linspace(-half,half,n)); pts=[]
for rr in (0.0,31.0):
    for a in As: pts.append([rr*np.sin(a),0,rr*np.cos(a)])
pts=np.array(pts); V=np.vstack([pts+[0,ystart,0],pts+[0,y1+0.5,0]])
cut=trimesh.convex.convex_hull(V)
new=D(car,cut)
# v3: widen both slots so each side wall keeps the old slot's width: slot half-angle = 90 - half
wide=90.0-half; As=np.radians(np.linspace(-wide,wide,n)); pts=[]
for rr in (0.0,31.0):
    for a in As: pts.append([rr*np.sin(a),0,rr*np.cos(a)])
pts=np.array(pts)
for sgn in (1,-1):                                       # top and bottom
    P=pts*[1,1,sgn]; V=np.vstack([P+[0,ystart,0],P+[0,y1+0.5,0]])
    new=D(new,trimesh.convex.convex_hull(V))
print(f"v3 slots: +/-{wide:.2f} deg top and bottom, side walls {2*half:.1f} deg each")
print(f"carrier v3: watertight={new.is_watertight} bodies={new.body_count} vol {new.volume/1000:.2f} cm3 (was {car.volume/1000:.2f})")
new.export(os.path.join(OUT,"GeneHead_eye_display_carrier.stl"))
