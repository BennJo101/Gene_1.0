import numpy as np, trimesh, json, os
from trimesh.creation import box
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
U = lambda ms: trimesh.boolean.union(ms, engine='manifold')


def bx(x0, x1, y0, y1, z0, z1):
    b = box(extents=[x1 - x0, y1 - y0, z1 - z0]); b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); return b


# Pi 5 on the v6 shelf: plate top Z -37, 4 mm standoffs, board centred (0,-29).
# Turned so the GPIO header runs along the FRONT long edge (towards the eyes) and USB/Ethernet sit at the -X end.
PZ = -37.0 + 4.0
board = bx(-42.5, 42.5, -57.0, -1.0, PZ, PZ + 1.6)
stack = bx(-42.5, 42.5, -57.0 + 9.0, -1.0, PZ + 1.6, PZ + 1.6 + 14.0)          # cooler etc., kept clear of the header strip
ports = bx(-42.5 - 2.5, -42.5 - 2.5 + 21.5, -57.0 + 1.5, -1.0 - 1.5, PZ + 1.6, PZ + 1.6 + 16.0)
# 2x20 header: 50.8 long along X, pin rows 3.5 mm in from the front edge; header spans 7.1..57.9 mm from the non-USB end
hx0, hx1 = 42.5 - 57.9, 42.5 - 7.1
header = bx(hx0, hx1, -57.0 + 3.5 - 2.54, -57.0 + 3.5 + 2.54, PZ + 1.6, PZ + 1.6 + 8.5)
idc_f = bx((hx0 + hx1) / 2 - 28.0, (hx0 + hx1) / 2 + 28.0, -57.0 + 3.5 - 4.6, -57.0 + 3.5 + 4.6, PZ + 1.6 + 2.5, PZ + 1.6 + 2.5 + 9.2)   # ribbon's female IDC on the header
pi = U([board, stack, ports, header])
# GPIO 1-to-2 splitter on the header: its lower socket takes the Pi's pins, the upper header carries the
# ribbon's female IDC (to the crown); the side header feeds the I2S amp. The ribbon plug now sits on top.
HZ = PZ + 1.6 + 8.5                                   # top of the Pi's header pins
splitter = bx((hx0 + hx1) / 2 - 28.0, (hx0 + hx1) / 2 + 28.0, -57.0 + 3.5 - 5.0, -57.0 + 3.5 + 5.0, HZ, HZ + 12.0)      # socket rides on the pin tops
idc_top = bx((hx0 + hx1) / 2 - 28.0, (hx0 + hx1) / 2 + 28.0, -57.0 + 3.5 - 4.6, -57.0 + 3.5 + 4.6, HZ + 12.0, HZ + 21.2)
U([splitter, idc_top]).export(os.path.join(OUT, "mocks/gpio_splitter.stl"))
print(f"splitter + ribbon IDC: Z {HZ:.1f}..{HZ + 21.2:.1f}")
# DYNAMIXEL TTL interface (U2D2 size) on the left shelf wing, resting on the two skull nut posts there (tops Z -31), and one MAX98357A amp centred on the shelf
# between the speakers (mono: both speakers in parallel on its output)
bx(-69.0, -51.0, -58.0, -10.0, -30.9, -16.3).export(os.path.join(OUT, "mocks/ttl_interface.stl"))
bx(-9.0, 9.0, -87.0, -69.0, -36.9, -33.9).export(os.path.join(OUT, "mocks/i2s_amp.stl"))
pi.export(os.path.join(OUT, "mocks/pi5.stl"))
print(f"Pi mock: GPIO header X {hx0:.1f}..{hx1:.1f} at Y {-57 + 3.5:.1f}; ribbon IDC top Z {PZ + 1.6 + 2.5 + 9.2:.1f}")

# Male IDC plug of the ribbon, seated in the crown insert
m = json.load(open("crown_meta.json"))
L_, W_, H_, P_ = m["IDC"]; CX, GYC = m["CX"], m["GYC"]
plug = bx(CX - W_ / 2, CX + W_ / 2, GYC - L_ / 2, GYC + L_ / 2, m["BODY_BOT"], m["BODY_TOP"])
pins = bx(CX - 2.54, CX + 2.54, GYC - 25.4, GYC + 25.4, m["BODY_TOP"], m["BODY_TOP"] + P_)   # pin field as a block
U([plug, pins]).export(os.path.join(OUT, "mocks/gpio_plug.stl"))
print(f"GPIO plug mock: body Z {m['BODY_BOT']:.1f}..{m['BODY_TOP']:.1f}, pins to {m['BODY_TOP'] + P_:.1f}")
