"""Gene's web lookups: DuckDuckGo's HTML results page, scraped with the standard library (no API key).

search(query) returns a few short "title: snippet" lines, which gene_client passes to the model as a
last line on the user message, like the camera line: "(web: ...)".
"""
import html, json, re, threading, urllib.parse, urllib.request

SEARCH_URL = "https://html.duckduckgo.com/html/"
WIKI_UA = "GeneRobotHead/1.0 (talking robot head on a Raspberry Pi; Python urllib)"   # Wikipedia's UA policy
UA = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MAX_RESULTS = 3
MAX_CHARS = 1000            # keep the 3B model's prompt short
WIKI_CHARS = 450            # of which Wikipedia's matching sentences

# "search the web for X", "look up X", "google X", "search online for X", "find out about X online"
ASK = re.compile(r"\b(?:search|look\s+up|google|check|find(?:\s+out)?)\b\s*(?:(?:on\s+)?(?:the\s+)?"
                 r"(?:web|internet|online|google)\s*)?(?:for|about|on|up)?\s+(.+)", re.I)
TOPICAL = r"\b(latest|news|headlines|weather|forecast|score|stock\s+price|lyrics?)\b"   # facts the 3B model can't know
WEB_WORDS = re.compile(r"\b(web|internet|online|google|look\s+up|search|find\s+(?:out|the|me|a|an|who|what|where|when|which)"
                       r")\b|" + TOPICAL, re.I)


# "who is Hunter Hancock?" / "what is Minecraft?" - people and named things Gene's 3B model can't know reliably
WHO = re.compile(r"\b(?:who|what)\s+(?:is|was|are|were)\s+(?!(?:you|i|we|he|she|they|it|this|that|your|my|up|going)\b)"
                 r"(.+)", re.I)
# a bare "check the web" / "look it up" / "find out" / "use the actual web and web scrape" means: search the last topic
FOLLOW_WORD = re.compile(r"\b(web|internet|online|google|googl\w*|search\w*|scrap\w*|look\s+(?:it|that|them|those)\s+up|"
                         r"find\s+out)\b", re.I)
FILLER = set("""a actual again ahead all and but can check could do find for gene go google googling hey internet it just
    look me now ok okay on online out please properly real really scrape scraping search searching so tell that the
    them then this those to up use web well will would yeah yes you your""".split())
# words that never make a search topic ("what are the first couple lyrics?" -> first couple lyrics)
STOP = FILLER | set("""about am an any are as at be been being by did does doing don't from had has have he her him his how
    i i'm if in into is isn't it's its know let's like many may might more much my no not of or our say she should
    some sure than that's their there they thing think was we were what what's when where which who who's why with
    wrong yet""".split())
# "and just tell me" / "for me" trailing an ask: "look up the lyrics and just tell me"
ASK_TAIL = re.compile(r"\s*\b(?:and|then)?\s*(?:just\s+)?(?:tell|read|say|give)\b.*$|\s+for\s+me\b.*$", re.I)


BACK_REF = re.compile(r"\bagain\b|\byou\s+(?:just\s+)?(?:said|told|mentioned)\b|\bearlier\b", re.I)
# a search engine's bot check, served instead of results: never read out as the answer
BLOCKED = re.compile(r"unusual traffic|captcha|are you a (?:robot|human)|verify you are|bot check|automated (?:queries|requests)|"
                     r"enable javascript|access denied", re.I)


