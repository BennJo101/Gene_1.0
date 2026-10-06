"""Gene's speaker volume, through the "Master" softvol control in asound.conf (the MAX98357A has no volume of its own).
Run on the Pi:  python3 volume.py         prints the level
                python3 volume.py 70      sets 70%
                python3 volume.py +10     / -10 steps it
Import:         volume.get(), volume.set(70), volume.step(-10)
100% is the ceiling set by max_dB in asound.conf, so nothing here can push the speakers past it."""
import re, subprocess, sys

CONTROL = "Master"


def get():
    out = subprocess.run(["amixer", "sget", CONTROL], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"\[(\d+)%\]", out).group(1))


def set(pct):
    pct = max(0, min(100, int(pct)))
    subprocess.run(["amixer", "-q", "sset", CONTROL, f"{pct}%"], check=True)
    return pct


def step(delta):
    return set(get() + delta)


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else None
    if a is None: print(f"{get()}%")
    elif a[0] in "+-": print(f"{step(int(a))}%")
    else: print(f"{set(a)}%")
