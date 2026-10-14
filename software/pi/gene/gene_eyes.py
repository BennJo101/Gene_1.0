"""Gene's eyes: one round eye drawn fullscreen on each connected monitor.

The look is the eye-screen design from the head sim (~/Desktop/Gene Robot/Head/cleaned/GeneHead_sim.html):
a camera-aperture iris round the lens (the lens IS the pupil), a focus ring, lids that shape the expression,
blinks and a wandering gaze. Expressions ease into each other.

What they show comes from two files in state/:
  eyes.json              {"emote": "happy", "t": ..., "until": ...}   written by gene_client.py when Gene's model
                         picks a face; "until" is set by settle() when he stops talking (back to neutral then,
                         unless the same face was on his last 3 replies: that's his mood and it stays 10 min)
  lids.json              {"left": until, "right": until}   eyes closed by voice ("close your left eye") until then,
                         on top of whatever face is showing; close_eyes() / open_eyes() / lids_wanted()
  upgrade_progress.json  {"percent": 42, "step": ..., "pid": ...}   written by upgrade.py while he upgrades;
                         the eyes show the loading face, its ring filled to that percentage, until it goes away
                         (or the upgrade process that wrote it dies).

Monitors are ordered left to right (as seen from the front): the first is the eye on the viewer's left.
"Switch your screens left and right" reverses that order (eye_swap.json, kept until switched back): for screens
mounted or cabled the other way round. swap_wanted() / swap_screens().
Monitors can be plugged in and out while it runs. Escape, or 3 quick taps/clicks, hides the eyes for 2 minutes.
One or two taps are a poke in the eye: the poke is left in state/poke.json ({"t", "eye": "right"/"left"/null,
"taps", "center"}) for gene_client.py. Gene no longer reacts to pokes (no flinch, no words); a poke only opens
closed eyes and unmutes a muted mic.

Needs the system python (GTK + cairo):  /usr/bin/python3 ~/gene/gene_eyes.py   (run by gene-eyes.service)
gene_client.py and upgrade.py only use show() / progress() / done(), which need nothing extra.
"""
import json, math, os, random, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
EYES = os.path.join(STATE, "eyes.json")
PROGRESS = os.path.join(STATE, "upgrade_progress.json")
IDLE_RESET = 120            # s: a face Gene chose goes back to neutral after this long without a new one
SETTLE_AFTER = 3            # s: ...or this long after Gene stops talking (settle()), as Joshua asked
MOOD_STREAK = 3             # replies in a row with the same face = Gene is in that mood...
MOOD_GAP = 300              # s: ...(at most this long between those replies)...
MOOD_HOLD = 600             # s: ...so the face stays after he stops talking, until the mood changes or this long passes
HIDE_FOR = 120              # s hidden after Escape / 3 taps
POKE = os.path.join(STATE, "poke.json")
LIDS = os.path.join(STATE, "lids.json")    # {"left": until, "right": until}: eyes closed by voice
SWAP = os.path.join(STATE, "eye_swap.json")   # {"swapped": true}: the left and right screens trade eyes (by voice)
TILT = os.path.join(STATE, "eye_tilt.json")   # {"left": deg, "right": deg}: each eye turned by voice, clockwise as seen from the front
LIDS_HOLD = 300             # s: an eye closed by voice opens again after this long, if nobody says "open your eyes"
WINK_FOR = 0.7              # s: "wink your right eye"
TAP_GAP = 0.5               # s: taps closer together than this are one gesture (3 of them hide the eyes)
FPS = 25
UPSIDE_DOWN = True          # 2026-10-13, asked by voice ("your eye monitors are upside down, flip them"): draw turned 180 deg
TILT_OUT = 8.0              # deg: 2026-10-13, asked by voice: the two eye screens are mounted tilted inwards (tops toward
                            # the nose), so each eye is drawn turned this much outwards to look level. Raise it if they still lean in.
                            # This is only the default: "rotate your left eye 2 degrees clockwise" fine-tunes it (eye_tilt.json).
TILT_MAX = 45.0             # deg either way, by voice
LEVEL_SHOW = 10.0           # s: after a turn by voice, a level line across each eye (+ a notch at its top) shows the angle -
                            # the eye is round, so without it a few degrees can't be seen (2026-10-13: "I don't see a change")
IDLE_EVERY = 3            # while nothing moves (no blink, glance, face change or lid), draw every 3rd frame: ~8 fps

# Expression parameters, from the sim. Unit coords: screen radius 1; the camera hub covers r < 0.34.
# top/bot: lid edges, tilt: brow slant, curve: lower lid smile, hue/sat/lit: colour, iris/pupil: blade radii.
EMOTES = {
    "neutral":    dict(top=-0.72, tilt=0.00,  bot=0.95, curve=0.00, hue=164, sat=72,  lit=50, iris=0.72, pupil=0.46, heart=0, tear=0, glow=1.0, fear=0, beam=0),
    "happy":      dict(top=-0.95, tilt=0.00,  bot=0.72, curve=0.32, hue=158, sat=74,  lit=53, iris=0.74, pupil=0.48, heart=0, tear=0, glow=1.1, fear=0, beam=0),
    "sad":        dict(top=-0.30, tilt=-0.40, bot=0.88, curve=0.00, hue=215, sat=70,  lit=50, iris=0.68, pupil=0.52, heart=0, tear=1, glow=0.8, fear=0, beam=0),
    "angry":      dict(top=-0.22, tilt=0.50,  bot=0.80, curve=0.00, hue=356, sat=92,  lit=48, iris=0.66, pupil=0.38, heart=0, tear=0, glow=1.2, fear=0, beam=0),
    "surprised":  dict(top=-1.10, tilt=0.00,  bot=1.10, curve=0.00, hue=168, sat=82,  lit=57, iris=0.80, pupil=0.37, heart=0, tear=0, glow=1.3, fear=0, beam=0),
    "sleepy":     dict(top=0.12,  tilt=-0.12, bot=0.72, curve=0.00, hue=170, sat=45,  lit=40, iris=0.68, pupil=0.56, heart=0, tear=0, glow=0.6, fear=0, beam=0),
    "love":       dict(top=-1.00, tilt=0.00,  bot=1.00, curve=0.00, hue=335, sat=90,  lit=58, iris=0.72, pupil=0.46, heart=1, tear=0, glow=1.2, fear=0, beam=0),
    "wink":       dict(top=-0.75, tilt=0.00,  bot=0.72, curve=0.32, hue=158, sat=74,  lit=53, iris=0.74, pupil=0.48, heart=0, tear=0, glow=1.1, fear=0, beam=0),
    # smaller iris and the lower lid out of the way of the progress ring
    "loading":    dict(top=-0.80, tilt=0.00,  bot=1.15, curve=0.00, hue=164, sat=62,  lit=38, iris=0.56, pupil=0.42, heart=0, tear=0, glow=0.7, fear=0, beam=0),
    "flashlight": dict(top=-1.25, tilt=0.00,  bot=1.25, curve=0.00, hue=46,  sat=100, lit=86, iris=0.90, pupil=0.36, heart=0, tear=0, glow=2.0, fear=0, beam=1),
    "scary":      dict(top=-0.46, tilt=0.62,  bot=0.80, curve=-0.10, hue=0,  sat=100, lit=40, iris=0.88, pupil=0.36, heart=0, tear=0, glow=1.8, fear=1, beam=0),
}
CHOICES = [e for e in EMOTES if e != "loading"]     # what Gene's model may pick; loading is for upgrades


