"""USB sticks, by voice: Gene can look at, write to and eject a USB stick plugged into the Pi.

  "what's on the USB stick?" / "is there a USB plugged in?"                - lists its top folder + free space
  "put your gene clock file on the USB" / "copy your state folder to the USB stick" / "back yourself up to the USB"
  "save your memories / our conversations / your voice / your memory vault (Obsidian) to the USB"         - copies from his home folder onto the stick
  "write hello world on the USB" / "write a note on the USB saying buy milk" - a new text file with those words
  "eject the USB" / "unmount the flash drive" / "can I take the USB out?"   - unmounts it so it's safe to pull out

The stick is found with lsblk (a disk on the usb bus) and mounted with udisksctl like the desktop does
(/media/<user>/<label>), else with sudo mount. Nothing on the stick is ever deleted or overwritten: a name that is
already there gets " 2", " 3"... Only files from the home folder are copied (not other users' or system files).
"""
import datetime, json, os, re, shutil, subprocess
import gene_files

HOME = gene_files.HOME
HERE = gene_files.HERE
SKIP = {"venv", "__pycache__", "lost+found"}       # never copied ("back yourself up" = ~/gene without the 271 MB venv)
USB = r"(?:usb|u\.?\s?s\.?\s?b\.?|flash\s?drive|thumb\s?drive|pen\s?drive|memory\s+stick)(?:\s+(?:stick|drive|key|disk))?"
TO_USB = re.compile(r"\b(?:to|on|onto|into|in|on\s+to)\s+(?:the|a|my|your|that)\s+" + USB + r"\b", re.I)
ON_USB = re.compile(r"\b(?:on|in|inside|onto|plugged|connected|attached|any)\b.{0,20}\b" + USB + r"\b|\b" + USB +
                    r"\b.{0,20}\b(?:plugged|connected|attached|in\b)", re.I)
HAS_USB = re.compile(r"\b" + USB + r"\b", re.I)
EJECT = re.compile(r"\b(?:eject|unmount|un-mount|dismount|safely\s+remove)\b|\b(?:take|pull|unplug)\b.{0,25}\bout\b|"
                   r"\bunplug\b", re.I)
COPY = re.compile(r"\b(?:put|copy|save|store|write|transfer|move|send|back\s+(?:up|yourself\s+up)|backup|export|download)\b",
                  re.I)
LOOK = re.compile(r"\b(?:what|which|list|show|see|tell|read|look|how\s+much|is\s+there|are\s+there|any|find|plugged|"
                  r"detect|is\s+(?:the|a|my|your))\b", re.I)
NOTE = re.compile(r"\b(?:saying|that\s+says|which\s+says|reading|with\s+the\s+words?|the\s+words?)\b[\s:,]*(.+)$|:\s*(.+)$", re.I)
QUESTION = re.compile(r"^\W*(?:how|why|when|did|have|were|was|can\s+you\s+tell)\b", re.I)
# things people call Gene's files that aren't file names
ALIASES = [
    (r"\b(?:your\s+)?(?:memory\s+vault|obsidian(?:\s+vault)?|knowledge\s+graph|memory\s+graph)\b", "state/memory-vault"),
    (r"\b(?:your|all\s+your)\s+memor(?:y|ies)\b", "state/memory.json"),
    (r"\b(?:our|your)\s+(?:conversations?|chats?|transcripts?)\b", "state/conversations.jsonl"),
    (r"\byour\s+voice\b", "piper/voices"),
    (r"\byour\s+(?:own\s+)?(?:code|software|program)\b|\b(?:back|copy)\s+yourself\b|\ball\s+(?:of\s+)?your\s+files\b|"
     r"\bback\s+(?:yourself|you)\s+up\b", "."),
    (r"\byour\s+(?:upgrade|upgrades)\s+(?:history|log)\b", "state/upgrades.jsonl"),
    (r"\byour\s+brain(?:'s)?\s+(?:prompt|modelfile|personality)\b", "brain/gene.Modelfile"),
]


