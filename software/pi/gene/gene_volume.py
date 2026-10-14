"""Gene's speaker volume, by voice.

  "turn the volume up" / "louder" / "speak up" / "a bit louder" / "a lot louder" / "you're too quiet"   - up
  "turn it down" / "lower your volume" / "quieter" / "not so loud" / "you're too loud"                 - down
  "set your volume to 50 percent" / "volume to max" / "volume to half"                                 - set
  "what's your volume?" / "how loud are you?"                                                          - say it

It is the PipeWire volume of the default sink (today the MAX98357A I2S amp, which has no hardware mixer), set with
wpctl like the mic mute; WirePlumber remembers it across restarts. Kept between MIN and MAX: never so quiet he can't be
heard answering, never above 100 % (above that would clip in software).

Gene sets his own volume as he talks (since 2026-10-08, asked by Joshua): his REGULAR level (75 %, the one these voice
commands change, kept in state/volume.json) for most replies, louder when his model starts a reply with [loud] (or
looks angry/surprised), quieter with [meek] (or sad/sleepy) - STYLES, relative to the regular level, so 75 -> 100 / 45.
Mouth calls use(style) before each sentence; sound bites and command results are at the regular level.
"""
import json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state", "volume.json")
SINK = "@DEFAULT_AUDIO_SINK@"
STEP, BIG, SMALL = 10, 25, 5        # percent: "louder" / "a lot louder" / "a bit louder"
MIN, MAX = 10, 100    # 100 %: asked 2026-10-08 (the cap was 80 % since 2026-10-05); amp GAIN on ground = 12 dB
REGULAR = 75          # his normal speaking level (asked 2026-10-08)
STYLES = {"loud": 25, "meek": -30}      # percent from the regular level: 75 -> 100 loud, 45 meek
FACE_STYLE = {"angry": "loud", "surprised": "loud", "sad": "meek", "sleepy": "meek"}    # when he gives no voice tag
TENS = {"ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90, "hundred": 100, "a hundred": 100, "one hundred": 100, "half": 50, "max": MAX, "maximum": MAX,
        "full": MAX, "min": MIN, "minimum": MIN, "lowest": MIN, "highest": MAX, "loudest": MAX, "quietest": MIN}
UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
LEVEL = (r"(\d{1,3}|" + "|".join(sorted(map(re.escape, TENS), key=len, reverse=True)) + r")(?:[\s-](" +
         "|".join(UNITS) + r"))?(?:\s*(?:%|percent|per\s+cent))?")

VOL = r"(?:the\s+|your\s+|my\s+)?(?:volume|sound|speakers?|voice)"
UP = re.compile(r"\b(?:turn|crank|bump|pump|put|bring)\s+(?:" + VOL + r"|it|yourself)\s+(?:back\s+)?up\b|"
                r"\b(?:turn|crank|bump|pump)\s+up\s+" + VOL + r"\b|"
                r"\b(?:raise|increase|boost|up)\s+" + VOL + r"\b|\bvolume\s+up\b|"
                r"\b(?:louder|speak\s+up|talk\s+up)\b|\btoo\s+(?:quiet|soft)\b|\bcan(?:'t|not|\s+not)\s+hear\s+you\b", re.I)
DOWN = re.compile(r"\b(?:turn|bring|put|tone)\s+(?:" + VOL + r"|it|yourself)\s+(?:back\s+)?down\b|"
                  r"\b(?:turn|tone)\s+down\s+" + VOL + r"\b|"
                  r"\b(?:lower|decrease|reduce|drop|cut)\s+" + VOL + r"\b|\bvolume\s+down\b|"
                  r"\b(?:quieter|softer|more\s+(?:quietly|softly))\b|\b(?:too|so|very)\s+loud\b|\bless\s+loud\b", re.I)
SET = re.compile(r"\b(?:volume|loudness)\b.{0,25}?\b(?:to|at|on)\s+(?:the\s+)?" + LEVEL + r"|"
                 r"\b(?:set|put|turn)\s+(?:yourself|your\s+voice)\s+(?:to|at)\s+(?:the\s+)?" + LEVEL, re.I)
