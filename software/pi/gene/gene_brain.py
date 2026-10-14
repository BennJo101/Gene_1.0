"""Gene's brain: Claude through the Anthropic API first, the Jetson's Ollama model `gene` (Llama 3.2 3B) as the fallback.

Since 2026-10-06 (asked by Joshua): Claude is the primary brain, so the head works on its own - Pi + a phone hotspot,
no Jetson. When Claude can't be reached (no internet, key revoked, API down) the Jetson answers, if it is on the network.

  - Claude: `claude-opus-5-5`, streamed, effort "low" (adaptive thinking is always on for this model; low keeps the
    first sentence at ~1.7-2 s), Gene's personality from `brain/gene.Modelfile` as the system prompt (cached), server-side
    refusal fallbacks on. The key is in ~/.config/gene/anthropic.env (chmod 600, NOT in git): ANTHROPIC_API_KEY=...
  - Jetson: Ollama http://<GENE_BRAIN>:11434/api/chat, model `gene` (its Modelfile holds the same prompt, so no system
    message is sent for the conversation).
  - A brain that just failed is skipped for a while (CLAUDE_RETRY / JETSON_RETRY), so a missing one costs one short
    timeout, not one per phrase. Callers see the same text either way; `last` says which brain answered.
  - Images (camera frames) only go to Claude; the Jetson path gets Moondream's description instead (gene_client).
  - Structured output: Ollama's `format` schema maps to Claude's output_config json_schema (additionalProperties false
    added, as Claude requires).

Test:  ./venv/bin/python gene_brain.py "hey gene, what's up?"
"""
import copy, json, os, re, socket, sys, threading, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.expanduser("~/.config/gene/anthropic.env")
MODEL = os.environ.get("GENE_CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("GENE_CLAUDE_EFFORT", "low")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
JETSON = os.environ.get("GENE_BRAIN", "192.168.0.37")
JETSON_URL = f"http://{JETSON}:11434/api/chat"
ORDER = [b for b in os.environ.get("GENE_BRAIN_ORDER", "claude,jetson").split(",") if b in ("claude", "jetson")]
CLAUDE_RETRY = 30       # s a failed Claude is skipped (network); a bad key is skipped for KEY_RETRY
KEY_RETRY = 600
JETSON_RETRY = 60
CONNECT_TIMEOUT = 2.5   # s to decide the Jetson isn't there
REPLY_TOKENS = 1024     # thinking counts against max_tokens; Gene stops after 3 sentences anyway
VOICE = ("\n\nYou are speaking out loud through a small speaker, in a live voice conversation: begin your visible answer "
         "immediately, keep it to 1-3 short spoken sentences, and never use lists, markdown, emoji or stage directions. "
         "What people say reaches you through speech-to-text, which sometimes mishears a word or cuts a phrase short: if "
         "what you were told looks garbled, answer what they most likely meant, or ask them to say it again - never "
         "answer the garbled words literally.")

last = None             # "claude" or "jetson": which brain gave the last answer
_down = {}              # brain -> time until which it is skipped
_lock = threading.Lock()
_client = None


def log(*a):
    print(time.strftime("%H:%M:%S"), "brain:", *a, flush=True)


def _key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        for line in open(KEY_FILE):
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return None


def _claude():
    global _client
    with _lock:
        if _client is None:
            import anthropic
            if not (k := _key()):
                raise RuntimeError(f"no Anthropic key ({KEY_FILE})")
            _client = anthropic.Anthropic(api_key=k, max_retries=1,
                                          timeout=anthropic.Timeout(30.0, connect=4.0))
        return _client


def _gene_prompt():
    """Gene's personality: the SYSTEM block of his Ollama Modelfile, so both brains are the same Gene."""
    try:
        m = re.search(r'SYSTEM\s+"""(.*?)"""', open(os.path.join(HERE, "brain", "gene.Modelfile")).read(), re.S)
        return m.group(1).strip() if m else ""
    except OSError:
        return ""


GENE = _gene_prompt()


def up(brain):
    return time.time() >= _down.get(brain, 0)


def _fail(brain, why, wait):
    _down[brain] = time.time() + wait
    log(f"{brain} unavailable for {wait} s: {why}")


def _jetson_there():
    try:
        socket.create_connection((JETSON, 11434), timeout=CONNECT_TIMEOUT).close()
        return True
    except OSError:
        return False


# ---- Claude ----

def _split(messages):
    """Ollama-style messages -> (system text, Claude messages). Leading system messages become the system prompt
    (memory and graph send their own); with none, it's Gene's personality."""
    system = [m["content"] for m in messages if m["role"] == "system"]
    msgs = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return ("\n\n".join(system) if system else GENE + VOICE), msgs


def _with_images(msgs, images):
    """Attaches PNG frames to the last user message."""
    if not images:
        return msgs
    import base64
    msgs = list(msgs)
    blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                           "data": base64.standard_b64encode(png).decode()}} for png in images]
    msgs[-1] = {"role": "user", "content": blocks + [{"type": "text", "text": msgs[-1]["content"]}]}
    return msgs


def _strict(schema):
    """Claude's json_schema needs additionalProperties: false on every object."""
    s = copy.deepcopy(schema)

    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object":
                n.setdefault("additionalProperties", False)
                n.setdefault("required", list(n.get("properties", {})))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(s)
    return s


