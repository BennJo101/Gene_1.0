"""Self-contained copy of the head sim for opening straight from disk: cleaned/head_sim.html.

All JSON the page fetches is inlined as window.__SIM, keyed by file name, and window.fetch is shimmed to serve it.
Rebuild after any export.py run or edit to web/index.html.

Optional: build_local_sim.py <web dir> <out file>. With GENE_POWER=powerbank the page text is relabelled for the
power bank setup (battery_powerbank.py); export that setup's meshes into its own copy of web/ first."""
import os, json, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "web")
html = open(os.path.join(HERE, "web", "index.html"), encoding="utf-8").read()
if os.environ.get("GENE_POWER") == "powerbank":
    RELABEL = [
        ("<title>Gene Head Fit Check</title>", "<title>Gene Head Fit Check, Power Bank</title>"),
        ("<h1>Gene Head Fit Check</h1>", "<h1>Gene Head Fit Check: power bank setup</h1>"),
        ("~3 h battery</span>", "~2 h power bank (INIU P50)</span>"),
        ("<p>The pack sits in the dome just above the twin servos, the lowest place a horizontal 2S2P pack fits. It is held in a tray that screws to pads on top of both servo brackets. A deck on top carries the two 5&nbsp;V converters and the charger board, so the pack, deck and electronics can be built on the bench as one unit.</p>",
         "<p>A bought power bank (INIU Pocket Rocket P50) lies across the dome just above the twin servos, ports at Gene's left. Its tray screws to the same pads on top of both servo brackets. A deck on top clamps the bank down and carries the two 5&nbsp;V converters and a 15&nbsp;V USB-C PD trigger board. There are no cells, BMS or charger board: the charge port plugs straight into the bank.</p>"),
        ("<tr class=\"tot\"><td>From the pack, at 90% converter efficiency</td>", "<tr class=\"tot\"><td>From the bank, at 90% converter efficiency</td>"),
        ("<div><dt>Pack</dt><dd>2S2P 18650, 7.2&nbsp;V nominal</dd></div>", "<div><dt>Bank</dt><dd>INIU P50, 83.6 &times; 53.1 &times; 25.4&nbsp;mm, one USB-C at 15&nbsp;V 3&nbsp;A (45&nbsp;W)</dd></div>"),
        ("<div><dt>Cells</dt><dd>4 &times; 3000&ndash;3500&nbsp;mAh, rated 10&nbsp;A or more (Samsung 30Q, Molicel P28A)</dd></div>", "<div><dt>Capacity</dt><dd>10000&nbsp;mAh</dd></div>"),
        ("<dd class=\"mono\">43&ndash;50 Wh</dd>", "<dd class=\"mono\">about 37 Wh</dd>"),
        ("<dd class=\"mono\">about 3 h</dd>", "<dd class=\"mono\">about 2 h</dd>"),
        ("<dd class=\"mono\">6.2 A at 6.4 V</dd>", "<dd class=\"mono\">2.4 A at 15 V</dd>"),
        ("<div><dt>BMS</dt><dd>2S balancing, 10&nbsp;A continuous</dd></div>", "<div><dt>PD trigger</dt><dd>USB-C, fixed 15&nbsp;V, into the switch and fuse</dd></div>"),
        ("<dd class=\"mono\">about 190 g of cells</dd>", "<dd class=\"mono\">about 160 g bank</dd>"),
        ("Build the pack, tray and deck on the bench first.", "Build the bank, tray and deck on the bench first."),
        ("drive 4 &times; M3&times;12 self-tappers up through the pads from underneath.", "drive the self-tappers up through the pads from underneath: 2 &times; M3&times;12 at the rear, 2 &times; M3&times;10 at the front."),
        ("<p>The pack stays in the head. It needs a charge port through the skull, which isn't cut yet.</p>", "<p>The bank stays in the head and charges through the USB-C port in the back of the skull. Plug and unplug the charger with Gene switched off: the bank's output blips when the charger goes in or out.</p>"),
        ("<span class=\"mono\">battery_tray.stl</span> has three cradle ribs, two strap windows for 22&nbsp;mm hook-and-loop straps, and a lead exit in the rear wall.",
         "<span class=\"mono\">battery_tray_pb.stl</span> has a 6&nbsp;mm floor on the bracket pads, walls on three sides, and an open end under the bank's plugs."),
        ("<span class=\"mono\">battery_deck.stl</span> has two 30&nbsp;&times;&nbsp;46 converter bays and a 40&nbsp;&times;&nbsp;20 charger bay,",
         "<span class=\"mono\">battery_deck_pb.stl</span> has two 26.4 converter bays and a 33&nbsp;&times;&nbsp;15 PD trigger bay,"),
        ('name:"2S2P 18650 pack",', 'name:"Power bank (INIU P50)",'),
        ('name:"Bucks + charger",', 'name:"Bucks + PD trigger",'),
        ('"Converters and charger in their bays"', '"Converters and PD trigger in their bays"'),
        ('"Pack in the ribs, strapped"', '"Bank in its bay, clamped by the deck"'),
        ('battery:"Battery pack + BMS"', 'battery:"Power bank"'),
        ('boards:"Bucks + charger"', 'boards:"Bucks + PD trigger"'),
        ("\"Sit the 2S2P pack in the tray's cradle ribs and strap it down through the two strap windows.\"",
         "\"Slide the power bank into the tray, ports to the open +X end, with a 1&nbsp;mm foam pad on top.\""),
        ("\"Screw the deck onto the tray posts from above, 4 &times; M3&times;10.\"", "\"Screw the deck onto the tray posts from above, 4 &times; M3&times;10. It clamps the bank down.\""),
        ("Zip-tie the two 5&nbsp;V bucks and the USB-C charger into their bays on the deck. Set the Pi's buck to 5.1&nbsp;V. The pack leads leave through the tray's rear wall.",
         "Zip-tie the two 5&nbsp;V bucks and the 15&nbsp;V PD trigger into their bays on the deck, and plug the trigger into the bank's USB-C output."),
        ('hw:["4 &times; M3&times;10 self-tapping","2 &times; hook-and-loop strap, 20&ndash;22&nbsp;mm","zip ties"]', 'hw:["4 &times; M3&times;10 self-tapping","1&nbsp;mm foam pad","zip ties"]'),
    ]
    for a, b in RELABEL:
        assert html.count(a) == 1, "relabel text not found: " + a[:60]
        html = html.replace(a, b)
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
fn = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(HERE), "head_sim.html")
open(fn, "w", encoding="utf-8").write(out)
print(f"{fn}: {len(data)} data files inlined, {os.path.getsize(fn) / 1e6:.1f} MB")
