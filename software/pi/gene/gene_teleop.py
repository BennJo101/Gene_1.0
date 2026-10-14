"""Gene's web control panel (teleoperation), run by gene-teleop.service: http://<this Pi>:8080 (password login).

  - see out of his eyes: both eye cameras live (the camera service goes to ~8 frames a second while the panel watches)
  - his expression: a screenshot of the eye screens (grim), the face he is showing, and buttons to set a face / close,
    open or wink an eye
  - make him say things: the text goes to state/teleop_say/, gene_client says it word for word (with a face and loud /
    meek voice if picked) and keeps it in the chat history
  - his mouth: gene_client writes state/mouth.json (words + visemes + start time) for each clip he plays; the panel
    animates a jaw from it with the head sim's viseme table. The jaw slider writes state/jaw.json {"deg", "t"} - the
    target for the jaw servos once they are fitted (nothing drives them yet)
  - what he hears and says: his journal, live
  - hear through his mic: /mic.pcm streams the default PipeWire source (the mic Gene listens with) as raw 16 kHz mono
    s16le from its own pw-cat recorder, so Gene's own recorder is untouched; a hard mute ("mute yourself") = silence
  - upgrades: progress, every step Claude Code takes (state/upgrade_live.jsonl, written by upgrade.py), a box to type
    to Claude while it works (state/upgrade_inbox/), Stop (cancels, keeps nothing), and starting one by typing
    (upgrade.py web "...")

SYSTEM python (/usr/bin/python3): Pillow encodes the camera frames as JPEG (the venv has no Pillow). Stdlib server only.
The password is in ~/.config/gene/teleop.env (TELEOP_PASSWORD=...), made on first start; never put it in git.
Run by hand:  /usr/bin/python3 gene_teleop.py   (GENE_TELEOP_PORT to change the port)
"""
import hashlib, hmac, http.server, io, json, os, queue, secrets, socketserver, subprocess, sys, threading, time
import urllib.parse
import numpy as np
from PIL import Image
import gene_eyes

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
PAGE = os.path.join(HERE, "teleop", "index.html")
PORT = int(os.environ.get("GENE_TELEOP_PORT", "8080"))
ENV = os.environ.get("GENE_TELEOP_ENV") or os.path.expanduser("~/.config/gene/teleop.env")
FRAMES = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "gene-camera")
CAMERAS = {"left": 1, "right": 0}           # Gene's side -> camera number (gene_cameras.SIDES)
MOUTH = os.path.join(STATE, "mouth.json")
JAW = os.path.join(STATE, "jaw.json")
SAY = os.path.join(STATE, "teleop_say")
VOLUME = os.path.join(STATE, "volume.json")
LIVE = os.path.join(STATE, "upgrade_live.jsonl")
INBOX = os.path.join(STATE, "upgrade_inbox")
STOP = os.path.join(STATE, "upgrade_stop")
HISTORY = os.path.join(STATE, "upgrades.jsonl")
JAW_MAX = 30.0              # deg: the jaw's speaking range (CLAUDE.md, hardware still to come)
COOKIE = "gene_teleop"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def password():
    try:
        for line in open(ENV):
            if line.startswith("TELEOP_PASSWORD="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    pw = secrets.token_urlsafe(9)
    os.makedirs(os.path.dirname(ENV), exist_ok=True)
    with open(os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write(f"TELEOP_PASSWORD={pw}\n")
    log("made a new panel password in", ENV)
    return pw


PASSWORD = password()
TOKEN = hmac.new(PASSWORD.encode(), b"gene-teleop-session", hashlib.sha256).hexdigest()


def read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, path)


def drop(folder, d):
    """A request file for gene_client / upgrade.py (they pick up *.json, oldest name first)."""
    write(os.path.join(folder, f"{time.time_ns()}.json"), d)


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def upgrading():
    """The upgrade progress ({"percent", "step"}) while upgrade.py runs, else None."""
    p = read(gene_eyes.PROGRESS)
    return p if p and alive(p.get("pid")) else None


def service(name):
    r = subprocess.run(["systemctl", "--user", "is-active", name], capture_output=True, text=True)
    return r.stdout.strip()


# ---------- pictures ----------

class Cached:
    """Makes a picture at most every `every` s, however many browsers ask."""
    def __init__(self, make, every):
        self.make, self.every, self.lock, self.t, self.data = make, every, threading.Lock(), 0.0, None

    def get(self):
        with self.lock:
            if time.time() - self.t >= self.every:
                try:
                    self.data = self.make()
                except Exception as e:
                    log("picture error:", e)
                    self.data = None
                self.t = time.time()
            return self.data


def camera_jpeg(n):
    path = os.path.join(FRAMES, f"cam{n}.npy")
    try:
        os.utime(FAST, None)
    except OSError:
        open(FAST, "a").close()
    if time.time() - os.path.getmtime(path) > 10:
        return None
    a = np.load(path)                           # B, G, R
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(a[..., ::-1])).save(buf, "JPEG", quality=72)
    return buf.getvalue()


