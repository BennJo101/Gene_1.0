"""Is a phrase someone talking, or just noise? (asked by voice 2026-10-06: "differentiate random noise from
actually being talked to")

The energy VAD in gene_client cuts out anything loud - a knock, a chair, the fan, a cough - and Parakeet turns that
into "Mm.", "Uh", "Okay." which Gene then answered ("Easy one."). Two checks now sit in front of the model:
  1. `voiced(pcm)`: Silero VAD (models/silero_vad/silero_vad.onnx, ~2 MB, from the silero-vad pip wheel's
     src/silero_vad/data/) - how many seconds of the phrase are a human voice. Below MIN_VOICE it never goes to STT.
  2. `ignore(heard, since_gene_spoke)`: a transcript that is only a filler sound ("mm", "hmm", "uh") is dropped,
     and a lone "okay" / "yeah" is only answered right after Gene said something (ACK_WINDOW) - out of nowhere it is
     someone talking to someone else, or noise.
Without the model file check 1 lets everything through (the old behaviour).
Test: ./venv/bin/python gene_vad.py file.wav
"""
import os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "models", "silero_vad", "silero_vad.onnx")
SR = 16000
CHUNK, CONTEXT = 512, 64    # Silero v5 at 16 kHz: 32 ms chunks, each with the last 64 samples of the one before
SPEECH_P = 0.5              # a chunk is voice above this probability
MIN_VOICE = 0.15            # s of voice a phrase needs to be sent to STT
ACK_WINDOW = 20             # s after Gene stops talking that a lone "okay" / "yeah" is still a reply to him

# just a sound, never words to answer
FILLER = re.compile(r"\W*(?:(?:u+h+|u+m+|m+|h?m+h?|hm+|a+h+|e+r+|o+h+|huh|mhm|uh-?oh|eh|ha|ooh|aw+)\W*)+", re.I)
# a lone acknowledgement: fine as a reply, not out of nowhere
ACK = re.compile(r"\W*(?:yeah|yep|yup|yes|no|nope|right|okay|ok|cool|nice|sure|alright|all\s+right|mm-?hmm|uh-?huh|"
                 r"true|exactly|word|bet|got\s+it|for\s+sure|totally|sweet|awesome|wow|sorry|thanks|thank\s+you)"
                 r"(?:[\s,.!]+(?:yeah|man|bro|dude|okay|ok|cool|nice|right|thanks))*\W*", re.I)


class Silero:
    def __init__(self):
        import onnxruntime as ort
        opts = ort.SessionOptions(); opts.intra_op_num_threads = 1; opts.inter_op_num_threads = 1
        self.s = ort.InferenceSession(MODEL, opts, providers=["CPUExecutionProvider"])

    def probs(self, pcm):
        """Voice probability for each 32 ms chunk of int16 or float audio at 16 kHz."""
        x = pcm.astype(np.float32) / (32768 if pcm.dtype == np.int16 else 1)
        state, ctx, sr, out = np.zeros((2, 1, 128), np.float32), np.zeros(CONTEXT, np.float32), np.array(SR, np.int64), []
        for i in range(0, len(x) - CHUNK + 1, CHUNK):
            c = x[i:i + CHUNK]
            p, state = self.s.run(None, {"input": np.concatenate([ctx, c])[None], "state": state, "sr": sr})
            ctx = c[-CONTEXT:]
            out.append(float(p.ravel()[0]))
        return np.array(out)


_silero = None


def voiced(pcm):
    """Seconds of human voice in the phrase, or None if the Silero model isn't there (then nothing is filtered)."""
    global _silero
    if _silero is None:
        if not os.path.exists(MODEL):
            return None
        _silero = Silero()
    return float((_silero.probs(pcm) > SPEECH_P).sum()) * CHUNK / SR


def ignore(heard, since_gene_spoke):
    """Why a transcript isn't words for Gene ("filler" / "lone ack"), or "" when it is."""
    if FILLER.fullmatch(heard):
        return "filler"
    if "gene" not in heard.lower() and ACK.fullmatch(heard) and since_gene_spoke > ACK_WINDOW:
        return "lone ack"
    return ""


if __name__ == "__main__":
    import soundfile as sf, time
    for f in sys.argv[1:]:
        a, sr = sf.read(f, dtype="int16")
        a = a if a.ndim == 1 else a[:, 0]
        if sr != SR:
            a = np.interp(np.arange(0, len(a), sr / SR), np.arange(len(a)), a).astype(np.int16)
        t = time.perf_counter(); v = voiced(a)
        print(f"{f}: {len(a) / SR:.1f} s, voice {v} s ({(time.perf_counter() - t) * 1000:.0f} ms)")
