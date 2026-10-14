"""Gene's sense of time: the date/time line for the model, plus spoken timers and reminders.

  "set a timer for 5 minutes" / "remind me in 20 minutes to check the oven" / "remind me at 7 pm to call mom"
  "how long is left on my timer?" / "cancel the timer" / "cancel all reminders"

Handled without the LLM. Timers are kept in state/timers.json, so they survive a restart.
"""
import datetime, json, os, re, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TIMERS = os.path.join(HERE, "state", "timers.json")

NUMS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                   "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
NUMS.update({"thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90, "a": 1, "an": 1,
             "a couple": 2, "a couple of": 2, "a few": 3, "half an": 0.5, "half a": 0.5})
NUM = r"(\d+(?:\.\d+)?|" + "|".join(sorted(map(re.escape, NUMS), key=len, reverse=True)) + r")"
UNIT = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600, "day": 86400}
DURATION = re.compile(NUM + r"(?:\s+and\s+a\s+half)?\s*(second|sec|minute|min|hour|hr|day)s?\b(?:\s+and\s+a\s+half)?", re.I)
AT = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?|\bat\s+(noon|midnight)", re.I)

TIMER_ASK = re.compile(r"\b(?:set|start|make)\s+(?:a\s+|an\s+|the\s+|my\s+)?(?:\S+\s+){0,3}?timer\b|\btimer\s+for\b", re.I)
REMIND_ASK = re.compile(r"\bremind\s+(?:me|us)\b|\bset\s+(?:a\s+|an\s+)?(?:reminder|alarm)\b|\bwake\s+me\s+up\b", re.I)
CANCEL = re.compile(r"\b(?:cancel|stop|delete|clear|remove|turn\s+off)\b.*\b(?:timer|reminder|alarm)s?\b", re.I)
STATUS = re.compile(r"\b(?:how\s+(?:long|much\s+time)|time\s+left|when\s+(?:is|does)|what\s+(?:timers|reminders))\b.*"
                    r"\b(?:timer|reminder|alarm)s?\b|\b(?:any|my)\s+(?:timers|reminders)\b.*\?", re.I)


def _n(s):
    s = s.lower()
    return float(s) if re.fullmatch(r"[\d.]+", s) else NUMS[s]


def clock_line():
    """For the model: "(clock: Thursday, October 1, 2026, 8:45 PM)". Never stored in history."""
    now = datetime.datetime.now()
    return "(clock: " + now.strftime("%A, %B ") + str(now.day) + now.strftime(", %Y, ") + speak_time(now) + ")"


