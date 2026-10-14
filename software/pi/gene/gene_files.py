"""Gene's own files and folders, by voice (read-only: nothing is changed, moved or deleted).

  "what files do you have?" / "can you see your files and folders?"   - his ~/gene folder
  "what's in your state folder?" / "list the files on your desktop" / "show me your home folder"
  "what's in the Gene Robot folder?" / "how many files are in your models folder?"
  "tell me about your gene clock file" / "what does gene_memory.py do?" / "open your Modelfile"
  "show me all the files on your Raspberry Pi" / "what's in your root folder?" - the whole Pi, from /
  "read me the jaw drive notes" / "read the readme in the brain folder" / "read the parts file in the legs folder" /
  "what does the dynamixel specs file say?" - read a file out loud, ~80 words at a time; then "keep reading" /
  "read more" / "go on" for the next part, "read it again" from the start (within 10 minutes)
  "what's in your etc folder?" / "what's in the var log folder?" / "what's in your boot firmware folder?"

Folders are found by name under the home folder (two levels into ~/gene, ~/Desktop and ~/Desktop/Gene Robot, one level
elsewhere) and on the rest of the Pi (the folders in /, and one level into /usr, /var, /boot and /media). Dot files and
__pycache__ are never shown, nor what's inside other users' home folders. A file is described by its kind and size,
and for text files in ~/gene or on the Desktop by what it says: a Python file's docstring, else its first line.
A file to read is searched for by the words of its name and of the folders it is in, anywhere in ~/gene (not venv,
state, models, piper), the Desktop (the whole Gene Robot folder) and a mounted USB stick; PDFs go through pdftotext.
"""
import os, re, subprocess, time, unicodedata

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.join(HOME, "Desktop")
MEDIA = os.path.join("/media", os.path.basename(HOME))   # USB sticks (gene_usb mounts them here)
READABLE = (HERE, DESK, MEDIA)  # text is only read aloud from these (not e.g. ~/claude-sudo-fan.txt)
SKIP = {"venv", "state", "models", "piper", "node_modules", "target", "__pycache__"}   # not searched for files to read
HIDE = {"__pycache__", "lost+found"}
MAX_NAMES = 12                  # names said per list ("... and 12 more")
ROOT = "/"
SYSTEM = [(ROOT, 1), ("/usr", 1), ("/var", 1), ("/boot", 1), ("/media", 1)]   # not /etc, /proc...: too many names
SAY = {"usr": "user", "etc": "etc", "tmp": "temp", "var": "var", "sbin": "s bin", "srv": "serve"}  # how STT hears them
# "the files on your Raspberry Pi", "your whole computer", "your SD card", "your root folder"
WHOLE_PI = re.compile(r"\b(?:raspberry\s+)?pie?\b|\bgod\s?pi\b|\bwhole\s+(?:system|computer|drive|disk)\b|"
                      r"\b(?:sd|s\.d\.)\s+card\b|\broot\s+(?:folder|directory)\b", re.I)

FILE_WORD = r"(?:files?|folders?|director(?:y|ies)|file\s?(?:sets?|system)|code\s+files?)"
LOOK = re.compile(r"\b(?:what|which|list|show|see|tell|read|open|look|name|how\s+many|describe|explain|browse)\b", re.I)
OWN = re.compile(r"\b(?:you|your|yours|you've|yourself|gene's)\b", re.I)
NOT_FILES = re.compile(r"\b(?:pins?|gpio|remember|forget|timers?|reminders?)\b", re.I)
KINDS = {".py": "a Python file", ".md": "a text note", ".txt": "a text file", ".json": "a data file",
         ".jsonl": "a log file", ".log": "a log file", ".wav": "a sound recording", ".onnx": "an AI model",
         ".sh": "a shell script", ".cpp": "a C++ source file", ".html": "a web page", ".stp": "a 3D CAD model",
         ".stl": "a 3D print model", ".3mf": "a 3D print model", ".step": "a 3D CAD model", ".ipynb": "a notebook", ".gguf": "an AI model", ".pdf": "a PDF document",
         ".png": "a picture", ".jpg": "a photo", ".conf": "a settings file", ".Modelfile": "my brain's Modelfile"}


