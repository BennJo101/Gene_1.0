"""Parakeet TDT 0.6B speech-to-text with the same HTTP API as whisper-server, so Gene's client is unchanged:
POST /inference, multipart "file" (any audio ffmpeg reads), returns {"text": ...}.
Keeps one resident parakeet-serve process (model loaded once).

Runs on the Pi 5 CPU (gene-stt.service, localhost only) since 2026-10-02: moved off the Jetson so its memory goes
to a bigger LLM. Built from whisper.cpp 6e4ab85 in ~/gene-stt (see stt/README.md); q8_0 model, ~0.5-1 s a phrase,
same transcripts as the f16 model on the Jetson GPU."""
import email.parser, email.policy, json, os, re, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STT = os.path.expanduser("~/gene-stt")
MODEL = os.environ.get("PARAKEET_MODEL", os.path.join(STT, "models/ggml-parakeet-tdt-0.6b-v3-q8_0.bin"))
SERVE = os.environ.get("PARAKEET_SERVE", os.path.join(STT, "parakeet-serve"))
PORT = int(os.environ.get("PORT", "8081"))
HOST = os.environ.get("HOST", "127.0.0.1")
lock = threading.Lock()

# Parakeet v3 is multilingual and spells the robot's name the French way ("Jean"), or clips it to "G"/"Gee"
# at the start of a sentence. Nobody else in Gene's conversations is called Jean, so map these back.
NAME_FIXES = [(re.compile(r"\b(Jean|Jeanne|Gene)('s)?\b", re.I), lambda m: "Gene" + (m.group(2) or "")),
              (re.compile(r"(^|[.!?]\s+)(G|Gee|Ji|Jee)\b(?=,)"), lambda m: m.group(1) + "Gene")]


def fix_names(text):
    for pat, rep in NAME_FIXES:
        text = pat.sub(rep, text)
    return text
proc = subprocess.Popen([SERVE, MODEL, os.environ.get("THREADS", "4")], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, text=True, bufsize=1)
assert proc.stdout.readline().strip() == "READY", "parakeet-serve failed to start"


def transcribe(audio_bytes):
    with tempfile.NamedTemporaryFile(suffix=".in") as src, tempfile.NamedTemporaryFile(suffix=".f32") as raw:
        src.write(audio_bytes); src.flush()
        wav = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src.name, "-ar", "16000", "-ac", "1",
                              "-c:a", "pcm_f32le", "-f", "wav", "-"], check=True, capture_output=True).stdout
        i = wav.find(b"data", 12)                     # samples start after the data chunk header
        raw.write(wav[i + 8:]); raw.flush()
        with lock:
            proc.stdin.write(raw.name + "\n"); proc.stdin.flush()
            return fix_names(proc.stdout.readline().strip())


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.rstrip("/") != "/inference":
            return self.send_error(404)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body)
        audio = next((p.get_payload(decode=True) for p in msg.iter_parts() if p.get_param("name", header="content-disposition") == "file"), None)
        if audio is None:
            return self.send_error(400, "no file field")
        try:
            out = json.dumps({"text": transcribe(audio)}).encode()
        except Exception as e:
            return self.send_error(500, str(e))
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def do_GET(self):
        out = b"parakeet-tdt-0.6b-v3 (Gene STT)\n"
        self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a):
        pass


print(f"Parakeet STT on :{PORT} ({MODEL})", flush=True)
ThreadingHTTPServer((HOST, PORT), H).serve_forever()
