"""Sound bites by name: "play the Wilhelm scream sound effect", "play the 'I am your father' sound bite",
"play the bruh sound", "play the look at all those chickens vine", "play a random vine", "play that sound again".

The clip is found on myinstants.com (a big library of meme / movie / TV sound buttons, searchable without a key),
downloaded once into state/sounds/ and played through the default speaker via Gene's mouth queue, so the mic stays
muted while it plays. Clips are cut to MAX_SECONDS so a long one can't take over.
"""
import html, json, os, re, subprocess, time, tempfile, urllib.error, urllib.parse, urllib.request

SITE = "https://www.myinstants.com"
UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "state", "sounds")
LAST = os.path.join(CACHE, "last.json")
MAX_SECONDS = 15
SR = 48000

KIND = r"(?:vines?|sound\s*bites?|sound\s*bytes?|soundbytes?|sound\s*clips?|sound\s*effects?|sfx|sounds?|clips?|bites?|soundbites?|memes?|noises?)"
# "play the X sound effect" / "play a sound bite of X" / "play me the X meme" / "can you play X sound"
ASK = re.compile(r"\bplay\s+(?:me\s+|us\s+)?(?P<rest>.+)", re.I)
# other ways of asking, which need an article right after: "give me a reference soundbite", "do the bruh sound",
# "make a funny noise", "let me hear the Wilhelm scream sound effect", "can I hear a vine"
ASK_OTHER = re.compile(r"(?:\bgive\s+(?:me|us)|\bdo|\bmake|\blet\s+(?:me|us)\s+hear|\blet's\s+hear|\b(?:can|could|may)\s+(?:i|we)\s+hear)"
                       r"\s+(?P<rest>(?:the|a|an|some|that|this|another|one\s+more|your)\b.+)", re.I)
QUESTION = re.compile(r"\?\s*$")
OPENER = re.compile(r"^\W*(?:(?:gene|okay|ok|so|now|just|please|and|then|hey)\W+)*(?:can|could|would|will)\s+you\b", re.I)
# "do the actual sound bite" = the one just asked for
FILLER = re.compile(r"\b(?:actual|real|proper|just|same|right|whole|full)\s+", re.I)
# "play another reference" / "another one" right after a clip: a different clip of the same kind
ANOTHER = re.compile(r"^(?:another|one\s+more|a\s+different|a\s+new)\b\s*(?P<name>.*)$", re.I)
RECENT = 300
AGAIN = re.compile(r"\b(?:play|do)\s+(?:that|the|it)\s+(?:" + KIND + r"\s+)?again\b|\b(?:play|do)\s+(?:that|it)\s+again\b", re.I)
# "play the Wilhelm scream sound effect" -> "Wilhelm scream"; "play a sound bite of Darth Vader" -> "Darth Vader"
OF = re.compile(r"^(?:the|a|an|some|that|this)?\s*" + KIND + r"\s+(?:of|from|for|called|named|where|when|that\s+goes|saying)\s+(?P<name>.+)", re.I)
SUFFIX = re.compile(r"^(?:the|a|an|some|that|this)?\s*(?P<name>.+?)\s+" + KIND + r"\b", re.I)
NOT_SOUND = re.compile(r"\b(?:pin|gpio|header|song\s+on|game|chess|music)\b", re.I)
STOPWORDS = set("a an the of from for me us you please sound sounds bite bites clip clips effect effects meme memes noise "
                "vine vines".split())
# no name given: "play a vine", "play a random sound bite", "play me some vines", "play a sound"
RANDOM = re.compile(r"^(?:the|a|an|some|any|one|another|other)?\s*(?:random|funny|cool|good|famous|popular|classic|new)?\s*"
                    r"(?:(?P<vine>vines?)\s*)?(?:" + KIND + r")?\s*(?:please|for\s+me|for\s+us|now)?$", re.I)
RANDOM_VINE, RANDOM_ANY = "random vine", "random"


