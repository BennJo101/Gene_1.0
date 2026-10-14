"""Gene's voice, run locally. The default is Gene's own trained Piper voice (tools/piper/voices/gene.onnx,
fine-tuned on Colab with tools/piper/Gene_Piper_Training.ipynb on the ElevenLabs "Gene" recordings).
Kokoro-82M (open-weight, Apache-2.0, ONNX Runtime) is kept as a fallback with stock voices.

Used by speech.py (the sim's canned phrases) and live_server.py (the Live panel's /api/tts).
The model reports how long it spends on every phoneme, so each phoneme becomes a mouth shape with
its exact time in the audio. The shapes use the same numbering as the Windows (SAPI) visemes the
sim was built on, so the page's jaw table (VIS_OPEN) and servo model work unchanged.

Model files live in tools/tts/ (not served):
  kokoro-v1.0.onnx, voices-v1.0.bin  from github.com/thewh1teagle/kokoro-onnx/releases (model-files-v1.1)
Piper voices: <name>.onnx + <name>.onnx.json in tools/piper/voices/, offered as "piper:<name>".
Needs: pip install kokoro-onnx soundfile "piper-tts[alignment]"
"""
import io, os, re, threading
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "tts", "kokoro-v1.0.onnx")
VOICES = os.path.join(HERE, "tts", "voices-v1.0.bin")
CUSTOM = os.path.join(HERE, "tts", "custom_voices.npz")   # voices fitted to a recording by voice_match.py
PIPER_DIR = os.path.join(HERE, "piper", "voices")
DEFAULT_VOICE = "piper:gene"        # Gene's trained voice
KOKORO_FALLBACK = "am_michael"      # used if a Kokoro voice name isn't found
GAIN = 2.0                          # output boost (master volume halved to match) - a limiter keeps it from clipping
SR = 24000
# English voices worth offering in the page: a = American, b = British; m = male, f = female
VOICE_CHOICES = ["am_michael", "am_fenrir", "am_puck", "am_echo", "am_eric", "am_liam", "am_onyx", "am_adam",
                 "bm_george", "bm_fable", "bm_lewis", "bm_daniel",
                 "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "bf_emma", "bf_isabella"]

# IPA phoneme (as espeak writes it for Kokoro) -> SAPI viseme number:
# 0 silence, 1 ae/ah, 2 aa, 3 ao, 4 ey/eh/uh, 5 er, 6 y/iy/ih, 7 w/uw, 8 ow, 9 aw, 10 oy, 11 ay,
# 12 h, 13 r, 14 l, 15 s/z, 16 sh/ch/jh, 17 th/dh, 18 f/v, 19 d/t/n, 20 k/g/ng, 21 p/b/m
VISEME = {}
for chars, v in (("æəʌɐ", 1), ("ɑa", 2), ("ɔɒ", 3), ("eɛʊ", 4), ("ɜɝɚ", 5), ("iɪjᵻy", 6), ("uwʉ", 7), ("o", 8),
                 ("hç", 12), ("ɹr", 13), ("lɫ", 14), ("sz", 15), ("ʃʒ", 16), ("θð", 17), ("fv", 18),
                 ("dtnɾʔ", 19), ("kgŋxɡ", 20), ("pbm", 21)):
    for c in chars:
        VISEME[c] = v
MARKS = "ˈˌːˑ"            # stress and length marks: they belong to the phoneme next to them
_lock = threading.Lock()
_synth = threading.Lock()   # one sentence at a time: the model already uses every core, and in-order
_tts = None                 # requests finish in order (in parallel, three sentences took 3-4x longer each)


def engine():
    """Load the model once (about 1.5 s), shared by every thread."""
    global _tts
    with _lock:
        if _tts is None:
            from kokoro_onnx import Kokoro
            _tts = Kokoro(MODEL, VOICES)
            if not _tts.has_timings:
                raise RuntimeError("this Kokoro export has no duration output, so no mouth timing: use model-files-v1.1")
        return _tts


def custom_voices():
    """Fitted voices, re-read when the file changes so a new fit shows up without a restart."""
    global _custom, _custom_mtime
    m = os.path.getmtime(CUSTOM) if os.path.exists(CUSTOM) else None
    if m != _custom_mtime:
        _custom, _custom_mtime = (dict(np.load(CUSTOM)) if m else {}), m
    return _custom


_custom, _custom_mtime = {}, None


def piper_voices():
    if not os.path.isdir(PIPER_DIR):
        return []
    return ["piper:" + f[:-5] for f in sorted(os.listdir(PIPER_DIR))
            if f.endswith(".onnx") and os.path.exists(os.path.join(PIPER_DIR, f + ".json"))]


def voice_choices():
    return [v for v in piper_voices() if v == DEFAULT_VOICE] + sorted(custom_voices()) + VOICE_CHOICES +            [v for v in piper_voices() if v != DEFAULT_VOICE]


_piper = {}


class _T:
    def __init__(self, phoneme, start, end):
        self.phoneme, self.start, self.end = phoneme, start, end


# Words a Piper voice says wrongly, as raw phonemes (Piper's [[ ]] syntax). "Gene" is /dʒˈiːn/, but the
# trained voice shortens that vowel mid-sentence until it sounds like "John", and a doubled length mark
# (dʒˈiːːn) tips it into "Jane". A short i gliding into ee (dʒˈɪiːn) keeps it a steady "ee" in every
# position (F1 ~360 Hz, F2 ~2600 Hz, like "see"), and was the one picked by ear from five options.
PIPER_LEXICON = {"Gene": "dʒˈɪiːn", "Gene's": "dʒˈɪiːnz"}


def piper_lexicon(text):
    for word, ph in PIPER_LEXICON.items():
        text = re.sub(r"(?<![\w'])" + re.escape(word) + r"(?![\w'])", f"[[ {ph} ]]", text)
    return text


def piper_speak(text, name, speed):
    """Piper voice -> (audio float32, sample rate, per-phoneme timings), timings from its alignment output."""
    from piper import PiperVoice, SynthesisConfig
    text = piper_lexicon(text)
    with _lock:
        if name not in _piper:
            _piper[name] = PiperVoice.load(os.path.join(PIPER_DIR, name + ".onnx"), include_alignments=True)
        v = _piper[name]
    parts, timings, n = [], [], 0
    for c in v.synthesize(text, syn_config=SynthesisConfig(length_scale=1.0 / speed), include_alignments=True):
        sr = c.sample_rate
        for a in (c.phoneme_alignments or []):
            timings.append(_T(a.phoneme, n / sr, (n + int(a.num_samples)) / sr)); n += int(a.num_samples)
        n = sum(len(p) for p in parts) + len(c.audio_float_array)      # stay on the audio even if an alignment is short
        parts.append(c.audio_float_array)
    return np.concatenate(parts), sr, timings



def visemes(timings):
    """Per-phoneme timings -> [[start ms, duration ms, SAPI viseme]], stress/length marks merged in."""
    out = []
    for t in timings:
        s, e, p = round(t.start * 1000), round(t.end * 1000), t.phoneme
        if p in MARKS and out:
            out[-1][1] = max(out[-1][1], e - out[-1][0])          # lengthens the sound it marks
            continue
        v = 0 if (p.isspace() or not p.isalpha()) else VISEME.get(p, 4)
        if out and out[-1][2] == 0 and v == 0:
            out[-1][1] = e - out[-1][0]                           # one silence, not a run of them
            continue
        if out and out[-1][2] == 1 and p == "ʊ":                 # British əʊ is one "ow" too
            out[-1][2] = 8; out[-1][1] = e - out[-1][0]; continue
        if out and out[-1][2] == 8 and v == 4 and p == "ʊ":      # oʊ is one "ow"
            out[-1][1] = e - out[-1][0]; continue
        if out and out[-1][2] == 2 and p in "ɪʊ":                # aɪ -> ay, aʊ -> aw
            out[-1][2] = 11 if p == "ɪ" else 9; out[-1][1] = e - out[-1][0]; continue
        if out and out[-1][2] == 3 and p == "ɪ":                 # ɔɪ -> oy
            out[-1][2] = 10; out[-1][1] = e - out[-1][0]; continue
        out.append([s, max(1, e - s), v])
    return out


def shout_windows(timings, ms):
    """[start, end] ms of every sentence that ends in '!': the sim opens the mouth wider there."""
    out, start = [], None
    for t in timings:
        if start is None and t.phoneme.isalpha():
            start = round(t.start * 1000)
        if t.phoneme in ".!?":
            if t.phoneme == "!" and start is not None:
                out.append([max(0, start - 40), round(t.end * 1000)])
            start = None
    return out


def boost(x, gain=GAIN, sr=SR, ceiling=0.98):
    """x * gain, with a 5 ms look-ahead peak limiter so the loud parts are turned down instead of clipped."""
    y = x * gain
    w = max(1, int(sr * 0.005)) | 1
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(y), 1e-9))
    pad = np.pad(need, w // 2, mode="edge")
    g = np.lib.stride_tricks.sliding_window_view(pad, w).min(1)             # every window covering a sample...
    g = np.convolve(np.pad(g, w // 2, mode="edge"), np.ones(w) / w, "valid")  # ...so the smoothed gain stays under it
    return (y * g).astype(np.float32)


def envelope(x, step_ms=10, sr=SR):
    """Loudness every 10 ms, 0-255, normalised to the phrase's loud parts (95th percentile)."""
    n = int(sr * step_ms / 1000); k = len(x) // n
    rms = np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1))
    rms = np.convolve(rms, np.ones(3) / 3, mode="same")
    ref = np.percentile(rms[rms > 0.01], 95) if (rms > 0.01).any() else 1
    return np.clip(rms / ref * 255, 0, 255).astype(int).tolist()


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


# Gene's model writes stage directions: "(laughs)", "*chuckles*", "Haha", "Hehe", "(pauses)". Laughs become a
# real laugh in his own voice; any other bracketed direction becomes a short pause instead of being read out.
LAUGH = re.compile(r"[(*\[]\s*(?:laugh|chuckl|giggl)\w*[^)*\]]*[)*\]]"
                   r"|\b(?:ha(?:ha)+h?|he(?:he)+h?|ha(?:[ ,]+ha)+|he(?:[ ,]+he)+)\b[!.,]*", re.I)
DIRECTION = re.compile(r"\(\s*\w[^)]{0,30}\)|\*\s*\w[^*]{0,30}\*")
_laughs = {}


def _syllable(v, ph, speed, sr):
    """One 'ha' / 'he' from the voice, trimmed to its sound, with a short fade so it ends like a breath."""
    from piper import SynthesisConfig
    a = np.concatenate([c.audio_float_array for c in v.synthesize(f"[[ {ph} ]]", syn_config=SynthesisConfig(length_scale=0.6))])
    loud = np.where(np.abs(a) > 0.02)[0]
    a = a[max(0, loud[0] - int(0.01 * sr)):loud[-1]][:int(0.2 * sr)]
    a = np.interp(np.arange(0, len(a) - 1, speed), np.arange(len(a)), a)     # resample: >1 = higher, shorter
    fade = int(0.06 * sr); a[-fade:] *= np.linspace(1, 0, fade)
    return a


def laugh(name="gene", chuckle=False):
    """A laugh in Gene's voice: a few falling 'ha's (a softer 'he-he' chuckle), made once and cached."""
    key = (name, chuckle)
    if key not in _laughs:
        from piper import PiperVoice
        with _lock:
            if name not in _piper:
                _piper[name] = PiperVoice.load(os.path.join(PIPER_DIR, name + ".onnx"), include_alignments=True)
            v = _piper[name]
        sr = v.config.sample_rate
        ph, steps = ("hˈɛ", [(1.06, 0.6), (1.0, 0.45)]) if chuckle else \
                    ("hˈa", [(1.1, 1.0), (1.06, 0.9), (1.0, 0.75), (0.95, 0.55)])
        parts, timings, n = [], [], 0
        for speed, gain in steps:
            a = _syllable(v, ph, speed, sr) * gain
            gap = np.zeros(int(0.07 * sr), np.float32)
            timings += [_T("h", n / sr, (n + len(a) * 0.3) / sr), _T(ph[-1], (n + len(a) * 0.3) / sr, (n + len(a)) / sr),
                        _T(" ", (n + len(a)) / sr, (n + len(a) + len(gap)) / sr)]
            parts += [a.astype(np.float32), gap]; n += len(a) + len(gap)
        _laughs[key] = (np.concatenate(parts), sr, timings)
    return _laughs[key]


def expressive(text, name, speed):
    """Speech with laughs mixed in: [(audio, sr, timings)] in order. Other stage directions become a pause."""
    out, pos = [], 0
    for m in list(LAUGH.finditer(text)) + [None]:
        piece = text[pos:m.start() if m else len(text)]
        pauses = len(DIRECTION.findall(piece))
        piece = clean(DIRECTION.sub(" ", piece))
        if pauses and not re.search(r"\w", piece):
            sr = 22050; out.append((np.zeros(int(0.35 * sr), np.float32), sr, []))
        elif re.search(r"\w", piece):
            out.append(piper_speak(piece, name, speed))
        if m:
            out.append(laugh(name, chuckle=m.group(0).lower().lstrip("(*[ ").startswith(("he", "chuck", "gigg"))))
            pos = m.end()
    return out


def speak(text, voice=DEFAULT_VOICE, speed=1.0, fmt="WAV"):
    """Text -> {audio (bytes), ms, visemes, shout, env}. fmt: "WAV" or "MP3"."""
    import soundfile as sf
    speed = max(0.5, min(2.0, float(speed)))
    if voice.startswith("piper:") and voice in piper_voices():
        with _synth:
            segs = expressive(text, voice[6:], speed) or [(np.zeros(2205, np.float32), 22050, [])]
        sr = segs[0][1]; audio, timings, t0 = [], [], 0.0
        for a, _, ts in segs:
            timings += [_T(t.phoneme, t.start + t0, t.end + t0) for t in ts]
            audio.append(a); t0 += len(a) / sr
        audio = np.concatenate(audio)
    else:
        tts = engine()
        style = custom_voices().get(voice)
        if style is None and voice not in tts.voices:
            voice = KOKORO_FALLBACK
        with _synth:
            audio, sr, timings = tts.create_timed(clean(text), voice if style is None else style, speed=speed)
    audio = np.clip(audio, -1, 1).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, boost(audio, sr=sr), sr, format=fmt, **({"subtype": "PCM_16"} if fmt == "WAV" else {}))
    ms = round(len(audio) / sr * 1000)
    return {"audio": buf.getvalue(), "ms": ms, "visemes": visemes(timings), "shout": shout_windows(timings, ms),
            "env": envelope(audio, sr=sr), "voice": voice}