GET = re.compile(r"\bwhat(?:'s|\s+is)\s+(?:the\s+|your\s+)?volume\b|\bhow\s+loud\s+(?:are\s+you|is\s+(?:the|your)\s+volume)\b|"
                 r"\bwhat\s+(?:is\s+)?(?:the\s+|your\s+)?volume\s+(?:at|set\s+to|on)\b", re.I)
BIG_WORDS = re.compile(r"\b(?:a\s+lot|lots|much|way|loads|really|heaps)\b", re.I)
SMALL_WORDS = re.compile(r"\b(?:a\s+(?:little|bit|tad|touch)(?:\s+bit)?|slightly|a\s+smidge)\b", re.I)
QUESTION = re.compile(r"^\W*(?:how\s+(?:do|can|would|should)|why|when|did|have|were|was|who)\b", re.I)


def _level(m):
    """The percent from a LEVEL match's groups (first, units)."""
    first, units = m
    first = first.lower()
    n = int(first) if first.isdigit() else TENS[re.sub(r"\s+", " ", first)]
    return n + (UNITS[units.lower()] if units else 0)


def wants(heard):
    """('up'|'down', step) / ('set', percent) / ('get',) / None."""
    if QUESTION.search(heard) or re.search(r"\bpins?\b", heard, re.I):
        return None
    if m := SET.search(heard):
        g = m.groups()
        return ("set", _level(g[0:2] if g[0] else g[2:4]))
    for verb, pat in (("up", UP), ("down", DOWN)):
        if pat.search(heard):
            return (verb, BIG if BIG_WORDS.search(heard) else SMALL if SMALL_WORDS.search(heard) else STEP)
    if GET.search(heard):
        return ("get",)
    return None


def _sink():
    """The default sink's volume in percent right now, and whether it is muted."""
    out = subprocess.run(["wpctl", "get-volume", SINK], capture_output=True, text=True, timeout=5).stdout
    m = re.search(r"Volume:\s*([\d.]+)", out)
    if not m:
        raise RuntimeError(f"wpctl get-volume: {out!r}")
    return round(float(m.group(1)) * 100), "MUTED" in out


def regular():
    """His regular speaking volume in percent."""
    try:
        return min(max(int(json.load(open(STATE))["regular"]), MIN), MAX)
    except Exception:
        return REGULAR


def level(style=None):
    """The volume for a sentence: regular, or "loud" / "meek" relative to it."""
    return min(max(regular() + STYLES.get(style, 0), MIN), MAX)


_applied = None     # what use() last set the sink to


def use(style=None):
    """Sets the speaker to the level for this sentence - only when it changes."""
    global _applied
    p = level(style)
    if p != _applied:
        subprocess.run(["wpctl", "set-volume", SINK, f"{p / 100:.2f}"], capture_output=True, timeout=5)
        _applied = p


def get():
    """His regular volume in percent (loud and meek are relative to it), and whether the speaker is muted."""
    return regular(), _sink()[1]


def set_percent(p):
    """A new regular level, kept across restarts."""
    global _applied
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"regular": p}, f)
    os.replace(tmp, STATE)
    subprocess.run(["wpctl", "set-volume", SINK, f"{p / 100:.2f}"], capture_output=True, timeout=5, check=True)
    subprocess.run(["wpctl", "set-mute", SINK, "0"], capture_output=True, timeout=5)
    _applied = p


def act(want):
    """Changes (or reads) the volume; returns the exact sentence for Gene to say."""
    now, _ = get()
    if want[0] == "get":
        return f"My volume is at {now} percent."
    if want[0] == "set":
        new = min(max(want[1], MIN), MAX)
    else:
        new = min(max(now + (want[1] if want[0] == "up" else -want[1]), MIN), MAX)
    if new == now:
        if want[0] == "up" or (want[0] == "set" and want[1] >= MAX):
            return f"My volume is already at the maximum, {MAX} percent."
        if want[0] == "down" or (want[0] == "set" and want[1] <= MIN):
            return f"My volume is already as low as it goes, {MIN} percent, so you can still hear me."
        return f"My volume is already at {now} percent."
    set_percent(new)
    if want[0] == "set" and want[1] < MIN:
        return f"Okay, my volume is now {new} percent, the lowest it goes so you can still hear me."
    return f"Okay, my volume is now {new} percent." + (" That's as loud as I go." if new == MAX and want[0] != "set" else "")