def _words(name):
    """'gene_clock.py' -> 'gene clock py'; 'Brain (Jetson)' -> 'brain jetson'."""
    return " ".join(re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", name).lower()))


def spoken(name, folder=False):
    """How a file name is said: 'gene_clock.py' -> 'gene clock dot py', 'upgrade_steps.json' -> 'upgrade steps dot json'."""
    if folder:
        return " ".join(re.sub(r"[_\-]+", " ", name).split())
    stem, ext = os.path.splitext(name)
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,9}", ext):     # 'config-6.18.50+rpt-rpi-2712' has no extension
        stem, ext = name, ""
    stem = " ".join(re.sub(r"[_\-.+]+", " ", stem).split()) or name
    return stem + (f" dot {ext[1:]}" if ext else "")


def _visible(path):
    try:
        return sorted((e for e in os.scandir(path) if not e.name.startswith(".") and e.name not in HIDE),
                      key=lambda e: e.name.lower())
    except OSError:
        return []


def folders():
    """Every folder Gene can name: [(path, spoken words)], his own first."""
    out = [(HERE, "gene"), (HERE, "own"), (HOME, "home"), (HOME, "bennjo")]
    todo = [(HERE, 2), (HOME, 1), (DESK, 1), (os.path.join(DESK, "Gene Robot"), 2)]
    while todo:
        path, depth = todo.pop()
        for e in _visible(path):
            if e.is_dir(follow_symlinks=False):
                out.append((e.path, _words(e.name)))
                if depth > 1:
                    todo.append((e.path, depth - 1))
    # the rest of the Pi after his own folders, so "the models folder" stays ~/gene/models; "the var log folder" = /var/log
    out.append((ROOT, "root"))
    for top, _ in SYSTEM:
        for e in _visible(top):
            if e.is_dir() and not e.name.isdigit():
                words = " ".join(SAY.get(w, w) for w in _words(e.path).split())
                out.append((e.path, words))
                if top != ROOT:     # "the log folder" also finds /var/log
                    out.append((e.path, " ".join(SAY.get(w, w) for w in _words(e.name).split())))
                if words != _words(e.path):
                    out.append((e.path, _words(e.path)))
    return out


def _named(heard, entries):
    """The entry whose spoken name appears in `heard` (longest name wins), else None."""
    said = " " + _words(heard) + " "
    best = None
    for path, words in entries:
        if words and f" {words} " in said and (best is None or len(words) > len(best[1])):
            best = (path, words)
    return best and best[0]


def _file_in(heard, folder):
    """A file named in `heard`: in `folder`, else in Gene's own folder. 'gene clock' matches gene_clock.py."""
    said = " " + re.sub(r" (?:dot|underscore|dash)(?= )", "", " " + _words(heard)) + " "
    for where in dict.fromkeys([folder, HERE, os.path.join(HERE, "brain")]):
        best = None
        for e in _visible(where):
            if not e.is_file():
                continue
            stem, ext = os.path.splitext(e.name)
            # "gene" alone is everything here (gene.log would answer "the Gene Robot folder"); "modelfile" names gene.Modelfile
            for w in (_words(e.name), _words(stem), ext == ".Modelfile" and "modelfile"):
                if w and len(w) >= 3 and w != "gene" and f" {w} " in said and (best is None or len(w) > best[0]):
                    best = (len(w), e.path)
        if best:
            return best[1]
    return None


