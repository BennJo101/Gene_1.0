"""Gene's ears and mouth on the Pi: mic -> Parakeet STT (this Pi) -> brain (streamed) -> Piper voice -> speaker.

Follows the Pi-client settings in "Brain (Jetson)/README.md":
  - end of speech after 0.3 s of silence
  - the brain is gene_brain.py: Claude (Anthropic API) first, the Jetson's Ollama model "gene" as the fallback, so
    the head works on its own on a hotspot; Gene's personality is the Modelfile prompt for both
  - what the two eye cameras see (gene_cameras.py, YOLOv10n on the Pi) as a "(camera: person, cup)" context line
  - a real look when asked ("what colour is this?", "what am I holding?", "read this"): the camera frame goes to
    Claude with the question; without Claude, Moondream on the Pi (gene_vision.py) describes it for the Jetson
  - web search results (gene_web.py) as a "(web: ...)" line when asked to look something up
  - sound bites by name (gene_sounds.py, "play the Wilhelm scream sound effect") are played directly
  - songs from YouTube (gene_music.py, "play Get Lucky by Daft Punk", "stop the music") play in the background; while
    one plays only music / volume commands or words with "Gene" in them are answered (the mic hears the song)
  - GPIO pin commands (gene_gpio.py, "turn on pin 17", "play a song on physical pin 12") are done directly
  - timers and reminders (gene_clock.py) too; the date and time go to the model as a "(clock: ...)" line
  - long-term memory (gene_memory.py): related facts from past conversations as a "(memory: ...)" line,
    "remember that ..." / "forget ..." handled directly, chat history kept across restarts
  - speak one sentence at a time as it streams in, hard stop after 3 sentences
  - eyes (gene_eyes.py): the model starts its reply with a face tag, "[happy] ...", which is shown on the eye
    screens and never spoken

Audio goes through PipeWire (pw-cat / pw-play), so it uses the default mic and speaker.
Run:  ~/gene/venv/bin/python ~/gene/gene_client.py
"""
import json, os, queue, re, subprocess, sys, tempfile, threading, time, urllib.request, uuid
import numpy as np
import gene_tts, gene_web, gene_gpio, gene_clock, gene_memory, gene_eyes, gene_sounds, gene_files, gene_usb, gene_volume, gene_music
import gene_cameras, gene_vad, gene_vision, gene_brain

STT_URL = os.environ.get("GENE_STT", "http://127.0.0.1:8081/inference")   # Parakeet on this Pi (stt/, gene-stt.service)
# since 2026-10-08 (asked: "as fast as possible") STT goes to whisper.cpp on the Jetson GPU first (~0.3 s vs ~0.85 s
# here); the Pi's Parakeet is the fallback when the Jetson is off or slow. GENE_STT_FIRST="" turns the Jetson off.
STT_FIRST = os.environ.get("GENE_STT_FIRST", f"http://{gene_brain.JETSON}:8081/inference")
STT_FIRST_TIMEOUT = 3      # s before giving up on the Jetson for this phrase
STT_FIRST_RETRY = 60       # s the Jetson STT is skipped after it fails
SR = 16000
FRAME = 480                 # 30 ms
END_SILENCE = 0.5           # s of quiet that ends a phrase (0.7 until 2026-10-08, cut for speed). Was 0.3 (README): a normal pause mid-sentence cut it in
                            # two ("What about this? Uh", "Looks like"), and halves transcribe worse (2026-10-06)
PREROLL = 0.5               # s kept from before speech starts, so a soft first syllable isn't clipped
MIN_SPEECH = 0.25           # s; shorter blips are ignored
MAX_PHRASE = 20             # s; a "phrase" this long is cut, and the noise floor re-measured from its quietest part: a
                            # hissy new mic (the C-Media dongle, 2026-10-07, ~0.09 RMS of noise) is "loud" all the time
                            # from the start, so the floor never got a quiet frame to learn from and no phrase ever ended
MAX_SENTENCES = 3
PLAY_SLACK = 8              # s past a clip's length before a stuck pw-play is killed
HISTORY_MAX = 16            # exchanges kept as context; trimmed to HISTORY_KEEP in one go, so the Jetson
HISTORY_KEEP = 6            # can reuse its cached prompt between turns instead of reprocessing it every time


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def mic_present():
    """True when PipeWire's default source is a real input. With no mic plugged in it falls back to a
    speaker's monitor, and Gene would be listening to his own voice."""
    out = subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True).stdout
    return 'media.class = "Audio/Source"' in out


def mics():
    """The real microphones PipeWire has now, {node name: (node id, description)} (speaker monitors aren't
    Audio/Source). The node name stays the same when the same mic is replugged; the id doesn't."""
    try:
        dump = json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5).stdout)
    except Exception:
        return {}
    out = {}
    for o in dump:
        props = (o.get("info") or {}).get("props") or {}
        if o.get("type") == "PipeWire:Interface:Node" and props.get("media.class") == "Audio/Source":
            out[props.get("node.name", o["id"])] = o["id"], props.get("node.description") or props.get("node.name")
    return out


def set_mic_mute(on):
    """Mutes the mic in the hardware (on the USB mic this flips its ALSA capture switch, not just a PipeWire volume).
    WirePlumber remembers it across restarts, so Gene clears it when he starts."""
    subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1" if on else "0"], capture_output=True, timeout=5)