def _run(*cmd, timeout=30):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def drives():
    """Filesystems on USB disks: [{path, label, fstype, mount, disk}], biggest first."""
    out = _run("lsblk", "-J", "-b", "-o", "PATH,TYPE,TRAN,FSTYPE,LABEL,MOUNTPOINTS,SIZE")
    found = []
    for disk in json.loads(out.stdout or "{}").get("blockdevices", []):
        if disk.get("type") != "disk" or disk.get("tran") != "usb":
            continue
        for part in [disk] + disk.get("children", []):
            if part.get("fstype") and part["fstype"] not in ("swap", "crypto_LUKS", "LVM2_member"):
                mounts = [m for m in part.get("mountpoints") or [] if m]
                found.append({"path": part["path"], "label": part.get("label") or "", "fstype": part["fstype"],
                              "mount": mounts[0] if mounts else None, "disk": disk["path"], "size": int(part["size"] or 0)})
    return sorted(found, key=lambda d: -d["size"])


def mount(d):
    """Mount the drive if it isn't yet; its mount folder, or None."""
    if d["mount"]:
        return d["mount"]
    r = _run("udisksctl", "mount", "-b", d["path"], "--no-user-interaction")
    if r.returncode == 0 and (m := re.search(r" at (.+?)\.?$", r.stdout.strip())):
        return m.group(1)
    # udisks needs an active desktop session; Gene's service may not count as one
    name = re.sub(r"[^\w.-]+", "_", d["label"]) or os.path.basename(d["path"])
    where = os.path.join("/media", os.environ.get("USER") or os.path.basename(HOME), name)
    opts = f"uid={os.getuid()},gid={os.getgid()}" if d["fstype"] in ("vfat", "exfat", "ntfs", "ntfs3") else "defaults"
    if _run("sudo", "-n", "mkdir", "-p", where).returncode == 0 and \
            _run("sudo", "-n", "mount", "-o", opts, d["path"], where).returncode == 0:
        return where
    return None


def eject(d):
    os.sync()
    if d["mount"]:
        if _run("udisksctl", "unmount", "-b", d["path"], "--no-user-interaction").returncode != 0:
            if _run("sudo", "-n", "umount", d["path"]).returncode != 0:
                return False
            if d["mount"].startswith("/media/"):
                _run("sudo", "-n", "rmdir", d["mount"])     # the folder our sudo mount made (udisks removes its own)
    _run("udisksctl", "power-off", "-b", d["disk"], "--no-user-interaction")    # light off; fine if it fails
    return True


def wants(heard):
    """('eject',) / ('list',) / ('copy', path) / ('note', text) if `heard` is about a USB stick, else None."""
    if not HAS_USB.search(heard) or re.search(r"\b(?:pins?|gpio)\b", heard, re.I):
        return None
    if EJECT.search(heard):
        return ("eject",)
    if COPY.search(heard) and TO_USB.search(heard) and not QUESTION.search(heard):
        # "write hello world on the USB" is a note, not hello.wav: with "write" only a named file or folder is copied
        named = any(re.search(pat, heard, re.I) for pat, _ in ALIASES) or re.search(r"\b(?:files?|folders?|director(?:y|ies)|dot\s+\w+|modelfile)\b|\w\.\w", heard, re.I)
        if re.search(r"\bwrite\b", heard, re.I) and not named and (text := note_text(heard)):
            return ("note", text)
        if src := source(heard):
            return ("copy", src)
        if re.search(r"\bwrite\b", heard, re.I) and (text := note_text(heard)):
            return ("note", text)
        return ("copy", None)       # "put files on the USB" - which ones?
    if LOOK.search(heard) and ON_USB.search(heard) and not re.match(r"\W*(?:how|why)\b", heard, re.I):
        return ("list",)
    return None


def source(heard):
    """The file or folder of Gene's that `heard` names, or None."""
    for pat, rel in ALIASES:
        if re.search(pat, heard, re.I):
            return os.path.normpath(os.path.join(HERE, rel))
    words = TO_USB.split(heard)[0] + " " + (TO_USB.split(heard)[-1] if len(TO_USB.split(heard)) > 1 else "")
    words = HAS_USB.sub(" ", words)
    if re.search(r"\b(?:folder|directory)\b", words, re.I):
        m = re.search(r"\b(?:your|the|my|gene's)\s+((?:\w+\s+){0,3}?)(?:folder|directory)\b", words, re.I)
        if m and (f := gene_files._named(m.group(1), gene_files.folders())):
            return f
    # "your eyes file" = gene_eyes.py
    if f := gene_files._file_in(words, HERE) or gene_files._file_in(re.sub(r"\byour\b", "gene", words, flags=re.I), HERE):
        return f
    return None