def wants(heard):
    """('list', folder), ('file', path), ('read', path) or ('more', path) if `heard` asks to see or read Gene's files
    or folders, else None."""
    if _reading and time.time() - _reading["at"] < READ_FOR:
        if MORE.search(heard):
            return ("more", _reading["path"])
        if AGAIN.search(heard) and not re.search(r"\b" + FILE_WORD + r"\b", heard, re.I):
            return ("read", _reading["path"])
    if NOT_FILES.search(heard) or not LOOK.search(heard):
        return None
    heard = re.sub(r"\bgene\s?robot\b", "Gene Robot", heard, flags=re.I)     # STT: "GeneRobot"
    has_word = re.search(r"\b" + FILE_WORD + r"\b", heard, re.I)
    ext = re.search(r"\b\w+(?:\.|\s+dot\s+)(?:py|json|jsonl|md|txt|sh|log|wav|cpp|onnx|pdf|csv)\b|\bmodelfile\b|\bread\s*me\b(?!\s+(?:the|a|your|my|what|some|it|that|this)\b)", heard, re.I)
    reading = READ.search(heard)
    if not (has_word or ext):
        f = reading and _search(heard, strict=True)     # "read me the jaw drive notes"
        return ("read", f) if f else None
    m = re.search(r"\b(?:in|inside|of|on|under)\s+(?:your|the|my|gene's)\s+((?:\w+\s+){0,3}?)(?:folder|directory)\b", heard, re.I)
    folder = None
    if m:
        folder = _named(m.group(1), folders())
    if not folder and re.search(r"\b(?:on|in)\s+(?:your|the)\s+desktop\b", heard, re.I):
        folder = DESK
    if not folder and WHOLE_PI.search(heard):
        folder = ROOT
    if not folder:
        folder = _named(re.sub(r"\b(?:files?)\b", " ", heard, flags=re.I).split("folder")[0], folders()) \
            if re.search(r"\b(?:folder|directory)\b", heard, re.I) else None
    if reading and (ext or re.search(r"\bfile\b", heard, re.I) or not re.search(r"\bfiles\b", heard, re.I)) \
            and (f := folder and _search(heard, folder) or _search(heard)):
        return ("read", f)  # "read the parts file in the legs folder"
    if not folder and has_word and re.search(r"\bfiles?\b", heard, re.I):     # STT heard "the Gene Robot file"
        folder = _named(re.sub(r"\bfiles?\b", " ", heard, flags=re.I), folders()[4:])
    if not (OWN.search(heard) or folder or ext):
        return None     # "what is a file?" is for the model
    if (ext or re.search(r"\bfile\b", heard, re.I)) and (f := _file_in(heard, folder or HERE)):
        return ("file", f)
    if not has_word:
        return None
    return ("list", folder or HERE)


# reading a file out loud
READ = re.compile(r"\b(?:read|recite)\b|\bwhat\s+does\s+.+\s+say\b|\bwhat(?:'s|\s+is)\s+written\b", re.I)
MORE = re.compile(r"^\W*(?:(?:ok(?:ay)?|yes|and|please|now|gene)\W+)*(?:keep\s+(?:on\s+)?(?:reading|going)|"
                  r"(?:read|tell\s+me)\s+(?:me\s+)?(?:some\s+)?more|read\s+(?:me\s+)?the\s+(?:next|rest)\b|"
                  r"continue(?:\s+reading)?|carry\s+on|go\s+on|next\s+(?:part|page|bit)|what\s+(?:does\s+it\s+say\s+)?next)"
                  r"\b[\w\s,.!']{0,25}$", re.I)
AGAIN = re.compile(r"\b(?:read|start)\s+(?:it|that|this)?\s*(?:again|over)\b|\bfrom\s+the\s+(?:start|beginning|top)\b", re.I)
CHUNK_WORDS = 80                # ~30 s of talking per part (the mic is off while he talks, so nobody can stop him)
READ_FOR = 600                  # "keep reading" works this long after the last part
TEXT_EXT = {".md", ".txt", ".py", ".json", ".csv", ".log", ".sh", ".toml", ".yml", ".yaml", ".xml", ".html", ".ino",
            ".cpp", ".c", ".h", ".rs", ".js", ".conf", ".cfg", ".ini", ".Modelfile", ".urdf", ".pdf", ""}