class Mic:
    """Reads 30 ms frames from the default PipeWire source; muted while Gene talks so he can't hear himself."""
    def __init__(self):
        self.p, self.muted_until, self.off = None, 0.0, threading.Event()
        self.on_missing = self.on_found = self.on_new = None     # set by main: Gene says out loud that he can't hear
        self.known = set(mics())    # every mic seen while running: one never seen before was just plugged in

    def new_mic(self):
        """A microphone plugged in since the last check becomes the default source (WirePlumber remembers it), so
        Gene listens through it (asked by voice 2026-10-07) - otherwise the one with the higher ALSA priority wins.
        A replugged mic isn't new. Returns its name, or None."""
        now = mics()
        new = [now[n] for n in now if n not in self.known]
        self.known |= set(now)
        if not new:
            return None
        i, name = max(new)      # the newest node
        subprocess.run(["wpctl", "set-default", str(i)], capture_output=True, timeout=5)
        log("new microphone plugged in:", name, "- listening through it")
        return name

    def _open(self):
        if self.p:
            self.p.kill(); self.p.wait()
        if not mic_present():
            log("no microphone found - waiting for one to be plugged in")
            if self.on_missing:     # else he'd sit there deaf and silent (2026-10-05: the USB mic was unplugged all night)
                self.on_missing()
            while not mic_present():
                time.sleep(2)
            log("microphone found")
            self.new_mic()
            if self.on_found:
                self.on_found()
        set_mic_mute(False)
        self.p = subprocess.Popen(["pw-cat", "--record", "--raw", "--rate", str(SR), "--channels", "1",
                                   "--format", "s16", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def frames(self):
        """Survives the mic dropping out (USB blips, unplugging): waits for it and reconnects, rather than
        exiting - a failed exit triggers gene-repair.service."""
        n, checked = FRAME * 2, time.time()
        while True:
            if self.off.is_set():           # hard mute: no recording at all until unmuted
                while self.off.is_set():
                    time.sleep(0.1)
                self._open(); checked = time.time()
            lost = None
            if time.time() - checked > 5:
                checked = time.time()
                if not mic_present():
                    lost = "microphone unplugged"
                elif name := self.new_mic():
                    self._open(); checked = time.time()
                    if self.on_new:
                        self.on_new(name)
                    continue
            if not lost:
                b = self.p.stdout.read(n)
                if len(b) < n:
                    lost = "microphone stream ended"
            if lost and self.off.is_set():
                continue
            if lost:
                log(lost, "- reconnecting")
                time.sleep(1)
                self._open(); checked = time.time()
                continue
            if time.time() < self.muted_until:
                continue
            yield np.frombuffer(b, np.int16).astype(np.float32) / 32768

    def hard_mute(self, on):
        """Physical mute: the mic's hardware capture switch goes off and the recorder is closed, so nothing is
        captured at all. Unmuting (from another thread) reopens it, which also turns the switch back on."""
        if on:
            self.off.set(); set_mic_mute(True)
            if self.p:
                self.p.kill()
        else:
            self.off.clear()


def level(f):
    """RMS of a 30 ms frame above ~100 Hz (FFT bins 3+), so rumble and hum don't count as someone talking; voice is
    above it. The C-Media dongle's hiss is mostly < 60 Hz: 0.087 RMS raw, 0.050 above 100 Hz, with far fewer spikes."""
    return float(np.sqrt((np.abs(np.fft.rfft(f)[3:]) ** 2).sum() * 2) / len(f))


def phrases(mic):
    """Yields each spoken phrase as int16 audio. Energy VAD with a noise floor that tracks the room."""
    floor, pre, cur, quiet, speaking = 0.002, [], [], 0, False
    npre, nend = int(PREROLL * SR / FRAME), int(END_SILENCE * SR / FRAME)
    for f in mic.frames():
        rms = level(f)
        loud = rms > max(0.006, min(floor * 4, floor + 0.03))    # 4x the floor in a quiet room; less over loud hiss
        if not speaking:
            floor = 0.98 * floor + 0.02 * rms if not loud else floor
            pre = (pre + [f])[-npre:]
            if loud:
                speaking, cur, quiet = True, pre[:], 0
            continue
        cur.append(f)
        quiet = 0 if loud else quiet + 1
        if len(cur) * FRAME >= MAX_PHRASE * SR:
            floor = max(floor, float(np.median([level(x) for x in cur])))
            log(f"phrase ran {MAX_PHRASE} s - noise floor now {floor:.3f}")
            quiet = nend           # ends it here; Silero (gene_vad) still drops it if it was only noise
        if quiet >= nend:
            speaking, pre = False, []
            audio = np.concatenate(cur)
            if len(audio) / SR - END_SILENCE >= MIN_SPEECH:
                yield (np.clip(audio, -1, 1) * 32767).astype(np.int16)


def wav_bytes(pcm):
    import io, soundfile as sf
    buf = io.BytesIO(); sf.write(buf, pcm, SR, format="WAV", subtype="PCM_16"); return buf.getvalue()


_stt_first_down = 0     # time until which the Jetson STT is skipped


def stt(pcm):
    global _stt_first_down
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() + wav_bytes(pcm) + \
           f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n--{b}--\r\n".encode()
    text = None
    if STT_FIRST and time.time() >= _stt_first_down:
        try:
            r = urllib.request.Request(STT_FIRST, body, {"Content-Type": f"multipart/form-data; boundary={b}"})
            text = json.load(urllib.request.urlopen(r, timeout=STT_FIRST_TIMEOUT))["text"].strip()
        except Exception as e:
            _stt_first_down = time.time() + STT_FIRST_RETRY
            log(f"Jetson STT unavailable for {STT_FIRST_RETRY} s ({e}) - using the Pi")
    if text is None:
        r = urllib.request.Request(STT_URL, body, {"Content-Type": f"multipart/form-data; boundary={b}"})
        text = json.load(urllib.request.urlopen(r, timeout=20))["text"].strip()
    # whisper's non-speech tags: [BLANK_AUDIO], (wind blowing), *coughs* ...
    return re.sub(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*", "", text).strip()


# the model sometimes echoes its context lines, "(memory: ...)", or adds stage directions, "(pauses)"
ECHO = re.compile(r"\((?:camera|web|clock|memory|eyes|status|math|pauses?|laughs?|sighs?|smiles?|beeps?|whirs?)\b[^)]*\)", re.I)


# the face tag Gene's model starts its reply with (Modelfile): "[happy] Oh wow!" - also seen as "[ sad ]", "[eyes: sad]"
EYE_TAG = re.compile(r"\[\s*(?:eyes?\s*:\s*)?(\w+)\s*\]", re.I)


def _clean(s):
    s = EYE_TAG.sub("", ECHO.sub("", s))
    s = re.sub(r"\*[^*]*\*|\*", "", s)                  # *laughs*, *continues playing music* - never spoken
    s = re.sub(r"\s{2,}", " ", re.sub(r"\[[^\]]*\]", "", s)).strip()    # other bracketed stage directions, "[clears screen]"
    s = re.sub(r"^User message:.*", "", s).strip()      # ...or invents a "User message: laptop" turn
    return s if re.search(r"\w", s) else ""


def drop_names(s, names):
    """Takes a name out where it's only said to someone: "Good, Joshua." -> "Good.", "Joshua, look." -> "Look.",
    "Thanks Joshua!" -> "Thanks!". Anyone may be talking (asked 2026-10-05), so Gene doesn't call people by name;
    a name that is part of the sentence ("Joshua built me") stays."""
    for n in {x for x in names if x}:
        n = re.escape(n)
        s = re.sub(r",\s*" + n + r"\b(?=\s*[.!?]|\s*$)", "", s)          # needs the comma: "I told Joshua." stays
        s = re.sub(r"^\s*" + n + r"\s*[,!]\s*", "", s)
        s = re.sub(r",\s*" + n + r"\s*,", ",", s)                       # "Sure thing, Joshua, here you go."
        s = re.sub(r"(\b(?:hey|yo|hi|hello|thanks|thank\s+you|sure|okay|ok|sorry|aw|ah|oh|well|good|nice|alright)),?\s+" + n
                   + r"\b(,?)", r"\1\2", s, flags=re.I)
    s = re.sub(r",(?=\s*[.!?])", "", s).strip(" ,")
    return s[:1].upper() + s[1:] if re.search(r"\w", s) else ""


# "bro" / "dude" / "man" said TO someone: at most once in a reply, and not if one of his last two replies had one (asked 2026-10-05)
SLANG = re.compile(r"\b(?:bro|dude|homie)\b|,\s*man\b", re.I)
SLANG_WORDS = ("bro", "Bro", "dude", "Dude", "man", "Man", "homie", "Homie")


def chat_sentences(messages, on_eyes=None, images=None):
    """Streams Gene's reply (gene_brain: Claude, else the Jetson) and yields whole sentences as they complete. Face
    tags go to on_eyes(name) as soon as they arrive (before the first sentence is spoken) and are taken out of the
    words. images: PNG camera frames for Claude to look at."""
    buf = ""
    for piece in gene_brain.stream(messages, images):
        buf += piece
        buf = ECHO.sub("", buf)
        for m in EYE_TAG.finditer(buf):
            if on_eyes:
                on_eyes(m.group(1).lower())
        buf = EYE_TAG.sub("", buf)
        while True:
            # don't end a sentence inside an unclosed "(...", it may be an echoed line spanning sentences
            # (or inside an unclosed "[...", a face tag still arriving)
            open_at = min(buf.rfind(o) if buf.rfind(o) > buf.rfind(c) else len(buf) for o, c in ("()", "[]"))
            if buf.count("*") % 2:          # nor inside an unclosed *stage direction*
                open_at = min(open_at, buf.rfind("*"))
            m = re.search(r"[.!?]+[\"')]*\s", buf[:open_at])    # a sentence ends once the next word starts
            if not m:
                break
            s, buf = _clean(buf[:m.end()]), buf[m.end():]
            if s:
                yield s
    buf = re.sub(r"\((?:camera|web|clock|memory|eyes|status|math)\b.*|\[[^\]]*$|\*[^*]*$", "", buf, flags=re.S | re.I)   # cut off mid-echo
    if s := _clean(buf):
        yield s


# Results of commands Gene does himself ("Okay, timer set for 5 minutes.") are said in his own words by his model,
# checked so the 3B model can't change what happened; if the check fails the exact line is said instead
OWN_WORDS = ('(done: you already did what {who} asked, and the result is: "{said}" Now tell them that result in ONE short '
             "sentence of your own, with your personality. Use different words from the result, but keep its meaning, "
             "its numbers (written as digits), names and times, and add nothing new.)")
OWN_WORDS_SIMILAR = 0.5     # MiniLM similarity to the result (or to what was asked + the result); bad rewrites score < 0.3
NUMBER = re.compile(r"\d+")
NAMES = re.compile(r"\b\w+\.com\b|(?<=[a-z,] )[A-Z][a-z]+\b")     # "myinstants.com", a clip or person's name mid-sentence
NEGATIVE = re.compile(r"\b(?:no|not|never|none|nothing|sorry|unfortunately|afraid|cannot|\w+n't)\b", re.I)
NOT_NEGATIVE = re.compile(r"\b(?:don't|no)\s+(?:worry|worries|problem)\b|\bnot\s+a\s+problem\b", re.I)
# things the model likes to make up about what it did: "I've activated the buzzer", "I've upgraded myself to dance"
INVENTED = re.compile(r"\b(?:upgraded|buzzer|tune|music|song|already|earlier|again|today|tomorrow)\b", re.I)


def own_words_ok(heard, said, reply, embed):
    """Why the model's rewrite of `said` can't be used, or None if it says the same thing."""
    if not reply or len(reply.split()) > 30:
        return "empty or long"
    if set(NUMBER.findall(said)) != set(NUMBER.findall(reply)):
        return "numbers"
    if bool(NEGATIVE.search(NOT_NEGATIVE.sub("", said))) != bool(NEGATIVE.search(NOT_NEGATIVE.sub("", reply))):
        return "yes/no flipped"
    if lost := [w for w in NAMES.findall(said) if w.lower() not in reply.lower()]:
        return "dropped " + lost[0]
    if bad := [w for w in INVENTED.findall(reply) if w.lower() not in (heard + " " + said).lower()]:
        return "added " + bad[0]
    v = embed([said, heard + " " + said, reply])
    if max(v[0] @ v[2], v[1] @ v[2]) < OWN_WORDS_SIMILAR:
        return f"different meaning ({max(v[0] @ v[2], v[1] @ v[2]):.2f})"
    return None


def own_words(messages, heard, said, who, embed):
    """Gene's model says the result `said` its own way: returns (face, words), or None to say `said` as it is."""
    content = "\n".join([OWN_WORDS.format(who=who, said=said.replace('"', "'")), "(eyes: start with an eye tag)",
                         f"{who} says: {heard}"])
    # the Jetson needs it warmer than chat, else it repeats the result; Claude takes no sampling options
    text = gene_brain.complete(messages + [{"role": "user", "content": content}], max_tokens=60, timeout=8,
                               options={"temperature": 0.9})
    faces = [m.group(1).lower() for m in EYE_TAG.finditer(text)]
    reply = " ".join(re.split(r"(?<=[.!?])\s+", _clean(text))[:2])      # at most two sentences ("myinstants.com" is one word)
    if why := own_words_ok(heard, said, reply, embed):
        log(f"own words rejected ({why}): {reply}")
        return None
    return (faces[0] if faces else None), reply


class Mouth:
    """Synthesises the next sentence while the current one plays."""
    def __init__(self, mic):
        self.mic, self.q, self.lock = mic, queue.Queue(), threading.Lock()
        threading.Thread(target=self._play, daemon=True).start()

    def say(self, text, style=None):
        """style: "loud" / "meek" (gene_volume.STYLES), else his regular volume."""
        with self.lock:     # timers and the announcer speak from their own threads
            r = gene_tts.speak(text)
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); f.write(r["audio"]); f.close()
            self.q.put((f.name, r["ms"] / 1000, style, (text, r["visemes"])))

    def play(self, path, seconds):
        """Queues a wav file (deleted after playing) after whatever Gene is saying."""
        self.q.put((path, seconds, None, None))

    def busy(self):
        return self.q.unfinished_tasks > 0 or self.lock.locked()

    def _play(self):
        while True:
            path, dur, style, words = self.q.get()
            self.mic.muted_until = time.time() + dur + 0.6          # covers playback + room echo
            gene_music.player.hold(dur + 1.0)                       # a song pauses while he talks
            try:
                gene_volume.use(style)
            except Exception as e:
                log("volume error:", e)
            try:    # what the mouth does and when, for the web panel's mouth (and the jaw servos, once fitted)
                write_json(MOUTH, {"t": time.time(), "ms": round(dur * 1000), "text": words[0] if words else None,
                                   "visemes": words[1] if words else None})
            except Exception as e:
                log("mouth file error:", e)
            try:    # a playback that never starts (the sink grabbed by something else) must not leave Gene deaf
                subprocess.run(["pw-play", path], timeout=dur + PLAY_SLACK)
            except subprocess.TimeoutExpired:
                log(f"playback stuck for {dur + PLAY_SLACK:.0f} s - skipped")
            self.mic.muted_until = time.time() + 0.4
            os.unlink(path)
            self.q.task_done()

    def wait(self):
        self.q.join()


UPGRADE_ASK = re.compile(r"\b(upgrade|improve|fix|update|reprogram)\s+(yourself|your\s+(code|software|brain))", re.I)
# "where / when / how did you upgrade yourself ...?" asks about a past upgrade - not a new one
UPGRADE_PAST = re.compile(r"\b(?:where|when|how|why|what)\s+(?:did|have|had)\s+you\b|\b(?:did|have)\s+you\s+(?:already\s+|just\s+)?"
                          r"(?:upgrade|improve|fix|update|reprogram)", re.I)
# "how do I SSH into you?" / "what's the command to SSH into you?": the login, said exactly (SSH enabled 2026-10-05)
SSH_ASK = re.compile(r"\b(?:ssh|s\.?\s?s\.?\s?h)\b", re.I)


# "say that again" / "what did you say?": his last reply, said again exactly (the model would answer something new)
REPEAT = re.compile(r"\W*(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:say\s+(?:that|it)\s+again|say\s+again|"
                    r"repeat\s+(?:that|it|yourself|what\s+you\s+(?:just\s+)?said)|what\s+did\s+you\s+(?:just\s+)?say|"
                    r"come\s+again|pardon(?:\s+me)?|sorry,?\s+what|what\s+was\s+that)"
                    r"(?:[\s,]+(?:again|please|gene|bro|dude|man))*\W*", re.I)
# "yeah" / "right" / "cool" after a reply that asked nothing: the model used to invent a status ("SSH connection count: 0")
BACKCHANNEL = re.compile(r"\W*(?:yeah|yep|yup|yes|right|okay|ok|cool|nice|sure|alright|all\s+right|mm-?hmm|uh-?huh|true|"
                         r"word|bet|got\s+it|for\s+sure|totally|sweet|awesome)(?:[\s,.!]+(?:yeah|man|bro|dude|gene|okay|ok|"
                         r"cool|nice|right|thanks))*\W*", re.I)
BACKCHANNEL_LINE = "(he just acknowledged what you said: answer in a few casual words or a short question back, and add no new facts)"


# "what's 17 times 23?" / "7 plus 8 plus 9" / "12 percent of 80" / "square root of 144": worked out exactly here and
# handed to the model as a "(math: ...)" line - small models get sums wrong
NUM = r"\d[\d,]*(?:\.\d+)?"
MATH_WORDS = [(r"\bmultiplied\s+by\b|\btimes\b|(?<=\d)\s*[x×]\s*(?=\d)", "*"), (r"\bdivided\s+by\b|\bover\b|÷", "/"),
              (r"\bplus\b", "+"), (r"\bminus\b|\btake\s+away\b|(?<=\d)\s+-\s+(?=\d)", "-"),
              (r"\bto\s+the\s+power\s+of\b", "^")]
MATH_ASK = re.compile(r"\b(?:what(?:'s|\s+is)|how\s+much\s+is|calculate|work\s+out|equals?)\b|\?\s*$", re.I)
EXPR = re.compile(NUM + r"(?:(?:\s*[+*/^]\s*|\s+-\s+)" + NUM + r")+")     # a bare "-" is a range or an address: 192-168


def _fmt(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    t = f"{abs(v):,}" if isinstance(v, int) else f"{abs(v):,.4f}".rstrip("0").rstrip(".")
    return ("minus " if v < 0 else "") + t


def _calc(expr):
    """Evaluates + - * / ^ on plain numbers (no names, no calls), or None."""
    import ast, operator as o
    ops = {ast.Add: o.add, ast.Sub: o.sub, ast.Mult: o.mul, ast.Div: o.truediv, ast.Pow: o.pow, ast.USub: o.neg}
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            l, r = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(r) > 12:
                raise ValueError("too big")
            return ops[type(n.op)](l, r)
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        raise ValueError("not a sum")
    try:
        return ev(ast.parse(expr.replace(",", "").replace("^", "**"), mode="eval").body)
    except ZeroDivisionError:
        return "zero"
    except (ValueError, SyntaxError):
        return None


def math_line(heard):
    """A "(math: ...)" line with the exact answer to a sum in what was heard, or ""."""
    if not MATH_ASK.search(heard):
        return ""
    say = lambda q, v: ("(math: that divides by zero, which has no answer)" if v == "zero"
                        else f"(math: {q} is {_fmt(v)} - say this exact answer)")
    if m := re.search(r"square\s+root\s+of\s+(" + NUM + ")", heard, re.I):
        v = float(m.group(1).replace(",", ""))
        return say(f"the square root of {m.group(1)}", v ** 0.5)
    if m := re.search(r"(" + NUM + r")\s+(squared|cubed)", heard, re.I):
        return say(f"{m.group(1)} {m.group(2).lower()}", _calc(f"{m.group(1)}^{2 if m.group(2).lower() == 'squared' else 3}"))
    if m := re.search(r"(" + NUM + r")\s*(?:percent|%)\s+of\s+(" + NUM + ")", heard, re.I):
        return say(f"{m.group(1)} percent of {m.group(2)}", _calc(f"{m.group(1)}*{m.group(2)}/100"))
    t = heard
    for rx, sym in MATH_WORDS:
        t = re.sub(rx, f" {sym} ", t, flags=re.I)
    if m := EXPR.search(t):
        if (v := _calc(m.group(0))) is not None:
            spoken = re.sub(r"\s+", " ", m.group(0).replace("*", " times ").replace("/", " divided by ").replace("+", " plus ")
                            .replace("^", " to the power of ").replace(" - ", " minus ")).strip()
            return say(spoken, v)
    return ""


def status_line():
    """Gene's real state, so the model doesn't make up a volume or what his cameras see."""
    parts = []
    try:
        vol, muted = gene_volume.get()
        parts.append(f"speaker volume {vol} percent" + (", muted" if muted else ""))
    except Exception:
        pass
    parts.append("cameras on" if camera_line() else "cameras not connected yet, so you can't see anything")
    try:
        parts.append(gene_eyes.screens_status())
    except Exception:
        pass
    try:
        parts.append(gene_eyes.tilt_status())
    except Exception:
        pass
    if gene_music.player.playing():
        parts.append(f"playing the song {gene_music.player.title} from YouTube")
    return "(status: " + "; ".join(parts) + ")"


def ssh_answer():
    """The ssh command for this Pi, with its current address (said exactly: digits must be right)."""
    up = subprocess.run(["systemctl", "is-active", "ssh"], capture_output=True, text=True).stdout.strip() == "active"
    if not up:
        return "SSH is switched off on me right now."
    ips = [a for a in subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split() if "." in a]
    user, host = os.environ.get("USER", "bennjo"), os.uname().nodename
    where = f"ssh {user} at {ips[0].replace('.', ' dot ')}, " if ips else ""
    return (f"SSH is on. From a computer on the same network, type {where}or ssh {user} at {host} dot local, "
            f"and log in with the {user} password.")


# "mute the mic" / "mute yourself" / "stop listening": a physical mute - the mic's hardware capture switch goes off and
# nothing is recorded (Mic.hard_mute), so he can't hear "unmute". The round eye screens have no touch, so the mute
# ends by itself: after the time asked for ("mute yourself for 10 minutes"), else MUTE_DEFAULT; a poke also ends it.
MUTE = re.compile(r"(?<!don't\s)(?<!not\s)(?:\bmute\s+(?:the\s+|your\s+)?(?:mic|microphone|yourself|your\s?self|ears?)\b|"
                  r"\b(?:turn|switch|shut)\s+(?:off\s+(?:the\s+|your\s+)?(?:mic|microphone|ears?)\b|"
                  r"(?:the\s+|your\s+)?(?:mic|microphone|ears?)\s+off\b)|\bstop\s+listening\b)", re.I)
UNMUTE = re.compile(r"\bun[\s-]?mute\b|\b(?:turn|switch)\s+(?:on\s+(?:the\s+|your\s+)?(?:mic|microphone|ears?)\b|"
                    r"(?:the\s+|your\s+)?(?:mic|microphone|ears?)\s+(?:back\s+)?on\b)|\bstart\s+listening\b|"
                    r"\blisten(?:ing)?\s+again\b|\bwake\s+up\b", re.I)
MUTE_ASK = re.compile(r"^\W*(?:how|why|what|when|did|have|were|was|are)\b", re.I)   # "how do I mute the mic?" isn't a command
MUTE_DEFAULT, MUTE_MAX = 300, 2 * 3600     # s
MUTED_MAX_PHRASE = 5        # s; longer phrases while muted aren't sent to STT ("unmute" is short)
HERE = os.path.dirname(os.path.abspath(__file__))
ANNOUNCE = os.path.join(HERE, "state", "announce.txt")
MOUTH = os.path.join(HERE, "state", "mouth.json")          # the clip playing now: start time, length, words, visemes
WEB_SAY = os.path.join(HERE, "state", "teleop_say")        # lines typed in the web panel (gene_teleop.py) for Gene to say


def write_json(path, d):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, path)


def start_upgrade(heard):
    """Hands the request to upgrade.py in its own systemd unit, so it survives Gene being restarted."""
    subprocess.Popen(["systemd-run", "--user", "--collect", f"--unit=gene-upgrade-{int(time.time())}",
                      "--property=WorkingDirectory=" + HERE,
                      sys.executable, "-u", os.path.join(HERE, "upgrade.py"), "voice", heard],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def announcer(mouth):
    """Speaks whatever upgrade.py leaves in state/announce.txt, when Gene isn't mid-reply."""
    while True:
        time.sleep(2)
        if os.path.exists(ANNOUNCE) and mouth.q.empty():
            text = open(ANNOUNCE).read().strip(); os.unlink(ANNOUNCE)
            if text:
                log("Gene (upgrade):", text); mouth.say(text)


SEER = None     # gene_cameras.Seer, started in main()
LOOK_FILLERS = ("Hang on, give me a few seconds to look.", "Let me take a good look, this takes a moment.")     # Moondream: 20-40 s


def camera_line():
    """What the eye cameras see, e.g. "(camera: person, cup)"; "" when no camera works."""
    try:
        return SEER.line() if SEER else ""
    except Exception as e:
        log("camera error:", e)
        return ""


def main():
    global SEER
    log("loading voice"); gene_tts.speak("Hi.")
    SEER = gene_cameras.Seer(lids=gene_eyes.lids_shut)      # frames come from gene-cameras.service; closed eyes see nothing
    threading.Thread(target=gene_brain.warm, daemon=True).start()      # the API connection, before the first reply
    threading.Thread(target=gene_vision.warm, daemon=True).start()     # Moondream into RAM, for looks without Claude
    mic = Mic(); mouth = Mouth(mic)

    def mic_missing():
        gene_eyes.show("sad")
        mouth.say("I can't find my microphone, so I can't hear anything. Please plug it in."); mouth.wait()

    def mic_found():
        gene_eyes.show("neutral")
        mouth.say("I can hear again."); mouth.wait()
    def mic_new(name):
        mouth.say("New microphone, I'm listening through it now."); mouth.wait()
    mic.on_missing, mic.on_found, mic.on_new = mic_missing, mic_found, mic_new
    mic._open()
    memory = gene_memory.Memory()
    history = memory.load_history()         # picks up the thread after a restart (e.g. an upgrade)
    timers = gene_clock.Timers(mouth.say)
    topic = gene_web.Topic()    # what we're talking about, so "check the web" / "look it up" knows what to search
    gene_eyes.show("neutral")
    if not os.path.exists(ANNOUNCE):
        mouth.say("Gene is online.")
    mouth.wait()
    threading.Thread(target=announcer, args=(mouth,), daemon=True).start()
    threading.Thread(target=memory.idle_loop, args=(mouth.busy,), daemon=True).start()

    def reply_directly(heard, said, rephrase=True, by_sentence=False):
        """For commands Gene handles himself: say the result (in his own words if his model manages), and keep it
        in the chat history. by_sentence: long text (a file read out) is voiced a sentence at a time, so he starts
        talking after ~1 s instead of ~10 s."""
        nonlocal history
        face = None
        if rephrase:
            try:
                if got := own_words(history, heard, said, memory.speaker, memory.embed):
                    face, said = got[0], drop_names(got[1], (memory.speaker, gene_memory.DEFAULT_SPEAKER)) or said
            except Exception as e:
                log("own words error:", e)
        if face := face and gene_eyes.show(face):       # None if the model made a face up
            log("eyes:", face)
        log("Gene:", said)
        for part in re.split(r"(?<=[.!?])\s+", said) if by_sentence else [said]:
            mouth.say(part)
        mouth.wait(); gene_eyes.settle()
        history += [{"role": "user", "content": heard},
                    {"role": "assistant", "content": (f"[{face}] " if face else "") + said}]
        if len(history) > 2 * HISTORY_MAX:
            history = history[-2 * HISTORY_KEEP:]
        memory.save_history(history)
    sound_played = 0        # when Gene last played a sound bite ("where did you get that from?" is then about it)
    brain_down_said = 0     # when Gene last said he can't reach the Jetson (so he doesn't repeat it every phrase)

    def brain_down():
        nonlocal brain_down_said
        if time.time() - brain_down_said > 60:
            brain_down_said = time.time()
            gene_eyes.show("sad")
            mouth.say("Sorry, I can't reach my brain right now, so I can't understand you."); mouth.wait(); gene_eyes.settle()
    def answer(heard, content, t0, max_sentences=MAX_SENTENCES, remember=True, images=None):
        """Gene's model replies to `content` (context lines + what was said); `heard` is what goes in the history."""
        nonlocal history
        messages = history + [{"role": "user", "content": content}]
        said, face, voice = [], [], []

        def on_eyes(name):
            if name in gene_volume.STYLES or name == "normal":     # [loud] / [meek]: how loud he says this reply
                voice[:] = [name]; log("voice:", name)
                return
            if shown := gene_eyes.show(name):
                log("eyes:", shown); face[:] = [shown]
        try:
            slang = any(SLANG.search(m["content"]) for m in history[-4:] if m["role"] == "assistant")
            for i, s in enumerate(chat_sentences(messages, on_eyes, images)):
                if not (s := drop_names(s, (memory.speaker, gene_memory.DEFAULT_SPEAKER) + (SLANG_WORDS if slang else ()))):
                    continue
                slang = slang or bool(SLANG.search(s))
                if not said:
                    log(f"first sentence after {time.perf_counter() - t0:.2f}s")
                log("Gene:", s); said.append(s)
                mouth.say(s, voice[0] if voice else gene_volume.FACE_STYLE.get(face[0] if face else ""))
                if len(said) >= max_sentences:
                    break
        except Exception as e:
            log("LLM error:", e)
            if not said:
                brain_down()
        mouth.wait(); gene_eyes.settle()        # his face goes back to neutral a few seconds after he stops talking
        if said:
            # the tag stays in the history, so the model keeps seeing its replies start with one
            history += [{"role": "user", "content": heard},
                        {"role": "assistant", "content": "".join(f"[{f}] " for f in face) + " ".join(said)}]
            if len(history) > 2 * HISTORY_MAX:
                history = history[-2 * HISTORY_KEEP:]
            memory.save_history(history)
            if remember:
                memory.exchange(heard, " ".join(said))

    turn = threading.Lock()     # one exchange at a time: something heard, or a poke in the eye
    muted = False               # "mute the mic": mic physically off until unmute_at (or a poke)
    unmute_at = 0.0

    def unmute(heard):
        nonlocal muted
        muted = False
        mic.hard_mute(False)
        log("mic unmuted")
        reply_directly(heard, "Okay, I'm listening again.")
    def poke_watch():
        """A poke in Gene's eye screens (gene_eyes.py leaves each poke in state/poke.json) no longer gets a reaction
        (asked by voice on 2026-10-04: no flinch, no words). It still quietly opens eyes he closed when asked to, and
        unmutes a muted mic. It also ends a mute when its time is up (he can't hear "unmute", and the round eye
        screens to come have no touch)."""
        seen = (gene_eyes.last_poke() or {}).get("t", time.time())
        while True:
            time.sleep(0.2)
            if muted and time.time() >= unmute_at:
                with turn:
                    if muted:
                        unmute(f"(your mic mute time is up and you can hear {memory.speaker} again)")
                continue
            if (gene_eyes.last_poke() or {}).get("t", 0) <= seen:
                continue
            with turn:
                mouth.wait()
                seen = (gene_eyes.last_poke() or {}).get("t", time.time())
                gene_eyes.open_eyes()
                if gene_music.player.stop():        # a poke stops a song (he may not hear "stop" over it)
                    log("music stopped by a poke")
                if muted:
                    unmute(f"({memory.speaker} pokes your eye to unmute you)")
    threading.Thread(target=poke_watch, daemon=True).start()

    def web_say_watch():
        """Says the lines typed in the web control panel (gene_teleop.py leaves each in state/teleop_say/ as
        {"text", "face", "style"}), between conversation turns, word for word. They go in the chat history as his
        own words, so he knows what he said if asked."""
        nonlocal history
        os.makedirs(WEB_SAY, exist_ok=True)
        while True:
            time.sleep(0.2)
            for name in sorted(n for n in os.listdir(WEB_SAY) if n.endswith(".json")):
                path = os.path.join(WEB_SAY, name)
                try:
                    with open(path) as f:
                        req = json.load(f)
                except (OSError, ValueError):
                    req = {}
                try:
                    os.unlink(path)
                except OSError:
                    pass
                text = str(req.get("text") or "").strip()[:1000]
                if not text:
                    continue
                with turn:
                    mouth.wait()
                    face = gene_eyes.show(req.get("face") or "")
                    log("Gene (web panel):", text)
                    for part in re.split(r"(?<=[.!?])\s+", text):
                        mouth.say(part, req.get("style") if req.get("style") in gene_volume.STYLES else None)
                    mouth.wait(); gene_eyes.settle()
                    history += [{"role": "user", "content": f"({gene_memory.DEFAULT_SPEAKER} typed a line for you "
                                                            "to say out loud, in your web control panel)"},
                                {"role": "assistant", "content": (f"[{face}] " if face else "") + text}]
                    if len(history) > 2 * HISTORY_MAX:
                        history = history[-2 * HISTORY_KEEP:]
                    memory.save_history(history)
    threading.Thread(target=web_say_watch, daemon=True).start()

    log("listening (Ctrl+C to stop)")
    for pcm in phrases(mic):
        with turn:
            if muted and len(pcm) / SR > MUTED_MAX_PHRASE:
                continue
            t0 = time.perf_counter()
            if not muted:           # a knock, a cough, the fan: loud but no voice in it - never sent to STT
                try:
                    voice = gene_vad.voiced(pcm)
                except Exception as e:
                    log("VAD error:", e); voice = None
                if voice is not None and voice < gene_vad.MIN_VOICE:
                    log(f"ignored noise ({len(pcm) / SR:.1f}s, voice {voice:.2f}s)")
                    continue
            SEER.heard()            # a fresh look at the cameras while STT runs
            try:
                heard = stt(pcm)
            except Exception as e:
                log("STT error:", e)
                if not muted:
                    brain_down()
                continue
            if len(re.sub(r"\W", "", heard)) < 2:
                continue
            if muted:
                if UNMUTE.search(heard) and not MUTE_ASK.search(heard):
                    unmute(heard)
                continue
            t1 = time.perf_counter()
            if why := gene_vad.ignore(heard, time.time() - mic.muted_until):
                log(f"ignored ({why}, {len(pcm) / SR:.1f}s): {heard}")     # "Mm." / a lone "Okay." out of nowhere
                continue
            if gene_music.player.playing() and not (gene_music.wants(heard, True) or gene_volume.wants(heard)
                                                     or re.search(r"\bgene\b", heard, re.I)):
                log(f"ignored (music playing, {len(pcm) / SR:.1f}s): {heard}")     # the song's lyrics, or talk over it
                continue
            log(f"heard ({len(pcm) / SR:.1f}s, STT {t1 - t0:.2f}s): {heard}")
            memory.hear(heard)
            if MUTE.search(heard) and not MUTE_ASK.search(heard) and not UPGRADE_ASK.search(heard):
                secs = min(max(gene_clock._duration(heard) or MUTE_DEFAULT, 10), MUTE_MAX)
                log(f"mic muted for {secs:.0f} s")
                reply_directly(heard, f"Okay, my mic is switched off for {gene_clock._spoken(secs)}, so I can't hear "
                               "anything until then.", rephrase=False)
                mouth.wait()
                unmute_at = time.time() + secs
                muted = True; mic.hard_mute(True); gene_eyes.hold("sleepy", secs)
                continue
            last_reply = history[-1]["content"] if history and history[-1]["role"] == "assistant" else ""
            if REPEAT.fullmatch(heard) and last_reply:
                said = EYE_TAG.sub("", last_reply).strip()
                log("repeat:", said); reply_directly(heard, said, rephrase=False, by_sentence=True)
                continue
            if said := gene_sounds.source_answer(heard, time.time() - sound_played < 300):
                log("sound source:", said); reply_directly(heard, said)
                continue
            if UPGRADE_ASK.search(heard) and not UPGRADE_PAST.search(heard):
                log("upgrade requested:", heard)
                reply_directly(heard, "Okay, I'll work on upgrading myself. It'll take a few minutes, and I'll tell you when I'm done.")
                start_upgrade(heard)
                continue
            if SSH_ASK.search(heard):
                said = ssh_answer(); log("ssh:", said); reply_directly(heard, said, rephrase=False)
                continue
            if tilt := gene_eyes.tilt_wanted(heard):
                # "rotate your left eye 2 degrees clockwise" / "tilt your eyes a bit more outwards": level each eye on its
                # screen by ear (said exactly: the numbers must be right)
                said = gene_eyes.tilt(tilt); log(f"eye tilt {tilt}:", said); reply_directly(heard, said, rephrase=False)
                continue
            if gene_eyes.swap_wanted(heard):
                # "switch your screens left and right": the two eye screens trade places (said exactly)
                now = gene_eyes.swap_screens()
                said = ("Okay, I've switched my eye screens over, left to right." if now else
                        "Okay, my eye screens are back the usual way round.")
                log("screens swapped:", now); reply_directly(heard, said, rephrase=False)
                continue
            if gene_eyes.screens_wanted(heard):
                said = gene_eyes.screens_answer(); log("screens:", said); reply_directly(heard, said, rephrase=False)
                continue
            if lids := gene_eyes.lids_wanted(heard):
                # "close your left eye" / "wink your right eye" / "open your eyes": said exactly (left/right must be right)
                verb, side = lids
                eyes = "eyes" if side == "both" else f"{side} eye"
                if verb == "close":
                    shut = gene_eyes.close_eyes(side)
                    said = (f"Okay, my {'eyes are' if shut == 'both' else shut + ' eye is'} closed. "
                            "Say open your eyes when you want them open again.")
                elif verb == "open":
                    gene_eyes.open_eyes(side)
                    still = gene_eyes.lids_shut()
                    said = f"Okay, my {eyes} {'is' if side != 'both' else 'are'} open" + (f", and my {still} eye is still closed." if still else ".")
                else:
                    gene_eyes.close_eyes(side, gene_eyes.WINK_FOR); said = f"There, I winked my {side} eye."
                log(f"lids {lids}:", said); reply_directly(heard, said, rephrase=False)
                continue
            if music := gene_music.wants(heard, gene_music.player.playing()):
                # "play Get Lucky by Daft Punk" / "play some Spotify or YouTube songs" / "next song" / "stop the music"
                log(f"music {music}")
                p = gene_music.player
                if music[0] == "stop":
                    p.stop(); p.paused = True
                    reply_directly(heard, "Okay, music off.", rephrase=False); continue
                if music[0] == "what":
                    said = (f"This is {p.title}, from YouTube." if p.playing() else
                            f"That was {p.title}, from YouTube." if p.title else "Nothing's playing right now.")
                    reply_directly(heard, said, rephrase=False); continue
                if music[0] == "resume":
                    music = ("again",) if p.played else ("play", "")
                note = ("I can't sign in to Spotify, so I'll get it from YouTube. " if gene_music.spotify(heard) else "")
                what = music[1] if music[0] == "play" and music[1] else ("another one" if music[0] == "next" else "a song")
                p.stop()
                mouth.say(note + (f"Okay, finding {what}." if music[0] != "again" else "Okay, from the top."))
                try:
                    if music[0] == "again":
                        got = (gene_music.download(p.played[-1]), p.title)
                    else:
                        got = gene_music.find(music[1]) if music[0] == "play" else gene_music.find_next()
                except Exception as e:
                    log("music error:", e); got = None
                    reply_directly(heard, "Sorry, I couldn't get music from YouTube right now.", rephrase=False); continue
                if not got:
                    reply_directly(heard, f"Sorry, I couldn't find {what} on YouTube.", rephrase=False); continue
                path, title = got
                reply_directly(heard, f"Here's {title}. Say stop the music when you've had enough.", rephrase=False)
                log(f"playing song {title!r} ({path})")
                p.play(path, title)
                continue
            if usb := gene_usb.wants(heard):
                # said exactly, like the file answers: names, sizes and "safe to pull out" must be right
                log(f"USB {usb}")
                if usb[0] == "copy" and usb[1] and gene_usb.drives():
                    mouth.say("Okay, copying it now.")
                try:
                    said = gene_usb.act(usb)
                except Exception as e:
                    log("USB error:", e); said = "Sorry, something went wrong with the USB stick."
                log("USB:", said); reply_directly(heard, said, rephrase=False)
                continue
            if said := timers.command(heard):
                log("timers:", said); reply_directly(heard, said)
                continue
            if said := memory.command(heard):
                # the model garbles forgetting ("I forget that you don't like cats"), so that is said exactly
                log("memory:", said); reply_directly(heard, said, rephrase=not gene_memory.FORGET.search(heard))
                continue
            if (clip := gene_sounds.wants(heard)) is not None:
                log("sound bite:", repr(clip))
                try:
                    got = gene_sounds.get(clip)
                except Exception as e:
                    log("sound bite error:", e); got = None
                    reply_directly(heard, "Sorry, I couldn't get that sound right now."); continue
                if not got:
                    reply_directly(heard, f"Sorry, I couldn't find a sound bite for {clip}."); continue
                title, wav, secs = got
                log(f"playing {title!r} ({secs:.1f}s)"); gene_eyes.show("happy")
                mouth.play(wav, secs); mouth.wait(); gene_eyes.settle(); sound_played = time.time()
                history += [{"role": "user", "content": heard}, {"role": "assistant", "content": f"[happy] Here is the {title} sound, from myinstants.com."}]
                memory.save_history(history)
                continue
            if vol := gene_volume.wants(heard):
                # said exactly (the number must be right), and at the new volume so they hear the difference
                try:
                    said = gene_volume.act(vol)
                except Exception as e:
                    log("volume error:", e); said = "Sorry, I couldn't change my volume right now."
                log(f"volume {vol}:", said); reply_directly(heard, said, rephrase=False)
                continue
            if files := gene_files.wants(heard):
                # said exactly: the model would garble file names and counts
                log(f"files {files}")
                try:
                    said = gene_files.answer(files)
                except Exception as e:
                    log("files error:", e); said = "Sorry, I couldn't look at my files right now."
                reply_directly(heard, said, rephrase=False, by_sentence=files[0] in ("read", "more"))
                continue
            if gpio := gene_gpio.wants(heard):
                try:
                    said = gene_gpio.act(gpio)
                except Exception as e:
                    log("GPIO error:", e); said = "Sorry, something went wrong with the pins."
                log(f"GPIO {gpio}:", said); reply_directly(heard, said)
                continue
            extra = []
            offered = bool(history) and re.search(r"\blook\s+(?:it|that|them|this)\s+up\b|\bsearch\b", history[-1]["content"], re.I)
            query = gene_web.wants_search(heard, topic)
            if not query and offered and re.fullmatch(r"\W*(?:yes|yeah|yep|sure|ok|okay|please|go\s+ahead|do\s+it)\b[\w\s,.!]{0,15}", heard, re.I):
                query = topic.query()   # Gene offered to look it up and was told "Do it."
            topic.hear(heard)
            if query:
                mouth.say("Let me look that up.")
                try:
                    found = gene_web.search(query)
                    log(f"web search {query!r}: {found[:120]}")
                    if found:
                        extra.append(f"(web: answer using these search results, mention the key facts: {found.replace('(', '[').replace(')', ']')})")
                except Exception as e:
                    log("web search error:", e); found = ""
                if not found:   # else the model claims it looked it up and makes an answer up
                    extra.append("(web: the search found nothing - say you couldn't find it online, don't guess)")
            try:   # "my mother's not Asian" - drop the wrong memory before it is offered again
                last = history[-1]["content"] if history and history[-1]["role"] == "assistant" else ""
                if wrong := memory.correct(heard, last):
                    extra.append("(memory: you had this wrong and have now forgotten it: "
                                 + " ".join(wrong).replace("(", "[").replace(")", "]")
                                 + " Say sorry briefly and that you've forgotten it.)")
            except Exception as e:
                log("memory correction error:", e)
            try:
                if mem := memory.recall(heard):
                    extra.append(mem); log(mem)
            except Exception as e:
                log("memory recall error:", e)
            extra.append(gene_clock.clock_line())
            extra.append(status_line())
            if sums := math_line(heard):
                extra.append(sums); log(sums)
            if cam := camera_line():
                extra.append(cam)
            pictures = None
            if gene_vision.wanted(heard):      # "what colour is this?": a real look, not just YOLO's labels
                shut = gene_eyes.lids_shut()
                if gene_brain.claude_ready() and (seen := gene_vision.pick(heard, shut)):
                    n, side, frame = seen       # Claude looks at the frame itself (~2-3 s)
                    pictures = [gene_vision.png(frame)]
                    extra.append(f"(camera look: the picture attached is what your {side} eye sees right now - answer "
                                 f"from it, and only say what you can really see in it)")
                    log(f"look: frame from the {side} eye goes to Claude")
                else:                           # Moondream on the Pi, ~5-15 s: say so first
                    looked = {}

                    def do_look():
                        try:
                            looked["line"] = gene_vision.look(heard, shut)
                        except Exception as e:
                            log("vision error:", e)
                    seer = threading.Thread(target=do_look, daemon=True); seer.start()
                    mouth.say(LOOK_FILLERS[int(time.time()) % len(LOOK_FILLERS)])
                    seer.join(gene_vision.TIMEOUT + 5); mouth.wait()
                    if look := looked.get("line"):
                        extra.append(look); log(look)
                    else:     # else the model makes up what it sees
                        extra.append("(camera look: you couldn't get a good look just now - say so, don't guess)")
            ack = bool(BACKCHANNEL.fullmatch(heard)) and not query and "?" not in last_reply
            if ack:
                extra.append(BACKCHANNEL_LINE)
            extra.append("(eyes: start with an eye tag)")       # with this the 3B model tags 14/14 test replies
            # context lines first, then the words: the 3B model uses its memories far more reliably this way
            answer(heard, "\n".join(extra + [f"{memory.speaker} says: {heard}"]), t0,
                   max_sentences=1 if ack else MAX_SENTENCES, images=pictures)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