# ---------- used by gene_client.py / upgrade.py ----------

def _write(path, d):
    os.makedirs(STATE, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, path)


def show(emote):
    """Set the face Gene wants. Unknown names are ignored. Returns the name used, or None."""
    emote = (emote or "").strip().lower()
    if emote not in CHOICES:
        return None
    mood = {k: v for k, v in (_read(EYES) or {}).items() if k in ("mood", "streak", "mood_t")}
    _write(EYES, {"emote": emote, "t": time.time(), **mood})
    return emote


def settle(after=SETTLE_AFTER):
    """Gene has finished talking: his face goes back to neutral `after` seconds from now (flashlight stays on).
    If his last MOOD_STREAK replies all had this face, that's his mood: it stays for MOOD_HOLD instead."""
    e = _read(EYES) or {}
    if "until" in e:            # already settled since the last face (e.g. two settles in one turn)
        return
    em, now = e.get("emote", "neutral"), time.time()
    streak = e.get("streak", 0) + 1 if em == e.get("mood") and now - e.get("mood_t", 0) < MOOD_GAP else 1
    e.update(mood=em, streak=streak, mood_t=now)
    e["until"] = now + (MOOD_HOLD if streak >= MOOD_STREAK else after)     # (flashlight ignores it)
    _write(EYES, e)


def hold(emote, seconds):
    """Show a face that stays `seconds` (e.g. sleepy while the mic is muted) until another face replaces it."""
    if emote := show(emote):
        e = _read(EYES) or {}
        e["until"] = time.time() + seconds
        _write(EYES, e)
    return emote


# "close your left eye", "shut your eyes", "wink your right eye", "open your eyes" (left/right are Gene's own).
# STT often hears "eye" as "I" after left/right.
_EYE = r"(?:eyes?|i)\b"
_LIDS = re.compile(r"\b(close|shut|wink|open)(?:\s+(?:up|with))?\s+(?:(?:your|ur|the|one\s+of\s+your|one|both(?:\s+of)?(?:\s+your)?)\s+)?"
                   r"(?:(left|right|both)\s+(?:" + _EYE + r")|(eyes?)\b)", re.I)
_LIDS_ASK = re.compile(r"^\W*(?:how|why|what|when|did|have|were|was|are|do|does)\b|\bdon'?t\s+(?:close|shut|wink|open)\b", re.I)


def lids_wanted(heard):
    """("close"/"open"/"wink", "left"/"right"/"both") if `heard` asks Gene to close, open or wink his eyes, else None.
    A plain "wink at me" is left to the model (its [wink] face); "close one eye" closes the left one, like that face."""
    if _LIDS_ASK.search(heard) or not (m := _LIDS.search(heard)):
        return None
    verb, side, plain = m.group(1).lower().replace("shut", "close"), (m.group(2) or "").lower(), (m.group(3) or "").lower()
    one = re.search(r"\bone\b", m.group(0), re.I)
    if verb == "wink":
        return ("wink", side) if side in ("left", "right") else None
    if not side:
        side = "left" if one or plain == "eye" and verb == "close" else "both"
    return verb, side


# "are both your screens connected?" / "how many screens do you have?": read from the kernel (/sys/class/drm), so it
# works without the desktop session. Gene has two round eye screens, one per micro-HDMI port.
DRM = "/sys/class/drm"
EYE_SCREENS = 2
_SCREENS_ASK = re.compile(r"\b(?:screens?|displays?|monitors?)\b", re.I)
_SCREENS_WHAT = re.compile(r"\b(?:connect\w*|plugged|hooked|attached|detect\w*|working|how\s+many|both|see|check)\b", re.I)
_SCREENS_NOT = re.compile(r"\b(?:share|turn|switch|brightness|bright|dim|screenshot|close|hide|show|put|copy)\b", re.I)


def screens():
    """[(port, connected, enabled)] for each HDMI/DSI output, e.g. [("HDMI 0", True, True), ("HDMI 1", False, False)]."""
    out = []
    for name in sorted(os.listdir(DRM)) if os.path.isdir(DRM) else []:
        m = re.fullmatch(r"card\d+-(HDMI-A|DSI)-(\d+)", name)
        if not m:
            continue
        def rd(f):
            try:
                with open(os.path.join(DRM, name, f)) as fh:
                    return fh.read().strip()
            except OSError:
                return ""
        port = f"HDMI {int(m.group(2)) - 1}" if m.group(1) == "HDMI-A" else f"DSI {int(m.group(2)) - 1}"
        out.append((port, rd("status") == "connected", rd("enabled") == "enabled"))
    return out


def screens_wanted(heard):
    """True if `heard` asks whether Gene's screens are connected ("are both your screens connected?")."""
    return bool(_SCREENS_ASK.search(heard) and _SCREENS_WHAT.search(heard) and not _SCREENS_NOT.search(heard))


def screens_status():
    """Short line for the model's status: 'eye screens: both connected (HDMI 0 and HDMI 1)'."""
    on = [p for p, c, _ in screens() if c]
    if len(on) >= EYE_SCREENS:
        return f"eye screens: {'both' if len(on) == 2 else len(on)} connected ({' and '.join(on)})"
    return f"eye screens: {len(on)} of {EYE_SCREENS} connected" + (f" ({on[0]})" if on else "")


def screens_answer():
    """What Gene says when asked if his screens are connected (said exactly: ports must be right)."""
    s = screens()
    on = [p for p, c, _ in s if c]
    off = [p for p, c, _ in s if not c and p.startswith("HDMI")]
    dark = [p for p, c, e in s if c and not e]
    if not s:
        said = "I can't find any screen outputs on my Pi at all."
    elif len(on) >= 2:
        said = (f"Yes, both my eye screens are connected, on {on[0]} and {on[1]}." if len(on) == 2 else
                f"Yes, I've got {len(on)} screens connected, on {', '.join(on[:-1])} and {on[-1]}.")
    elif len(on) == 1:
        said = f"Only one of my eye screens is connected, on {on[0]}." + (f" Nothing is plugged into {off[0]}." if off else "")
    else:
        said = "Neither of my eye screens is connected right now."
    if dark:
        said += f" The one on {' and '.join(dark)} is plugged in but switched off."
    return said


# "switch your screens left and right" / "swap your monitors" / "swap your left and right eyes": the two screens
# trade eyes (each shows the other's, lids, winks and pokes go with it). Says it again = back. Not "switch off ...".
_SWAP = re.compile(r"\b(?:switch|swap|swop|flip|reverse|trade|exchange|mirror)\b(?!\s+(?:on|off|to|between)\b)"
                   r"(?=.*\b(?:screens?|monitors?|displays?|eyes?)\b)", re.I)
_SWAP_HOW = re.compile(r"\b(?:left|right|around|round|over|sides?|back|places|positions|order)\b|\b(?:screens|monitors|displays|eyes)\b", re.I)
_SWAP_ASK = re.compile(r"^\W*(?:how|why|when|did|have|were|was|are|is|do|does)\b|\bdon'?t\s+(?:switch|swap)\b|\b(?:on|off)\b", re.I)