def topic_words(text):
    """The content words of a line: "Tell me what the theme song for Steven Universe is" -> theme song Steven Universe."""
    return [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9']*", text) if w.lower() not in STOP]


def has_name(text):
    """True if the line names something: STT capitalises names, so a capital past a sentence's first word."""
    return any(re.search(r"\s[A-Z0-9]", " " + sent.strip()[1:]) for sent in re.split(r"[.!?,]+", text))


class Topic:
    """What the conversation is about, so "look it up" / "do it" / "look up the lyrics" search something sensible.
    Keeps the last line that named something ("...theme song for Steven Universe") plus the questions since."""

    def __init__(self):
        self.base = []          # content words of the last line that named something
        self.asks = []          # content words of recent questions, newest last

    def hear(self, heard):
        if has_name(heard):
            self.base, self.asks = topic_words(heard), []
        elif re.search(r"\?|^\s*(?:what|who|how|when|where|why|which|tell|look|find)\b", heard, re.I):
            self.asks = (self.asks + [topic_words(heard)])[-3:]

    def query(self, detail=""):
        """Search query for the current topic, optionally with an extra detail ("the lyrics"); None if no topic."""
        words = []
        for w in self.base + [w for a in self.asks for w in a] + topic_words(detail):
            if w.lower() not in (x.lower() for x in words):
                words.append(w)
        return " ".join(words[:10]) or None


def is_follow_up(heard):
    """True for a sentence like "Check the web." that asks for a lookup but names no topic."""
    for sent in re.split(r"[.!?]+", heard):
        words = re.findall(r"[a-z']+", sent.lower())
        if words and FOLLOW_WORD.search(sent) and all(w in FILLER for w in words):
            return True
    return False


def wants_search(heard, last_topic=None):
    """The search query if Gene was asked to look something up, else None.
    last_topic is what was being talked about (a Topic or a string), for follow-ups like "check the web"."""
    topic = last_topic if isinstance(last_topic, Topic) else None
    if is_follow_up(heard):
        return topic.query() if topic else last_topic
    m = WHO.search(heard)
    if m and BACK_REF.search(heard):        # "what was the IP address again?" asks about what was just said
        m = None
    if m and not WEB_WORDS.search(heard):
        q = m.group(1).strip(" ,.?!")
        named = re.search(r"\b[A-Z0-9]", q)                 # STT capitalises names: "what is Minecraft", not "what is love"
        if len(re.sub(r"(?i)\b(the|a|an)\b", "", q).strip()) >= 3 and (named or m.group(0).lower().startswith("who")):
            return q
    if not WEB_WORDS.search(heard):
        return None
    m = ASK.search(heard)
    if m:
        q = re.sub(r"\b(?:on|in|from)\s+(?:the\s+)?(?:web|internet|online|google)\b|\bonline\b|\bplease\b",
                   "", m.group(1), flags=re.I)
        q = ASK_TAIL.sub("", q).strip(" ,.?!")
        if topic and not has_name(" x " + q):       # "look up the lyrics" / "find the original theme song": of our topic
            return topic.query(q)
        if len(q) >= 3:
            return q
    if re.search(TOPICAL, heard, re.I):
        if topic and not has_name(heard) and re.search(r"\blyric", heard, re.I):   # "what are the first couple lyrics?"
            return topic.query(heard)
        return " ".join(topic_words(heard)) or None
    return None


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def _get(url, data=None, headers=None, timeout=6):
    req = urllib.request.Request(url, data, {"User-Agent": UA, "Accept-Language": "en-US,en", **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _duckduckgo(query, timeout):
    """(title, snippet) pairs; empty when DuckDuckGo serves its bot challenge instead of results."""
    page = _get(SEARCH_URL, urllib.parse.urlencode({"q": query}).encode(), timeout=timeout)
    out = []
    for block in re.split(r'class="result results_links', page)[1:]:
        if "result--ad" in block[:200]:
            continue
        title = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.S)
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        if snip:
            out.append((_text(title.group(1)) if title else "", _text(snip.group(1)), ""))
    return out


def _brave(query, timeout):
    page = _get("https://search.brave.com/search?" + urllib.parse.urlencode({"q": query}), timeout=timeout)
    out = []
    for block in re.split(r'<div class="snippet svelte', page)[1:]:
        if 'data-type="web"' not in block[:200]:
            continue
        url = re.search(r'<a href="(https?://[^"]+)"', block)
        title = re.search(r'class="title[^"]*"[^>]*>(.*?)</div>', block, re.S)
        snip = re.search(r'class="content[^"]*"[^>]*>(.*?)</div>', block, re.S)
        if snip and _text(snip.group(1)):
            out.append((_text(title.group(1)) if title else "", re.sub(r"^\w+ \d+, \d{4} - |^\d+ \w+ ago - ", "",
                        _text(snip.group(1))), url.group(1) if url else ""))
    return out


def _bing(query, timeout):
    page = _get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "setlang": "en-US", "cc": "US"}),
                timeout=timeout)
    out = []
    for block in re.split(r'<li class="b_algo"', page)[1:]:
        title = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
        snip = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        if snip:
            out.append((_text(title.group(1)) if title else "", _text(snip.group(1)).rstrip(" …"), ""))
    return out


def _lyrics(url, timeout, lines=4):
    """The opening lines of a song from its Genius page: "We are the Crystal Gems! / We always save the day ..."."""
    page = _get(url, timeout=timeout)
    i = page.find('data-lyrics-container="true"')
    if i < 0:
        return ""
    body = re.sub(r"<br\s*/?>", "\n", page[page.find(">", i) + 1:i + 8000])
    body = re.sub(r"<div[^>]*data-exclude-from-selection[^>]*>.*?</div>\s*</div>", "", body, flags=re.S)
    body = re.split(r"You might also like|\d*Embed", html.unescape(re.sub(r"<[^>]+>", "", body)))[0]
    body = re.sub(r"^[^\n]{0,600}?Read More\s*", "", body)        # an "about this song" blurb before the lyrics
    got = [l.strip() for l in body.split("\n")]
    got = [l for l in got if l and not re.fullmatch(r"[\[(].*[\])]|.*\bContributors?\b.*", l)]
    return " / ".join(got[:lines])


