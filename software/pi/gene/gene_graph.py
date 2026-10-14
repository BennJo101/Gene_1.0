"""Gene's knowledge graph: the things his memories name (people, pets, places, hobbies...) and how they're linked.

  - While the room is quiet, each remembered fact and conversation summary is turned into links by the Jetson model,
    one memory per request (~2 s): "Joshua's sister Amy plays the violin." -> Joshua -has sister-> Amy -plays-> violin.
    Both ends must be named in the memory; pronouns, numbers and vague words ("information") are dropped.
  - Every link keeps the memory it came from, so forgetting / correcting a fact removes its links too.
  - related(heard): facts linked to a thing that was just mentioned, up to two hops away ("how's Amy?" also brings
    "Amy plays the violin." when only "Joshua's sister Amy is 12." was close by embedding).
  - The graph is written out as an Obsidian vault, state/memory-vault/: one note per thing with [[wiki links]], so
    Obsidian's graph view draws it. Open that folder as a vault (or copy it: "put your memory vault on the USB").

Kept in state/graph.json (git-ignored, like the rest of the memory).
"""
import datetime, json, os, re, time, urllib.request
import gene_brain

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state")
GRAPH = os.path.join(STATE, "graph.json")
VAULT = os.path.join(STATE, "memory-vault")
RELATED_MAX = 3             # extra facts a turn can get from the graph

LINKS = """You turn one memory of Gene (a talking robot head) into knowledge-graph links between the things it names:
people, pets, places, objects, projects, hobbies, foods, events. Each link is {"from": thing, "relation": short verb
phrase, "to": thing}. Examples:
"Joshua's dog Max loves tennis balls." -> {"from": "Joshua", "relation": "has dog", "to": "Max"}, {"from": "Max", "relation": "loves", "to": "tennis balls"}
"Sam's dad works at a bakery in York." -> {"from": "Sam", "relation": "has dad", "to": "Sam's dad"}, {"from": "Sam's dad", "relation": "works at", "to": "bakery"}, {"from": "bakery", "relation": "is in", "to": "York"}
Use names (1-3 words) exactly as written in the memory. Only links the memory says; none if it names fewer than two things."""
SCHEMA = {"type": "object", "required": ["links"], "properties": {"links": {"type": "array", "items": {
    "type": "object", "required": ["from", "relation", "to"],
    "properties": {"from": {"type": "string"}, "relation": {"type": "string"}, "to": {"type": "string"}}}}}}
VAGUE = {"he", "she", "him", "her", "himself", "herself", "it", "they", "them", "you", "i", "me", "we", "us", "someone",
         "something", "thing", "things", "information", "stuff", "conversation", "question", "questions", "way",
         "capabilities", "solution", "request", "person", "people"}
ARTICLE = re.compile(r"^(?:a|an|the|his|her|their|its|my|your|some)\s+", re.I)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _key(name):
    """Merge key: "The Amplifiers" and "amplifier" are one thing."""
    k = re.sub(r"[^a-z0-9' ]+", " ", ARTICLE.sub("", name.strip()).lower()).strip()
    return re.sub(r"(?<=[a-z]{3})s$", "", k)


def _named(name, text):
    """Each word of the name is in the memory (plural or not)."""
    words = set(re.findall(r"[a-z0-9']+", text.lower()))
    words |= {w.removesuffix("'s") for w in words} | {w.rstrip("s") for w in words}
    return all(w in words or w.rstrip("s") in words for w in re.findall(r"[a-z0-9']+", name.lower()))


