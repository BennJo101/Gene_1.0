"""Gene's close look: a small vision model (Moondream 2 in Ollama on THIS Pi) answers questions only real vision can
("what colour is this?", "what am I holding?", "read this", "describe what you see").

YOLO (gene_cameras.Seer) still names things every 2 s; this runs only when such a question is heard, because it takes
20-40 s on the Pi CPU (only used when Claude can't be reached). The answer goes to Gene's own model as a "(camera look: ...)" context line, so he still
replies in his own words and voice.

  - Ollama on the Pi: http://127.0.0.1:11434 (system service `ollama`), model `moondream` (~1.7 GB), kept loaded
    (KEEP_ALIVE) so a look doesn't wait for it to load from the SD card.
  - Frame: the newest from gene-cameras.service ($XDG_RUNTIME_DIR/gene-camera); the eye asked for ("with your left
    eye"), else the sharper of the open eyes (an eye closed by voice sees nothing).
  - No Pillow in the venv: frames go to Ollama as PNG written with zlib.

Test:  ./venv/bin/python gene_vision.py "what do you see?"
"""
import base64, json, os, re, struct, sys, time, urllib.request, zlib
import numpy as np
import gene_cameras

URL = os.environ.get("GENE_VISION", "http://127.0.0.1:11434")
MODEL = "moondream"
KEEP_ALIVE = "24h"
TIMEOUT = 75            # s; a new picture takes ~20 s to encode on the Pi CPU, ~20-40 s for the answer
MAX_WORDS = 60          # Moondream rambles; the 3B model only needs the gist

# questions that need eyes, not a list of object names
ASK = re.compile(
    r"\bwhat(?:'s|\s+is|\s+are)?\s+(?:colou?r|colou?rs)\b|\bwhat\s+colou?r\b|\bcolou?r\s+(?:is|are)\s+(?:this|that|these|those|my|the)\b|"
    r"\bwhat\s+am\s+i\s+(?:holding|wearing|doing|showing|pointing)\b|\bwhat(?:'s|\s+is)\s+in\s+my\s+hands?\b|"
    r"\bwhat\s+(?:do|can)\s+you\s+see\b|\bwhat\s+are\s+you\s+(?:seeing|looking\s+at)\b|"
    r"\b(?:describe|tell\s+me)\s+what\s+you\s+see\b|\bdescribe\s+(?:this|that|me|the\s+room|what's\s+in\s+front)\b|"
    r"\blook\s+at\s+(?:this|that|me|my)\b|\btake\s+a\s+look\b|\bwhat(?:'s|\s+is)\s+(?:this|that)\s*\??$|"
    r"\bread\s+(?:this|that)\b(?!\s+(?:file|again|out))|\bwhat\s+does\s+(?:this|that|it)\s+say\b|"
    r"\bhow\s+many\s+(?:fingers|people|things)\b|\bwhat\s+do\s+i\s+look\s+like\b|\bhow\s+do\s+i\s+look\b|"
    r"\bwhat(?:'s|\s+is)\s+in\s+front\s+of\s+(?:you|your\s+(?:face|eyes?|cameras?|nose))\b|"
    r"\bwhat\s+kind\s+of\s+\w+\s+is\s+(?:this|that)\b|"
    # reading things held up (2026-10-13: "Okay, read it now." / "Read the freaking water bottle." went unseen and
    # Gene guessed "Dasani"); files are checked first, so "read the jaw drive notes" never gets here
    r"(?:^|[.!?,]\s*|\b(?:please|now|can\s+you|could\s+you|try\s+to|go\s+ahead\s+and)\s+)read\s+it\b(?!\s+(?:again|out|back))|"
    r"\bcan\s+you\s+read\s+(?:this|that|the|my)\b|"
    r"\bread\s+(?:the|my|this|that)\s+(?:\w+\s+){0,2}(?:bottle|label|sign|can|box|book|page|paper|shirt|card|cover|"
    r"writing|words|text|brand|packet|package|wrapper|logo|poster|screen|phone|mug|cup)\b|"
    r"\bwhat(?:'s|\s+is)\s+written\b|\bwhat(?:'s|\s+is)\s+(?:this|that|it)\s+in\s+my\s+hands?\b|"
    # how his eyes see: "is your camera right side up now?", "can you see properly?", "is the picture sideways?"
    r"\b(?:camera|cameras|picture|view|image|eyes?)\b.*\b(?:right\s+side\s+up|upside\s+down|sideways|tilted|crooked|"
    r"straight|level|flipped|the\s+right\s+way)\b|\b(?:right\s+side\s+up|upside\s+down|sideways)\b.*\b(?:camera|view|"
    r"picture|see)\b|\bcan\s+you\s+see\s+(?:properly|clearly|okay|ok|right|well|straight)\b|"
    r"\bhow(?:'s|\s+is|\s+are)\s+(?:your|the)\s+(?:camera|cameras|view|vision|eyesight)\b", re.I)