def _recent():
    """What was asked for last time ("" if unknown), if a clip played in the last RECENT seconds, else None."""
    try:
        if time.time() - os.path.getmtime(LAST) < RECENT:
            return json.load(open(LAST)).get("asked", "")
    except (OSError, ValueError):
        pass
    return None


def _clean(name):
    name = re.sub(r"^[\"'\s]+|[\"'\s,]+$|\s+(?:please|for\s+me|now)$", "", name, flags=re.I).strip()
    return re.sub(r"^(?:the|a|an)\s+", "", name, flags=re.I)


def wants(heard):
    """The clip name if `heard` asks for a sound bite, "" for "play that again", else None.
    "another X" names ask for a different clip than the last one."""
    if NOT_SOUND.search(heard):
        return None
    if AGAIN.search(heard) and os.path.exists(LAST) and re.search(KIND + r"|\bthat\b|\bit\b", heard, re.I):
        return ""
    m = ASK.search(heard)
    if not m:
        m = ASK_OTHER.search(heard)
        # "do the sound effects come from the internet?" is a question, "can you do the bruh sound?" is a request
        if m and QUESTION.search(heard) and not OPENER.search(heard):
            return None
    if not m:
        return None
    rest = FILLER.sub("", re.sub(r"[.!?]+$", "", m.group("rest"))).strip()
    recent = _recent()
    if a := ANOTHER.match(rest):
        name = _clean(re.sub(r"(?:\s+|^)" + KIND + r"\b", " ", a.group("name"), flags=re.I))
        if re.fullmatch(r"(?:one)?", a.group("name").strip(), re.I):   # just "another (one)"
            if recent:
                return recent if recent in (RANDOM_VINE, RANDOM_ANY) else "another " + recent
        elif name.lower() not in ("", "one", "random", "funny") and (
                re.search(KIND, rest, re.I) or recent is not None and not re.search(r"\b(?:song|tune|round|time)\b", name, re.I)):
            return "another " + name
    if not re.search(KIND, rest, re.I):
        return None
    if r := RANDOM.match(rest):
        # "do the sound bite" / "do the sound" = the one just played (or asked for)
        if re.match(r"(?:the|that|this)\b", rest, re.I) and not r.group("vine") and os.path.exists(LAST):
            return ""
        return RANDOM_VINE if r.group("vine") or re.search(r"\bvines?\b", rest, re.I) else RANDOM_ANY
    for pat in (OF, SUFFIX):
        if n := pat.match(rest):
            name = _clean(n.group("name"))
            if re.search(r"\w", name) and name.lower() not in ("a", "that", "this", "some", "funny", "random", "cool"):
                return name
    return None


# "where did you get that from?", "where do you get the vines from?", "where did you upgrade yourself to do the vines?"
SOURCE_Q = re.compile(r"\bwhere\b.*\b(?:get|got|find|found|from|come|comes|upgrade|learn|download)", re.I)
ABOUT_SOUND = re.compile(KIND + r"|\b(?:that|it|those|these)\b", re.I)


def source_answer(heard, recent):
    """What Gene says to "where did you get that sound from?", or None. `recent`: a clip was just played,
    so a bare "where did you get that from?" is about it."""
    if not SOURCE_Q.search(heard) or NOT_SOUND.search(heard):
        return None
    if not (re.search(KIND, heard, re.I) or (recent and ABOUT_SOUND.search(heard))):
        return None
    last = json.load(open(LAST))["title"] if os.path.exists(LAST) else None
    said = "I get my sound bites and Vines from myinstants dot com, a big website of meme and movie sound buttons."
    if last and recent:
        said = f"That was {last}. " + said
    return said + " I download each one once and keep it, so it plays faster next time."


def _get(url, timeout=10):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()


def _words(s):
    return {w for w in re.findall(r"[a-z0-9']+", s.lower().replace("'", "")) if w not in STOPWORDS}


def _search(name):
    try:
        page = _get(f"{SITE}/en/search/?name={urllib.parse.quote_plus(name)}").decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:       # the site's answer to "no results"
            return []
        raise
    hits = re.findall(r"play\('(/media/sounds/[^']+)'.*?class=\"instant-link[^\"]*\">([^<]+)<", page, re.S)
    return [(html.unescape(t).strip(), SITE + u) for u, t in hits]


