"""Gene's long-term memory: what he has learned about people, kept across restarts.

  - Every exchange is appended to state/conversations.jsonl (the full transcript, never trimmed).
  - When the room has been quiet for a while, the new part of the conversation is "consolidated": the Jetson
    model pulls out durable facts ("Joshua's sister Amy is 12.") and a one-line summary of what was talked
    about. Done while idle because the side request costs the Jetson its cached chat prompt.
  - "Remember that ..." stores a fact straight away; "forget ..." removes the closest one.
  - Each turn, recall(heard) picks the few facts most related to what was just said (MiniLM sentence
    embeddings, on the Pi's CPU in ~7 ms) and gene_client adds them as a "(memory: ...)" line.
  - The facts and summaries are also linked up into a knowledge graph while idle (gene_graph.py, state/graph.json),
    which brings in facts about the things just mentioned and is written out as an Obsidian vault (state/memory-vault/).
  - The recent chat history is saved too, so a restart (e.g. after an upgrade) doesn't lose the thread.

Everything lives in state/ (git-ignored), so an upgrade rollback never erases what Gene remembers.
"""
import datetime, json, os, re, threading, time, urllib.request
import gene_brain
import numpy as np
import gene_graph

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
FACTS = os.path.join(STATE, "memory.json")
TRANSCRIPT = os.path.join(STATE, "conversations.jsonl")
HISTORY = os.path.join(STATE, "history.json")
PENDING = os.path.join(STATE, "unconsolidated.json")
WRONG = os.path.join(STATE, "corrected.json")   # facts the person said were wrong or asked to forget: never re-learned
MODEL_DIR = os.path.join(HERE, "models", "minilm")

RECALL_K = 4                # facts added to a turn
GRAPH_K = 2                 # more facts from the knowledge graph (about the things just mentioned)
RECALL_MIN = 0.30           # cosine similarity a fact needs to count as related
SAME_FACT = 0.86            # a new fact this close to an old one replaces it
GENE_SAID = 0.05           # not closer (by this margin) to something Gene said: that's his answer echoed back
HISTORY_FRESH = 30 * 60     # s; saved chat history older than this is not resumed
SUMMARIES_SHOWN = 2         # past-conversation summaries offered when asked "what did we talk about?"
DEFAULT_SPEAKER = os.environ.get("GENE_OWNER", "Joshua")
SPEAKER_RESET = 10 * 60     # s of silence after which the speaker is assumed to be the owner again

EXTRACT = """You keep the long-term memory of Gene, a talking robot head. The person talking to Gene here is {speaker}.
First write a one-sentence summary of the conversation. Then list every personal fact {speaker} shared that would
be worth knowing next week: names, family, friends, pets, likes and dislikes, job, school, plans and their dates,
important dates, projects, and requests about how Gene should behave.
Write each fact as one short stand-alone sentence in the third person that names the person, for example
"{speaker}'s dog is called Max." or "{speaker} is allergic to peanuts." Never use "I", "my" or "you".
Leave out greetings, small talk, things only Gene said, general knowledge and answers to questions, and facts
listed under "Already known"."""
SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"},      # summary first: it gets the model
                                           "facts": {"type": "array", "items": {"type": "string"}}},   # to read it all
          "required": ["summary", "facts"]}
# the 3B model pads its list with non-facts about the conversation itself
JUNK = re.compile(r"\b(?:asked|asks|asking|inquired|wondered|wants\s+to\s+know|not\s+mentioned|does\s+not\s+know|"
                  r"doesn't\s+know|is\s+curious|joke|greeted|said\s+(?:hi|hello)|talked\s+(?:to|with)\s+Gene)\b", re.I)
GROUNDED = 0.38             # a fact must be this close to something the person said (not asked)...
CLEARLY_SAID = 0.50         # ...and if it's only loosely grounded,
CALENDAR = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February",
            "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"}
CONTRADICTED = 0.50         # "my mother's not Asian" vs "Joshua's mother is Asian." is ~0.6; unrelated lines < 0.25
# a correction: "my mother's not Asian", "she doesn't do writing", "that's wrong", "no, I never said that"
NEGATION = re.compile(r"\b(?:not|never|no|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|haven't|hasn't|wrong|"
                      r"untrue|false|incorrect|neither|nor)\b|n't\b", re.I)