def _stem(w):
    return w.lower()[:5]


def _wikipedia(query, timeout, max_chars=WIKI_CHARS):
    """Read the best-matching Wikipedia articles and keep the sentences that answer the query - the search engines'
    snippets are only a line long, this finds facts deeper in the page (e.g. which song is a show's title theme)."""
    api = "https://en.wikipedia.org/w/api.php?"
    hits = json.loads(_get(api + urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": query,
                                                          "srlimit": 2, "format": "json"}), None, {"User-Agent": WIKI_UA},
                           timeout))
    asked = {_stem(w) for w in topic_words(query)}
    titles = [h["title"] for h in hits["query"]["search"]                  # skip off-topic articles ("Black Sabbath")
              if asked & {_stem(w) for w in re.findall(r"\w+", h["title"])}]
    if not titles:
        return ""
    pages = json.loads(_get(api + urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1,
                                                          "titles": "|".join(titles), "format": "json"}), None,
                            {"User-Agent": WIKI_UA}, timeout))
    texts = {p["title"]: p.get("extract", "") for p in pages["query"]["pages"].values()}
    in_title = {_stem(w) for t in titles for w in re.findall(r"\w+", t)}
    wanted = {_stem(w) for w in topic_words(query)} - in_title   # "theme song" matters, "Steven Universe" is every line
    scored = []
    for rank, title in enumerate(titles):
        text = re.sub(r"\n=+ [^=]+ =+\n", "\n", texts.get(title, ""))
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 25 < len(s.strip()) < 400]
        if sents and rank == 0:
            scored.append((99, 0, title + ": " + sents[0]))           # the lead sentence says what the thing is
        for i, s in enumerate(sents[1:], 1):
            got = {_stem(w) for w in re.findall(r"[A-Za-z0-9']+", s)} & wanted
            score = len(got) + 0.8 * bool(re.search(r'"[^"]{3,60}"', s)) * bool(got)   # a quoted name: a title
            if got:
                scored.append((score - 0.1 * rank, -i, s))
    out, n = [], 0
    for score, _, s in sorted(scored, reverse=True):
        if n + len(s) > max_chars:
            continue
        out.append(s); n += len(s) + 1
    return " ".join(out)


def search(query, timeout=6):
    """Top results as one short string, or "" if nothing came back. Tries DuckDuckGo, then Bing (DuckDuckGo starts
    serving a bot check after a burst of searches), and adds what Wikipedia's articles say about it."""
    wiki = {}
    def read_wikipedia():
        try:
            wiki["text"] = _wikipedia(query, timeout)
        except Exception as e:
            print(f"wikipedia lookup failed: {e}", flush=True)
    reader = threading.Thread(target=read_wikipedia, daemon=True)
    reader.start()                                                     # in parallel with the search engines
    results = []
    for engine in (_duckduckgo, _brave, _bing):
        try:
            results = [r for r in engine(query, timeout) if not BLOCKED.search(" ".join(r[:2]))][:MAX_RESULTS]
        except Exception as e:
            print(f"{engine.__name__[1:]} search failed: {e}", flush=True)
        if results:
            break
    lyrics = ""
    if re.search(r"\b(lyric|words to|sing)", query, re.I):
        for t, s, url in results:
            if re.match(r"https://genius\.com/.+-lyrics$", url):
                try:
                    lines = _lyrics(url, timeout)
                    lyrics = lines and f"Opening lyrics of {re.split(r' Lyrics| [|]', t)[0]}: {lines}"
                except Exception as e:
                    print(f"lyrics fetch failed: {e}", flush=True)
                break
    out = [(t + ": " if t else "") + s for t, s, _ in results]
    out.sort(key=len, reverse=True)      # the most informative snippet first, so the 3B model leans on it
    found = " | ".join(([lyrics] if lyrics else []) + out)[:MAX_CHARS - WIKI_CHARS]
    reader.join(timeout)
    wiki = wiki.get("text", "")
    return " | ".join(x for x in (found, wiki and "Wikipedia: " + wiki) if x)


if __name__ == "__main__":
    import sys
    print(search(" ".join(sys.argv[1:]) or "Raspberry Pi 5"))
