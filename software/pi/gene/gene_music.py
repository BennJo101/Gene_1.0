"""Songs by voice from YouTube: "play Get Lucky by Daft Punk", "play some Spotify or YouTube songs", "play a song",
"play Blinding Lights on Spotify", "next song", "what song is this?", "stop the music" (asked by voice 2026-10-12).

Spotify can't be used here (it needs a Premium login and a Spotify Connect player), so a Spotify request is played from
YouTube too, and Gene says so. yt-dlp (in the venv, with deno for YouTube's JS) searches YouTube, picks the first result
under MAX_SECONDS (no hour-long mixes), downloads its audio into state/music/ (kept, so a replay is instant; the oldest
go past CACHE_MB) and ffmpeg -> pw-cat plays it in the background. The mic stays ON while music plays so "stop" can be
heard: gene_client only listens to music commands, volume commands, or anything with "Gene" in it until it ends. Gene's
own voice pauses the music (`hold`, like Mic.muted_until) and it carries on after he's done. A poke stops it too.
Test: ./venv/bin/python gene_music.py "play get lucky by daft punk"
"""
import os, random, re, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "state", "music")
CACHE_MB = 400
MAX_SECONDS = 600           # longer results are skipped (mixes, "1 hour" loops)
SR, CH = 48000, 2
CHUNK = SR * CH * 2 // 40   # 25 ms of s16 stereo
YTDLP = os.path.join(HERE, "venv", "bin", "yt-dlp")
ENV = dict(os.environ, PATH=os.path.join(HERE, "venv", "bin") + os.pathsep + os.environ.get("PATH", ""))   # deno
# no song named ("play some Spotify or YouTube songs", "play a song"): one of these - upbeat classics and the synth
# music Gene says he loves (Modelfile)
PICKS = ["Daft Punk Get Lucky", "The Weeknd Blinding Lights", "Kavinsky Nightcall", "a-ha Take On Me",
         "Daft Punk Harder Better Faster Stronger", "Mark Ronson Uptown Funk", "The Midnight Sunset",
         "Queen Don't Stop Me Now", "Pharrell Williams Happy", "Europe The Final Countdown", "Toto Africa",
         "Gorillaz Feel Good Inc", "Daft Punk Around the World", "Survivor Eye of the Tiger"]

SERVICE = r"(?:spotify|you\s*tube|youtube|youtube\s+music|soundcloud|apple\s+music)"
MUSIC = r"(?:songs?|music|tracks?|tunes?|albums?|playlists?|jams?|bangers?)"
# "play X", "put on X", "can you play X", "I want to hear X", "listen to X"
ASK = re.compile(r"\b(?:play|put\s+on|blast|queue\s+up|(?:want|wanna|like)\s+to\s+(?:hear|listen\s+to)|let(?:'s|\s+us)\s+"
                 r"(?:hear|listen\s+to)|can\s+(?:i|we)\s+(?:hear|listen\s+to))\s+(?:me\s+|us\s+)?(?P<rest>.+)", re.I)
NOT_MUSIC = re.compile(r"\b(?:pin|gpio|header|sound\s*(?:bite|byte|effect|clip)s?|vines?|memes?|game|chess|catch|"
                       r"tag|cards|dead|instrument|guitar|piano|violin)\b", re.I)
QUESTION = re.compile(r"^\W*(?:how|why|when|where|did|do|does|have|were|was|who|which|is|are)\b(?!.*\b(?:can|could)\s+you\s+play\b)", re.I)
STOP = re.compile(r"\b(?:stop|pause|halt|enough|shut\s+up|be\s+quiet|silence|kill\s+(?:it|the\s+music)|"
                  r"turn\s+(?:it|that|the\s+music|this|the\s+song)\s+off|turn\s+off\s+(?:the\s+)?(?:music|song)|"
                  r"no\s+more\s+music|cut\s+(?:it|the\s+music))\b", re.I)
NEXT = re.compile(r"\b(?:next|skip|another|different|change\s+the)\s+(?:one|song|track|tune)\b|\bskip\s+(?:it|this|that)\b|"
                  r"^\W*(?:gene\W+)?(?:next|skip)\W*$", re.I)
WHAT = re.compile(r"\bwhat(?:'s|\s+is|\s+was)\s+(?:this|that|the)\s+(?:song|track|tune|music)\b|"
                  r"\bwhat\s+(?:song|track|tune)\s+(?:is|was)\s+(?:this|that)\b|\bwho\s+(?:sings|sang|is\s+singing)\b", re.I)