# ...that points at what Gene just said rather than naming it
YOU_GOT_IT_WRONG = re.compile(r"\b(?:that's|that\s+is|that\s+was|you're|you\s+are|you\s+got\s+(?:that|it))\s+"
                              r"(?:not\s+(?:true|right|correct)|wrong|incorrect|false|untrue|made\s+up)\b|"
                              r"\bI\s+never\s+(?:said|told\s+you)\b", re.I)

# "remember that my sister is Amy" / "please remember I like jazz" / "don't forget my birthday is May 3rd"
REMEMBER = re.compile(r"\b(?:please\s+)?(?:remember|don't\s+forget|do\s+not\s+forget|make\s+a\s+note|note\s+down|"
                      r"keep\s+in\s+mind)\s+(?:that\s+|this\s*:?\s+)?(.{4,})", re.I)
# "forget that my sister is Amy" / "forget about the party" - but not "don't forget ..."
FORGET = re.compile(r"(?<!don't\s)(?<!not\s)\bforget\s+(?:that\s+|about\s+)?(.{3,})", re.I)
FORGET_ALL = re.compile(r"\bforget\s+every\s?thing\b", re.I)
# "what do you know about me" / "what do you remember" - show the newest facts, not just the related ones
ASK_MEMORY = re.compile(r"\bwhat\s+(?:do|did|else\s+do)\s+you\s+(?:know|remember)\b|\bdo\s+you\s+remember\b|"
                        r"\bwhat\s+(?:have\s+you|did\s+you)\s+(?:learn|learned)\b|\bwhat\s+did\s+we\s+(?:talk|chat)", re.I)
# "remember when", "remember me?" are questions, not things to store
NOT_A_NOTE = re.compile(r"^(?:when|what|who|me|us|him|her|it|that|this|how|where|why|if)\b", re.I)
# "my name is Amy" / "this is Amy" / "I'm Amy." / "It's Amy here" - who Gene is talking to (STT capitalises names)
NAME = re.compile(r"\b(?i:my\s+name\s+is|my\s+name's|call\s+me)\s+([A-Z][a-z]+)\b|"
                  r"\b(?i:this\s+is)\s+([A-Z][a-z]+)\s+(?i:speaking|here)\b|"
                  r"(?:^|[.!?]\s+)(?:(?i:hi|hey|hello)\b)?[,\s]*(?:I'm|I\s+am|(?i:it's))\s+([A-Z][a-z]+)(?:\s+here)?\s*(?:[.!,]|$)")
NOT_NAMES = {"Gene", "Jean", "Fine", "Good", "Okay", "Ok", "Sorry", "Here", "Back", "Done", "Sure", "Just", "Not",
             "So", "Very", "Really", "American", "English", "Canadian", "British", "Mexican", "Ready", "Tired", "Home"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Embedder:
    """all-MiniLM-L6-v2 sentence embeddings with onnxruntime on the Pi's CPU."""

    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
        self.tok.enable_truncation(128); self.tok.enable_padding()
        opts = ort.SessionOptions(); opts.intra_op_num_threads = 2     # leave cores for Piper and the mic
        self.s = ort.InferenceSession(os.path.join(MODEL_DIR, "model.onnx"), opts, providers=["CPUExecutionProvider"])

    def __call__(self, texts):
        if not texts:
            return np.zeros((0, 384), np.float32)
        enc = self.tok.encode_batch(list(texts))
        ids = np.array([e.ids for e in enc], np.int64)
        mask = np.array([e.attention_mask for e in enc], np.int64)
        out = self.s.run(None, {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)})[0]
        v = (out * mask[..., None]).sum(1) / mask.sum(1, keepdims=True)
        return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float32)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _when(iso):
    """'earlier today' / 'yesterday' / 'on Tuesday' / 'on September 3' for a saved timestamp."""
    d = datetime.datetime.fromisoformat(iso).date()
    days = (datetime.date.today() - d).days
    if days <= 0:
        return "earlier today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return "on " + d.strftime("%A")
    return "on " + d.strftime("%B ") + str(d.day)