def note_text(heard):
    """'write a note on the USB saying buy milk' -> 'buy milk'; 'write hello world on the USB' -> 'hello world'."""
    if m := NOTE.search(heard):
        text = m.group(1) or m.group(2)
    else:
        m = re.search(r"\bwrite\s+(?:down\s+)?(.+?)\s*" + TO_USB.pattern, heard, re.I)
        text = m.group(1) if m else ""
        text = re.sub(r"^(?:a\s+)?(?:note|message|file|text\s+file)\b", "", text, flags=re.I)
    text = TO_USB.sub("", text).strip(" ,.:\"'")
    if not text or re.fullmatch(r"(?:something|some\s+(?:files?|stuff|things?|text)|files?|it|that|this|a\s+file|to)", text, re.I):
        return None
    return text[0].upper() + text[1:] + ("" if text[-1] in ".!?" else ".")


def _free_name(folder, name):
    stem, ext = os.path.splitext(name)
    n, out = 1, name
    while os.path.lexists(os.path.join(folder, out)):
        n += 1
        out = f"{stem} {n}{ext}"
    return os.path.join(folder, out)


def _size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP]
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files
                     if not f.startswith(".") and os.path.isfile(os.path.join(root, f)))
    return total


def _name_of(path):
    if path == HERE:
        return "all my own files"
    if os.path.isdir(path):
        return "my " + gene_files.spoken(os.path.basename(path), True) + " folder"
    return gene_files.spoken(os.path.basename(path))


def _cap(s):
    return s[:1].upper() + s[1:]


def _where(d):
    return f"the USB stick called {d['label']}" if d["label"] else "the USB stick"


def act(req):
    """Do what `wants` found; the sentence Gene says."""
    found = drives()
    if not found:
        return "I can't find a USB stick. Plug one into one of my USB ports and ask me again."
    d = found[0]
    if req[0] == "eject":
        if not d["mount"]:
            eject(d)
            return f"{_cap(_where(d))} isn't in use, so it's safe to pull it out."
        return f"Done. It's safe to pull out {_where(d)} now." if eject(d) else \
            f"I couldn't eject {_where(d)}. Something may still be using it."
    where = mount(d)
    if not where:
        return f"I found {_where(d)}, but I couldn't open it. It might use a format I can't read."
    if req[0] == "list":
        free = shutil.disk_usage(where).free
        said, gw = gene_files.describe_folder(where), gene_files._where(where)
        said = said.replace(f"In {gw}", f"On {_where(d)}").replace(gw.capitalize(), _cap(_where(d)))
        return said + f" It has {gene_files._size(free)} free."
    if not os.access(where, os.W_OK):
        return f"{_cap(_where(d))} is read only, so I can't write to it."
    if req[0] == "note":
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M")     # no ':' - USB sticks are usually FAT
        dest = _free_name(where, f"Gene note {stamp}.txt")
        with open(dest, "w") as f:
            f.write(req[1] + "\n")
        os.sync()
        return f"I wrote your note on {_where(d)}, in a text file called Gene note with today's date and time."
    src = req[1]
    if not src:
        return ("Which of my files should I put on the USB stick? You could say my gene clock file, my state folder, "
                "my memories, or all my files.")
    real = os.path.realpath(src)
    if real != HOME and not real.startswith(HOME + os.sep):
        return "I only copy files from my own home folder onto a USB stick."
    if not os.path.exists(src):
        return f"I can't find {_name_of(src)}."
    size = _size_of(src)
    if size > shutil.disk_usage(where).free:
        return (f"To copy {_name_of(src)} I need {gene_files._size(size)}, but {_where(d)} only has "
                f"{gene_files._size(shutil.disk_usage(where).free)} free.")
    dest = _free_name(where, "Gene" if src == HERE else os.path.basename(src))
    # copyfile, not copy2: FAT sticks can't take Linux permissions and copy2 would fail on them
    if os.path.isdir(src):
        shutil.copytree(src, dest, symlinks=False, copy_function=shutil.copyfile,
                        ignore=lambda _, names: [n for n in names if n.startswith(".") or n in SKIP])
    else:
        shutil.copyfile(src, dest)
    os.sync()
    return f"I put {_name_of(src)} on {_where(d)}, {gene_files._size(size)}, as {gene_files.spoken(os.path.basename(dest), os.path.isdir(dest))}."