def _claude_args(messages, images=None, schema=None, max_tokens=REPLY_TOKENS):
    system, msgs = _split(messages)
    out = {"effort": EFFORT}
    if schema:
        out["format"] = {"type": "json_schema", "schema": _strict(schema)}
    return dict(model=MODEL, max_tokens=max_tokens, output_config=out, messages=_with_images(msgs, images),
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                betas=[FALLBACK_BETA], fallbacks="default")


def _claude_error(e):
    import anthropic
    if isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        _fail("claude", f"key rejected ({e.status_code})", KEY_RETRY)
    elif isinstance(e, RuntimeError) and "no Anthropic key" in str(e):
        _fail("claude", str(e), KEY_RETRY)
    else:
        _fail("claude", f"{type(e).__name__}: {e}", CLAUDE_RETRY)


def _claude_stream(messages, images=None):
    with _claude().beta.messages.stream(**_claude_args(messages, images)) as st:
        for text in st.text_stream:
            yield text
        final = st.get_final_message()
    if final.stop_reason == "refusal":
        log("claude declined:", getattr(final.stop_details, "category", None))


def _claude_complete(messages, schema=None, max_tokens=REPLY_TOKENS, timeout=60):
    with _claude().with_options(timeout=timeout).beta.messages.stream(
            **_claude_args(messages, schema=schema, max_tokens=max_tokens)) as st:
        final = st.get_final_message()
    if final.stop_reason == "refusal":
        raise RuntimeError("claude declined")
    return "".join(b.text for b in final.content if b.type == "text")


# ---- Jetson (Ollama) ----

def _ollama_messages(messages):
    """The Jetson can't see pictures; list content (text + images) becomes its text."""
    return [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str)
             else " ".join(b.get("text", "") for b in m["content"] if isinstance(b, dict))} for m in messages]


def _jetson_stream(messages):
    body = {"model": "gene", "stream": True, "messages": _ollama_messages(messages)}
    req = urllib.request.Request(JETSON_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        for line in r:
            d = json.loads(line)
            if t := d.get("message", {}).get("content", ""):
                yield t
            if d.get("done"):
                break


def _jetson_complete(messages, schema=None, max_tokens=None, timeout=60, options=None):
    body = {"model": "gene", "stream": False, "keep_alive": -1, "messages": _ollama_messages(messages),
            "options": dict(options or {})}
    if schema:
        body["format"] = schema
    if max_tokens:
        body["options"].setdefault("num_predict", max_tokens)
    req = urllib.request.Request(JETSON_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))["message"]["content"]


# ---- what the rest of Gene calls ----

def stream(messages, images=None):
    """Gene's reply as text chunks, from the first brain that answers. A brain that fails before its first chunk is
    skipped and the next one tried; one that fails mid-reply just ends the reply. Raises if no brain answers."""
    global last
    errors = []
    # a picture needs eyes: the Jetson can't see, so Claude goes first then (else it makes up what it sees)
    for brain in (sorted(ORDER, key=lambda b: b != "claude") if images else ORDER):
        if not up(brain):
            continue
        if brain == "jetson" and not _jetson_there():
            _fail("jetson", "not on the network", JETSON_RETRY); continue
        got, t0 = False, time.time()
        try:
            for chunk in (_claude_stream(messages, images) if brain == "claude" else _jetson_stream(messages)):
                if not got:
                    got, last = True, brain
                    log(f"{brain} first words after {time.time() - t0:.2f}s" + (f" ({len(images)} picture)" if images else ""))
                yield chunk
            if got:
                return
            errors.append(f"{brain}: empty reply")
        except GeneratorExit:
            raise
        except Exception as e:
            if got:
                log(f"{brain} stopped mid-reply: {e}"); return
            errors.append(f"{brain}: {e}")
            _claude_error(e) if brain == "claude" else _fail("jetson", e, JETSON_RETRY)
    raise RuntimeError("no brain answered (" + "; ".join(errors or ["all skipped"]) + ")")


def complete(messages, schema=None, max_tokens=REPLY_TOKENS, timeout=60, options=None):
    """One whole reply (JSON text when `schema` is given), from the first brain that answers. `options` are Ollama
    sampling options for the Jetson (Claude Opus 5.5 takes none)."""
    global last
    errors = []
    for brain in ORDER:
        if not up(brain):
            continue
        if brain == "jetson" and not _jetson_there():
            _fail("jetson", "not on the network", JETSON_RETRY); continue
        try:
            if brain == "claude":
                text = _claude_complete(messages, schema, max(max_tokens, 512), timeout)
            else:
                text = _jetson_complete(messages, schema, None if max_tokens == REPLY_TOKENS else max_tokens, timeout, options)
            last = brain
            return text
        except Exception as e:
            errors.append(f"{brain}: {e}")
            _claude_error(e) if brain == "claude" else _fail("jetson", e, JETSON_RETRY)
    raise RuntimeError("no brain answered (" + "; ".join(errors or ["all skipped"]) + ")")


def claude_ready():
    """True when Claude should be tried now (key present, not recently failed): pictures then go straight to it."""
    return "claude" in ORDER and up("claude") and bool(_key())


def warm():
    """Opens the TLS connection to the API at start, so the first reply doesn't pay for it."""
    try:
        _claude().models.retrieve(MODEL)
        return True
    except Exception as e:
        _claude_error(e)
        return False


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "hey gene, what's up?"
    t = time.time(); first = None; out = ""
    for c in stream([{"role": "user", "content": f"(eyes: start with an eye tag)\nJoshua says: {q}"}]):
        first = first or time.time() - t; out += c
    print(f"[{last}] first chunk {first:.2f}s, total {time.time() - t:.2f}s: {out}")
