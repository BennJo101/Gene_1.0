"""Gene's eye cameras: the two ribbon-cable cameras on the Pi 5 (CAM/DISP 0 = his left eye, CAM/DISP 1 = his right).

Two halves, because picamera2 lives in the SYSTEM python and onnxruntime only in the venv:

  - Capture (`/usr/bin/python3 gene_cameras.py`, run by gene-cameras.service): every CAPTURE_EVERY s (FAST_EVERY while
    the web panel watches) a frame (640x480, turned upright: 480x640)
    from each camera is written to $XDG_RUNTIME_DIR/gene-camera/cam<N>.npy (tmpfs - 2 MB/s would wear the SD card).
    A camera that fails is retried every RETRY s, so one can be plugged in later (needs a reboot to be detected).
  - Seeing (`Seer`, a thread in gene_client): YOLOv10n (models/yolov10n/, ~200 ms a frame on 2 cores, COCO's 80 kinds
    of things) on the newest frames, ALWAYS every DETECT_EVERY s (since 2026-10-06, asked by voice: "cameras always
    taking snapshots" - before, it was only every 20 s unless someone had spoken; ~0.4 s of 2 cores per look), and
    right away when a phrase is heard.
    `Seer.line()` is the "(camera: person, 2 cups, laptop on your left)" line for the model; "" when no camera
    has given a frame for STALE s (then gene_client says the cameras aren't connected).

Model, if missing: https://huggingface.co/onnx-community/yolov10n (onnx/model.onnx + config.json for the labels).
Test:  ./venv/bin/python gene_cameras.py see
"""
import json, os, sys, threading, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "gene-camera")
MODEL = os.path.join(HERE, "models", "yolov10n")
# camera number -> Gene's side. The design notes said CAM/DISP 0 = left, but on 2026-10-13 Joshua checked by voice: the
# picture Gene called his left eye's was really his right eye's ("that was actually your right eye, switch 'em").
SIDES = {0: "right", 1: "left"}
# Degrees clockwise each camera's picture is turned so the room is upright. 2026-10-12, asked by voice ("tilt your
# camera properly", then "is your camera right side up now?" -> "fix ..."): both cameras are mounted on their sides -
# camera 0's picture needs 90 deg clockwise, camera 1's 270 (it is the other way round). Turned by numpy after capture
# (~1 ms a frame), so frames are 480 wide x 640 high. Check by viewing frames: cabinets stand on the floor.
# 2026-10-13 (asked by voice: "flip the camera that's upside down"): camera 1 was still upside down - the 180 part had
# been left to libcamera's hflip+vflip Transform, which was never applied (270 and 90 gave the same picture).
ROTATE = {0: 90, 1: 270}
W, H = 640, 480
CAPTURE_EVERY = 1.0     # s
FAST_EVERY = 0.12       # s: while the web control panel (gene_teleop.py) is watching, ~8 frames a second
FAST = os.path.join(FRAMES, "fast")     # touched by the panel while it shows the cameras
FAST_FOR = 5            # s after the last touch
RETRY = 30              # s before a missing camera is tried again
DETECT_EVERY = 2.0      # s between looks, always
STALE = 10              # s; older frames mean that camera is gone
MIN_SCORE = 0.45
DARK = 12               # mean pixel value below which he says it's too dark to see


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---- capture (system python) ----