def speak_time(t):
    return t.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def _spoken(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} second{'s' * (seconds != 1)}"
    if seconds < 300 and seconds % 60:
        m, s = divmod(seconds, 60)
        return f"{m} minute{'s' * (m != 1)} and {s} second{'s' * (s != 1)}"
    h, m = divmod((seconds + 30) // 60, 60)
    parts = [f"{h} hour{'s' * (h != 1)}"] * bool(h) + [f"{m} minute{'s' * (m != 1)}"] * bool(m)
    return " and ".join(parts)


def _duration(text):
    total = 0
    for m in DURATION.finditer(text):
        n = _n(m.group(1)) + (0.5 if "and a half" in m.group(0).lower() else 0)
        total += n * UNIT[m.group(2).lower().rstrip("s")]
    return total


def _at(text):
    """'at 7 pm' -> the next such datetime, or None."""
    m = AT.search(text)
    if not m:
        return None
    now = datetime.datetime.now()
    if m.group(4):
        h, mi = (12, 0) if m.group(4).lower() == "noon" else (0, 0)
    else:
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower().replace(".", "")
        if h > 23 or mi > 59:
            return None
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
    t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if not m.group(3) and not m.group(4) and h <= 12:      # "at 7" - the next 7 o'clock, am or pm
        while t <= now:
            t += datetime.timedelta(hours=12)
    while t <= now:
        t += datetime.timedelta(days=1)
    return t


def _what(text):
    """'remind me in 20 minutes to check the oven' -> 'check the oven'."""
    m = re.search(r"\b(?:to|that|about)\s+(.+)", REMIND_ASK.split(text, 1)[-1], re.I)
    if not m:
        return ""
    w = DURATION.sub("", AT.sub("", m.group(1)))
    w = re.sub(r"\b(?:in|for|after)\s*$|\s+(?:in|for)\s+(?=[.!?]|$)", "", w.strip(), flags=re.I)
    w = re.sub(r"\bmy\b", "your", re.sub(r"\bI\b", "you", re.sub(r"\bI'm\b", "you're", w)))
    return w.strip(" .!?,")


class Timers:
    def __init__(self, say):
        self.say, self.lock = say, threading.Lock()
        try:
            self.items = json.load(open(TIMERS))
        except (OSError, ValueError):
            self.items = []
        threading.Thread(target=self._run, daemon=True).start()

    def _save(self):
        os.makedirs(os.path.dirname(TIMERS), exist_ok=True)
        with open(TIMERS + ".tmp", "w") as f:
            json.dump(self.items, f)
        os.replace(TIMERS + ".tmp", TIMERS)

    def _run(self):
        while True:
            time.sleep(1)
            with self.lock:
                due = [t for t in self.items if t["due"] <= time.time()]
                if not due:
                    continue
                self.items = [t for t in self.items if t not in due]
                self._save()
            for t in due:
                late = time.time() - t["due"] > 120          # Gene was off when it went off
                if t["what"]:
                    self.say(("I missed it while I was off, but you" if late else "Reminder: you") + f" wanted to {t['what']}."
                             if not re.match(r"(?i)(?:the|your|a|an)\b", t["what"]) else f"Reminder: {t['what']}.")
                else:
                    self.say(f"Your {t['label']} timer is done." + (" Sorry, I was off when it finished." if late else ""))

    def command(self, heard):
        """Returns what Gene should say if `heard` is about timers or reminders, else None."""
        if CANCEL.search(heard):
            with self.lock:
                n = len(self.items)
                if not n:
                    return "There aren't any timers or reminders set."
                if re.search(r"\b(?:all|every)\b|timers|reminders", heard, re.I) or n == 1:
                    self.items = []
                else:
                    self.items = self.items[:-1]
                self._save()
            return "Okay, cancelled." if n == 1 or self.items else f"Okay, I cancelled all {n} of them."
        if STATUS.search(heard):
            with self.lock:
                items = sorted(self.items, key=lambda t: t["due"])
            if not items:
                return "You don't have any timers or reminders set."
            parts = [(f"{t['what']} at {speak_time(datetime.datetime.fromtimestamp(t['due']))}" if t["what"]
                      else f"{_spoken(t['due'] - time.time())} left on the {t['label']} timer") for t in items[:3]]
            return "You have " + "; ".join(parts) + "."
        is_timer, is_remind = TIMER_ASK.search(heard), REMIND_ASK.search(heard)
        if not (is_timer or is_remind):
            return None
        secs, at = _duration(heard), _at(heard)
        if not secs and not at:
            return None             # "remind me what we said" - not a reminder; let the model answer
        due = at.timestamp() if at and not secs else time.time() + secs
        what = _what(heard) if is_remind else ""
        label = re.sub(r"(second|minute|hour)s\b", r"\1", _spoken(secs)) if secs else "your"   # "5 minute timer"
        with self.lock:
            self.items.append({"due": due, "what": what, "label": label, "set": time.time()})
            self._save()
        when = f"in {_spoken(due - time.time())}" if secs else f"at {speak_time(datetime.datetime.fromtimestamp(due))}"
        if what:
            return f"Okay, I'll remind you {when} to {what}."
        if is_remind:
            return f"Okay, I'll remind you {when}."
        return f"Okay, {label} timer, starting now." if secs else f"Okay, timer set for {when[3:]}."
