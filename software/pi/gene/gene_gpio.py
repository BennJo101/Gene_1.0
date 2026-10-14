"""Gene's GPIO pins, by voice.

  "turn on pin 17" / "set GPIO 22 low" / "read pin 4" / "toggle pin 17"
  "change pin 17" (flips it) / "make pin 4 an input with pull-up" / "pull pin 4 down" / "let pin 4 float"
  "turn on physical pin 12"            - header positions 1-40 ("physical", "header" or "board" pin)
  "play a song on physical pin 12"     - a tune as a square wave, for a buzzer or small speaker
  "play happy birthday through the pins" / "beep pin 18" / "stop the music"

Plain pin numbers are BCM GPIO numbers (GPIO17 is physical pin 11). Saying "physical" switches to header
positions, and power and ground positions are explained instead of switched ("physical pin 6 is ground").
On/off uses the `pinctrl` tool, so an output stays set after the command finishes.

Tunes: a software square wave through gpiod, on any pin. If RP1 PWM0 is ever enabled (config.txt
`dtoverlay=pwm,pin=18,func=2` - not set today, and GPIO18 is meant for the I2S amps), GPIO 12, 13, 18 and 19
use hardware PWM instead, for cleaner tones. Today's /sys/class/pwm/pwmchip0 is PWM1, which runs the fan.
A pin is refused only if something is using it: the HAT ID EEPROM (0, 1), or any pin set to another function
(I2C on 2/3, I2S once the speaker amps are fitted, ...).
"""
import json, os, re, subprocess, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state", "gpio.json")
PWM0_DEVICE = "1f00098000.pwm"   # RP1 PWM0. (1f0009c000.pwm is PWM1, the cooling fan's - never touch it)
PWM = {12: (0, "a0"), 13: (1, "a0"), 18: (2, "a3"), 19: (3, "a3")}    # BCM pin -> (PWM0 channel, alt function)
ID_PINS = {0, 1}
VOICE_PINS = {18: "its bit clock", 19: "its left-right clock", 20: "its spare data line", 21: "its data line"}
# GPIO 18-21 (physical 12, 35, 38, 40) are Gene's I2S voice (MAX98357A amp): never driven by voice, even if the
# I2S overlay ever fails to load and they read as plain inputs (asked 2026-10-08: "isolate the GPIO just for voice").

# 40-pin header: physical position -> BCM GPIO number, or a name for power and ground
HEADER = {1: "3.3 volt power", 2: "5 volt power", 3: 2, 4: "5 volt power", 5: 3, 6: "ground", 7: 4, 8: 14,
          9: "ground", 10: 15, 11: 17, 12: 18, 13: 27, 14: "ground", 15: 22, 16: 23, 17: "3.3 volt power", 18: 24,
          19: 10, 20: "ground", 21: 9, 22: 25, 23: 11, 24: 8, 25: "ground", 26: 7, 27: 0, 28: 1, 29: 5, 30: "ground",
          31: 6, 32: 12, 33: 13, 34: "ground", 35: 19, 36: 16, 37: 26, 38: 20, 39: "ground", 40: 21}
PHYSICAL = {b: p for p, b in HEADER.items() if isinstance(b, int)}

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
       "seventeen eighteen nineteen".split()
WORDS = {w: i for i, w in enumerate(ONES)}
for tens, base in (("twenty", 20), ("thirty", 30), ("forty", 40)):
    WORDS[tens] = base
    for i, w in enumerate(ONES[1:10], 1):
        WORDS[f"{tens} {w}"] = WORDS[f"{tens}-{w}"] = base + i
NUM = r"(?:\d{1,2}|" + "|".join(sorted(map(re.escape, WORDS), key=len, reverse=True)) + r")\b"
# "pin 6", "pins six and twelve", "GPIO 18", "physical pin 6, 12", "header pins 11 & 13"
PINS = re.compile(r"\b(?:(physical|header|board)\s+)?(?:gpio|g\.?p\.?i\.?o\.?|pins?)\s*(?:numbers?\s+)?"
                  r"(" + NUM + r"(?:\s*(?:,|and|&|\+)\s*(?:pins?\s+)?" + NUM + r")*)", re.I)