def swap_wanted(heard):
    """True if `heard` asks Gene to switch his left and right screens over."""
    return bool(_SWAP.search(heard) and _SWAP_HOW.search(heard) and not _SWAP_ASK.search(heard))


def swapped():
    return bool((_read(SWAP) or {}).get("swapped"))


def swap_screens():
    """Switch which screen is Gene's left eye and which his right (the eyes window picks it up within a second).
    Returns True if they are now the other way round from the usual left-to-right order."""
    now = not swapped()
    _write(SWAP, {"swapped": now, "t": time.time()})
    return now


# "rotate your left eye 2 degrees clockwise" / "tilt your eyes a bit more outwards" / "turn your right eye back a degree"
# / "set your eye rotation to 10 degrees" / "reset your eye rotation" / "how much are your eyes rotated?": each eye's
# turn, to get it level on its screen by ear. Kept per PHYSICAL screen (Gene's left/right side of the head), so a
# screen swap doesn't move it. Positive = clockwise as seen from the front; outwards = top away from the nose
# (Gene's right eye, the viewer's left screen, turns outwards anticlockwise).
_TILT_VERB = re.compile(r"\b(?:rotate|rotat\w+|turn|tilt|twist|spin|angle|lean|level|straighten)\b(?!\s+(?:on|off|up|down)\b)", re.I)
_TILT_ON = re.compile(r"\b(?:eyes?|screens?|monitors?|displays?)\b", re.I)
_TILT_HOW = re.compile(r"\b(?:clockwise|anti-?clockwise|counter-?\s?clockwise|out|outwards?|outward|in|inwards?|inward|more|less|back|degrees?|reset|"
                       r"normal|default|zero|straight\w*|level\w*|rotation|tilt|angle)\b|°", re.I)
_TILT_ASK = re.compile(r"^\W*(?:how|what|are|is|which)\b(?=.*\b(?:rotat\w*|tilt\w*|turned|angled?|level|straight)\b)", re.I)
_TILT_NOT = re.compile(r"^\W*(?:why|when|did|have|were|was|do|does|can\s+you\s+see)\b|\bdon'?t\b|\blook\b|\bcameras?\b|\bheads?\b", re.I)
_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "half": 0.5, "half a": 0.5}


TILT_FOLLOW = 300           # s: after a turn (or "tell me which way"), "a bit more outwards" / "do it substantially" go on
_tilt_last = {"t": 0.0, "req": None}       # the last turn asked for (this process: gene_client), for follow-ups
# a follow-up: a way to turn ("a bit more outwards"), "do it/try that (again/substantially)", or only "(a bit) more" /
# "again" - not any sentence with "more" in it ("tell me more about dinosaurs")
_NUM = r"(?:\d+(?:\.\d+)?|half\s+a|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|an?)"
_TILT_AMOUNT = re.compile(r"\b(" + _NUM + r")\s*(?:(?:more|extra|further)\s+)?(?:degrees?|°)|\b(" + _NUM + r")\s+(?:more|extra)\b", re.I)
_TILT_MORE = re.compile(r"\b(?:outwards?|outward|inwards?|inward|clockwise|anti-?clockwise|counter-?\s?clockwise|back\s+in)\b"
                        r"|\b(?:do|doing|try|trying|turn|rotate|tilt|go|move|keep)\b(?!.*\b(?:up|down|on|off)\b).*"
                        r"\b(?:it|them|that|more|again|further|going)\b", re.I)
# "Slightly bit more." / "Yeah, a little more please." / "Keep going.": only these words around more/again/further
_TILT_FILL = {"a", "bit", "little", "tiny", "lot", "lots", "way", "much", "even", "some", "just", "now", "ok", "okay", "and",
              "uh", "um", "slightly", "slight", "yeah", "yes", "yep", "please", "go", "keep", "going", "still",
              "not", "enough", "that's", "thats", "bigger", "smaller", "do", "try", "the", "same", "one", "tad", "touch"}
_TILT_BARE = {"more", "again", "further", "less", "going"}
_TILT_SAME = re.compile(r"\b(?:don'?t|can'?t|cannot|didn'?t)\s+(?:\w+\s+){0,2}(?:see|notice|tell)\b.*\b(?:difference|change\w*|move\w*|rotat\w*)\b"
                        r"|\bnothing\s+(?:changed|happened|moved)\b|\b(?:didn'?t|did\s+not)\s+(?:change|move|rotate|turn)\b"
                        r"|\b(?:doesn'?t|does\s+not)\s+look\s+like\s+(?:you|they|it|anything)\b"
                        r"|\b(?:still\s+)?(?:not|hasn'?t|haven'?t)\s+(?:moved|moving|rotated|rotating|turned|turning|changed)\b", re.I)
_TILT_QUESTION = re.compile(r"^\W*(?:how|what|why|when|who|where|which|is|are|does|did|can|could|would|will)\b"
                            r"|^\W*do\s+(?:you|i|we|they|he|she|my|your)\b", re.I)   # "do five more degrees" is a request
# "the right eye to the left and the left eye to the right": which way the TOP of each screen goes, as the person
# looking at Gene sees it (to the right = clockwise)
_TILT_EACH = re.compile(r"\b(left|right)\s+(?:eye|screen|monitor|display)s?\b(?:(?!\b(?:left|right)\s+(?:eye|screen|monitor|display))"
                        r".){0,30}?\bto(?:wards?)?\s+(?:the\s+|your\s+|my\s+)?(left|right)\b", re.I)


def tilt_wanted(heard):
    """("ask",) / ("reset",) / ("same",) / ("turn", side, degrees, "cw" or "out") / ("set", side, degrees, outwards: bool)
    / ("each", [(side, degrees clockwise), ...]) if `heard` asks Gene to rotate his eyes on their screens, else None.
    ("help",) when it's clearly about turning his eyes but how much/which way wasn't heard. side: "left", "right" or
    "both". Within TILT_FOLLOW of the last turn, "a bit more outwards" / "do it substantially" / "again" need no eye
    word (2026-10-13: "tilt your eyes a bit more outwards" was heard as "Families a bit more outwards" and the model
    only pretended to turn them), and "I don't see a difference" says how they're turned now."""
    follow = time.time() - _tilt_last["t"] < TILT_FOLLOW
    if follow:
        # 2026-10-13: "Slightly bit more." / "Do five more degrees." / "It doesn't look like you move them. Make sure
        # that you move them outwards five more degrees." all went to the model, which only SAID it turned them
        ask = re.sub(r"^\W*(?:(?:ok(?:ay)?|so|and|uh|um|yeah|now|gene)\W+)*(?:can|could|would|will)\s+you\s+(?:please\s+)?", "",
                     heard, flags=re.I)                       # "can you rotate them more?" is a request, not a question
        words = re.findall(r"[a-z']+", ask.lower())
        bare = words and set(words) <= _TILT_FILL | _TILT_BARE and set(words) & _TILT_BARE
        asked = _TILT_AMOUNT.search(ask) or re.search(r"\b(?:outwards?|outward|inwards?|inward|clockwise)\b", ask, re.I)
        other = re.search(r"\b(?:volume|louder|quieter|song|music|sound|tell|about|story|joke)\b", ask, re.I)
        if not other and not _TILT_QUESTION.search(ask) and (
                bare or (not _TILT_ON.search(ask) and len(words) <= 14 and _TILT_MORE.search(ask))
                or (asked and len(words) <= 24 and (_TILT_MORE.search(ask) or _TILT_ON.search(ask) or len(words) <= 6))):
            return _tilt_how(ask.lower(), follow=True)
        if _TILT_SAME.search(heard):
            return ("same",)
    if not _TILT_ON.search(heard) or _TILT_NOT.search(heard):
        return None
    if _TILT_ASK.search(heard):
        return ("ask",)
    if not _TILT_VERB.search(heard) or not re.search(r"\b(?:eyes?|screens?|monitors?|displays?)\b", heard, re.I):
        return None
    if not _TILT_HOW.search(heard) and not _TILT_EACH.search(heard):     # "rotate your eyes": which way and how much wasn't said
        if not follow:
            return ("help",) if re.search(r"\b(?:rotate|tilt|twist)\b", heard, re.I) else None
    return _tilt_how(heard.lower(), follow=follow)


