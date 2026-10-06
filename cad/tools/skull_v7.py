# Skull v7 = v6 + clearances for the parts actually bought (Amazon, 2026-09-30 order):
#  * Arducam B0066 mini OV5647 camera: 6 mm wide flex, rigid 16 x 30 mm connector end that can't bend.
#    The 14 x 4 ribbon slot in each barrel's inboard wall becomes 26.5 x 7.5 so the rigid end passes
#    flat (width along the barrel axis) and the 6 mm ribbon lies in it without folding.
#  * TekGroAml 2.1" round LCD + its 57 mm round HDMI driver board: the board sits behind the display
#    with the LCD flex at the bottom, so the mini-HDMI and micro-USB plugs point straight up.
#    The barrel gets a top window mirroring the existing bottom one (+/-37.5 deg), and the skull's
#    inner wall above each eye is pocketed for the plugs, keeping >= SKIN mm of outer wall.
import trimesh, numpy as np, os
from trimesh.creation import box
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIFT=np.array([-64.8,-61.4,-35.0])                         # file frame -> head frame (as in parts.py)
AXL,AXR,ZC=-60.96,60.95,-0.32
D=lambda a,b: trimesh.boolean.difference([a,b],engine='manifold')
U=lambda ms: trimesh.boolean.union(ms,engine='manifold')

# ---- camera ribbon slot (inboard wall, centred on the bezel spoke) ----
SLOT_Y0,SLOT_Y1=-114.0,-87.5     # was -111.5..-96.0 (14 mm); 26.5 mm now. Front of the carrier is -96.1,
                                 # so 17.9 mm stays open even with the carrier glued in
SLOT_H=7.5                       # was 4.0; Arducam flex is 6.0 wide
SLOT_R0,SLOT_R1=27.0,40.0        # from inside the bore (through the ridge notch) well past the 34.25 wall OD
# ---- top window + plug pocket ----
WIN_A=37.5                       # half-angle, same as the bottom window
WIN_Y0,WIN_Y1=-96.0,-58.0        # bottom window starts at -96; run past the barrel end (-61.5)
POCKET_Y0=-88.0                  # plugs sit behind the display carrier (ends -84.1); deep pocket from here back
R_IN=29.5                        # inside the 30.3 bore, so the cutter's inner face is in air
R_CAP_FRONT, R_CAP=36.0, 54.0    # over the carrier only open the barrel wall; behind it up to 54 (25 mm above the board edge)
SKIN=3.0                         # outer wall kept everywhere
DY, DA = 0.5, 0.5                # heightfield grid (mm, deg)

def rays_last_exit(sh, ax, Ys, As):
    """for each (Y, angle) cast a ray from the barrel axis outward; return the radius where it finally
    leaves the solid (the exterior), and the radius where the barrel wall ends (first exit)"""
    O=[];Dd=[]
    for y in Ys:
        for a in As:
            r=np.radians(a); O.append([ax,y,ZC]); Dd.append([np.sin(r),0,np.cos(r)])
    O=np.array(O); Dd=np.array(Dd)
    loc,idx,_=sh.ray.intersects_location(O,Dd,multiple_hits=True)
    dist=np.linalg.norm(loc-O[idx],axis=1)
    last=np.zeros(len(O)); first=np.full(len(O),np.inf); cnt=np.zeros(len(O),int)
    for i,dd in zip(idx,dist):
        if dd<R_IN: continue
        last[i]=max(last[i],dd); first[i]=min(first[i],dd); cnt[i]+=1
    return last.reshape(len(Ys),len(As)), cnt.reshape(len(Ys),len(As))

def heightfield_cutter(ax, Ys, As, Rout):
    """closed solid between r=R_IN and r=Rout(Y,a) over the Y x angle grid, around the barrel axis"""
    nY,nA=Rout.shape
    def P(r,y,a): a=np.radians(a); return [ax+r*np.sin(a), y, ZC+r*np.cos(a)]
    V=[];idx=lambda s,i,j: s*nY*nA+i*nA+j
    for s in (0,1):
        for i,y in enumerate(Ys):
            for j,a in enumerate(As):
                V.append(P(R_IN if s==0 else Rout[i,j], y, a))
    F=[]
    for i in range(nY-1):
        for j in range(nA-1):
            a,b,c,d=idx(1,i,j),idx(1,i,j+1),idx(1,i+1,j+1),idx(1,i+1,j)
            F+= [[a,b,c],[a,c,d]]                                     # outer
            a,b,c,d=idx(0,i,j),idx(0,i,j+1),idx(0,i+1,j+1),idx(0,i+1,j)
            F+= [[a,c,b],[a,d,c]]                                     # inner
    for i in range(nY-1):                                             # angle-min / angle-max walls
        for j,sg in ((0,1),(nA-1,-1)):
            a,b,c,d=idx(0,i,j),idx(0,i+1,j),idx(1,i+1,j),idx(1,i,j)
            F+= [[a,b,c],[a,c,d]] if sg>0 else [[a,c,b],[a,d,c]]
    for j in range(nA-1):                                             # Y-min / Y-max walls
        for i,sg in ((0,1),(nY-1,-1)):
            a,b,c,d=idx(0,i,j),idx(0,i,j+1),idx(1,i,j+1),idx(1,i,j)
            F+= [[a,b,c],[a,c,d]] if sg>0 else [[a,c,b],[a,d,c]]
    m=trimesh.Trimesh(np.array(V),np.array(F),process=True)
    trimesh.repair.fix_normals(m)
    if m.volume<0: m.invert()
    assert m.is_volume, ("cutter not a volume", m.is_watertight, m.is_winding_consistent)
    assert m.is_watertight, "cutter not watertight"
    return m

