"""Gene's self-upgrades: hands a task to Claude Code (full shell access), then restarts Gene and checks he
comes back up. If he doesn't, rolls back to the last commit that ran (git tag `last-good`).

  upgrade.py voice "<what was said>"   someone asked Gene by voice ("Gene, upgrade yourself to ...")
  upgrade.py review                    nightly self-review of the last day's conversations and errors
  upgrade.py repair                    gene.service is crash-looping (run by gene-repair.service)
  upgrade.py web "<what was typed>"     typed into Gene's web control panel (gene_teleop.py)

Runs outside gene.service (systemd-run / its own unit), so restarting Gene doesn't kill it.
Gene speaks the result: it is left in state/announce.txt, which gene_client.py picks up.
While it runs, Gene's eyes show the loading face with the real progress (gene_eyes.progress):
  0-5 % getting ready, 5-85 % Claude's own steps done / planned (it writes state/upgrade_steps.json),
  85-100 % restarting Gene and the health check.
The web control panel (gene_teleop.py) watches it live: every step Claude takes goes to state/upgrade_live.jsonl,
messages typed there while Claude works (state/upgrade_inbox/) are passed on to Claude Code (stream-json input), and
its Stop button (state/upgrade_stop) cancels the upgrade: Claude is stopped and nothing it changed is kept.
"""
import datetime, fcntl, json, os, re, subprocess, sys, threading, time, uuid
import gene_eyes

HOME = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HOME, "state")
HISTORY = os.path.join(STATE, "upgrades.jsonl")
ANNOUNCE = os.path.join(STATE, "announce.txt")
CLAUDE = os.path.expanduser("~/.local/bin/claude")
MAX_PER_DAY = int(os.environ.get("GENE_UPGRADES_PER_DAY", "15"))   # Claude usage cap
CLAUDE_TIMEOUT = 40 * 60
HEALTH_TIMEOUT = 90         # s for Gene to reach "listening" after a restart
HEALTH_HOLD = 15            # s he must then stay up
STEPS = os.path.join(STATE, "upgrade_steps.json")
LIVE = os.path.join(STATE, "upgrade_live.jsonl")      # each step Claude takes, for the web panel
INBOX = os.path.join(STATE, "upgrade_inbox")          # <name>.json {"text": ...}: typed in the web panel for Claude
STOP = os.path.join(STATE, "upgrade_stop")            # the web panel's Stop button


class Progress:
    """The percentage on Gene's eyes. Only ever goes up."""
    def __init__(self):
        self.pct = 0.0

    def __call__(self, pct, step=""):
        self.pct = max(self.pct, min(100.0, pct))
        gene_eyes.progress(round(self.pct), step)
        if step != getattr(self, "step", None):
            self.step = step
            live(kind="stage", step=step)

    def claude(self):
        """5-85 %: the share of its planned steps Claude says it has finished."""
        try:
            d = json.load(open(STEPS))
            done, total = float(d["done"]), float(d["total"])
            if total > 0:
                self(5 + 80 * max(0.0, min(1.0, done / total)), "working")
        except (OSError, ValueError, KeyError, TypeError):
            pass


progress = Progress()


def sh(*cmd, check=True, **kw):
    return subprocess.run(cmd, cwd=HOME, text=True, capture_output=True, check=check, **kw).stdout.strip()


def git(*a, check=True):
    return sh("git", "-c", "user.name=Gene", "-c", "user.email=gene@localhost", *a, check=check)


def commit_all(msg):
    git("add", "-A")
    if git("status", "--porcelain"):
        git("commit", "-q", "-m", msg)


def announce(text):
    with open(ANNOUNCE, "w") as f:
        f.write(text.strip() + "\n")


def live(**ev):
    """One line of the live log the web panel shows."""
    ev["t"] = time.time()
    try:
        with open(LIVE, "a") as f:
            f.write(json.dumps(ev) + "\n")
    except OSError:
        pass


def _clip(text, n):
    text = text if isinstance(text, str) else json.dumps(text)
    return text if len(text) <= n else text[:n] + f"\n... ({len(text) - n} more characters)"


