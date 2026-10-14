import json, time, urllib.request, re, uuid
def stt(path):
    b = uuid.uuid4().hex; data = open(path, "rb").read()
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n").encode() + data + \
           f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n--{b}--\r\n".encode()
    r = urllib.request.Request("http://192.168.0.37:8081/inference", body, {"Content-Type": f"multipart/form-data; boundary={b}"})
    return json.load(urllib.request.urlopen(r))["text"].strip()
for f in ["short.wav", "jfk.wav", "short.wav"]:
    t0 = time.perf_counter(); text = stt(f); t1 = time.perf_counter()
    body = {"model": "gene", "stream": True, "messages": [{"role": "user", "content": f"{text}\n(camera: person, laptop)"}]}
    req = urllib.request.Request("http://192.168.0.37:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    out = ""; 
    with urllib.request.urlopen(req) as r:
        for line in r:
            out += json.loads(line).get("message", {}).get("content", "")
            if re.search(r"[.!?](\s|$)", out): break
    t2 = time.perf_counter()
    print(f"{f}: STT {t1-t0:.2f}s + LLM first sentence {t2-t1:.2f}s = {t2-t0:.2f}s | heard: {text!r} -> Gene: {out.strip()!r}")
