# Head mass and centre-of-mass estimate, and the jaw-servo torque it needs.
#
# Printed parts: mass from the watertight model (volume + surface area) at the given print settings.
# Bought parts: typical catalogue weights (marked ~ where no datasheet figure is at hand), placed at the
# centroid of their fit-check shape. Cables: route length x g/m at each route's centroid.
# Everything in the head frame: pivot axis = X through the origin, face towards -Y, Z up.
#
# Torque is about the jaw pivot, which is the servo axis (the hubs sit on the horns), so it is what
# the two XL330s must hold together.
#   neck mode : skull held, the servos hold the jaw (+ hubs) up against gravity
#   table mode: jaw held flat on the table, the servos hold the whole rest of the head up
# Writes web/mass.json for the sim. With GENE_POWER=powerbank it weighs that setup (bank, its boards, cables_pb.json)
# and writes mass_pb.json instead, for that sim's copy of web/.
import json, os, numpy as np
from parts import load_all, MOVING, POWER

G = 9.81
STALL = 2 * 0.52          # N.m, two XL330-M288-T in tandem at 5 V (ROBOTIS e-manual)
W0 = 103 * 2 * np.pi / 60 # rad/s, no-load speed at 5 V; available torque falls linearly to 0 there
PLA, PETG = 1.24, 1.27    # g/cm3

# (walls mm = perimeter shell thickness incl. top/bottom skin, infill fraction, density)
DEFAULT = (0.9, 0.15, PLA)                  # Creality defaults: 2 walls, 15 %
STRONG  = (1.7, 0.22, PLA)                  # BOM: 4 walls, 20-25 % for jaw, hubs, brackets, handle
SOLID   = (9.0, 1.00, PLA)                  # BOM: jaw pins at 100 % infill
PRINT = {"shell": DEFAULT, "brow": DEFAULT, "barrel_L": DEFAULT, "barrel_R": DEFAULT,
         "jaw": STRONG, "hub_L": STRONG, "hub_R": STRONG, "pin_L": SOLID, "pin_R": SOLID, "handle": STRONG,
         "bracket_L": (1.7, 0.22, PETG), "bracket_R": (1.7, 0.22, PETG),
         "tray": (0.9, 0.15, PETG), "deck": (0.9, 0.15, PETG), "flashlight": (0.9, 0.15, PETG),
         "shelf": DEFAULT, "insert": DEFAULT, "gpio_cover": DEFAULT,
         "carrier_L": DEFAULT, "carrier_R": DEFAULT, "retainer_L": DEFAULT, "retainer_R": DEFAULT,
         "bezel_L": DEFAULT, "bezel_R": DEFAULT, "pupil_L": DEFAULT, "pupil_R": DEFAULT,
         "neck": DEFAULT, "neck_collar": DEFAULT, "neck_base": DEFAULT}

# bought parts, grams
BOUGHT = {
    "servo_L": 18.0, "servo_R": 18.0,             # XL330-M288-T datasheet
    "pi5": 46.0 + 21.0 + 2.0,                     # board, Active Cooler (~), microSD
    "display_L": 25.0, "display_R": 25.0,          # ~ 2.1" round LCD with driver board
    "camera_L": 3.0, "camera_R": 3.0,              # ~ micro camera module
    "speakers": 2 * 8.0,                           # ~ 28 mm speakers
    "battery": 4 * 47.0 + 15.0,                    # 4 x 18650 (30Q 45-48 g) + BMS, nickel, wrap
    "boards": 2 * 7.0 + 5.0,                       # ~ two 5 V 5 A bucks + charger
    "amps": 2.0, "ttl": 9.0, "splitter": 8.0,
    "gpio_plug": 15.0,                             # ~ ribbon + IDC plugs
    "gpio_header": 10.0,                           # ~ flashlight header + LED star, optic, driver, wire
    "usbc_port": 12.0,                             # ~ panel-mount USB-C extension: female end + flange + 30 cm lead
}
if POWER == "powerbank":
    BOUGHT.update({
        "battery": 160.0,                          # INIU Pocket Rocket P50 (INIU listing: 160 g)
        "boards": 2 * 7.0 + 3.0,                   # ~ two 5 V 5 A bucks + 15 V PD trigger board
        "usbc_port": 5.0,                          # ~ female end + flange only: the lead is a routed run in cables_pb.json
    })