def _tilt_how(low, follow=False):
    """The turn asked for in `low` (lower case). follow: a follow-up of the last turn, so with no direction it goes
    the same way again (with no amount, by the same amount)."""
    if re.search(r"\b(?:reset|normal|default|usual)\b", low) or re.search(r"\b(?:back\s+to\s+how|like\s+before)\b", low):
        return ("reset",)
    m = re.search(r"\b(left|right)\s+(?:eye|screen|monitor|display)", low)
    side = m.group(1) if m else "both"
    n = _TILT_AMOUNT.search(low)            # "5 degrees", "five more degrees", "five more"
    num = n and (n.group(1) or n.group(2))
    amount = (float(num) if num[0].isdigit() else _NUMS[re.sub(r"\s+", " ", num)]) if n else None
    sized = amount is not None
    if amount is None:
        sized = True
        amount = (1.0 if re.search(r"\b(?:tiny|tad|touch|smidge|little\s+bit|tiny\s+bit|fraction)\b", low) else
                  2.0 if re.search(r"\b(?:bit|little|slightly|smidgen|nudge)\b", low) else
                  6.0 if re.search(r"\b(?:lot|much\s+more|way\s+more|loads|substantial\w*|significant\w*|heaps|big\w*)\b", low) else None)
        if amount is None:
            sized, amount = False, 3.0
    if re.search(r"\b(?:straight\w*|level\w*|zero|no\s+(?:rotation|tilt))\b", low) and not n or re.search(r"\bto\s+zero\b", low):
        return ("set", side, 0.0, False)
    each = _TILT_EACH.findall(low)
    if each:
        return ("each", [(s, amount if way == "right" else -amount) for s, way in each])
    ccw = re.search(r"\b(?:anti-?\s?clockwise|counter-?\s?clockwise)\b", low)
    if ccw or re.search(r"\bclockwise\b", low):
        sign = -1 if ccw else 1
        return ("set", side, sign * amount, False) if re.search(r"\bto\s+[\w.]+\s*(?:degrees?|°)", low) and n else ("turn", side, sign * amount, "cw")
    out = re.search(r"\b(?:out\w*|away|apart|more)\b", low)
    inn = re.search(r"\b(?:in|inwards?|inward|towards?|together|less|back)\b", low)
    if re.search(r"\bto\s+[\w.]+\s*(?:degrees?|°)", low) and n:
        return ("set", side, -amount if inn and not out else amount, True)
    if follow:
        last = _tilt_last["req"]
        said_way = re.search(r"\b(?:out\w*|away|apart|in|inwards?|inward|towards?|together|less|back)\b", low)
        if last and last[0] == "each" and not said_way:
            return ("each", [(s, math.copysign(amount if sized else abs(d), d)) for s, d in last[1]])
        if last and last[0] == "turn" and not said_way:
            return ("turn", last[1] if side == "both" else side, math.copysign(amount if sized else abs(last[2]), last[2]), last[3])
        if not said_way and not (last and last[0] == "set"):
            return ("help",)
    if out or inn:
        return ("turn", side, (-amount if inn and not out else amount), "out")
    return ("help",)


def tilts():
    """Each eye's turn now, degrees clockwise as seen from the front: {"left": ..., "right": ...} (Gene's own sides;
    his right eye is the screen on the viewer's left)."""
    d = _read(TILT) or {}
    out = {}
    for side, default in (("left", TILT_OUT), ("right", -TILT_OUT)):
        try:
            out[side] = max(-TILT_MAX, min(TILT_MAX, float(d.get(side, default))))
        except (TypeError, ValueError):
            out[side] = default
    return out


def _outwards(side, cw):
    """Degrees clockwise -> degrees outwards (top away from the nose) for that eye, and back (it's its own inverse)."""
    return cw if side == "left" else -cw


def tilt(request):
    """Carry out a tilt_wanted() request; returns what Gene says (said exactly: numbers and sides must be right)."""
    kind, now = request[0], tilts()
    if kind in ("help", "turn", "each", "set"):
        _tilt_last.update(t=time.time(), req=request)
    if kind == "help":
        return ("Tell me which eye and which way, like rotate your left eye 2 degrees clockwise, "
                "or tilt your eyes a bit more outwards.")
    if kind == "reset":
        now = {"left": TILT_OUT, "right": -TILT_OUT}
    elif kind == "each":
        for s, deg in request[1]:
            now[s] = round(max(-TILT_MAX, min(TILT_MAX, now[s] + deg)), 1)
        _write(TILT, {**now, "t": time.time()})
    elif kind not in ("ask", "same"):
        _k, side, deg, how = request
        for s in (("left", "right") if side == "both" else (side,)):
            if kind == "set":
                now[s] = _outwards(s, deg) if how else (deg if side != "both" else _outwards(s, abs(deg)) if deg else 0.0)
            elif how == "out":
                now[s] += _outwards(s, deg)
            else:
                now[s] += deg
            now[s] = round(max(-TILT_MAX, min(TILT_MAX, now[s])), 1)
        _write(TILT, {**now, "t": time.time()})

    def say(s):
        o = _outwards(s, now[s])
        n = f"{abs(o):g} degree{'' if abs(o) == 1 else 's'}"
        return f"my {s} eye is level" if not o else f"my {s} eye is turned {n} {'outwards' if o > 0 else 'inwards'}"
    if _outwards("left", now["left"]) == _outwards("right", now["right"]):
        o = _outwards("left", now["left"])
        what = ("my eyes aren't rotated at all" if not o else
                f"both my eyes are turned {abs(o):g} degree{'' if abs(o) == 1 else 's'} {'outwards' if o > 0 else 'inwards'}")
    else:
        what = f"{say('left')} and {say('right')}"
    if kind == "ask":
        return what[0].upper() + what[1:] + "."
    if kind == "same":
        return what[0].upper() + what[1:] + ". Say a lot more outwards, or 10 degrees, for a bigger turn."
    return ("Okay, back to normal: " if kind == "reset" else "Okay, ") + what + "."