def clean(links, text, gene_names=("you", "gene")):
    """The model's links, kept only if both ends are real things named in the memory."""
    out = []
    for l in links:
        if not isinstance(l, dict):
            continue
        a, rel, b = (str(l.get(k, "")).strip(" .,\"'") for k in ("from", "relation", "to"))
        a, b = ARTICLE.sub("", a), ARTICLE.sub("", b)
        a, b = ("Gene" if x.lower() in gene_names else x for x in (a, b))
        rel = re.sub(r"\s+", " ", rel.lower())[:40]
        if not (a and b and rel) or _key(a) == _key(b) or len(a) > 40 or len(b) > 40:
            continue
        if re.match(r"(?:is|are|was|were|be|to)\b", b, re.I):
            continue        # "Gene -claims-> is finished"
        if {a.lower(), b.lower()} & VAGUE or any(re.fullmatch(r"[\d\s.,%]+", x) for x in (a, b)):
            continue
        if not (a == "Gene" or _named(a, text)) or not (b == "Gene" or _named(b, text)):
            continue
        if (a, rel, b) not in [(x["from"], x["rel"], x["to"]) for x in out]:
            out.append({"from": a, "rel": rel, "to": b})
    return out


class Graph:
    def __init__(self, path=GRAPH, vault=VAULT):
        self.path, self.vault = path, vault
        self.links = []         # [{"from", "rel", "to", "memory": text it came from}]
        self.done = []          # memory texts already turned into links (some give none)
        try:
            d = json.load(open(path))
            self.links, self.done = d["links"], d["done"]
        except (OSError, ValueError, KeyError):
            pass

    def _save(self):
        with open(self.path + ".tmp", "w") as f:
            json.dump({"links": self.links, "done": self.done}, f, indent=1)
        os.replace(self.path + ".tmp", self.path)

    @staticmethod
    def extract(text, timeout=60):
        """The links one memory states (gene_brain: Claude, else the Jetson; ~2-5 s)."""
        messages = [{"role": "system", "content": LINKS}, {"role": "user", "content": text}]
        out = json.loads(gene_brain.complete(messages, schema=SCHEMA, max_tokens=300, timeout=timeout,
                                             options={"temperature": 0, "num_predict": 300}))
        return clean(out.get("links", []), text)

    def todo(self, memories):
        done = set(self.done)
        return [m["text"] for m in memories if m["text"] not in done]

    def sync(self, memories, may_continue=lambda: True, most=5):
        """Drops the links of forgotten memories, links up to `most` new ones (stopping early if may_continue() turns
        False, e.g. someone speaks) and rewrites the vault. `memories` = Memory.facts. Returns how many it linked."""
        texts = {m["text"] for m in memories}
        changed = len(self.links) + len(self.done)
        self.links = [l for l in self.links if l["memory"] in texts]
        self.done = [t for t in self.done if t in texts]
        changed = changed != len(self.links) + len(self.done)
        n = 0
        for text in self.todo(memories)[:most]:
            if not may_continue():
                break
            try:
                links = self.extract(text)
            except ValueError as e:     # a garbled reply (the 3B model can repeat itself until cut off): it would again
                log(f"graph: no links for {text!r}, reply unreadable:", e)
                links = []
            except Exception as e:
                log("graph: linking failed, will retry:", e)
                break
            self.links += [dict(l, memory=text) for l in links]
            self.done.append(text); n += 1; changed = True
            log(f"graph: {text!r} -> " + ("; ".join(f"{l['from']} -{l['rel']}-> {l['to']}" for l in links) or "no links"))
        if changed:
            self._save()
            try:
                self.write_vault(memories)
            except OSError as e:
                log("graph: couldn't write the vault:", e)
        return n

    # ---- recall ----
    def names(self):
        """{key: display name} of every thing in the graph."""
        out = {}
        for l in self.links:
            for x in (l["from"], l["to"]):
                out.setdefault(_key(x), x)
        return out

    def related(self, heard, skip=()):
        """Memories linked to the things mentioned in `heard`, nearest first (1 hop, then 2). `skip`: names not to
        start from (Gene and the speaker - linked to nearly everything)."""
        said = " " + " ".join(re.findall(r"[a-z0-9']+", heard.lower())) + " "
        said_keys = " " + " ".join(_key(w) for w in said.split()) + " "
        skip = {_key(s) for s in skip} | {"gene"}
        seeds = {k for k in self.names() if k not in skip and len(k) >= 3 and (f" {k} " in said or f" {k} " in said_keys)}
        for l in self.links:        # "my sister" -> the link "Joshua -has sister-> Amy" starts from Amy
            m = re.fullmatch(r"has (?:a |an )?(\w+(?: \w+)?)", l["rel"])
            if m and _key(l["from"]) in skip and f" {_key(m.group(1))} " in said_keys:
                seeds.add(_key(l["to"]))
        out, frontier = [], set(seeds)
        for _ in range(2):
            nxt = set()
            for l in self.links:
                a, b = _key(l["from"]), _key(l["to"])
                if a in frontier or b in frontier:
                    if l["memory"] not in out:
                        out.append(l["memory"])
                    nxt |= {a, b}
            frontier = nxt - seeds - skip
            seeds |= nxt
        return out

    # ---- Obsidian vault ----
    def write_vault(self, memories):
        """One note per thing: its links as [[wiki links]] and the memories that name it. Notes Gene wrote before
        are replaced; anything else in the folder (e.g. Obsidian's .obsidian settings) is left alone."""
        os.makedirs(self.vault, exist_ok=True)
        names = self.names()
        when = {m["text"]: m for m in memories}
        notes = {}
        def note(x):
            k = _key(x)
            return notes.setdefault(k, {"name": names.get(k, x), "out": [], "in": [], "mem": []})
        for l in self.links:
            a, b = note(l["from"]), note(l["to"])
            a["out"].append((l["rel"], b["name"])); b["in"].append((a["name"], l["rel"]))
            for n in (a, b):
                if l["memory"] not in n["mem"]:
                    n["mem"].append(l["memory"])
        files = {}
        for n in notes.values():
            body = [f"---\ntags: [gene-memory]\n---\n# {n['name']}\n"]
            if n["out"]:
                body += ["## Links"] + [f"- {r} [[{_file(b)}|{b}]]" for r, b in dict.fromkeys(n["out"])] + [""]
            if n["in"]:
                body += ["## Linked from"] + [f"- [[{_file(a)}|{a}]] {r}" for a, r in dict.fromkeys(n["in"])] + [""]
            body += ["## Memories"]
            for t in n["mem"]:
                m = when.get(t, {})
                kind = "conversation" if m.get("kind") == "summary" else "fact"
                body.append(f"- {t} *({kind}, {m.get('time', '?')[:10]})*")
            files[_file(n["name"]) + ".md"] = "\n".join(body) + "\n"
        top = sorted(notes.values(), key=lambda n: -(len(n["out"]) + len(n["in"])))
        files["Gene's memory.md"] = ("---\ntags: [gene-memory]\n---\n# Gene's memory\n\nWhat Gene the robot head remembers, "
            f"as a graph: {len(notes)} things, {len(self.links)} links, from {len(self.done)} memories. "
            f"Written {datetime.datetime.now():%Y-%m-%d %H:%M}. Open the graph view to see it.\n\n"
            + "\n".join(f"- [[{_file(n['name'])}|{n['name']}]] ({len(n['out']) + len(n['in'])} links)" for n in top) + "\n")
        mine = os.path.join(self.vault, ".gene-notes")
        try:
            old = set(json.load(open(mine)))
        except (OSError, ValueError):
            old = set()
        for f in old - set(files):
            try:
                os.remove(os.path.join(self.vault, f))
            except OSError:
                pass
        for f, text in files.items():
            with open(os.path.join(self.vault, f), "w") as fh:
                fh.write(text)
        with open(mine, "w") as fh:
            json.dump(sorted(files), fh)


def _file(name):
    """A note's file name (and [[link]] target): no characters Obsidian or the file system refuse."""
    return re.sub(r"[\\/:*?\"<>|#^\[\]]+", " ", name).strip() or "thing"


if __name__ == "__main__":      # link all memories now and write the vault: ./venv/bin/python gene_graph.py
    g = Graph()
    mems = json.load(open(os.path.join(STATE, "memory.json")))
    while g.sync(mems, most=50):
        pass
    print(f"{len(g.names())} things, {len(g.links)} links -> {VAULT}")