def capture():
    from picamera2 import Picamera2
    os.makedirs(FRAMES, exist_ok=True)
    cams, tried = {}, {}

    def open_cam(n):
        tried[n] = time.time()
        try:
            c = Picamera2(n)
            c.configure(c.create_still_configuration(main={"size": (W, H), "format": "RGB888"}, buffer_count=2))
            c.start(); cams[n] = c
            log(f"camera {n} ({SIDES.get(n, n)}) on" + (f" (turned {ROTATE[n]} deg)" if ROTATE.get(n) else ""))
        except Exception as e:
            log(f"camera {n} failed:", e)
    while True:
        t = time.time()
        for n in range(len(Picamera2.global_camera_info())):
            if n not in cams and t - tried.get(n, 0) > RETRY:
                open_cam(n)
        for n, c in list(cams.items()):
            try:
                a = c.capture_array()           # "RGB888" is B, G, R in memory
                if ROTATE.get(n, 0) % 360:      # turn clockwise
                    a = np.ascontiguousarray(np.rot90(a, k=-(ROTATE[n] // 90)))
                tmp = os.path.join(FRAMES, f".cam{n}.npy")
                np.save(tmp, a); os.replace(tmp, os.path.join(FRAMES, f"cam{n}.npy"))
            except Exception as e:
                log(f"camera {n} lost:", e)
                try:
                    c.close()
                except Exception:
                    pass
                del cams[n]
        try:
            every = FAST_EVERY if time.time() - os.path.getmtime(FAST) < FAST_FOR else CAPTURE_EVERY
        except OSError:
            every = CAPTURE_EVERY
        time.sleep(max(0.01, every - (time.time() - t)))


# ---- seeing (venv) ----

def fresh(max_age=STALE):
    """{camera number: frame file} of the cameras that gave a frame in the last max_age s."""
    out = {}
    try:
        names = os.listdir(FRAMES)
    except OSError:
        return out
    for f in names:
        if f.startswith("cam") and f.endswith(".npy"):
            p = os.path.join(FRAMES, f)
            try:
                if time.time() - os.path.getmtime(p) <= max_age:
                    out[int(f[3:-4])] = p
            except (OSError, ValueError):
                pass
    return out


def frames(max_age=STALE):
    """{camera number: BGR frame} of the cameras that gave a frame in the last max_age s."""
    out = {}
    for n, p in fresh(max_age).items():
        try:
            out[n] = np.load(p)
        except (OSError, ValueError):
            pass
    return out


class Detector:
    def __init__(self, threads=2):
        import onnxruntime as ort
        o = ort.SessionOptions(); o.intra_op_num_threads = threads     # leave cores for STT and the voice
        self.s = ort.InferenceSession(os.path.join(MODEL, "model.onnx"), o, providers=["CPUExecutionProvider"])
        self.labels = json.load(open(os.path.join(MODEL, "config.json")))["id2label"]
        self.size = self.s.get_inputs()[0].shape[2]

    def __call__(self, bgr):
        """[(label, score)] of the things in one BGR frame."""
        h, w = bgr.shape[:2]
        k = self.size / max(h, w)
        if k != 1:      # nearest-neighbour resize, no cv2 here
            ys = (np.arange(int(h * k)) / k).astype(int); xs = (np.arange(int(w * k)) / k).astype(int)
            bgr = bgr[ys][:, xs]; h, w = bgr.shape[:2]
        img = np.full((self.size, self.size, 3), 114, np.uint8)     # letterboxed like YOLO's training
        y0, x0 = (self.size - h) // 2, (self.size - w) // 2
        img[y0:y0 + h, x0:x0 + w] = bgr[..., ::-1]
        x = img.transpose(2, 0, 1)[None].astype(np.float32) / 255
        out = self.s.run(None, {self.s.get_inputs()[0].name: x})[0][0]     # [300, 6]: box, score, class (NMS-free)
        return [(self.labels[str(int(c))], float(p)) for *_, p, c in out if p >= MIN_SCORE]


def describe(seen):
    """{camera: [labels]} (None = too dark) -> "person, 2 cups, laptop on your left"."""
    dark = [n for n, v in seen.items() if v is None]
    counts = {n: {} for n in seen if seen[n] is not None}
    for n, labels in seen.items():
        for lab in labels or ():
            counts[n][lab] = counts[n].get(lab, 0) + 1
    if not counts:
        return "too dark to see anything"
    order, parts = [], []
    for n in sorted(counts):
        order += [lab for lab in sorted(counts[n], key=lambda l: (l != "person", -counts[n][l])) if lab not in order]
    for lab in order:
        where = [n for n in counts if lab in counts[n]]
        k = max(counts[n][lab] for n in where)          # both eyes see the same things: not twice as many
        word = lab if k == 1 else f"{k} {'people' if lab == 'person' else lab + ('es' if lab.endswith(('s', 'ch', 'sh')) else 's')}"
        if len(where) == 1 and len(seen) > 1 and len(counts) > 1:
            word += f" on your {SIDES.get(where[0], where[0])}"
        parts.append(word)
    text = ", ".join(parts) if parts else "nothing you recognise"
    if dark and counts:
        text += f" (your {' and '.join(SIDES.get(n, str(n)) for n in dark)} eye sees only darkness)"
    return text


class Seer:
    """Keeps what the cameras see up to date in the background, for gene_client's camera line."""

    def __init__(self, background=True, lids=None):
        self.seen, self.at = None, 0.0
        self.lids = lids        # () -> "left"/"right"/"both"/None: eyes closed by voice see nothing (gene_eyes.lids_shut)
        self.wake = threading.Event()
        self.detect = None
        if background:
            threading.Thread(target=self._loop, daemon=True).start()

    def heard(self):
        """Someone spoke: look right away if the last look is old."""
        if time.time() - self.at > DETECT_EVERY:
            self.wake.set()

    def look(self):
        got = frames()
        if not got:
            return None
        if self.detect is None:
            self.detect = Detector()
        return {n: (None if f.mean() < DARK else [lab for lab, _ in self.detect(f)]) for n, f in got.items()}

    def _loop(self):
        while True:
            try:
                self.seen, self.at = self.look(), time.time()
            except Exception as e:
                log("camera error:", e); self.seen = None
            self.wake.wait(DETECT_EVERY)
            self.wake.clear()

    def line(self):
        """The model's "(camera: ...)" line; "" when no camera works."""
        if not self.seen or time.time() - self.at > STALE + DETECT_EVERY or not fresh():
            return ""
        shut = self.lids() if self.lids else None
        closed = [n for n in self.seen if shut in ("both", SIDES.get(n))]
        seen = {n: v for n, v in self.seen.items() if n not in closed}     # he looks through his lids, not past them
        if not seen:
            return "(camera: your eyes are closed, so you can't see anything)"
        text = describe(seen)
        if closed:
            text += f" (your {' and '.join(SIDES.get(n, str(n)) for n in closed)} eye is closed)"
        return f"(camera: {text})"


if __name__ == "__main__":
    if sys.argv[1:] == ["see"]:
        t = time.time(); seen = Seer(background=False).look()
        print(seen, f"{time.time() - t:.2f}s")
        print(f"(camera: {describe(seen)})" if seen else "no camera frames - is gene-cameras.service running?")
    else:
        capture()