def live_event(ev, prompt_uuid):
    """A Claude Code stream-json event -> the live log, shortened (file contents can be huge)."""
    t, msg = ev.get("type"), ev.get("message") or {}
    if t == "assistant":
        for c in msg.get("content") or []:
            if c.get("type") == "text" and c.get("text", "").strip():
                live(kind="text", text=c["text"])
            elif c.get("type") == "tool_use":
                live(kind="tool", name=c.get("name"), input=_clip(c.get("input"), 3000))
    elif t == "user":
        content = msg.get("content")
        if isinstance(content, str):        # a replayed message of ours: Claude has now taken it in
            if ev.get("uuid") != prompt_uuid:
                live(kind="you", text=content)
            return
        for c in content or []:
            if c.get("type") == "tool_result":
                out = c.get("content")
                if isinstance(out, list):
                    out = "\n".join(x.get("text", "") for x in out if isinstance(x, dict) and x.get("type") == "text")
                live(kind="output", text=_clip(out or "", 4000), error=bool(c.get("is_error")))
    elif t == "result":
        live(kind="result", text=ev.get("result") or "", cost=ev.get("total_cost_usd"))


def record(**kw):
    live(kind="end", result=kw.get("result"))
    kw["time"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(HISTORY, "a") as f:
        f.write(json.dumps(kw) + "\n")
        f.flush(); os.fsync(f.fileno())     # Gene's power gets cut: don't leave a half-written line


def history():
    """The upgrade records. Skips damaged lines (a power cut mid-write left one of NUL bytes, which stopped
    every upgrade from starting)."""
    if not os.path.exists(HISTORY):
        return []
    out = []
    for l in open(HISTORY, errors="replace"):
        try:
            out.append(json.loads(l.replace("\0", "")))
        except ValueError:
            pass
    return [e for e in out if isinstance(e, dict)]


def runs_today():
    today = datetime.date.today().isoformat()
    return sum(1 for e in history() if e.get("time", "").startswith(today) and e.get("ran_claude"))


def journal(since):
    return sh("journalctl", "--user-unit", "gene", "--since", since, "--no-pager", "-o", "short-iso", check=False)[-20000:]


def recent_upgrades(n=10):
    if not os.path.exists(HISTORY):
        return "none yet"
    return "".join(open(HISTORY).readlines()[-n:]) or "none yet"


def prompt_for(mode, request):
    head = ("You are upgrading Gene, the robot head running on this Pi. Read CLAUDE.md in this folder first "
            "and follow its rules.\n\n"
            "Gene's eyes show your progress as a percentage while you work. As soon as you know your plan, and "
            "after you finish each step of it, write how many steps are done out of how many in total (count "
            "testing and committing as steps; it's fine to raise the total if the plan grows), e.g.:\n"
            "    echo '{\"done\": 2, \"total\": 5}' > state/upgrade_steps.json\n\n"
            "Joshua can watch your work live in Gene's web control panel and may type messages to you while you "
            "work; they arrive as new user messages - take them into account.\n\n")
    if mode == "web":
        return head + (f"Joshua typed this request into Gene's web control panel:\n\n    {request}\n\n"
                       "Do it. If it can't sensibly be done on this Pi, make no changes and ANNOUNCE why, in one "
                       "sentence.")
    if mode == "voice":
        return head + (f"Someone asked Gene, by voice, to upgrade himself. Speech-to-text heard:\n\n    {request}\n\n"
                       "Work out what they want and do it. Speech-to-text can mishear, so read it charitably. If it "
                       "can't sensibly be done on this Pi, make no changes and ANNOUNCE why, in one sentence.")
    if mode == "repair":
        return head + ("gene.service keeps crashing and systemd has given up restarting it. Find out why "
                       "(journalctl below, and run the client by hand) and fix it.\n\nRecent log:\n"
                       + journal("-30min"))
    return head + ("This is Gene's nightly self-review. Below are his last 24 hours of conversations, timings and "
                   "errors, and his recent upgrades. Pick the ONE improvement that would most improve talking to "
                   "Gene (accuracy, latency, robustness, mishearings, things he got wrong, crashes) and make it. "
                   "Don't repeat an upgrade that was rolled back unless you know why it failed. If nothing is "
                   "worth changing, make no changes and reply `ANNOUNCE: none`.\n\n"
                   f"Recent upgrades:\n{recent_upgrades()}\n\nLast 24 h of gene.service log:\n{journal('-24h')}")


def healthy(since, eyes=False):
    """gene.service is active, has logged "listening" since `since`, and stays up a while (and so do the eyes,
    if they were changed)."""
    end = time.time() + HEALTH_TIMEOUT
    while time.time() < end:
        log = sh("journalctl", "--user-unit", "gene", "--since", since, "--no-pager", "-o", "cat", check=False)
        if "listening" in log:
            progress(92, "checking")
            for i in range(HEALTH_HOLD):
                time.sleep(1); progress(92 + 8 * (i + 1) / HEALTH_HOLD, "checking")
            return (sh("systemctl", "--user", "is-active", "gene", check=False) == "active" and
                    (not eyes or sh("systemctl", "--user", "is-active", "gene-eyes", check=False) == "active"))
        time.sleep(2)
    return False


def restart_gene(eyes=False):
    since = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sh("systemctl", "--user", "reset-failed", "gene", check=False)
    sh("systemctl", "--user", "restart", "gene", check=False)
    if eyes:        # gene_eyes.py changed: the eyes run the new code (they come back on the progress file)
        sh("systemctl", "--user", "try-restart", "gene-eyes", check=False)
    return since


def run_claude(prompt):
    """Claude Code, streaming (stream-json in and out). Each step goes to the live log, messages typed in the web panel
    are passed on while it works, its progress file is read every second for Gene's eyes, and the Stop button kills
    it. Returns (final text, cost in USD, cancelled)."""
    for path in (STEPS, STOP):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    os.makedirs(INBOX, exist_ok=True)
    for name in os.listdir(INBOX):      # left over from before: not meant for this upgrade
        os.unlink(os.path.join(INBOX, name))
    p = subprocess.Popen([CLAUDE, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                          "--replay-user-messages", "--dangerously-skip-permissions"],
                         cwd=HOME, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lock = threading.Lock()
    sent, seen = set(), set()           # our messages' ids, and the ones Claude Code has replayed (= taken in)
    st = {"open": True, "cancelled": False, "timeout": False}

    def send(text):
        u = str(uuid.uuid4())
        p.stdin.write(json.dumps({"type": "user", "uuid": u, "message": {"role": "user", "content": text}}) + "\n")
        p.stdin.flush()
        sent.add(u)
        return u

    def close():        # no more messages: Claude Code ends after its current reply
        if st["open"]:
            st["open"] = False
            try:
                p.stdin.close()
            except OSError:
                pass

    def watch():        # progress, the Stop button, the timeout, and messages from the web panel
        end = time.time() + CLAUDE_TIMEOUT
        while p.poll() is None:
            progress.claude()
            if os.path.exists(STOP):
                st["cancelled"] = True; live(kind="stopped"); p.kill(); return
            if time.time() > end:
                st["timeout"] = True; p.kill(); return
            for name in sorted(n for n in os.listdir(INBOX) if n.endswith(".json")):
                path = os.path.join(INBOX, name)
                try:
                    with open(path) as f:
                        text = str(json.load(f).get("text") or "").strip()
                except (OSError, ValueError, AttributeError):
                    text = ""
                try:
                    os.unlink(path)
                except OSError:
                    pass
                with lock:
                    if text and st["open"]:
                        try:
                            send(text)
                        except (OSError, ValueError):
                            live(kind="late", text=text)
                    elif text:
                        live(kind="late", text=text)
            time.sleep(0.3)

    err = []
    threading.Thread(target=lambda: err.append(p.stderr.read()), daemon=True).start()
    with lock:
        first = send(prompt)
    threading.Thread(target=watch, daemon=True).start()
    text, cost = "", None
    for line in p.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "user" and isinstance((ev.get("message") or {}).get("content"), str):
            seen.add(ev.get("uuid"))
        live_event(ev, first)
        if ev.get("type") == "result":
            text = ev.get("result") or text
            cost = ev.get("total_cost_usd", cost)
            with lock:
                if sent <= seen:        # every message answered: done (else it goes on to the newer ones)
                    close()
    p.wait()
    with lock:
        close()
    progress.claude()
    if st["timeout"]:
        text = "timed out"
    return text or "".join(err)[-500:], cost, st["cancelled"]


def main():
    try:
        upgrade()
    except Exception:
        announce("Something went wrong in my upgrade system before I could start, so I didn't change anything.")
        raise
    finally:
        gene_eyes.done()


def upgrade():
    mode = sys.argv[1] if len(sys.argv) > 1 else "review"
    request = " ".join(sys.argv[2:])
    os.makedirs(STATE, exist_ok=True)
    lock = open(os.path.join(STATE, "upgrade.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if mode == "voice":
            announce("I'm already in the middle of upgrading myself. Ask me again when I'm done.")
        return

    if runs_today() >= MAX_PER_DAY:
        record(mode=mode, request=request, ran_claude=False, result="daily limit reached")
        if mode == "voice":
            announce(f"I've already upgraded myself {MAX_PER_DAY} times today. Ask me again tomorrow.")
        return

    with open(LIVE, "w") as f:      # a new live log for the web panel
        f.write(json.dumps({"kind": "start", "mode": mode, "request": request, "t": time.time()}) + "\n")
    progress(1, "starting")
    commit_all("auto: uncommitted changes found before upgrade")
    if not git("tag", "-l", "last-good"):
        git("tag", "last-good")
    start = git("rev-parse", "HEAD")

    progress(5, "working")
    t0 = time.time()
    text, cost, cancelled = run_claude(prompt_for(mode, request))
    if cancelled:       # the web panel's Stop button: keep nothing Claude changed
        changed_files = git("diff", "--name-only", start, check=False)     # tracked files, committed or not
        touched, eyes_touched = bool(changed_files), "gene_eyes.py" in changed_files
        git("reset", "-q", "--hard", start)
        git("clean", "-fdq")        # new files Claude made (state/, venv/ and models/ are git-ignored, so they stay)
        record(mode=mode, request=request, ran_claude=True, minutes=round((time.time() - t0) / 60, 1), cost_usd=cost,
               changed=False, from_commit=start[:7], to_commit=start[:7], claude_said=text[-1500:],
               result="stopped from the web panel")
        if touched:     # Claude may have restarted the eyes on its new code: back to the old code everywhere
            progress(88, "restarting")
            restart_gene(eyes_touched)
        announce("Okay, I stopped that upgrade and kept everything how it was.")
        return
    progress(85, "restarting")
    m = re.findall(r"ANNOUNCE:\s*(.+)", text)
    said = m[-1].strip() if m else ""
    commit_all(f"auto: leftover changes from {mode} upgrade")
    changed = git("rev-parse", "HEAD") != start
    entry = dict(mode=mode, request=request, ran_claude=True, minutes=round((time.time() - t0) / 60, 1),
                 cost_usd=cost, changed=changed, from_commit=start[:7], to_commit=git("rev-parse", "--short", "HEAD"),
                 claude_said=text[-1500:])

    if not changed and mode != "repair":
        record(**entry, result="no changes")
        if mode == "voice":
            announce(said or "I looked into that, but I didn't change anything.")
        return

    eyes_changed = "gene_eyes.py" in git("diff", "--name-only", start, "HEAD")
    since = restart_gene(eyes_changed)
    progress(88, "restarting")
    if healthy(since, eyes_changed):
        git("tag", "-f", "last-good")
        record(**entry, result="ok")
        if said and said.lower() != "none":
            announce("I've upgraded myself. " + said)
        return

    # Broken: back to the last version that ran.
    good = git("rev-parse", "last-good")
    bad = git("rev-parse", "--short", "HEAD")
    git("tag", "-f", f"failed-{datetime.datetime.now():%Y%m%d-%H%M%S}", "HEAD")
    git("reset", "-q", "--hard", good)
    record(**entry, result=f"rolled back {bad} -> {good[:7]}")
    announce("I tried to upgrade myself, but the new version didn't work, so I went back to how I was.")
    restart_gene(eyes_changed)


if __name__ == "__main__":
    main()