STOP = {"the", "a", "an", "of", "and", "in", "on", "to", "me", "my", "your", "you", "can", "please", "read", "out",
        "loud", "aloud", "what", "does", "it", "say", "says", "file", "files", "folder", "folders", "gene", "robot",
        "is", "that", "this", "for", "from", "inside", "under", "with", "whole", "all", "called", "named", "recite",
        "s", "written", "there", "find", "open", "up", "now", "for", "us"}
_reading = {}                   # {"path", "parts", "next", "at"}


def _tokens(text):
    """'Dynamixel XL330-M288-T - specs.md' -> {'dynamixel', 'xl', '330', 'm', '288', 't', 'specs', 'md'}."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower()
    text = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", text)
    words = (re.sub(r"ies$", "y", w) if len(w) > 4 else w for w in re.findall(r"[a-z0-9]+", text))
    words = (w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)   # notes = note
    return [w for w in words if w not in STOP and (len(w) > 1 or w.isdigit())]


def _ext(name):
    return ".Modelfile" if name.endswith(".Modelfile") else os.path.splitext(name)[1].lower()


def _search(heard, folder=None, strict=False):
    """The file `heard` names, searched for by the words of its name and of the folders it is in.
    strict (no 'file' word nor extension said): only text files whose name is (nearly) all in what was heard."""
    heard = re.sub(r"\bgene\s*robot\b", " ", heard, flags=re.I)
    heard = re.sub(r"\b(the|your|a|my)\s+read\s*me\b", r"\1 readme", heard, flags=re.I)    # README.md
    said = set(_tokens(re.sub(r"\b(\w+)\s+dot\s+(\w+)\b", r"\1 \2", heard)))
    if not said:
        return None
    best = None
    for root in ([folder] if folder else [HERE, DESK, MEDIA]):
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP and d not in HIDE]
            under = set(_tokens(os.path.relpath(dirpath, root))) if dirpath != root else set()
            for name in names:
                if name.startswith("."):
                    continue
                stem = set(_tokens(os.path.splitext(name)[0] if _ext(name) != ".Modelfile" else name))
                ext = _ext(name)
                if ext == ".Modelfile":
                    stem.add("modelfile")
                hits, ext_said = len(stem & said), ext[1:].lower() in said
                if not (hits or ext_said) and (strict or not under & said):     # "the story file" = the one in stories/
                    continue
                cover = len(stem & said) / max(len(stem), 1)
                text = ext in TEXT_EXT
                if strict and not (text and (cover == 1 or (len(stem & said) >= 2 and cover >= 0.6))):
                    continue
                score = (hits + len(under & said), cover, ext_said, text, -dirpath.count(os.sep), dirpath.startswith(HERE))
                if best is None or score > best[0]:
                    best = (score, os.path.join(dirpath, name))
    return best and best[1]


def _text(path):
    """A file's words, cleaned up for speaking; None if it isn't text."""
    if path.lower().endswith(".pdf"):
        try:
            text = subprocess.run(["pdftotext", "-q", path, "-"], capture_output=True, timeout=30).stdout
        except (OSError, subprocess.TimeoutExpired):
            return None
        text = text.decode("utf-8", "replace").replace("\f", "\n")
    else:
        try:
            with open(path, "rb") as f:
                raw = f.read(300_000)
        except OSError:
            return None
        if b"\0" in raw[:4000]:
            return None
        text = raw.decode("utf-8", "replace")
    text = unicodedata.normalize("NFKC", text)     # the PDFs' "ﬁ" ligatures
    out, open_line = [], False
    fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)                     # images
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)                 # [text](link) -> text
        line = re.sub(r"https?://\S+", "a link", line)
        line = re.sub(r"<[^>]{1,80}>", " ", line)                              # html tags
        if re.fullmatch(r"[\s|:\-=+*#_~`]*", line):                             # rules, table separators
            continue
        line = line.replace("|", ", ").replace("_", " ")
        line = re.sub(r"[*`]+|\"\"\"|'''", "", line)
        line = re.sub(r"[#>~]+", " ", line)
        line = re.sub(r"^\s*[-+•]\s+", "", line)
        line = " ".join(line.split()).strip(" ,")
        if not line:
            open_line = False
        elif open_line and (line[0].islower() or line[0] in "(&"):     # a hard-wrapped sentence goes on
            out[-1] += " " + line
        else:
            out.append(line)
            open_line = line[-1] not in ".!?:;,"
    return " ".join(l if l[-1] in ".!?:;," else l + "." for l in out)     # a pause after headings and list items


def _parts(text):
    """~CHUNK_WORDS-word parts, cut at sentence ends."""
    parts, cur = [], []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        words = sent.split()
        while len(words) > CHUNK_WORDS * 3 // 2:    # a 'sentence' with no full stops (code, lists)
            if cur:
                parts.append(" ".join(cur)); cur = []
            parts.append(" ".join(words[:CHUNK_WORDS]) + "...")
            words = words[CHUNK_WORDS:]
        cur += words
        if len(cur) >= CHUNK_WORDS:
            parts.append(" ".join(cur)); cur = []
    if cur:
        parts.append(" ".join(cur))
    return parts


def read_file(path, more=False):
    """The next part of a file, read out loud, with what to say for more."""
    global _reading
    name = os.path.basename(path)
    title = spoken(os.path.splitext(name)[0] if _ext(name) in (".md", ".txt", ".pdf") else name)
    title = title.lower() if title.isupper() else title     # "JAW_DRIVE_NOTES" isn't spelled out
    if more and _reading.get("path") == path:
        r = _reading
        if r["next"] >= len(r["parts"]):
            return f"That was the end of {title}. Say read it again to start over."
    else:
        if not any(os.path.realpath(path).startswith(root + os.sep) for root in READABLE):
            return f"I only read files in my own folders, on my desktop or on a USB stick, so I won't read {title} out."
        text = _text(path)
        if text is None:
            return describe_file(path).rstrip(".") + ". It isn't text, so I can't read it out loud."
        if not text.strip():
            return f"{title.capitalize()} is empty."
        r = _reading = {"path": path, "parts": _parts(text), "next": 0}
    i, n = r["next"], len(r["parts"])
    r["next"], r["at"] = i + 1, time.time()
    said = (f"Reading {title}. " if i == 0 else "") + r["parts"][i]
    if i + 1 >= n:
        return said + (" The end." if n > 1 else "")
    if i == 0:
        mins = round(sum(len(p.split()) for p in r["parts"]) / 160)
        return said + f" That's part 1 of {n}{f', about {mins} minutes in all' if mins > 1 else ''}. Say keep reading for more."
    return said + f" That's part {i + 1} of {n}. Say keep reading for more."


def _size(n):
    if n < 1000:
        return f"{n} bytes"
    for unit in ("kilobytes", "megabytes", "gigabytes"):
        n /= 1000
        if n < 1000:
            return f"{n:.0f} {unit}" if n >= 10 else f"{n:.1f} {unit}"
    return f"{n:.0f} terabytes"


def _names(items, folder=False, most=MAX_NAMES):
    names = [spoken(e.name, folder) for e in items]
    more = len(names) - most
    names = names[:most] + ([f"and {more} more"] if more > 0 else [])
    if len(names) > 1 and more <= 0:
        names[-1] = "and " + names[-1]
    return ", ".join(names) if len(names) > 2 else " ".join(names)


def _where(folder):
    if folder == ROOT:
        return "my Raspberry Pi's main folder"
    if folder == HERE:
        return "my own gene folder"
    if folder == HOME:
        return "my home folder"
    if folder == DESK:
        return "my desktop"
    if not folder.startswith(HOME + os.sep):    # a system folder: "the var log folder"
        return "the " + " ".join(SAY.get(w, w) for w in _words(folder).split()) + " folder"
    return f"my {spoken(os.path.basename(folder), True)} folder"


def _disk():
    """'My SD card holds 464 gigabytes, and 11 gigabytes are used.'"""
    try:
        st = os.statvfs(ROOT)
    except OSError:
        return ""
    total, free = st.f_blocks * st.f_frsize, st.f_bfree * st.f_frsize
    return f" My SD card holds {_size(total)}, and {_size(total - free)} {'are' if total - free >= 2000 else 'is'} used."


def describe_folder(folder):
    items = _visible(folder)
    dirs = [e for e in items if e.is_dir()]
    files = [e for e in items if not e.is_dir()]
    if not items:
        return f"{_where(folder).capitalize()} is empty."
    parts = []
    if dirs:
        parts.append(f"{len(dirs)} folder{'s' if len(dirs) > 1 else ''}: {_names(dirs, True, 30 if folder == ROOT else MAX_NAMES)}")
    if files:
        py = [e for e in files if e.name.endswith(".py")]
        rest = [e for e in files if not e.name.endswith(".py")]
        if len(py) > 2 and rest:    # "8 Python files: gene client, gene clock, ..." reads better than "dot py" eight times
            parts.append(f"{len(py)} Python files: {_names([type('E', (), {'name': e.name[:-3]}) for e in py])}")
            parts.append(f"{len(rest)} other file{'s' if len(rest) > 1 else ''}: {_names(rest)}")
        else:
            parts.append(f"{len(files)} file{'s' if len(files) > 1 else ''}: {_names(files)}")
    said = f"{'On' if folder == DESK else 'In'} {_where(folder)} I have " + ". And ".join(parts) + "."
    return said + _disk() if folder == ROOT else said


def _first_text(path):
    """A Python file's docstring summary, else the first real line of a text file; '' for binary files."""
    try:
        with open(path, "rb") as f:
            head = f.read(4000)
    except OSError:
        return ""
    if b"\0" in head:
        return ""
    text = head.decode("utf-8", "replace")
    if path.endswith(".py") and (m := re.match(r'\s*(?:#.*\n)*\s*[rb]?("""|\'\'\')(.*?)(?:\1|$)', text, re.S)):
        text = m.group(2).strip().split("\n\n")[0]
        text = re.split(r"(?<=[.!?])\s", " ".join(text.split()))[0]
    else:
        text = next((l.strip(" #/*-") for l in text.splitlines() if len(l.strip(" #/*-{}[]\"'")) > 2), "")
    text = text[:200].rsplit(" ", 1)[0] + "..." if len(text) > 200 else text
    return text.replace("_", " ")


def describe_file(path):
    name = os.path.basename(path)
    ext = ".Modelfile" if name.endswith(".Modelfile") else os.path.splitext(name)[1].lower()
    kind = KINDS.get(ext, "a file")
    try:
        size = os.path.getsize(path)
    except OSError:
        return f"I can't open {spoken(name)}."
    said = f"{spoken(name)} is {kind}, {_size(size)}"
    if any(os.path.realpath(path).startswith(r + os.sep) for r in READABLE) and (first := _first_text(path)):
        try:
            with open(path, "rb") as f:
                lines = f.read().count(b"\n")
            said += f", {lines} lines"
        except OSError:
            pass
        said += f". It says: {first}" if ext == ".py" else f". It starts: {first}"
    return said if said.endswith((".", "!", "?", "...")) else said + "."


def answer(req):
    kind, path = req
    real = os.path.realpath(path)
    if real == "/root" or real.startswith("/root/") or (real.startswith("/home/") and real != HOME
                                                        and not real.startswith(HOME + os.sep)):
        return "That folder belongs to someone else, so I don't look in it."
    if kind in ("read", "more"):
        return read_file(path, more=kind == "more")
    return describe_folder(path) if kind == "list" else describe_file(path)