def tilt_status():
    """For gene_client's status line: how the eyes are really turned, so the model never claims a turn it didn't make
    (2026-10-13: "five more degrees" reached the model, which said "now turned 22 degrees" while nothing moved)."""
    t = tilts()
    o = {s: _outwards(s, t[s]) for s in t}
    how = (f"both {abs(o['left']):g} degrees {'outwards' if o['left'] >= 0 else 'inwards'}" if o["left"] == o["right"] else
           f"left {o['left']:g}, right {o['right']:g} degrees outwards")
    return (f"eye screens rotated {how} - only the rotate-your-eyes command turns them; you can't turn them in a reply, "
            "so never say you turned or moved them")


def close_eyes(which="both", seconds=LIDS_HOLD):
    """Close Gene's "left", "right" or "both" eyes for `seconds` (on top of the face he is showing).
    Returns which eyes are closed now."""
    d, now = _read(LIDS) or {}, time.time()
    for side in (("left", "right") if which == "both" else (which,)):
        d[side] = max(float(d.get(side) or 0), now + seconds)       # a wink doesn't cut a longer close short
    _write(LIDS, d)
    return lids_shut()


def open_eyes(which="both"):
    """Open Gene's "left", "right" or "both" eyes."""
    d = _read(LIDS) or {}
    for side in (("left", "right") if which == "both" else (which,)):
        d[side] = 0
    _write(LIDS, d)


def lids_shut():
    """Which eyes are closed by voice right now: "left", "right", "both" or None."""
    d, now = _read(LIDS) or {}, time.time()
    shut = [side for side in ("left", "right") if isinstance(d.get(side), (int, float)) and now < d[side]]
    return "both" if len(shut) == 2 else shut[0] if shut else None


def progress(percent, step=""):
    """Show the loading eyes at `percent` (0-100) for as long as this process lives or until done()."""
    _write(PROGRESS, {"percent": max(0.0, min(100.0, float(percent))), "step": step, "pid": os.getpid(),
                      "t": time.time()})


def last_poke():
    return _read(POKE)


def done():
    try:
        os.unlink(PROGRESS)
    except FileNotFoundError:
        pass


# ---------- the display ----------

def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


class Mood:
    """What the eyes should show right now, re-read from the state files a few times a second."""
    def __init__(self):
        self.emote, self.percent, self.since, self.checked = "neutral", None, time.time(), 0.0
        self.shut = None        # eyes closed by voice: "left", "right", "both" (not while upgrading)
        self.swapped = swapped()    # screens switched left and right by voice
        self.tilt = tilts()         # each eye's turn, by voice
        self.tilt_t = (_read(TILT) or {}).get("t", 0)

    def update(self, now):
        if now - self.checked < 0.15:
            return
        self.checked = now
        old = self.emote
        p = _read(PROGRESS)
        if p and _alive(p.get("pid")):
            self.emote, self.percent = "loading", float(p.get("percent", 0))
        else:
            self.percent = None
            e = _read(EYES) or {}
            em = e.get("emote", "neutral")
            until = e.get("until") or e.get("t", 0) + IDLE_RESET
            if em not in CHOICES or (em != "flashlight" and time.time() > until):
                em = "neutral"
            self.emote = em
        self.shut = None if self.percent is not None else lids_shut()
        self.swapped = swapped()
        self.tilt = tilts()
        self.tilt_t = (_read(TILT) or {}).get("t", 0)
        if self.emote != old:
            self.since = now


def _rgb(h, s, l):
    import colorsys
    return colorsys.hls_to_rgb((h % 360) / 360, max(0, min(100, l)) / 100, max(0, min(100, s)) / 100)


_backdrops = {}


def _backdrop(w, h):
    """The parts that never change, drawn once per screen size: the dark screen, and the rim's vignette ring
    (radial-gradient paints are the slowest thing here)."""
    if (w, h) not in _backdrops:
        import cairo
        R = min(w, h) / 2
        bg = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h); g = cairo.Context(bg)
        g.set_source_rgb(0, 0, 0); g.paint()
        g.translate(w / 2, h / 2); g.scale(R, R)
        grad = cairo.RadialGradient(0, 0, 0.1, 0, 0, 1)
        grad.add_color_stop_rgb(0, 0x05 / 255, 0x0c / 255, 0x12 / 255); grad.add_color_stop_rgb(1, 1 / 255, 3 / 255, 5 / 255)
        g.set_source(grad); g.arc(0, 0, 1, 0, 2 * math.pi); g.fill()
        rim = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h); g = cairo.Context(rim)
        g.translate(w / 2, h / 2); g.scale(R, R)
        grad = cairo.RadialGradient(0, 0, 0.86, 0, 0, 1)
        grad.add_color_stop_rgba(0, 0, 0, 0, 0); grad.add_color_stop_rgba(1, 0, 0, 0, 0.85)
        g.set_source(grad); g.arc(0, 0, 1, 0, 2 * math.pi); g.fill()
        _backdrops[(w, h)] = bg, rim
    return _backdrops[(w, h)]