def queries(name):
    """What to search for, most specific first: "Darth Vader saying I am your father" -> the whole thing,
    "I am your father", "Darth Vader"; then the content words alone."""
    out = [name]
    parts = re.split(r"\s+(?:saying|says|said|goes|going|where|when|who|that|from|in|with)\s+", name, flags=re.I)
    if len(parts) > 1:
        out += [parts[-1], parts[0]]
    out.append(" ".join(w for w in re.findall(r"[\w']+", name) if w.lower() not in STOPWORDS))
    return [q for i, q in enumerate(out) if q.strip() and q.lower() not in (x.lower() for x in out[:i])]


def random_hit(vine):
    """A random (title, mp3 url): one of the vines on myinstants, or one of today's popular sounds."""
    import random
    if vine:
        hits = _search("vine")
    else:
        page = _get(f"{SITE}/en/index/us/").decode("utf-8", "replace")
        hits = [(html.unescape(t).strip(), SITE + u) for u, t in
                re.findall(r"play\('(/media/sounds/[^']+)'.*?class=\"instant-link[^\"]*\">([^<]+)<", page, re.S)]
    last = json.load(open(LAST))["title"] if os.path.exists(LAST) else None
    return random.choice([h for h in hits if h[0] != last] or hits) if hits else None


def search(name):
    """[(title, mp3 url)] from myinstants, best title match first."""
    want = _words(name)
    for q in queries(name):
        if found := _search(q):
            # the site orders by popularity; prefer titles that share the most words with what was asked
            return sorted(found, key=lambda h: -len(want & _words(h[0])))
    return []


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "sound"


def fetch(name):
    """(title, path of the cached clip), or (None, None) if nothing was found."""
    os.makedirs(CACHE, exist_ok=True)
    index_path = os.path.join(CACHE, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else {}
    if name in (RANDOM_VINE, RANDOM_ANY):
        hit = random_hit(name == RANDOM_VINE)
        if not hit:
            return None, None
        key, (title, url) = None, hit
    elif name.lower().startswith("another "):
        import random
        last = json.load(open(LAST))["title"] if os.path.exists(LAST) else None
        hits = search(name[8:])[:8]
        hits = [h for h in hits if h[0] != last] or hits
        if not hits:
            return None, None
        key, (title, url) = None, random.choice(hits)
    else:
        key = " ".join(sorted(_words(name))) or name.lower()
        if key in index and os.path.exists(index[key]["path"]):
            return index[key]["title"], index[key]["path"]
        hits = search(name)
        if not hits:
            return None, None
        title, url = hits[0]
    path = os.path.join(CACHE, _slug(title) + os.path.splitext(urllib.parse.urlparse(url).path)[1])
    if not os.path.exists(path):
        data = _get(url, timeout=20)
        with open(path, "wb") as f:
            f.write(data)
    if key:
        index[key] = {"title": title, "path": path, "url": url}
        json.dump(index, open(index_path, "w"), indent=1)
    return title, path


def to_wav(path):
    """Decodes a clip to a temporary wav (caller deletes it); returns (wav path, seconds)."""
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-t", str(MAX_SECONDS), "-ac", "2", "-ar", str(SR),
                    "-af", f"afade=t=out:st={MAX_SECONDS - 0.5}:d=0.5", out], check=True, timeout=30)
    import soundfile as sf
    return out, sf.info(out).duration


def get(name):
    """(title, wav path, seconds) for a requested clip ("" = the last one played), or None if not found."""
    if name == "":
        last = json.load(open(LAST))
        title, path, name = last["title"], last["path"], last.get("asked", "")
    else:
        title, path = fetch(name)
        if not path:
            return None
    asked = re.sub(r"^another\s+", "", name, flags=re.I)
    json.dump({"title": title, "path": path, "asked": asked}, open(LAST, "w"))
    wav, secs = to_wav(path)
    return title, wav, secs
