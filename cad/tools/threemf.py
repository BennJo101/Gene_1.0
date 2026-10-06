import zipfile, numpy as np
CT='''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
RELS='''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
def write_3mf(path, objects):
    """objects: list of (name, trimesh) already placed in plate coordinates (mm)."""
    out=['<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n<resources>']
    for i,(name,m) in enumerate(objects,1):
        v=np.asarray(m.vertices); f=np.asarray(m.faces)
        out.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>')
        out.append("".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a,b,c in v))
        out.append('</vertices><triangles>')
        out.append("".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in f))
        out.append('</triangles></mesh></object>')
    out.append('</resources>\n<build>')
    out.append("".join(f'<item objectid="{i}"/>' for i in range(1,len(objects)+1)))
    out.append('</build>\n</model>')
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",CT); z.writestr("_rels/.rels",RELS); z.writestr("3D/3dmodel.model","".join(out))