FAST = os.path.join(FRAMES, "fast")
CAMS = {side: Cached(lambda n=n: camera_jpeg(n), 0.1) for side, n in CAMERAS.items()}


def screens_jpeg():
    """What the eye screens show right now (as laid out on the desktop - each screen is mounted upside down; the page
    turns them)."""
    env = dict(os.environ, WAYLAND_DISPLAY=os.environ.get("WAYLAND_DISPLAY", "wayland-0"))
    r = subprocess.run(["grim", "-t", "ppm", "-"], capture_output=True, env=env, timeout=5)   # (no jpeg in this grim)
    if r.returncode or not r.stdout:
        return None
    buf = io.BytesIO()
    Image.open(io.BytesIO(r.stdout)).convert("RGB").save(buf, "JPEG", quality=75)
    return buf.getvalue()


SCREENS = Cached(screens_jpeg, 0.4)
MIC_RATE = 16000


def mic_info():
    """Gene's mic: its name and whether it is muted (wpctl), for the page."""
    r = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True, timeout=3)
    if r.returncode:
        return {"found": False}
    name = subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True, timeout=3).stdout
    desc = next((l.split("=", 1)[1].strip().strip('"') for l in name.splitlines() if "node.description" in l), "")
    return {"found": True, "muted": "MUTED" in r.stdout, "name": desc}


MIC = Cached(mic_info, 3)
SERVICES = Cached(lambda: {s: service(s) for s in ("gene", "gene-eyes", "gene-cameras", "gene-stt")}, 3)


# ---------- what the page shows ----------

def face_now(e):
    """The face the eyes are showing, from state/eyes.json (the eyes go back to neutral after `until`)."""
    e = e or {}
    em = e.get("emote", "neutral")
    if em != "flashlight" and e.get("until") and time.time() > e["until"]:
        return "neutral"
    if em != "flashlight" and time.time() - e.get("t", 0) > gene_eyes.IDLE_RESET and not e.get("until"):
        return "neutral"
    return em


def status():
    vol = read(VOLUME) or {}
    return {
        "now": time.time(),
        "face": "loading" if upgrading() else face_now(read(gene_eyes.EYES)),
        "lids": gene_eyes.lids_shut(),
        "mouth": read(MOUTH),
        "jaw": read(JAW),
        "volume": vol.get("regular"),
        "upgrade": upgrading(),
        "services": SERVICES.get(),
        "mic": MIC.get(),
    }


def history(n=15):
    out = []
    try:
        lines = open(HISTORY, errors="replace").readlines()[-n:]
    except OSError:
        return out
    for l in reversed(lines):
        try:
            e = json.loads(l.replace("\0", ""))
        except ValueError:
            continue
        out.append({k: e.get(k) for k in ("time", "mode", "request", "result", "minutes", "cost_usd", "changed",
                                           "to_commit")} | {"said": (e.get("claude_said") or "")[-600:]})
    return out