def _parse(content):
    """The consolidation reply. The 3B model sometimes repeats a fact until it runs out of tokens, which leaves the
    JSON unterminated (and retrying gives the same reply forever) - keep the complete strings from such a reply."""
    try:
        return json.loads(content)
    except ValueError:
        summary = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', content)
        facts = content.split('"facts"', 1)
        if not summary or len(facts) < 2:
            raise
        found = [json.loads(f'"{f}"') for f in re.findall(r'"((?:[^"\\]|\\.)*)"\s*[,\]]', facts[1])]
        log(f"memory: consolidation reply was cut off, kept {len(set(found))} complete facts")
        return {"summary": json.loads(f'"{summary.group(1)}"'), "facts": list(dict.fromkeys(found))}


class Memory:
    def __init__(self):
        os.makedirs(STATE, exist_ok=True)
        self.lock = threading.RLock()
        self.embed = Embedder()
        self.facts = []         # [{"text", "time", "kind": "fact" | "summary", "src": "told" | "learned"}]
        if os.path.exists(FACTS):
            try:
                self.facts = json.load(open(FACTS))
            except (OSError, ValueError) as e:
                log("memory file unreadable, starting fresh:", e)
                os.replace(FACTS, FACTS + f".bad-{int(time.time())}")
        try:
            self.wrong = json.load(open(WRONG))
        except (OSError, ValueError):
            self.wrong = []
        self.wrong_vecs = self.embed(self.wrong)
        self.vecs = self.embed([f["text"] for f in self.facts])
        if len(self.wrong) and len(self.facts):      # e.g. written back by an older Gene that hadn't heard the correction
            bad = [i for i in range(len(self.facts)) if self.facts[i]["kind"] == "fact" and self._is_wrong(self.vecs[i])]
            for i in reversed(bad):
                log(f"memory: dropping corrected fact {self.facts[i]['text']!r}")
                del self.facts[i]; self.vecs = np.delete(self.vecs, i, 0)
            if bad:
                self._save()
        self.speaker = DEFAULT_SPEAKER
        self.last_fact = self.last_exchange = 0.0
        self.pending = []       # exchanges not yet consolidated, kept on disk so a restart doesn't drop them
        try:
            self.pending = [tuple(p) for p in json.load(open(PENDING))]
        except (OSError, ValueError):
            pass
        self.last_heard = time.time()
        self.recalled = []      # facts offered on the last turn, so "that's wrong" knows what it refers to
        self.graph = gene_graph.Graph()
        log(f"memory: {sum(f['kind'] == 'fact' for f in self.facts)} facts, "
            f"{sum(f['kind'] == 'summary' for f in self.facts)} conversation summaries")

    # ---- storage ----
    def _save_pending(self):
        with open(PENDING + ".tmp", "w") as f:
            json.dump(self.pending, f)
        os.replace(PENDING + ".tmp", PENDING)

    def _save(self):
        tmp = FACTS + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.facts, f, indent=1)
        os.replace(tmp, FACTS)

    def _is_wrong(self, v):
        return bool(len(self.wrong)) and float((self.wrong_vecs @ v).max()) >= SAME_FACT

    def _mark_wrong(self, texts):
        """Remembers that these facts are wrong, so consolidation can't learn them again."""
        self.wrong = (self.wrong + list(texts))[-200:]
        self.wrong_vecs = self.embed(self.wrong)
        with open(WRONG + ".tmp", "w") as f:
            json.dump(self.wrong, f, indent=1)
        os.replace(WRONG + ".tmp", WRONG)

    def add(self, text, kind="fact", src="learned"):
        """Stores a fact; one that says nearly the same as an old one replaces it (newest wins)."""
        text = text.strip()
        if not text:
            return
        v = self.embed([text])
        with self.lock:
            if kind == "fact" and src != "told" and self._is_wrong(v[0]):
                log(f"memory: not re-learning corrected fact {text!r}")
                return
            if len(self.facts):     # a fact (or a summary) that says nearly the same as an old one replaces it
                sims = self.vecs @ v[0]
                for i in np.argsort(-sims):
                    if sims[i] < SAME_FACT:
                        break
                    if self.facts[i]["kind"] == kind:
                        log(f"memory: replacing {self.facts[i]['text']!r}")
                        del self.facts[i]; self.vecs = np.delete(self.vecs, i, 0)
                        break
            self.facts.append({"text": text, "time": _now(), "kind": kind, "src": src})
            self.last_fact = time.time()
            self.vecs = np.vstack([self.vecs, v])
            self._save()
        log(f"memory: + {kind} {text!r}")

    def forget(self, what):
        """Removes the fact closest to `what`; returns its text, or None if nothing is close enough."""
        v = self.embed([what])[0]
        with self.lock:
            idx = [i for i, f in enumerate(self.facts) if f["kind"] == "fact"]
            if not idx:
                return None
            sims = self.vecs[idx] @ v
            best = idx[int(sims.argmax())]
            if sims.max() < 0.45:
                return None
            gone = self.facts.pop(best)["text"]; self.vecs = np.delete(self.vecs, best, 0)
            self._save(); self._mark_wrong([gone])
        log(f"memory: forgot {gone!r}")
        return gone

    def forget_last(self):
        """ "Forget that." - drops what was just said if it isn't consolidated yet, else the newest fact."""
        with self.lock:
            if self.pending and self.last_exchange > self.last_fact:
                gone = self.pending.pop()[0]; self._save_pending()
                log(f"memory: won't remember {gone!r}")
                return gone
            idx = [i for i, f in enumerate(self.facts) if f["kind"] == "fact"]
            if not idx:
                return None
            gone = self.facts.pop(idx[-1])["text"]; self.vecs = np.delete(self.vecs, idx[-1], 0)
            self._save()
        log(f"memory: forgot {gone!r}")
        return gone

    def forget_all(self):
        with self.lock:
            if os.path.exists(FACTS):
                os.replace(FACTS, FACTS + f".forgotten-{int(time.time())}")   # kept on disk, just not used
            self.facts, self.vecs = [], self.embed([])
            self._save()
            self.graph.sync([])

    # ---- each turn ----
    def hear(self, heard):
        """Call first for every line heard: notices who is talking. Returns the speaker's name."""
        if time.time() - self.last_heard > SPEAKER_RESET:
            self.speaker = DEFAULT_SPEAKER
        m = NAME.search(heard)
        name = m and (m.group(1) or m.group(2) or m.group(3))
        if name and name not in NOT_NAMES and name != self.speaker:
            log(f"memory: now talking to {name}")
            with self.lock:     # the conversation so far was with the previous speaker
                convo, self.pending = self.pending, []
            if convo:
                threading.Thread(target=self.consolidate, args=(convo, self.speaker), daemon=True).start()
            self.speaker = name
        self.last_heard = time.time()
        return self.speaker

    def command(self, heard):
        """Handles "remember that ..." / "forget ..." itself; returns what Gene should say, or None."""
        if FORGET_ALL.search(heard) and re.search(r"\b(me|us|everything)\b", heard, re.I):
            self.forget_all()
            return "Okay. I've forgotten everything I knew about you."
        m = REMEMBER.search(heard)
        if m and not NOT_A_NOTE.match(m.group(1)) and not heard.rstrip().endswith("?"):
            note = re.sub(r"^\s*(?:that|this)\s+", "", m.group(1)).strip().rstrip(".!, ")
            self.add(f'{self.speaker} told you: "{note}."', src="told")
            return "Got it. I'll remember that."
        m = FORGET.search(heard)
        if m and not re.search(r"\b(?:did|do|don't|never|not)\s+(?:you\s+)?forget\b|\bforget\s+(?:it|about\s+it)\s*[.!]?$", heard, re.I):
            what = m.group(1).strip(" .!?,")
            gone = self.forget_last() if re.fullmatch(r"(?i)(?:that|this|it|what\s+I\s+(?:just\s+)?said)", what) else self.forget(what)
            return "Okay, I've forgotten that." if gone else "I don't think I had that remembered anyway."
        return None

    def correct(self, heard, gene_said=""):
        """Drops remembered facts the person just said are wrong; returns their texts ([] if none).

        "My mother's not Asian." removes "Joshua's mother is of Asian race." (a negated line that is close to a
        fact). "That's wrong." / "I never said that." removes the facts offered last turn that Gene's reply used.
        """
        if not NEGATION.search(heard):
            return []
        parts = [c for c in [heard] + re.split(r"[.;!?]+\s*|,\s*(?:and|but)?\s*|\s+(?:and|but)\s+", heard)
                 if len(c) > 3 and NEGATION.search(c)]
        with self.lock:
            idx = [i for i, f in enumerate(self.facts) if f["kind"] == "fact"]
            if not idx:
                return []
            sims = (self.vecs[idx] @ self.embed(parts).T).max(1)
            wrong = {idx[j] for j in range(len(idx)) if sims[j] >= CONTRADICTED}
            if YOU_GOT_IT_WRONG.search(heard) and self.recalled and gene_said:
                said = self.embed([c for c in [gene_said] + re.split(r"[.,;!?]+\s*", gene_said) if len(c) > 3])
                for i in idx:
                    if self.facts[i]["text"] in self.recalled and float((said @ self.vecs[i]).max()) >= GROUNDED + 0.07:
                        wrong.add(i)
            gone = [self.facts[i]["text"] for i in sorted(wrong)]
            for i in sorted(wrong, reverse=True):
                del self.facts[i]; self.vecs = np.delete(self.vecs, i, 0)
            if gone:
                self._save(); self._mark_wrong(gone)
                self.recalled = [t for t in self.recalled if t not in gone]
        for t in gone:
            log(f"memory: corrected, forgot {t!r}")
        return gone

    def recall(self, heard):
        """The "(memory: ...)" line for this turn, or "" if nothing related is remembered."""
        with self.lock:
            if not self.facts:
                return ""
            is_fact = np.array([f["kind"] == "fact" for f in self.facts])
            sims = self.vecs @ self.embed([heard])[0]
            if ASK_MEMORY.search(heard):          # "what do you know about me?" - the newest facts, related first
                picks = [i for i in np.argsort(-sims) if is_fact[i]][:RECALL_K]
                picks += [i for i in range(len(self.facts) - 1, -1, -1) if is_fact[i] and i not in picks][:8 - len(picks)]
            else:
                picks = [i for i in np.argsort(-sims) if is_fact[i] and sims[i] >= RECALL_MIN][:RECALL_K]
            linked = self.graph.related(heard, skip=(self.speaker, DEFAULT_SPEAKER))
            where = {f["text"]: i for i, f in enumerate(self.facts) if f["kind"] == "fact"}
            picks += [i for i in (where[t] for t in linked if t in where) if i not in picks][:GRAPH_K]
            said = [self.facts[i]["text"] + self._noted(i) for i in picks]
            self.recalled = [self.facts[i]["text"] for i in picks]
            # past conversations: a closely related one, or the last few when asked what you talked about
            summ = [i for i in np.argsort(-sims) if not is_fact[i] and sims[i] >= RECALL_MIN + 0.15][:1]
            if re.search(r"\b(last time|yesterday|earlier|talk(?:ed)? about|chat(?:ted)? about|we\s+discuss)", heard, re.I):
                summ += [i for i in range(len(self.facts) - 1, -1, -1) if not is_fact[i] and i not in summ][:SUMMARIES_SHOWN]
            said += [f"{_when(self.facts[i]['time']).capitalize()} you talked about: {self.facts[i]['text']}" for i in summ]
        if not said:
            return f"(memory: you are talking to {self.speaker}.)" if self.speaker != DEFAULT_SPEAKER else ""
        text = " ".join(s if s.endswith((".", "!", "?", '"')) else s + "." for s in said)
        return (f"(memory: you are talking to {self.speaker}. Things you remember from before, use them only if they help, "
                "exactly as written - never add details to them: "
                + text.replace("(", "[").replace(")", "]") + ")")

    def _noted(self, i):
        """ " [noted yesterday]" for an older fact, so "on Friday" can be placed in time."""
        d = datetime.datetime.fromisoformat(self.facts[i]["time"]).date()
        return "" if d == datetime.date.today() else f" [noted {_when(self.facts[i]['time']).removeprefix('on ')}]"

    def exchange(self, heard, said):
        """Logs one exchange to the transcript and queues it for consolidation."""
        self.last_heard = self.last_exchange = time.time()
        with open(TRANSCRIPT, "a") as f:     # synced: a power cut on 2026-10-04 lost the last lines (NULs instead)
            f.write(json.dumps({"time": _now(), "speaker": self.speaker, "user": heard, "gene": said}) + "\n")
            f.flush(); os.fsync(f.fileno())
        with self.lock:
            self.pending.append((heard, said)); self._save_pending()

    # ---- chat history across restarts ----
    @staticmethod
    def save_history(history):
        tmp = HISTORY + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"time": time.time(), "history": history}, f)
        os.replace(tmp, HISTORY)

    @staticmethod
    def load_history():
        try:
            d = json.load(open(HISTORY))
            return d["history"] if time.time() - d["time"] < HISTORY_FRESH else []
        except (OSError, ValueError, KeyError):
            return []

    # ---- consolidation, while idle ----
    def consolidate(self, convo=None, speaker=None):
        """Turns the queued exchanges (or `convo`) into facts and a summary. Returns True if it ran."""
        speaker = speaker or self.speaker
        if convo is None:
            with self.lock:
                convo, self.pending = self.pending, []
        if not convo:
            return False
        with self.lock:
            known = [f["text"] for f in self.facts if f["kind"] == "fact"][-40:]
        text = ("Already known:\n" + ("\n".join("- " + k for k in known) or "- nothing yet") + "\n\nConversation:\n" +
                "\n".join(f"{speaker}: {h}\nGene: {s}" for h, s in convo))
        messages = [{"role": "system", "content": EXTRACT.format(speaker=speaker)}, {"role": "user", "content": text}]
        try:    # gene_brain: Claude, else the Jetson
            out = _parse(gene_brain.complete(messages, schema=SCHEMA, max_tokens=500, timeout=120,
                                             options={"temperature": 0, "num_predict": 500}))
        except Exception as e:
            log("memory: consolidation failed, will retry:", e)
            with self.lock:
                self.pending = convo + self.pending
            return False
        finally:
            with self.lock:
                self._save_pending()
        def clauses(lines):     # long lines dilute an embedding, so compare against their parts too
            return [c for l in lines for c in [l] + re.split(r"[.,;!?]+\s*|\s+(?:and|but|so|because)\s+", l) if len(c) > 3]
        user_vecs = self.embed(clauses(h for h, _ in convo if not h.rstrip().endswith("?")))   # questions state nothing
        gene_vecs = self.embed(clauses(s for _, s in convo))
        heard_words = set(re.findall(r"[a-z0-9]+", " ".join(h for h, _ in convo).lower()))
        seen = set()
        for fact in out.get("facts", [])[:12]:
            if not isinstance(fact, str) or len(fact) < 8 or JUNK.search(fact) or fact.strip().lower() in seen:
                continue            # the model sometimes lists the same fact twice
            seen.add(fact.strip().lower())
            v = self.embed([fact])[0]
            user = float((user_vecs @ v).max()) if len(user_vecs) else 0.0
            gene = float((gene_vecs @ v).max()) if len(gene_vecs) else 0.0
            if user < GROUNDED or (user < CLEARLY_SAID and gene > user + GENE_SAID):
                log(f"memory: skipping {fact!r} (heard {user:.2f}, Gene said {gene:.2f})")
                continue
            if new := self._unsaid_names(fact, heard_words, speaker):
                log(f"memory: skipping {fact!r} ({', '.join(new)} never said)")
                continue
            self.add(fact)
        if len(convo) >= 2 and isinstance(out.get("summary"), str) and out["summary"].strip():
            self.add(out["summary"], kind="summary")
        return True

    @staticmethod
    def _unsaid_names(fact, heard_words, speaker):
        """Names, places, nationalities... (capitalised words) in a fact that the person never said.
        "Mother being little by race." (misheard) became "Joshua's mother is of Asian race." - "Asian" was never said."""
        words = re.findall(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]+)", fact)
        return [w for w in words if w.lower() not in heard_words and w not in (speaker, "Gene", "I") and w not in CALENDAR
                and not w.lower().rstrip("s") in heard_words]

    def idle_loop(self, busy, idle_after=45):
        """Background thread: consolidates once nobody has spoken for `idle_after` s and Gene isn't talking, then
        links new memories into the knowledge graph (and drops the links of forgotten ones)."""
        quiet = lambda: time.time() - self.last_heard > idle_after and not busy()
        while True:
            time.sleep(5)
            if self.pending and quiet():
                log(f"memory: consolidating {len(self.pending)} exchanges")
                self.consolidate()
            elif quiet():
                with self.lock:
                    facts = list(self.facts)
                texts = {f["text"] for f in facts}
                if self.graph.todo(facts) or any(t not in texts for t in self.graph.done):
                    self.graph.sync(facts, may_continue=lambda: quiet() and not self.pending)

    def flush(self):
        """Consolidates whatever is left (on shutdown)."""
        if self.pending:
            self.consolidate()
