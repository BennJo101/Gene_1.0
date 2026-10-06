import numpy as np, trimesh, pickle, os
from threemf import write_3mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUTP=os.path.join(OUT,"print")
D=pickle.load(open("printparts.pkl","rb"))
M={k:trimesh.Trimesh(v,f,process=False) for k,(v,f,q) in D.items()}
Q={k:q for k,(v,f,q) in D.items()}
GAP=8.0; BED=250.0
PLATES={
 "Plate1_skull":[["skull"]],
 "Plate2_jaw":[["jaw"]],
 "Plate3_shelf_battery":[["pi_shelf"],["battery_tray","battery_deck"]],
 "Plate5_crown_insert_handle":[["crown_insert"],["bridge_handle"]],
 "Plate6_neck":[["neck"],["neck_base","neck_collar"]],
 "Plate7_gpio_flashlight_cover":[["gpio_flashlight","gpio_cover"]],
 "Plate4_small_parts":[["carrier","carrier","bezel"],["bezel","retainer","retainer"],["bracket_L","bracket_R","hub","hub","pupil_ring","pupil_ring"]],
 "Plate8_bezels_carriers_reprint":[["bezel","bezel"],["carrier","carrier"]],   # reprint: Arducam-sized bezels + carriers with the top slot (Plate 4 was printed before them)
 "Plate9_skull_v7_reprint":[["skull"]],                           # reprint: skull with the camera-slot and display-plug clearances (Plate 1 was printed as v6)
}
# individual oriented STLs (one copy each; qty in the file name)
for k,m in M.items():
    m.export(os.path.join(OUTP,f"{k}_x{Q[k]}.stl"))
summary={}
for pname,rows in PLATES.items():
    placed=[]; y=0.0; W=0
    for row in rows:
        x=0.0; h=0
        for k in row:
            m=M[k].copy(); m.apply_translation([x,y,0]); placed.append((k,m))
            x+=m.extents[0]+GAP; h=max(h,M[k].extents[1])
        W=max(W,x-GAP); y+=h+GAP
    H=y-GAP
    assert W<=BED and H<=BED, (pname,W,H)
    for i,(k,m) in enumerate(placed):
        m.apply_translation([-W/2,-H/2,0])                      # centre the layout on the plate
    # pairwise gap check on the plate
    for i in range(len(placed)):
        for j in range(i+1,len(placed)):
            a,b=placed[i][1].bounds,placed[j][1].bounds
            sep=max(b[0][0]-a[1][0],a[0][0]-b[1][0],b[0][1]-a[1][1],a[0][1]-b[1][1])
            assert sep>=GAP-1e-6,(pname,i,j,sep)
    fn=os.path.join(OUTP,pname+".3mf"); write_3mf(fn,[(f"{k}_{i+1}",m) for i,(k,m) in enumerate(placed)])
    import zipfile, re
    xml=zipfile.ZipFile(fn).read("3D/3dmodel.model").decode(); nobj=len(re.findall("<object ",xml))
    ztop=max(m.bounds[1][2] for _,m in placed)
    summary[pname]=(len(placed),round(W,1),round(H,1),round(ztop,1),round(sum(m.volume for _,m in placed)/1000,1))
    print(f"{pname:30s} {len(placed):2d} objects  footprint {W:6.1f} x {H:6.1f} mm  height {ztop:6.1f}  solid {summary[pname][4]:6.1f} cm3  objects in file={nobj}")
print(sorted(os.listdir(OUTP)))