TOGGLE = re.compile(r"\b(?:toggle|flip)\b", re.I)
CHANGE = re.compile(r"\b(?:change|switch|swap|invert|reverse)\b(?!\s+(?:over\s+)?to\b)", re.I)   # with no on/off said: flip it
INPUT = re.compile(r"\b(?:in\s?put|float\w*|no\s+pull)\b", re.I)
PULL_UP = re.compile(r"\bpull(?:ed)?[\s-]*(?:\S+\s+){0,3}?(?:up|high)\b|\bpull[\s-]*ups?\b", re.I)
PULL_DOWN = re.compile(r"\bpull(?:ed)?[\s-]*(?:\S+\s+){0,3}?(?:down|low)\b|\bpull[\s-]*downs?\b", re.I)
READ = re.compile(r"\b(?:read|check|state|status|level|what(?:'s| is))\b|^\W*(?:is|are|tell me)\b", re.I)
PLAY = re.compile(r"\b(?:play|sing|beep|buzz|music|song|tune|melody|tone|jingle)\b", re.I)
STOP = re.compile(r"\b(?:stop|quiet|enough|silence|shut\s+up|turn\s+(?:it|that)\s+off)\b", re.I)
ABOUT_PINS = re.compile(r"\b(?:pins?|gpio|buzzer|speaker|piezo)\b", re.I)

# Public-domain tunes: (note, beats); "R" is a rest. Notes like "C4", "F#5".
TUNES = {
    "twinkle": ("Twinkle Twinkle Little Star", 100, "C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2 "
                "G4 G4 F4 F4 E4 E4 D4:2 G4 G4 F4 F4 E4 E4 D4:2 C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2"),
    "birthday": ("Happy Birthday", 110, "C4:.75 C4:.25 D4 C4 F4 E4:2 C4:.75 C4:.25 D4 C4 G4 F4:2 C4:.75 C4:.25 "
                 "C5 A4 F4 E4 D4:2 A#4:.75 A#4:.25 A4 F4 G4 F4:2"),
    "ode": ("Ode to Joy", 120, "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4:1.5 D4:.5 D4:2 "
            "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:.5 C4:2"),
    "mary": ("Mary Had a Little Lamb", 120, "E4 D4 C4 D4 E4 E4 E4:2 D4 D4 D4:2 E4 G4 G4:2 "
             "E4 D4 C4 D4 E4 E4 E4 E4 D4 D4 E4 D4 C4:4"),
    "jingle": ("Jingle Bells", 140, "E4 E4 E4:2 E4 E4 E4:2 E4 G4 C4:1.5 D4:.5 E4:4 F4 F4 F4:1.5 F4:.5 "
               "F4 E4 E4 E4:.5 E4:.5 E4 D4 D4 E4 D4:2 G4:2"),
    "scale": ("a scale", 160, "C4 D4 E4 F4 G4 A4 B4 C5:2 R C5 B4 A4 G4 F4 E4 D4 C4:2"),
    "beep": ("a beep", 120, "A5:1"),
}
TUNE_WORDS = [("birthday", "birthday"), ("twinkle", "twinkle"), ("star", "twinkle"), ("ode|joy|beethoven", "ode"),
              ("mary|lamb", "mary"), ("jingle|christmas", "jingle"), ("scale", "scale"), ("beep|buzz|tone", "beep")]
SEMI = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

_player = {"thread": None, "stop": threading.Event()}


def _num(s):
    return int(s) if s.isdigit() else WORDS[s.lower()]


def _freq(note):
    m = re.fullmatch(r"([A-G]#?)(\d)", note)
    return 440.0 * 2 ** ((SEMI[m.group(1)] + 12 * (int(m.group(2)) + 1) - 69) / 12)


CONTEXT_FRESH = 180         # s a pin conversation stays live for follow-ups ("what about pin 12?", "try again")
# "I'm not hearing anything", "nothing is coming through", "it doesn't work"
COMPLAINT = re.compile(r"(?:\b(?:not|nothing|no|cannot)\b|n't\b)[^.?!]*\b(?:hear\w*|sound\w*|work\w*|coming|playing|"
                       r"happen\w*|music|noise)\b", re.I)
AGAIN = re.compile(r"\b(?:again|retry|one\s+more\s+time|replay|once\s+more)\b", re.I)
# only a real command turns a pin on: "turn on pin 17", "pin 17 on", "set pin 17 high" - not "nothing on pin 12"
ON = re.compile(r"\b(?:turn|switch|set|put|drive|power)\b[^.?!]{0,30}?\b(?:on|high|up)\b|\bhigh\b|"
                r"\b(?:pin|gpio)\s+\S+\s+on\b|\bon\s*[.!]?\s*$", re.I)
OFF = re.compile(r"\b(?:turn|switch|set|put|drive|power)\b[^.?!]{0,30}?\b(?:off|low|down)\b|\blow\b|"
                 r"\b(?:pin|gpio)\s+\S+\s+off\b|\boff\s*[.!]?\s*$", re.I)