RESUME = re.compile(r"\b(?:resume|unpause|continue|carry\s+on\s+with)\s+(?:the\s+)?(?:music|song|it|playing)\b|"
                    r"\bplay\s+(?:it|the\s+(?:song|music))\s+again\b", re.I)


def _clean(rest):
    """"Get Lucky by Daft Punk on Spotify please" -> "Get Lucky by Daft Punk"; "some Spotify or YouTube songs" -> ""."""
    q = re.sub(r"[.!?]+$", "", rest).strip()
    q = re.sub(r"\b(?:on|from|off|using|through|via|with|in)\s+(?:my\s+|your\s+|the\s+)?" + SERVICE + r"\b", " ", q, flags=re.I)
    q = re.sub(r"\b" + SERVICE + r"(?:\s+(?:or|and)\s+" + SERVICE + r")*\b", " ", q, flags=re.I)
    q = re.sub(r"\b(?:please|for\s+(?:me|us)|now|right\s+now|gene|bro|dude|man)\b", " ", q, flags=re.I)
    q = re.sub(r"^\W*(?:me\s+|us\s+)?(?:some|a|an|the|any|one|good|random|cool|nice|great|of|your|my|favou?rite|"
               r"or|and|new|\s)*", "", q, flags=re.I)
    q = re.sub(r"^" + MUSIC + r"\b\s*(?:called|named|by|from|of)?\s*", "", q, flags=re.I)    # "songs by Daft Punk"
    q = re.sub(r"(?:\s+(?:or|and))?\s+" + MUSIC + r"$", "", q, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip(" ,'\"")
    return "" if re.fullmatch(r"(?:" + MUSIC + r"|something|anything|stuff)?", q, re.I) else q


def wants(heard, playing=False):
    """What a music command asks for: ("play", query or "" for anything), ("stop",), ("next",), ("what",),
    ("resume",) - or None. Stop / next / what only count while a song is playing (or was just stopped)."""
    if playing or player.recent():
        if WHAT.search(heard):
            return ("what",)
        if NEXT.search(heard):
            return ("next",)
        if RESUME.search(heard) and player.paused:
            return ("resume",)
        if playing and STOP.search(heard) and not re.search(r"\b(?:timer|reminder|alarm|listening)s?\b", heard, re.I):
            return ("stop",)
    m = ASK.search(heard)
    if not m or NOT_MUSIC.search(heard) or (QUESTION.search(heard) and "?" in heard):
        return None
    rest = m.group("rest")
    # a song word, a music service, "X by Y", or "put on ..." / "listen to ..." (which only go with music)
    if not (re.search(r"\b" + MUSIC + r"\b|\b" + SERVICE + r"\b|\S\s+by\s+\S", rest, re.I)
            or not re.match(r"play\b", m.group(0), re.I)):
        return None
    if re.match(r"\s*(?:it|that|this)\s+again\b", rest, re.I):
        return None
    return ("play", _clean(rest))


def spotify(heard):
    return bool(re.search(r"\bspotify\b", heard, re.I))


def search(query, skip=()):
    """[(id, seconds, title)] of YouTube results for `query` under MAX_SECONDS, not in `skip`."""
    out = subprocess.run([YTDLP, "--flat-playlist", "--no-warnings", "--print", "%(id)s\t%(duration)s\t%(title)s",
                          f"ytsearch8:{query}"], capture_output=True, text=True, timeout=30, env=ENV)
    hits = []
    for line in out.stdout.splitlines():
        vid, secs, title = (line.split("\t", 2) + ["", ""])[:3]
        try:
            secs = float(secs)
        except ValueError:
            continue            # live streams have no duration
        if 30 < secs <= MAX_SECONDS and vid not in skip:
            hits.append((vid, secs, title))
    return hits


def download(vid):
    """Path of the cached audio for YouTube id `vid`."""
    os.makedirs(CACHE, exist_ok=True)
    for f in os.listdir(CACHE):
        if f.startswith(vid + ".") and not f.endswith(".part"):
            os.utime(os.path.join(CACHE, f))
            return os.path.join(CACHE, f)
    out = subprocess.run([YTDLP, "--no-playlist", "--no-warnings", "-f", "bestaudio/best", "-o",
                          os.path.join(CACHE, "%(id)s.%(ext)s"), "--print", "after_move:filepath", "--no-simulate",
                          f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=120, env=ENV)
    path = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not os.path.exists(path):
        raise RuntimeError(f"yt-dlp failed: {out.stderr.strip()[-200:]}")
    _prune()
    return path


def _prune():
    files = sorted((os.path.join(CACHE, f) for f in os.listdir(CACHE) if not f.endswith(".json")), key=os.path.getmtime)
    total = sum(os.path.getsize(f) for f in files)
    while files and total > CACHE_MB * 1e6:
        total -= os.path.getsize(files[0]); os.unlink(files.pop(0))


def spoken_title(title):
    """"Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)" -> "Never Gonna Give You Up by Rick Astley"."""
    t = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", title)
    t = re.sub(r"\s*\b(?:official\s+(?:music\s+)?(?:video|audio|lyric\s+video)|lyrics?|hd|hq|4k|remaster(?:ed)?)\b", "", t, flags=re.I)
    t = re.sub(r"\s+(?:ft|feat)\.?\s.*$", "", t, flags=re.I).strip(" -|")
    if m := re.match(r"(.+?)\s+[-–—|]\s+(.+)", t):
        return f"{m.group(2).strip()} by {m.group(1).strip()}"
    return t or title


class Player:
    """One song at a time: ffmpeg decodes, a thread feeds pw-cat 25 ms at a time, so it can pause (Gene talking)."""
    def __init__(self):
        self.lock = threading.Lock()
        self.procs, self.title, self.query, self.played = None, None, "", []
        self.quiet_until = 0.0      # paused while Gene talks (Mouth sets it, like Mic.muted_until)
        self.paused = False         # stopped by "stop the music" ("resume the music" starts it again)
        self.stopped_at = 0.0
        self.gen = 0

    def playing(self):
        return self.procs is not None

    def recent(self):
        return self.playing() or time.time() - self.stopped_at < 120

    def hold(self, seconds):
        """Pauses the music for `seconds` (Gene is about to speak)."""
        self.quiet_until = max(self.quiet_until, time.time() + seconds)

    def play(self, path, title):
        self.stop()
        import gene_volume
        try:
            gene_volume.use(None)       # his regular level, not the last loud/meek sentence
        except Exception:
            pass
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", str(CH), "-ar", str(SR), "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out = subprocess.Popen(["pw-cat", "--playback", "--raw", "--format", "s16", "--rate", str(SR), "--channels",
                                str(CH), "--latency", "100ms", "-"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        with self.lock:
            self.gen += 1
            self.procs, self.title, self.paused = (dec, out), title, False
            gen = self.gen
        threading.Thread(target=self._feed, args=(dec, out, gen), daemon=True).start()

    def _feed(self, dec, out, gen):
        was_quiet = False
        try:
            while True:
                if time.time() < self.quiet_until:
                    was_quiet = True
                    time.sleep(0.05)
                    if self.gen != gen:
                        return
                    continue
                if was_quiet:
                    was_quiet = False
                    try:
                        import gene_volume; gene_volume.use(None)
                    except Exception:
                        pass
                b = dec.stdout.read(CHUNK)
                if not b or self.gen != gen:
                    break
                out.stdin.write(b)
            out.stdin.close(); out.wait(timeout=10)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        with self.lock:
            if self.gen == gen and self.procs:
                self._end()

    def _end(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
        self.procs, self.stopped_at = None, time.time()

    def stop(self):
        """Stops the song; True if one was playing."""
        with self.lock:
            if not self.procs:
                return False
            self.gen += 1
            self._end()
            return True


player = Player()


def find(query):
    """Finds and downloads a song for `query` ("" = one of PICKS): (path, spoken title), or None if nothing found.
    Played with player.play(path, title) - after Gene has said what it is."""
    q = query or random.choice(PICKS)
    hits = search(q)
    if not hits and query:
        hits = search(q + " song")
    if not hits:
        return None
    vid, secs, title = hits[0]
    path = download(vid)
    player.query, player.played = query, [vid]
    return path, spoken_title(title)


def find_next():
    """Another song: a different result of the same search, or another pick. (path, spoken title) or None."""
    if not player.query:
        return find("")
    hits = search(player.query + " songs", skip=player.played) or search(player.query, skip=player.played)
    if not hits:
        return None
    vid, secs, title = hits[0]
    path = download(vid)
    player.played.append(vid)
    return path, spoken_title(title)


if __name__ == "__main__":
    heard = " ".join(sys.argv[1:]) or "play some Spotify or YouTube songs"
    print("wants:", wants(heard))
    w = wants(heard)
    if w and w[0] == "play":
        t0 = time.time()
        path, title = find(w[1])
        player.play(path, title)
        print("playing:", title, f"({time.time() - t0:.1f} s to start)")
        time.sleep(8); player.stop(); print("stopped")