class Journal:
    """`journalctl -f` for gene.service, shared by every open page: the last lines and a queue per page."""
    def __init__(self):
        self.lines, self.subs, self.lock = [], set(), threading.Lock()
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            p = subprocess.Popen(["journalctl", "--user-unit", "gene", "-f", "-n", "150", "-o", "json", "--no-pager"],
                                 stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                try:
                    d = json.loads(line)
                    msg = d.get("MESSAGE")
                    if isinstance(msg, list):
                        msg = bytes(msg).decode("utf-8", "replace")
                    item = {"t": int(d.get("__REALTIME_TIMESTAMP", 0)) / 1e6, "text": msg or ""}
                except ValueError:
                    continue
                with self.lock:
                    self.lines = (self.lines + [item])[-150:]
                    for q in list(self.subs):
                        q.put(("log", item))
            p.wait()
            time.sleep(2)

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.subs.add(q)
            return q, list(self.lines)

    def unsubscribe(self, q):
        with self.lock:
            self.subs.discard(q)


JOURNAL = Journal()


# ---------- the server ----------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "GeneTeleop/1"

    def log_message(self, fmt, *a):         # only errors, not every picture
        pass

    def authed(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE and hmac.compare_digest(v, TOKEN):
                return True
        return False

    def send(self, code, body=b"", kind="application/json", headers=()):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 65536:
            raise ValueError("too big")
        raw = self.rfile.read(n) if n else b"{}"
        if "json" in (self.headers.get("Content-Type") or ""):
            return json.loads(raw or b"{}")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode()).items()}

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            return self.send(200, LOGIN_PAGE, "text/html; charset=utf-8")
        if not self.authed():
            if path == "/":
                return self.send(303, "", headers=[("Location", "/login")])
            return self.send(401, {"error": "log in"})
        if path == "/":
            return self.send(200, open(PAGE, "rb").read(), "text/html; charset=utf-8")
        if path.startswith("/cam/") and path.endswith(".jpg"):
            side = path[5:-4]
            if side in CAMS and (img := CAMS[side].get()):
                return self.send(200, img, "image/jpeg")
            return self.send(404, {"error": "no picture from that camera"})
        if path == "/screens.jpg":
            if img := SCREENS.get():
                return self.send(200, img, "image/jpeg")
            return self.send(404, {"error": "no screenshot"})
        if path == "/api/upgrades":
            return self.send(200, history())
        if path == "/mic.pcm":
            return self.mic()
        if path == "/events":
            return self.events()
        self.send(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self.body()
        except ValueError:
            return self.send(400, {"error": "bad request"})
        if path == "/login":
            if hmac.compare_digest(str(data.get("password", "")), PASSWORD):
                return self.send(303, "", headers=[("Location", "/"), ("Set-Cookie",
                                 f"{COOKIE}={TOKEN}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000")])
            time.sleep(1)
            return self.send(303, "", headers=[("Location", "/login?wrong=1")])
        if not self.authed() or self.headers.get("X-Gene") != "1":
            return self.send(401, {"error": "log in"})
        try:
            return self.send(200, self.act(path, data))
        except ApiError as e:
            return self.send(e.code, {"error": str(e)})

    def act(self, path, d):
        if path == "/api/say":
            text = str(d.get("text") or "").strip()
            if not text:
                raise ApiError("Nothing to say.")
            face = d.get("face") if d.get("face") in gene_eyes.CHOICES else None
            style = d.get("style") if d.get("style") in ("loud", "meek") else None
            drop(SAY, {"text": text[:1000], "face": face, "style": style})
            log("say:", text[:80])
            return {"ok": True, "gene_running": service("gene") == "active"}
        if path == "/api/face":
            face = d.get("face")
            if face not in gene_eyes.CHOICES:
                raise ApiError("Unknown face.")
            if face == "neutral":
                gene_eyes.show("neutral")
            else:
                gene_eyes.hold(face, max(2, min(600, float(d.get("seconds") or 20))))
            return {"ok": True}
        if path == "/api/lids":
            which = d.get("which") if d.get("which") in ("left", "right", "both") else "both"
            act = d.get("action")
            if act == "close":
                gene_eyes.close_eyes(which)
            elif act == "open":
                gene_eyes.open_eyes(which)
            elif act == "wink":
                gene_eyes.close_eyes(which, gene_eyes.WINK_FOR)
            else:
                raise ApiError("Unknown eye action.")
            return {"ok": True}
        if path == "/api/jaw":
            deg = max(0.0, min(JAW_MAX, float(d.get("deg") or 0)))
            write(JAW, {"deg": deg, "t": time.time()})
            return {"ok": True, "deg": deg}
        if path == "/api/upgrade":
            text = " ".join(str(d.get("text") or "").split())
            if not text:
                raise ApiError("Say what to upgrade.")
            if upgrading():
                raise ApiError("Gene is already upgrading himself.", 409)
            subprocess.Popen(["systemd-run", "--user", "--collect", f"--unit=gene-upgrade-web-{int(time.time())}",
                              "--property=WorkingDirectory=" + HERE,
                              os.path.join(HERE, "venv", "bin", "python"), "-u", os.path.join(HERE, "upgrade.py"),
                              "web", text[:4000]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log("upgrade started:", text[:80])
            return {"ok": True}
        if path == "/api/upgrade/message":
            text = str(d.get("text") or "").strip()
            if not text:
                raise ApiError("Nothing to send.")
            if not upgrading():
                raise ApiError("No upgrade is running.", 409)
            drop(INBOX, {"text": text[:8000]})
            return {"ok": True}
        if path == "/api/upgrade/stop":
            if not upgrading():
                raise ApiError("No upgrade is running.", 409)
            open(STOP, "w").close()
            return {"ok": True}
        raise ApiError("Not found.", 404)

    def mic(self):
        """Gene's mic, live: raw 16 kHz mono s16le in 100 ms pieces until the page stops listening."""
        p = subprocess.Popen(["pw-cat", "--record", "--raw", "--rate", str(MIC_RATE), "--channels", "1", "--format", "s16",
                              "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        log("mic: someone is listening")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Sample-Rate", str(MIC_RATE))
            self.end_headers()
            while chunk := p.stdout.read(MIC_RATE // 10 * 2):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            p.kill(); p.wait()
            log("mic: stopped listening")

    def events(self):
        """Server-sent events: the status (when it changes), journal lines and the upgrade's live log."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q, backlog = JOURNAL.subscribe()

        def emit(kind, data):
            self.wfile.write(f"event: {kind}\ndata: {json.dumps(data)}\n\n".encode())

        try:
            emit("hello", {"faces": gene_eyes.CHOICES, "upside_down": getattr(gene_eyes, "UPSIDE_DOWN", False),
                           "jaw_max": JAW_MAX, "now": time.time()})
            emit("logs", backlog)
            live_pos, live_id, last, beat = 0, None, None, time.time()
            while True:
                st = status()
                key = json.dumps({k: v for k, v in st.items() if k != "now"}, sort_keys=True)
                if key != last:
                    emit("status", st); last = key
                elif time.time() - beat > 1:
                    emit("clock", {"now": time.time()}); beat = time.time()
                try:            # the upgrade's live log: a new file (new upgrade) starts again from the top
                    s = os.stat(LIVE)
                    if (s.st_ino, s.st_dev) != live_id or s.st_size < live_pos:
                        live_id, live_pos = (s.st_ino, s.st_dev), 0
                        emit("live_reset", {})
                    if s.st_size > live_pos:
                        with open(LIVE, "rb") as f:
                            f.seek(live_pos)
                            chunk = f.read(s.st_size - live_pos)
                        cut = chunk.rfind(b"\n") + 1
                        live_pos += cut
                        items = []
                        for l in chunk[:cut].splitlines():
                            try:
                                items.append(json.loads(l))
                            except ValueError:
                                pass
                        if items:
                            emit("live", items)
                except OSError:
                    pass
                lines = []
                try:
                    while True:
                        lines.append(q.get_nowait()[1])
                except queue.Empty:
                    pass
                if lines:
                    emit("logs", lines)
                self.wfile.flush()
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            JOURNAL.unsubscribe(q)


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg); self.code = code


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Gene control</title>
<style>
:root{color-scheme:dark}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0f12;
font:16px system-ui,sans-serif;color:#d8e4e8}form{background:#131a1f;border:1px solid #23303a;border-radius:14px;
padding:28px;width:min(320px,calc(100vw - 32px));box-sizing:border-box}h1{margin:0 0 4px;font-size:22px}
p{margin:0 0 18px;color:#7d929c;font-size:14px}input,button{width:100%;box-sizing:border-box;font:inherit;
border-radius:9px;padding:11px 12px}input{background:#0b0f12;border:1px solid #2c3b46;color:inherit;margin-bottom:12px}
button{background:#2bd4b0;border:0;color:#04211b;font-weight:600;cursor:pointer}.bad{color:#ff8a80}
</style></head><body><form method="post" action="/login"><h1>Gene</h1><p>Control panel</p>
<script>if(location.search.includes("wrong"))document.write('<p class="bad">Wrong password.</p>')</script>
<input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
<button>Log in</button></form></body></html>"""


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.makedirs(FRAMES, exist_ok=True)
    log(f"Gene's control panel on port {PORT}")
    Server(("0.0.0.0", PORT), Handler).serve_forever()