def _state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {}


def _save_state(**kw):
    st = _state(); st.update(kw)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f)


def _last_pins():
    return _state().get("pins", [])


def _recent():
    """The last pin request if it was in the last few minutes, else None."""
    st = _state()
    return st if st.get("action") and time.time() - st.get("time", 0) < CONTEXT_FRESH else None


def _pin_numbers(heard):
    """Every pin mentioned -> (BCM pins, notes about power/ground pins, physical?).
    Once someone says "physical", plain "pin 12" keeps meaning the header position until they say "GPIO 12"."""
    physical_mode = _state().get("mode") == "physical"
    pins, other, physical_any = [], [], False
    for m in PINS.finditer(heard):
        word = m.group(0).lower()
        if m.group(1) or re.search(r"\b(?:physical|header|board)\b", heard[max(0, m.start() - 25):m.start()], re.I):
            physical = True
        elif re.match(r"(?:bcm|gpio|g\.?p\.?i\.?o\.?)\s*(?:number\s+)?\d|(?:bcm|gpio)\s+(?!pin)", word):
            physical = False            # "GPIO 18" / "GPIO eighteen" means the BCM number
        else:
            physical = physical_mode    # "pin 12", "GPIO pin 12"
        physical_any |= physical
        for n in (_num(x) for x in re.findall(NUM, m.group(2), re.I)):
            if not physical:
                pins.append(n)
            elif HEADER.get(n) is None:
                other.append(f"there's no physical pin {n}, the header has 40")
            elif isinstance(HEADER[n], str):
                other.append(f"physical pin {n} is {HEADER[n]}")
            else:
                pins.append(HEADER[n])
    if physical_any:
        _save_state(mode="physical")
    elif re.search(r"\b(?:bcm|gpio)\s*(?:number\s+)?" + NUM, heard, re.I) and pins:   # bare "GPIO 18"
        _save_state(mode="bcm")
    return list(dict.fromkeys(pins)), other, physical_any


def wants(heard):
    """Returns a request dict if `heard` is a GPIO command, else None:
    {"action": on|off|toggle|read|input|play|stop, "pins": [BCM...], "other": ["physical pin 6 is ground", ...],
     "tune": key, "retry": bool, "pull": up|down|none (input only)}"""
    playing = _player["thread"] is not None and _player["thread"].is_alive()
    recent = _recent()
    if not PINS.search(heard):
        if playing and STOP.search(heard):
            return {"action": "stop", "pins": [], "other": []}
        # "play a song through them", "play happy birthday on the speaker"
        if PLAY.search(heard) and (ABOUT_PINS.search(heard) or re.search(r"\bthrough\s+(?:them|it)\b", heard, re.I)) \
                and not re.search(r"\b(?:radio|spotify|song\s+called)\b", heard, re.I):
            return {"action": "play", "pins": _last_pins(), "other": [], "tune": _tune(heard)}
        # "I don't hear anything" / "try again", right after a pin request
        if recent and (COMPLAINT.search(heard) or AGAIN.search(heard)) and recent["action"] in ("play", "on", "toggle"):
            return {"action": recent["action"], "pins": recent.get("pins", []), "other": [],
                    "tune": recent.get("tune", "twinkle"), "retry": True}
        return None
    pins, other, _ = _pin_numbers(heard)
    req = {"pins": pins, "other": other, "tune": _tune(heard), "retry": False}
    if PLAY.search(heard):
        return {**req, "action": "play"}
    if playing and STOP.search(heard):
        return {**req, "action": "stop"}
    if recent and COMPLAINT.search(heard):            # "I'm not hearing anything on pin twelve"
        return {**req, "action": recent["action"] if recent["action"] in ("play", "on") else "play",
                "tune": recent.get("tune", req["tune"]), "retry": True}
    if READ.search(heard) and not re.search(r"\bwhat\s+about\b", heard, re.I):   # "Is pin 4 high?" asks
        return {**req, "action": "read"}
    if (INPUT.search(heard) or PULL_UP.search(heard) or PULL_DOWN.search(heard)) and not re.search(r"\boutput\b", heard, re.I):
        pull = "up" if PULL_UP.search(heard) else "down" if PULL_DOWN.search(heard) else "none"
        return {**req, "action": "input", "pull": pull}
    if TOGGLE.search(heard):
        return {**req, "action": "toggle"}
    if OFF.search(heard):
        return {**req, "action": "off"}
    if ON.search(heard):
        return {**req, "action": "on"}
    if re.search(r"\boutput\b", heard, re.I):          # "make pin 17 an output" - starts low
        return {**req, "action": "off"}
    if CHANGE.search(heard):                           # "change pin 17" - flip it
        return {**req, "action": "toggle"}
    if recent:                                          # "What about physical pin twelve?" / "try pin 18"
        return {**req, "action": recent["action"], "tune": recent.get("tune", req["tune"])}
    return None