def exterior_tree(sh):
    """KD-tree of dense points on the head's OUTSIDE surface: faces whose normal ray escapes to infinity once
    the open bottom, the crown slot (filled by the insert) and the eye bores (filled by the displays) are capped"""
    from scipy.spatial import cKDTree
    slab=box(extents=[400,400,6]); slab.apply_translation([0,0,-56.0])
    crown=box(extents=[34,130,30]); crown.apply_translation([1.25,-48,80])
    caps=[]
    for ax in (AXL,AXR):
        c=trimesh.creation.cylinder(radius=30.0,height=4,sections=64)
        c.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])); c.apply_translation([ax,-95.0,ZC]); caps.append(c)
    probe=trimesh.util.concatenate([sh,slab,crown]+caps)
    hit=probe.ray.intersects_any(sh.triangles_center+sh.face_normals*0.02, sh.face_normals)
    tc=sh.triangles_center
    keep=(~hit)&(np.abs(tc[:,0])>20)&(tc[:,1]>-110)&(tc[:,1]<-45)&(tc[:,2]>5)      # only the region near the pockets
    ext=sh.submesh([np.where(keep)[0]],append=True)
    pts,_=trimesh.sample.sample_surface_even(ext,400000)
    pts=np.vstack([pts,ext.vertices])
    return cKDTree(pts), float(np.sqrt(ext.area/len(pts)))

def build():
    raw=trimesh.load(os.path.join(OUT,"GeneTop_v6_neck.stl"))
    sh=raw.copy(); sh.apply_translation(SHIFT)
    v0=sh.volume
    cuts=[]; report={}
    tree,spacing=exterior_tree(sh)
    for side,ax in (("L",AXL),("R",AXR)):
        inb=1 if ax<0 else -1
        # ribbon slot
        x0,x1=sorted([ax+inb*SLOT_R0, ax+inb*SLOT_R1])
        s=box(extents=[x1-x0, SLOT_Y1-SLOT_Y0, SLOT_H]); s.apply_translation([(x0+x1)/2,(SLOT_Y0+SLOT_Y1)/2,ZC]); cuts.append(s)
        # top window / pocket
        Ys=np.arange(WIN_Y0,WIN_Y1+1e-6,DY); As=np.arange(-WIN_A,WIN_A+1e-6,DA)
        last,cnt=rays_last_exit(sh,ax,Ys,As)
        cap=np.where(Ys[:,None]<POCKET_Y0,R_CAP_FRONT,R_CAP)*np.ones_like(last)
        lim=np.minimum(last-SKIN,cap)
        # radial depth overstates the wall where the outside surface is oblique (the crease where the skull side
        # meets the barrel top), so walk each ray out and stop where the TRUE distance to the outside drops below SKIN
        rr=np.arange(30.0,R_CAP+0.01,0.25)
        for i,y in enumerate(Ys):
            a=np.radians(As)[:,None]
            P=np.stack([ax+rr[None,:]*np.sin(a), np.full((len(As),len(rr)),y), ZC+rr[None,:]*np.cos(a)],-1)
            dd,_=tree.query(P.reshape(-1,3)); dd=dd.reshape(len(As),len(rr))-spacing     # conservative
            for j in range(len(As)):
                bad=np.where(dd[j]<SKIN)[0]
                if len(bad): lim[i,j]=min(lim[i,j], rr[bad[0]]-0.25)
        ok=(lim>=34.6)&(cnt>0)                                        # only where the whole barrel wall can go and SKIN still stays
        lim=np.where(ok,lim,R_IN+0.1)
        # erode one cell so the cutter's slanted faces between grid points never reach into the skin
        from scipy.ndimage import minimum_filter
        lim=minimum_filter(lim,size=3,mode='nearest')
        lim=np.maximum(lim,R_IN+0.1)
        cuts.append(heightfield_cutter(ax,Ys,As,lim))
        openA=As[(lim>34.3).any(0)]
        report[side]=(openA.min() if len(openA) else None, openA.max() if len(openA) else None)
    new=D(sh,U(cuts))
    bodies=[b for b in new.split(only_watertight=False) if abs(b.volume)>1.0]
    new=bodies[0] if len(bodies)==1 else U(bodies)
    print(f"skull v7: removed {(v0-new.volume)/1000:.2f} cm3, bodies={len(bodies)}, watertight={new.is_watertight}, vol {new.volume/1000:.1f} cm3")
    for k,(a0,a1) in report.items(): print(f"   {k} eye top window spans {a0:+.1f} .. {a1:+.1f} deg (+ = towards +X)")
    out=new.copy(); out.apply_translation(-SHIFT)
    out.export(os.path.join(OUT,"GeneTop_v7_skull.stl"))
    return sh,new

if __name__=="__main__":
    build()
