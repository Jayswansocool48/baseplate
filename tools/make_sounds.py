#!/usr/bin/env python3
"""Generate the app's sound effects into roblox_vault/sounds/.

The sounds are synthesized here from scratch (no samples), so they are
original work released with the app under the MIT License.
Run:  python3 tools/make_sounds.py
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
PEAK = 0.30  # about -10 dBFS, gentle next to system sounds
OUT = Path(__file__).resolve().parent.parent / "roblox_vault" / "sounds"


def env(i, n, attack=0.008, release=0.06):
    t, dur = i / RATE, n / RATE
    a = min(1.0, t / attack) if attack else 1.0
    r = min(1.0, (dur - t) / release) if release else 1.0
    return max(0.0, min(a, r))


def tone(freq, ms, shape="sine", decay=0.0, freq_end=None):
    n = int(RATE * ms / 1000)
    out, phase = [], 0.0
    for i in range(n):
        f = freq if freq_end is None else freq + (freq_end - freq) * i / n
        phase += 2 * math.pi * f / RATE
        if shape == "sine":
            v = math.sin(phase)
        else:  # soft triangle
            v = 2 / math.pi * math.asin(math.sin(phase))
        v += 0.25 * math.sin(2 * phase)  # a little warmth
        v *= env(i, n) * (math.exp(-decay * i / RATE) if decay else 1)
        out.append(v)
    return out


def silence(ms):
    return [0.0] * int(RATE * ms / 1000)


def noise(ms, seed=7):
    rnd = random.Random(seed)
    n = int(RATE * ms / 1000)
    prev, out = 0.0, []
    for i in range(n):
        prev = 0.6 * prev + 0.4 * rnd.uniform(-1, 1)  # low-passed
        out.append(prev * env(i, n, 0.001, 0.015))
    return out


def mix(*parts):
    n = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(n)]


def save(name, samples):
    peak = max(abs(s) for s in samples) or 1
    data = b"".join(struct.pack("<h", int(s / peak * PEAK * 32767)) for s in samples)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


SOUNDS = {
    "success": lambda: tone(659, 70) + tone(880, 110, decay=8),
    "import": lambda: tone(523, 60) + tone(659, 60) + tone(784, 140, decay=6),
    "error": lambda: tone(247, 90, "tri") + silence(20) + tone(196, 140, "tri", decay=6),
    "click": lambda: mix(noise(22), tone(1500, 22, decay=120)),
    "sync_on": lambda: tone(440, 180, freq_end=880, decay=3),
    "sync_off": lambda: tone(880, 180, freq_end=440, decay=3),
    "delete": lambda: tone(140, 160, decay=18, freq_end=90),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        save(name, make())
        print("wrote", OUT / f"{name}.wav")


if __name__ == "__main__":
    main()
