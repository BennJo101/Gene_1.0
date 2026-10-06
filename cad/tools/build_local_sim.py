"""Self-contained copy of the head sim for opening straight from disk: cleaned/GeneHead_sim.html.

All JSON the page fetches is inlined as window.__SIM, keyed by file name, and window.fetch is shimmed to serve it.
Rebuild after any export.py run or edit to web/index.html."""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
data = {}
for p in sorted(glob.glob(os.path.join(WEB, "*.json"))):
    data[os.path.basename(p)] = json.load(open(p, encoding="utf-8"))
shim = ("<script>window.__SIM=" + json.dumps(data, separators=(",", ":")) + ";"
        "(function(){var f0=window.fetch;window.fetch=function(u){var k=String(u).replace(/^\.\//,'').split('?')[0];"
        "if(window.__SIM[k])return Promise.resolve({ok:true,status:200,json:function(){return Promise.resolve(window.__SIM[k]);}});"
        "return f0.apply(this,arguments);};})();</script>\n")
anchor = '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'
assert html.count(anchor) == 1, "three.js tag not found"
out = '<meta charset="utf-8">\n' + html.replace(anchor, shim + anchor)
fn = os.path.join(os.path.dirname(HERE), "GeneHead_sim.html")
open(fn, "w", encoding="utf-8").write(out)
print(f"{fn}: {len(data)} data files inlined, {os.path.getsize(fn) / 1e6:.1f} MB")
