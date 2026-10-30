# Optional copies of the print plates with tree supports already set, for Creality Print (Orca based).
# Reads print/plates/*.3mf as laid out and writes print/plates/tree_supports/<plate>_tree_supports.3mf, with per-object
# settings: organic tree supports on the parts that need them, supports explicitly off on the rest of that plate.
# Plates with nothing that needs supports are not copied. The plain plates stay as they are.
# Tuned to come off easily at 0.2 mm layers: one-layer (0.2) air gap under the part, 0.6 mm off side walls, a sparse
# 2-layer interface on top and none where a branch lands on the part, so the trees snap away and leave little scarring.
import zipfile, re, os, numpy as np, trimesh
from threemf import write_3mf
OUT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PL=os.path.join(os.path.dirname(OUT),"print","plates")
EASY={"enable_support":1,"support_type":"tree(auto)","support_style":"organic","support_threshold_angle":30,
      "support_on_build_plate_only":0,"support_critical_regions_only":0,"support_remove_small_overhang":1,
      "support_top_z_distance":0.2,"support_bottom_z_distance":0.2,"support_object_xy_distance":0.6,
      "support_interface_top_layers":2,"support_interface_bottom_layers":0,"support_interface_spacing":0.5,
      "tree_support_tip_diameter":0.8,"tree_support_branch_diameter_organic":2}
PETG={**EASY,"support_interface_spacing":0.8,"support_object_xy_distance":0.8}   # PETG welds to itself: sparser, further off
SUPPORTED={
 "skull":{**EASY,"brim_type":"outer_only","brim_width":5,"brim_object_gap":0.1,   # 144 mm tall on a 7 mm rim (4054 mm2)
          "seam_position":"back","support_speed":100},      # seam on the back of the head; dome trees ~130 mm tall, go steady
 "jaw":EASY,
 "pi_shelf":{**EASY,"support_interface_top_layers":3,"support_interface_spacing":0.4},   # plate sits 7 mm up on the speaker cradles: flat underside
 "battery_tray":PETG, "battery_deck":PETG,
 "crown_insert":EASY,                                       # the lower step, printed on its side
 "bridge_handle":EASY,                                      # the grip span
 "gpio_flashlight":PETG,                                    # strap and lamp pod
}
OFF={"enable_support":0}

def read_3mf(fn):
    x=zipfile.ZipFile(fn).read("3D/3dmodel.model").decode(); objs=[]
    for name,body in re.findall(r'<object id="\d+" name="([^"]*)"[^>]*>(.*?)</object>',x,re.S):
        v=np.array(re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"',body),float)
        f=np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"',body),int)
        objs.append((name,trimesh.Trimesh(v,f,process=False)))
    return objs

if __name__=="__main__":
    os.makedirs(os.path.join(PL,"tree_supports"),exist_ok=True)
    for fn in sorted(f for f in os.listdir(PL) if f.endswith(".3mf")):
        objs=read_3mf(os.path.join(PL,fn))
        part=[re.sub(r"_\d+$","",n) for n,_ in objs]
        if not any(p in SUPPORTED for p in part): continue
        settings=[{k:str(v) for k,v in SUPPORTED.get(p,OFF).items()} for p in part]
        dst=os.path.join(PL,"tree_supports",fn.replace(".3mf","_tree_supports.3mf"))
        write_3mf(dst,objs,settings)
        back=read_3mf(dst)
        assert [n for n,_ in back]==[n for n,_ in objs] and all(np.allclose(a.vertices,b.vertices,atol=1e-3) and len(a.faces)==len(b.faces) for (_,a),(_,b) in zip(objs,back))
        print(f"{os.path.basename(dst):48s} "+", ".join(f"{p}{' (tree)' if p in SUPPORTED else ''}" for p in part))