class Eye:
    def __init__(self, inner):
        self.inner = inner          # +1: the inboard side is screen right (the viewer's left eye), -1: screen left
        self.p = dict(EMOTES["neutral"])
        self.lid = 0.0              # 0 open .. 1 closed (wink / closed by voice), eased so the lid slides shut
        self.shown = 0.0            # progress as drawn, chasing the real value so the ring sweeps smoothly
        self.turn = None            # deg clockwise as drawn, easing to the voice-set tilt so the eye visibly turns

    def ease(self, goal, k):
        for key, v in goal.items():
            d = v - self.p[key]
            if key == "hue":
                d = ((d % 360) + 540) % 360 - 180      # the short way round the colour wheel
            self.p[key] += d * k
            if key == "hue":
                self.p["hue"] %= 360

    def col(self, g, l, a):
        r, gg, b = _rgb(self.p["hue"], self.p["sat"], l)
        g.set_source_rgba(r, gg, b, a)

    def render(self, g, w, h, t, mood, blink, gx, gy, closed, pulse):
        import cairo
        p, s = self.p, self.inner
        R = min(w, h) / 2
        bg, rim = _backdrop(w, h)
        g.set_source_surface(bg); g.paint()
        g.save()
        g.translate(w / 2, h / 2); g.scale(R, R)
        g.arc(0, 0, 1, 0, 2 * math.pi); g.clip()

        def colstop(grad, off, l, a):
            r, gg, b = _rgb(p["hue"], p["sat"], l); grad.add_color_stop_rgba(off, r, gg, b, a)

        def quad(cx, cy, x, y):       # canvas quadraticCurveTo -> cairo cubic
            x0, y0 = g.get_current_point()
            g.curve_to(x0 + 2 / 3 * (cx - x0), y0 + 2 / 3 * (cy - y0), x + 2 / 3 * (cx - x), y + 2 / 3 * (cy - y), x, y)

        HUB = 0.34
        P = max(HUB + 0.02, p["pupil"] - 0.07 * pulse)
        I = p["iris"]
        loading = mood.emote == "loading"
        spin = (0.9 - P) * 2.2 + gx * 0.35 + (t * 3.5 * s if loading else 0)
        focus = t * 0.25 * (0.3 + abs(gx)) + gx * 0.8
        N = 9
        if p["beam"] > 0.5:
            # torch: the whole panel full warm-white; only the camera hub stays dark
            fl = min(1, p["beam"]) * (1 - 0.6 * pulse * random.random())
            pan = cairo.RadialGradient(0, 0, HUB, 0, 0, 1)
            pan.add_color_stop_rgba(0, 1, 1, 250 / 255, fl); colstop(pan, 0.85, p["lit"] + 6, fl); colstop(pan, 1, p["lit"] - 6, fl)
            g.set_source(pan); g.paint()
        elif p["heart"] > 0.5:
            beat = 1 + 0.05 * math.sin(t * 9)
            g.save(); g.scale(0.82 * beat, 0.82 * beat); g.translate(0, 0.08)
            def heart():
                g.new_path(); g.move_to(0, 0.95)
                g.curve_to(-1.25, 0.1, -0.75, -0.95, 0, -0.35); g.curve_to(0.75, -0.95, 1.25, 0.1, 0, 0.95); g.close_path()
            for k in range(6, 0, -1):         # glow (canvas shadowBlur)
                g.save(); sc = 1 + 0.035 * k * p["glow"]; g.scale(sc, sc); heart(); self.col(g, 60, 0.07); g.fill(); g.restore()
            heart()
            hg = cairo.RadialGradient(0, -0.05, 0.3, 0, 0, 1); colstop(hg, 0, p["lit"] + 15, 1); colstop(hg, 1, p["lit"] - 12, 1)
            g.set_source(hg); g.fill(); g.restore()
        else:
            # glow behind the iris
            gl = cairo.RadialGradient(0, 0, I * 0.9, 0, 0, I + 0.3 * p["glow"])
            colstop(gl, 0, 58, 0.55); colstop(gl, 1, 58, 0)
            g.set_source(gl); g.arc(0, 0, I + 0.3 * p["glow"], 0, 2 * math.pi); g.fill()
            self.col(g, p["lit"] - 25, 1); g.arc(0, 0, I, 0, 2 * math.pi); g.fill()
            # aperture blades: N wedges between curved seams, alternately shaded, like a camera diaphragm
            m = (P + I) * 0.55
            for k in range(N):
                a0 = spin + k * 2 * math.pi / N; a1 = a0 + 2 * math.pi / N
                shade = p["lit"] + (4 if k % 2 else -4)
                bgr = cairo.RadialGradient(0, 0, P, 0, 0, I)
                colstop(bgr, 0, shade + 22, 1); colstop(bgr, 0.5, shade + 4, 1); colstop(bgr, 1, shade - 16, 1)
                g.new_path(); g.move_to(math.cos(a0) * P, math.sin(a0) * P)
                quad(math.cos(a0 + 0.45) * m, math.sin(a0 + 0.45) * m, math.cos(a0 + 0.75) * I, math.sin(a0 + 0.75) * I)
                g.arc(0, 0, I, a0 + 0.75, a1 + 0.75)
                quad(math.cos(a1 + 0.45) * m, math.sin(a1 + 0.45) * m, math.cos(a1) * P, math.sin(a1) * P)
                g.close_path(); g.set_source(bgr); g.fill()
                g.move_to(math.cos(a0) * P, math.sin(a0) * P)
                quad(math.cos(a0 + 0.45) * m, math.sin(a0 + 0.45) * m, math.cos(a0 + 0.75) * I, math.sin(a0 + 0.75) * I)
                g.set_source_rgba(0, 0, 0, 0.55); g.set_line_width(0.012); g.stroke()
            # the dark polygonal opening the lens looks out through
            g.new_path()
            for k in range(N + 1):
                a = spin + k * 2 * math.pi / N
                (g.line_to if k else g.move_to)(math.cos(a) * P, math.sin(a) * P)
            g.set_source_rgb(1 / 255, 2 / 255, 3 / 255); g.fill_preserve()
            self.col(g, p["lit"] + 30, 0.7); g.set_line_width(0.015); g.stroke()
            # focus ring with engraved ticks, turning with gaze
            self.col(g, p["lit"] + 28, 0.9); g.set_line_width(0.028); g.arc(0, 0, I + 0.035, 0, 2 * math.pi); g.stroke()
            for k in range(60):
                a = focus + k * math.pi / 30; long = k % 5 == 0
                r0, r1 = I + 0.07, I + (0.15 if long else 0.11)
                self.col(g, p["lit"] + (25 if long else 10), 0.85 if long else 0.5); g.set_line_width(0.018 if long else 0.01)
                g.move_to(math.cos(a) * r0, math.sin(a) * r0); g.line_to(math.cos(a) * r1, math.sin(a) * r1); g.stroke()
            if loading:
                # progress ring: filled to the real upgrade percentage; a comet of dots chases round inside it
                RR, a0 = I + 0.075, -math.pi / 2
                g.set_line_cap(cairo.LINE_CAP_ROUND); g.set_line_width(0.075)
                self.col(g, p["lit"] - 10, 0.55); g.arc(0, 0, RR, 0, 2 * math.pi); g.stroke()
                if mood.percent is None:
                    frac = (t * 0.32) % 1
                else:
                    self.shown += (mood.percent / 100 - self.shown) * 0.12
                    frac = self.shown
                for wdt, alpha in ((0.16, 0.18), (0.11, 0.3), (0.075, 1)):     # glow, then the bar
                    self.col(g, p["lit"] + 42, alpha); g.set_line_width(wdt)
                    g.arc(0, 0, RR, a0, a0 + max(0.02, frac) * 2 * math.pi); g.stroke()
                hd = a0 + t * 6 * s
                for q in range(8):
                    aq, rq = hd - q * 0.22 * s, (P + I) / 2
                    r, gg, b = _rgb(p["hue"], 90, 85); g.set_source_rgba(r, gg, b, 1 - q / 8)
                    g.arc(math.cos(aq) * rq, math.sin(aq) * rq, 0.05 * (1 - q / 12), 0, 2 * math.pi); g.fill()
                g.set_line_cap(cairo.LINE_CAP_BUTT)
            # catch-light on the blades, never on the lens itself
            g.save(); g.translate(-I * 0.52, -I * 0.52); g.rotate(-0.8); g.scale(0.07, 0.045)
            g.arc(0, 0, 1, 0, 2 * math.pi); g.restore()
            g.set_source_rgba(1, 1, 1, 0.55); g.fill()
        if p["fear"] > 0.05:
            # slit pupil, veins creeping in from the rim, the whole screen twitching
            fr = min(1, p["fear"]); jit = (random.random() - 0.5) * 0.12 if random.random() < 0.08 else 0
            g.save(); g.translate(jit, 0); g.push_group()
            sw = 0.24 + 0.05 * math.sin(t * 4)
            g.move_to(0, -I * 1.02); quad(sw, 0, 0, I * 1.02); quad(-sw, 0, 0, -I * 1.02)
            g.set_source_rgb(0, 0, 0); g.fill()
            self.col(g, p["lit"] + 22, 0.85); g.set_line_cap(cairo.LINE_CAP_ROUND)
            for k in range(14):
                va = k * 2.39996 + 0.3; vx, vy = math.cos(va), math.sin(va)
                ln = 0.3 + 0.12 * math.sin(k * 7.1 + t)
                mx = vx * (1 - ln * 0.5) + vy * 0.05 * math.sin(k * 3.3); my = vy * (1 - ln * 0.5) - vx * 0.05 * math.sin(k * 3.3)
                g.set_line_width(0.026); g.move_to(vx, vy); quad(mx, my, vx * (1 - ln), vy * (1 - ln)); g.stroke()
                g.set_line_width(0.009); g.move_to(mx, my); g.line_to(mx + vy * 0.07, my - vx * 0.07); g.stroke()
            g.pop_group_to_source(); g.paint_with_alpha(fr); g.restore()
        # lids: tilted top edge, bottom edge that bows into a smile; gaze shifts them a little
        top, bot = p["top"] + gy * 0.10, p["bot"] + gy * 0.06
        if blink > 0:
            top += (bot - 0.02 - top) * blink
        if closed > 0:          # 0..1 while the lid slides shut
            top, bot = top + (0.35 - top) * closed, bot + (0.36 - bot) * closed
        tilt, M = p["tilt"] * s + gx * 0.08, 24
        xs = [-1.2 + 2.4 * k / M for k in range(M + 1)]
        for edge_y, corner in ((lambda x: top + tilt * x * 0.5, -1.2), (lambda x: bot - p["curve"] * (1 - x * x), 1.2)):
            g.new_path(); g.move_to(-1.2, corner)
            for x in xs:
                g.line_to(x, edge_y(x))
            g.line_to(1.2, corner); g.close_path()
            g.set_source_rgb(1 / 255, 3 / 255, 5 / 255); g.fill()
            g.new_path()
            for x in xs:
                g.line_to(x, edge_y(x))
            self.col(g, p["lit"] + 10, 0.6); g.set_line_width(0.025); g.stroke()
        if p["tear"] > 0.05 and closed < 0.5:
            ty, tx = 0.4 + ((t * 0.4) % 1) * 0.5, -s * 0.55
            g.move_to(tx, ty - 0.12); quad(tx + 0.08, ty, tx, ty + 0.05); quad(tx - 0.08, ty, tx, ty - 0.12)
            self.col(g, p["lit"] + 20, 0.9 * min(1, p["tear"])); g.fill()
        if p["fear"] > 0.05 and closed < 0.5:
            # blood running from the lower lid, two drips per eye on their own clocks
            self.col(g, p["lit"] - 8, min(1, p["fear"]))
            for dx0, sp, ph in ((-0.3, 0.37, 0), (0.22, 0.29, 0.45)):
                dx = dx0 * s; u = (t * sp + ph) % 1; y0 = bot - p["curve"] * (1 - dx * dx); ln = 0.08 + u * 0.55
                g.rectangle(dx - 0.018, y0 - 0.01, 0.036, ln); g.fill()
                g.arc(dx, y0 + ln, 0.045, 0, 2 * math.pi); g.fill()
        if mood.emote == "sleepy" and s > 0:
            zz = (t * 0.6) % 1
            g.select_font_face("sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); g.set_font_size(0.32)
            self.col(g, 70, 0.8 * (1 - zz)); g.move_to(0.4, -0.5 - zz * 0.3); g.show_text("z")
        # dark rim, as on the round LCD
        g.save(); g.identity_matrix(); g.set_source_surface(rim); g.paint(); g.restore()
        if p["fear"] > 0.5 and random.random() < 0.05:
            g.set_source_rgba(0, 0, 0, 0.85); g.rectangle(-1, 2 * random.random() - 1, 2, 2 * (0.08 + random.random() * 0.3)); g.fill()
        g.restore()


def main():
    import gi
    gi.require_version("Gtk", "3.0"); gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk, GLib

    mood = Mood()
    t0 = time.monotonic()
    anim = dict(pulse=0.0, next_blink=2.5, blink_start=-1.0, gx=0.0, gy=0.0, tx=0.0, ty=0.0, next_gaze=0.0, emote=None,
                hidden_until=0.0, covered=False, swapped=False)
    windows = []        # (window, area, eye)

    def hide(*_):
        print(time.strftime("%H:%M:%S"), f"hidden for {HIDE_FOR} s", flush=True)
        anim["hidden_until"] = time.monotonic() + HIDE_FOR
        for win, _a, _e in windows:
            win.hide()
        return True

    def build(*_):
        for win, _a, _e in windows:
            win.destroy()
        windows.clear()
        anim["covered"] = False
        disp = Gdk.Display.get_default()
        mons = sorted((disp.get_monitor(i) for i in range(disp.get_n_monitors())),
                      key=lambda m: (m.get_geometry().x, m.get_geometry().y), reverse=mood.swapped)
        anim["swapped"] = mood.swapped
        print(time.strftime("%H:%M:%S"), f"{len(mons)} monitor(s):",
              ", ".join(f"{m.get_model() or '?'} {m.get_geometry().width}x{m.get_geometry().height}" for m in mons), flush=True)
        screen = Gdk.Screen.get_default()
        for i, mon in enumerate(mons):
            eye = Eye(+1 if i % 2 == 0 else -1)
            win = Gtk.Window(title=f"Gene eye {i + 1}")
            win.set_decorated(False)
            win.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1))
            area = Gtk.DrawingArea()
            area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            area.connect("draw", lambda w, g, eye=eye, i=i: draw(w, g, eye, i))
            area.connect("button-press-event", lambda w, ev, i=i: tap(w, ev, i))
            win.connect("key-press-event", lambda w, ev: ev.keyval == Gdk.KEY_Escape and hide())
            win.connect("focus-out-event", lambda *_: GLib.timeout_add(300, check_covered) and False)
            win.connect("realize", lambda w: w.get_window().set_cursor(Gdk.Cursor.new_from_name(w.get_display(), "none")))
            win.add(area)
            win.show_all()
            win.fullscreen_on_monitor(screen, [disp.get_monitor(k) for k in range(disp.get_n_monitors())].index(mon))
            windows.append((win, area, eye))
        return False

    taps = {"n": 0, "last": 0.0, "eye": 0, "center": False, "timer": 0}

    def tap(widget, ev, i):
        """Touch arrives as emulated clicks. GTK also sends synthetic double/triple-click events: count only real presses."""
        if ev.type != Gdk.EventType.BUTTON_PRESS:
            return True
        now = time.monotonic()
        if now - taps["last"] > TAP_GAP:
            taps["n"] = 0
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        r = math.hypot(ev.x - w / 2, ev.y - h / 2) / (min(w, h) / 2)
        taps.update(n=taps["n"] + 1, last=now, eye=i, center=r < 0.45)
        if taps["timer"]:
            GLib.source_remove(taps["timer"]); taps["timer"] = 0
        if taps["n"] >= 3:
            taps["n"] = 0; hide()
        else:
            taps["timer"] = GLib.timeout_add(int(TAP_GAP * 1000), poked)
        return True

    def poked():
        """The taps stopped short of 3: that was a poke. Monitors run left to right as seen from the front
        (right to left when switched by voice), so the first is Gene's right eye."""
        taps["timer"] = 0
        n = len(windows)
        eye = None if n < 2 else ("right" if taps["eye"] == 0 else "left")
        print(time.strftime("%H:%M:%S"), f"poked {eye + ' ' if eye else ''}eye x{taps['n']}{' in the lens' if taps['center'] else ''}", flush=True)
        _write(POKE, {"t": time.time(), "eye": eye, "taps": taps["n"], "center": taps["center"]})
        taps["n"] = 0
        return False

    def check_covered():
        """Focus went to some other window (not just between the eyes): it is probably on top of them now."""
        if windows and not any(w.is_active() for w, _a, _e in windows):
            anim["covered"] = True
        return False

    def draw(widget, g, eye, i):
        t = time.monotonic() - t0
        # monitors run left to right as seen from the front (right to left when switched): even ones are Gene's right eye, odd ones his left.
        # With a single screen, closing either eye closes it
        side = "right" if i % 2 == 0 else "left"
        closed = (mood.emote == "wink" and (i == 1 or len(windows) == 1)
                  or mood.shut == "both" or mood.shut == side or (mood.shut and len(windows) == 1))
        eye.lid += ((1.0 if closed else 0.0) - eye.lid) * 0.45
        eye.lid = 1.0 if eye.lid > 0.99 else 0.0 if eye.lid < 0.01 else eye.lid
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        if UPSIDE_DOWN:     # the screens are mounted upside down: turn the whole eye 180 deg about the centre
            g.translate(w, h); g.rotate(math.pi)
        if eye.turn:            # undo the inward tilt of the screens (set and eased in tick)
            g.translate(w / 2, h / 2); g.rotate(math.radians(eye.turn)); g.translate(-w / 2, -h / 2)
        eye.render(g, w, h, t, mood, anim["blink"],
                   anim["gx"], anim["gy"], eye.lid, anim["pulse"])
        level = LEVEL_SHOW - (time.time() - mood.tilt_t)
        if 0 < level <= LEVEL_SHOW and len(windows) >= 2:
            # just turned by voice: a level line through the middle and a notch at the eye's top, turned with it
            R, a = min(w, h) / 2, min(1.0, level / 2)
            g.save(); g.translate(w / 2, h / 2); g.scale(R, R)
            g.set_source_rgba(1, 1, 1, 0.85 * a); g.set_line_width(0.02)
            g.move_to(-0.97, 0); g.line_to(0.97, 0); g.stroke()
            # (UPSIDE_DOWN is already applied, so -y is the eye's top as seen from the front)
            g.move_to(-0.06, -0.97); g.line_to(0.06, -0.97); g.line_to(0, -0.82); g.close_path(); g.fill()
            g.restore()
        return True

    def turn_goal(i):
        """The voice-set turn of the eye in window i, by PHYSICAL position (a swap reverses i); 0 with one screen."""
        if len(windows) < 2:
            return 0.0
        viewer_left = (i % 2 == 0) != bool(anim["swapped"])     # = Gene's right eye
        return mood.tilt["right" if viewer_left else "left"]

    def tick():
        now = time.monotonic(); t = now - t0
        if anim["hidden_until"]:
            if now < anim["hidden_until"]:
                return True
            anim["hidden_until"] = 0.0
            for win, _a, _e in windows:
                win.show_all()
        mood.update(now)
        if mood.swapped != anim["swapped"]:
            print(time.strftime("%H:%M:%S"), "screens switched", "over" if mood.swapped else "back", flush=True)
            build()
        if mood.emote != anim["emote"]:
            starting = mood.emote == "loading" and not any(w.is_active() for w, _a, _e in windows)
            if anim["emote"] is not None and (anim["covered"] or starting):
                # a new face while another window is in front: labwc ignores present(), but a newly mapped window
                # goes on top, so open the eyes again. An upgrade starting always does this unless the eyes have
                # focus: "covered" only notices a window that took focus from the eyes, not one already in front
                print(time.strftime("%H:%M:%S"), "bringing the eyes back to the front", flush=True)
                build()
            anim["emote"], anim["pulse"] = mood.emote, 1.0
            if mood.emote == "surprised":
                anim["blink_start"], anim["next_blink"] = -1.0, t + 1.5
        goal = EMOTES[mood.emote]
        turning = time.time() - mood.tilt_t < LEVEL_SHOW + 0.5
        for k, (_w, _a, eye) in enumerate(windows):
            eye.ease(goal, 0.18)
            want = turn_goal(k)
            if eye.turn is None:
                eye.turn = want
            elif abs(want - eye.turn) > 0.05:
                eye.turn += (want - eye.turn) * 0.1; turning = True
            else:
                eye.turn = want
        blink = 0.0
        if mood.emote not in ("sleepy", "wink", "scary", "flashlight"):
            if anim["blink_start"] < 0 and t > anim["next_blink"]:
                anim["blink_start"] = t
            if anim["blink_start"] >= 0:
                u = (t - anim["blink_start"]) / 0.16
                blink = u if u < 1 else (2 - u if u < 2 else 0)
                if u >= 2:
                    anim["blink_start"], anim["next_blink"] = -1.0, t + 2.2 + random.random() * 3.5
        anim["blink"] = blink
        if mood.emote == "loading":         # eyes steady on the progress while upgrading
            anim["tx"] = anim["ty"] = 0.0
        elif t > anim["next_gaze"]:
            anim["tx"], anim["ty"] = random.uniform(-1, 1), random.uniform(-0.7, 0.7)
            anim["pulse"] = max(anim["pulse"], 0.35); anim["next_gaze"] = t + 0.9 + random.random() * 1.8
        anim["gx"] += (anim["tx"] - anim["gx"]) * 0.2; anim["gy"] += (anim["ty"] - anim["gy"]) * 0.2
        anim["pulse"] *= 0.88
        # the iris drifts slowly all the time, which 8 fps shows just as well; anything quicker gets every frame
        moving = (turning or blink > 0 or abs(anim["tx"] - anim["gx"]) + abs(anim["ty"] - anim["gy"]) > 0.02 or anim["pulse"] > 0.03
                  or mood.emote in ("loading", "scary", "love")
                  or any(0 < eye.lid < 1          # a lid sliding (it starts within IDLE_EVERY frames)
                         or max(abs(((v - eye.p[k]) % 360 + 540) % 360 - 180) if k == "hue" else abs(v - eye.p[k])
                                for k, v in goal.items()) > 0.01
                         for _w, _a, eye in windows))
        anim["frame"] = anim.get("frame", 0) + 1
        if moving or anim["frame"] % IDLE_EVERY == 0:
            for _w, area, _e in windows:
                area.queue_draw()
        return True

    anim["blink"] = 0.0
    disp = Gdk.Display.get_default()
    if disp is None:
        raise SystemExit("no display")
    # rebuild shortly after a hotplug, once the new monitor's geometry has settled
    pending = {"id": 0}
    def replug(*_):
        if pending["id"]:
            GLib.source_remove(pending["id"])
        def go():
            pending["id"] = 0; build(); return False
        pending["id"] = GLib.timeout_add(700, go)
    disp.connect("monitor-added", replug)
    disp.connect("monitor-removed", replug)
    build()
    GLib.timeout_add(1000 // FPS, tick)
    Gtk.main()


if __name__ == "__main__":
    main()