EYE = re.compile(r"\b(left|right)\s+eye\b", re.I)


def wanted(heard):
    """True when `heard` asks something only a real look can answer."""
    return bool(ASK.search(heard or ""))


def png_rgb(rgb):
    """RGB uint8 HxWx3 -> PNG bytes, no Pillow."""
    h, w = rgb.shape[:2]
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def png(bgr):
    """A BGR camera frame as PNG bytes."""
    return png_rgb(np.ascontiguousarray(bgr[..., ::-1]))


def _sharpness(bgr):
    g = bgr.mean(axis=2)
    return float(np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean())


def pick(heard="", shut=None):
    """(camera number, side, BGR frame) to look with, or None when no open eye has a fresh frame."""
    got = gene_cameras.frames()
    closed = {n for n in got if shut in ("both", gene_cameras.SIDES.get(n))}
    got = {n: f for n, f in got.items() if n not in closed and f.mean() >= gene_cameras.DARK}
    if not got:
        return None
    if m := EYE.search(heard or ""):
        side = m.group(1).lower()
        for n, f in got.items():
            if gene_cameras.SIDES.get(n) == side:
                return n, side, f
    n = max(got, key=lambda k: _sharpness(got[k]))
    return n, gene_cameras.SIDES.get(n, str(n)), got[n]


def prompt_for(heard):
    """What Gene was asked, turned into a question about the picture (Moondream doesn't know who "I" or "you" is)."""
    q = (heard or "").strip().rstrip("?.! ") or "What is in this picture"
    q = re.sub(r"^(?:hey\s+)?gene[,\s]+", "", q, flags=re.I)
    q = re.sub(r"\b(?:with|through)\s+your\s+(?:left|right)\s+eye\b,?", "", q, flags=re.I).strip(" ,") or "What is in this picture"
    if re.search(r"\bread\s+(?:this|that)\b|\bwhat\s+does\s+(?:this|that|it)\s+say\b", q, re.I):
        return "What does the text in this picture say?"
    if re.search(r"\b(?:describe|tell\s+me)\s+what\s+you\s+see\b|\blook\s+at\s+(?:this|that)\b|\btake\s+a\s+look\b", q, re.I):
        return "Describe this picture."
    if re.search(r"\blook\s+at\s+me\b|\bhow\s+do\s+i\s+look\b", q, re.I):
        return "Describe the person in this picture."
    for a, b in ((r"\bwhat\s+(?:do|can)\s+you\s+see\b", "what is in this picture"), (r"\bin\s+front\s+of\s+you\b", "in this picture"),
                 (r"\bam\s+i\b", "is the person"), (r"\bdo\s+i\b", "does the person"), (r"\bi'm\b", "the person is"),
                 (r"\bmy\b", "the person's"), (r"\bme\b", "the person"), (r"\bi\b", "the person"), (r"\byou\b", "the camera")):
        q = re.sub(a, b, q, flags=re.I)
    return q[0].upper() + q[1:] + "?"


def ask(prompt, bgr, timeout=TIMEOUT):
    body = {"model": MODEL, "prompt": prompt, "images": [base64.b64encode(png(bgr)).decode()],
            "stream": False, "keep_alive": KEEP_ALIVE, "options": {"num_predict": 90}}   # plain prompts: Moondream 2 garbles instructions
    req = urllib.request.Request(URL + "/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = json.load(r).get("response", "")
    words = re.sub(r"\s+", " ", text).strip().split()
    return " ".join(words[:MAX_WORDS]) + ("..." if len(words) > MAX_WORDS else "")


def look(heard, shut=None):
    """The "(camera look: ...)" line for `heard`; "" when there's nothing to look with or the model failed."""
    p = pick(heard, shut)
    if p is None:
        return ""
    n, side, frame = p
    prompt = prompt_for(heard)
    text = ask(prompt, frame)
    if not text and prompt != "Describe this picture.":    # Moondream 2 answers some questions with nothing at all;
        text = ask("Describe this picture.", frame)        # the picture is cached by then, so this is quick
    text = text.replace("(", "[").replace(")", "]")
    if not text:
        return ""
    return (f"(camera look: through your {side} eye just now you see: {text} - this is what you really see; "
            f"answer from it in your own words, don't add things it doesn't say)")


def warm():
    """Loads the model into RAM in the background at start, so the first look doesn't wait ~10 s for it."""
    try:
        req = urllib.request.Request(URL + "/api/generate", json.dumps({"model": MODEL, "keep_alive": KEEP_ALIVE}).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=TIMEOUT).read()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "what do you see?"
    print("wanted:", wanted(q), "| prompt:", prompt_for(q))
    t = time.time()
    print(look(q) or "no look (no fresh frame, or Ollama/moondream not running)", f"\n{time.time() - t:.1f}s")