def _tune(heard):
    for pat, key in TUNE_WORDS:
        if re.search(pat, heard, re.I):
            return key
    return "twinkle"


def _function(pin):
    """pinctrl's view of a pin: 'op', 'ip', 'no', or an alt function like 'a3'."""
    out = subprocess.run(["pinctrl", "get", str(pin)], capture_output=True, text=True, timeout=5).stdout
    m = re.match(r"\s*\d+:\s+(\S+)", out)
    return m.group(1) if m else "?"


def _busy(pin):
    """Why this pin can't be driven, or None."""
    if pin in ID_PINS:
        return "it's for the HAT ID chip"
    if pin in VOICE_PINS:
        return f"it's my voice, {VOICE_PINS[pin]} for the speaker amp"
    f = _function(pin)
    if f.startswith("a") and not (pin in PWM and f == PWM[pin][1]):
        name = subprocess.run(["pinctrl", "get", str(pin)], capture_output=True, text=True).stdout.split("=")[-1].strip()
        return f"it's in use as {name or f}"
    return None


def _level(pin):
    out = subprocess.run(["pinctrl", "lev", str(pin)], capture_output=True, text=True, timeout=5)
    return out.stdout.strip() == "1"


def _pull(pin):
    """'up', 'down' or 'none', from pinctrl get ("4: ip    pu | hi // GPIO4 = input")."""
    out = subprocess.run(["pinctrl", "get", str(pin)], capture_output=True, text=True, timeout=5).stdout
    return {"pu": "up", "pd": "down"}.get(out.split()[2] if len(out.split()) > 2 else "", "none")


def _set_input(pin, pull):
    subprocess.run(["pinctrl", "set", str(pin), "ip", {"up": "pu", "down": "pd"}.get(pull, "pn")],
                   check=True, capture_output=True, timeout=5)


def _set(pin, on):
    subprocess.run(["pinctrl", "set", str(pin), "op", "dh" if on else "dl"], check=True, capture_output=True, timeout=5)


# ---- tunes ----
def _notes(key):
    name, bpm, score = TUNES[key]
    beat = 60 / bpm
    for tok in score.split():
        note, _, beats = tok.partition(":")
        yield (None if note == "R" else _freq(note)), float(beats or 1) * beat


def _pwm0_chip():
    """The sysfs pwmchip of RP1 PWM0, or None when it's not enabled."""
    for chip in sorted(os.listdir("/sys/class/pwm")) if os.path.isdir("/sys/class/pwm") else []:
        if os.path.realpath(f"/sys/class/pwm/{chip}/device").endswith(PWM0_DEVICE):
            return f"/sys/class/pwm/{chip}"
    return None


class _HardwarePWM:
    def __init__(self, pin, chip):
        self.pin, (ch, self.alt) = pin, PWM[pin]
        self.dir = f"{chip}/pwm{ch}"
        if not os.path.isdir(self.dir):
            open(f"{chip}/export", "w").write(str(ch))
            for _ in range(50):         # udev fixes the new files' group a moment later
                if os.access(f"{self.dir}/period", os.W_OK):
                    break
                time.sleep(0.02)
        self._w("enable", 0); self._w("duty_cycle", 0)
        subprocess.run(["pinctrl", "set", str(pin), self.alt], check=True, timeout=5)

    def _w(self, f, v):
        with open(f"{self.dir}/{f}", "w") as fh:
            fh.write(str(int(v)))

    def tone(self, hz, secs, stop):
        if hz:
            period = 1e9 / hz
            self._w("duty_cycle", 0); self._w("period", period); self._w("duty_cycle", period / 2)
            self._w("enable", 1)
        stop.wait(secs * 0.9)
        self._w("enable", 0)            # short gap so repeated notes are heard as separate notes
        stop.wait(secs * 0.1)

    def close(self):
        try:
            self._w("enable", 0)
        finally:
            _set(self.pin, False)