HARDWARE = 25.0            # ~ screws, straps, glue; placed at the skull's centroid
CABLE_GPM = {"power": 30.0, "video": 35.0, "data": 10.0, "ribbon": 4.0, "audio": 6.0}   # g/m, incl. plugs
CABLE_PLUGS = {"power": 6.0, "video": 8.0, "data": 2.0, "ribbon": 1.0, "audio": 1.0}      # g per run

# the sim's default build: flashlight fitted, handle and GPIO cover off
LEFT_OFF = {"handle", "gpio_cover"}
NECK = {"neck", "neck_collar", "neck_base", "bearings", "slip_ring"}


def printed(m, spec):
    t, infill, rho = spec
    V = m.volume / 1000.0                          # cm3
    shell = min(V, m.area * t / 1000.0)            # every face gets t of solid walls/skin; thin walls end up solid
    return rho * (shell + (V - shell) * infill)


def main():
    P = load_all()
    items = []                                     # (name, grams, com, group)
    for n, m in P.items():
        if n in LEFT_OFF or n in NECK:
            continue
        grp = "jaw" if n in MOVING else "head"
        if n in PRINT:
            g = printed(m, PRINT[n]); src = "printed"
        elif n in BOUGHT:
            g = BOUGHT[n]; src = "bought"
        else:
            raise SystemExit("no mass for " + n)
        com = m.center_mass if m.is_watertight else m.bounds.mean(axis=0)
        # own inertia about its CoM, X axis, as if its mass were spread evenly through the model (kg m2)
        own = m.moment_inertia[0, 0] / m.volume * g * 1e-9 if m.is_watertight and m.volume > 0 else 0.0
        items.append((n, g, np.asarray(com, float), grp, src, own))
    skull_c = next(i[2] for i in items if i[0] == "shell")
    items.append(("hardware", HARDWARE, skull_c, "head", "bought", 0.0))
    here = os.path.dirname(__file__)
    cab = json.load(open(os.path.join(here, "cables_pb.json") if POWER == "powerbank" else os.path.join(here, "web", "cables.json")))
    for k in cab["cables"]:
        if not k.get("ok") or not k.get("pts"):
            continue
        pts = np.asarray(k["pts"], float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        mid = (pts[1:] + pts[:-1]) / 2
        c = (mid * seg[:, None]).sum(0) / seg.sum()
        g = k["buy"] / 1000.0 * CABLE_GPM[k["kind"]] + CABLE_PLUGS[k["kind"]]
        items.append(("cable: " + k["name"], g, c, "head", "cable", 0.0))

    def agg(sel):
        m = sum(i[1] for i in sel)
        c = sum(i[1] * i[2] for i in sel) / m
        return m, c

    mh, ch = agg([i for i in items if i[3] == "head"])
    mj, cj = agg([i for i in items if i[3] == "jaw"])
    mt, ct = agg(items)

    def inertia(sel):     # about the pivot (X axis through the origin), kg m2
        return sum(i[5] + i[1] / 1000 * ((i[2][1] ** 2 + i[2][2] ** 2) * 1e-6) for i in sel)
    Ih = inertia([i for i in items if i[3] == "head"])
    Ij = inertia([i for i in items if i[3] == "jaw"])
    # speech: the mouth flapping 0-20-0 deg four times a second (a sine, 10 deg amplitude at 4 Hz)
    AMP, HZ = np.radians(10), 4.0
    alpha = AMP * (2 * np.pi * HZ) ** 2           # peak angular acceleration, rad/s2

    # torque about the pivot (X axis). Positive = gravity closing the mouth, which the servos must hold.
    # table: skull tipped back by a about the pivot -> CoM y' = y cos a + z sin a ; the face is at -Y,
    # so a CoM in front of the pivot (y' < 0) pulls the face down onto the jaw.
    # neck: jaw opened by a -> jaw CoM y' = y cos a - z sin a; a jaw CoM in front hangs and pulls it open.
    angs = np.arange(0, 60.5, 0.5)
    r = np.radians(angs)
    tab = -(ch[1] * np.cos(r) + ch[2] * np.sin(r)) / 1000 * mh / 1000 * G
    nk = -(cj[1] * np.cos(r) - cj[2] * np.sin(r)) / 1000 * mj / 1000 * G
    # servo torque needed over one speech cycle, theta = amp*(1-cos wt)/2 ... here amp = full swing
    def cycle(mode, swing_deg, hz):
        I = Ih if mode == "table" else Ij
        t = np.linspace(0, 1 / hz, 400, endpoint=False); w = 2 * np.pi * hz; A = np.radians(swing_deg) / 2
        th = A * (1 - np.cos(w * t)); dth = A * w * np.sin(w * t); ddth = A * w * w * np.cos(w * t)
        tg = np.interp(np.degrees(th), angs, nk if mode == "neck" else -tab)    # gravity, in the opening direction
        need = I * ddth - tg                                                      # servo, opening direction
        motoring = need * dth > 0
        avail = np.where(motoring, STALL * np.clip(1 - np.abs(dth) / W0, 0, 1), STALL)
        return float(np.max(np.abs(need) / avail)), float(np.max(np.abs(need)))
    def max_rate(mode, swing_deg, limit=0.8):
        hz = 0.25
        while hz < 12 and cycle(mode, swing_deg, hz + 0.05)[0] <= limit:
            hz += 0.05
        return round(hz, 2)
    SWING, HZ_SPEECH = 20, 4.0
    speech = {m: dict(zip(("frac", "Nm"), cycle(m, SWING, HZ_SPEECH))) for m in ("neck", "table")}
    rates = {m: max_rate(m, SWING) for m in ("neck", "table")}
    out = {
        "stall": STALL,
        "total_g": round(mt, 1), "head_g": round(mh, 1), "jaw_g": round(mj, 1),
        "com_head": [round(v, 1) for v in ch], "com_jaw": [round(v, 1) for v in cj],
        "com_all": [round(v, 1) for v in ct],
        "printed_g": round(sum(i[1] for i in items if i[4] == "printed"), 1),
        "bought_g": round(sum(i[1] for i in items if i[4] != "printed"), 1),
        "neck_parts_g": round(sum(printed(P[n], PRINT[n]) for n in ("neck", "neck_collar")), 1),
        "I_head": round(Ih, 5), "I_jaw": round(Ij, 5), "speech_alpha": round(alpha, 1),
        "speech": "0-20-0 deg at 4 Hz", "dyn_table_Nm": round(Ih * alpha, 3), "dyn_neck_Nm": round(Ij * alpha, 3),
        "speech_check": {m: {"peak_Nm": round(speech[m]["Nm"], 3), "use": round(speech[m]["frac"], 3), "max_hz_80pct": rates[m]} for m in speech},
        "w0": round(W0, 2),
        "angles": angs.tolist(),
        "table_Nm": [round(v, 4) for v in tab],       # skull on the jaw: servos hold the head up
        "neck_Nm": [round(v, 4) for v in nk],         # on the neck: servos hold the jaw
        "parts": sorted([[i[0], round(i[1], 1), i[3], i[4]] for i in items], key=lambda x: -x[1]),
    }
    json.dump(out, open(os.path.join(here, "mass_pb.json") if POWER == "powerbank" else os.path.join(here, "web", "mass.json"), "w"), indent=1)

    print(f"total {mt:.0f} g  (head {mh:.0f} g, jaw+hubs+pins {mj:.0f} g)   printed {out['printed_g']:.0f} g, bought+cables {out['bought_g']:.0f} g")
    print("head CoM", np.round(ch, 1), " jaw CoM", np.round(cj, 1))
    for a in (0, 10, 20, 30, 33, 40, 50):
        i = int(a * 2)
        print(f"{a:>3} deg  table {tab[i]:6.3f} N.m ({tab[i] / STALL * 100:4.0f} % stall)   neck {nk[i]:6.3f} N.m ({nk[i] / STALL * 100:4.0f} %)")
    print(f"inertia about the pivot: head {Ih*1e4:.1f}, jaw {Ij*1e4:.1f} kg cm2; speech peak accel {alpha:.0f} rad/s2")
    print(f"speech adds {Ih*alpha:.3f} N.m on the table, {Ij*alpha:.3f} N.m on the neck")
    for m in ("neck", "table"):
        print(f"speech 0-{SWING}-0 deg at {HZ_SPEECH} Hz, {m}: peak {speech[m]['Nm']:.3f} N.m, {speech[m]['frac']*100:.0f} % of what the servos can give at that speed; "
              f"max rate within 80 %: {rates[m]} Hz")
    for p in out["parts"][:14]:
        print("  ", p)


if __name__ == "__main__":
    main()