class _SoftwarePWM:
    """Bit-banged square wave with gpiod; busy-waits on one core while a note plays."""
    def __init__(self, pin):
        import gpiod
        from gpiod.line import Direction, Value
        self.pin, self.V = pin, Value
        self.req = gpiod.request_lines("/dev/gpiochip0", consumer="gene-tune",
                                       config={pin: gpiod.LineSettings(direction=Direction.OUTPUT)})

    def tone(self, hz, secs, stop):
        end = time.perf_counter() + secs * 0.9
        if hz:
            half, nxt, high = 0.5 / hz, time.perf_counter(), False
            while nxt < end and not stop.is_set():
                high = not high
                self.req.set_value(self.pin, self.V.ACTIVE if high else self.V.INACTIVE)
                nxt += half
                while time.perf_counter() < nxt:
                    pass
            self.req.set_value(self.pin, self.V.INACTIVE)
        stop.wait(max(0, end - time.perf_counter()) + secs * 0.1)

    def close(self):
        self.req.release()
        _set(self.pin, False)


def _play(pins, key, stop):
    drivers = []
    try:
        chip = _pwm0_chip()
        drivers = [_HardwarePWM(p, chip) if chip and p in PWM else _SoftwarePWM(p) for p in pins[:1]]  # one pin plays
        for hz, secs in _notes(key):
            if stop.is_set():
                break
            for d in drivers:
                d.tone(hz, secs, stop)
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "GPIO tune error:", e, flush=True)
    finally:
        for d in drivers:
            try:
                d.close()
            except Exception:
                pass


def stop_tune():
    if _player["thread"] and _player["thread"].is_alive():
        _player["stop"].set(); _player["thread"].join(3)


def play(pins, key):
    stop_tune()
    _player["stop"] = threading.Event()
    _player["thread"] = threading.Thread(target=_play, args=(pins, key, _player["stop"]), daemon=True)
    _player["thread"].start()


def tune_seconds(key):
    return sum(s for _, s in _notes(key))


# ---- the command ----
def _name(pin):
    """ "physical pin 12, GPIO 18" - both numberings, so there's no doubt which pin was used."""
    return f"physical pin {PHYSICAL[pin]}, GPIO {pin}" if pin in PHYSICAL else f"GPIO {pin}"


_PULL_SAID = {"up": " with pull-up", "down": " with pull-down", "none": " with no pull"}


def act(req):
    """Does it and returns the sentence for Gene to say."""
    said = _act(req)
    return said[0].upper() + said[1:]


def _act(req):
    action, pins, other = req["action"], req["pins"], list(req["other"])
    note = (" " + ". ".join(o[0].upper() + o[1:] for o in other) + ".") if other else ""
    if action == "stop":
        stop_tune()
        return "Okay, stopped."
    _save_state(action=action, tune=req.get("tune", "twinkle"), time=time.time())   # for "what about pin 12?"
    if not pins:
        if other:
            return note.strip() + (" Which pin is your speaker's other wire on?" if action == "play"
                                   else " So there's nothing there I can switch.")
        return "Which pin do you mean? For example, say play a song on physical pin 12."
    bad = [p for p in pins if not 0 <= p <= 27]
    if bad:
        return f"I only have GPIO pins zero to twenty seven, so there's no GPIO {bad[0]}."
    if action == "read":
        return " ".join(f"{_name(p)} is {'high' if _level(p) else 'low'}"
                        + (f", as an input{_PULL_SAID[_pull(p)]}." if _function(p) == "ip" else ".") for p in pins) + note
    for p in pins:
        if why := _busy(p):
            return f"I'd better not drive {_name(p)}, {why}." + note
    _save_state(pins=pins)
    if action == "play":
        play(pins, req["tune"])
        if req.get("retry"):
            return (f"Playing it again on {_name(pins[0])}. If it's still silent, the speaker needs to go between "
                    f"that pin and a ground pin, like physical pin 6, and a plain speaker needs a transistor.")
        return f"Playing {TUNES[req['tune']][0]} on {_name(pins[0])}." + note
    if action == "input":
        for p in pins:
            _set_input(p, req.get("pull", "none"))
        time.sleep(0.01)                                # let the pull settle before reading
        return " ".join(f"{_name(p)} is now an input{_PULL_SAID[req.get('pull', 'none')]}, reading "
                        f"{'high' if _level(p) else 'low'}." for p in pins) + note
    for p in pins:
        _set(p, not _level(p) if action == "toggle" else action == "on")
    return " ".join(f"{_name(p)} is now {'on' if _level(p) else 'off'}." for p in pins) + note


if __name__ == "__main__":
    import sys
    r = wants(" ".join(sys.argv[1:]))
    print(r, act(r) if r else "")
    while _player["thread"] and _player["thread"].is_alive():
        time.sleep(0.2)
