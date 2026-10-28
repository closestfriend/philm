#!/usr/bin/env python3
"""beat_grid.py — write a beat grid for embed_cut.py's --beats flag.

Run with the .venv-mir interpreter (Python 3.13 + essentia + librosa), not the main venv:
  .venv-mir/bin/python scripts/beat_grid.py TRACK [-o grid.json]

Why not librosa's beat_track (what embed_cut uses by default): it makes one global tempo guess and can
land on half-time (rav3rz: 78 instead of 156), and a beat tracker's first beat is wherever its tracking
settled, not where the first kick is. So this does it in two steps:
  1. TEMPO from Essentia RhythmExtractor2013 (octave-proof on rav3rz, validated 2026-05-30).
  2. PHASE by sliding a constant-tempo grid over the track's onset-strength curve and keeping the offset
     whose grid lines sit on the most transient energy. The grid is then anchored to the actual hits.

Output JSON: {"bpm", "confidence", "pulse", "beats": [...seconds...], "essentia_beats": [...]}.
`pulse` is false when Essentia's confidence is too low to trust (ambient material): cut those at a
fixed rate (embed_cut `silent --cut`) instead of on a grid.

Limits: constant tempo. A track whose tempo changes mid-way (e.g. love: ~90 then ~117 by Essentia's read)
needs a piecewise grid; this does not do that.
"""
import argparse
import json
from pathlib import Path

import essentia
import essentia.standard as es
import librosa
import numpy as np

essentia.log.warningActive = False
MIN_CONF = 0.5          # RhythmExtractor2013 "multifeature" confidence; <~0.5 is not a usable pulse
HOP = 256


def phase_locked_grid(path: Path, bpm: float, dur: float) -> list[float]:
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    t = librosa.frames_to_time(np.arange(len(env)), sr=sr, hop_length=HOP)
    period = 60.0 / bpm
    best_phase, best_score = 0.0, -1.0
    for phase in np.arange(0.0, period, 0.005):
        score = float(np.interp(np.arange(phase, dur, period), t, env).sum())
        if score > best_score:
            best_phase, best_score = phase, score
    return [float(x) for x in np.arange(best_phase, dur, period)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("track")
    ap.add_argument("-o", "--out", default=None, help="default: <track stem>_beats.json next to this script's cwd")
    a = ap.parse_args()
    path = Path(a.track).expanduser()
    audio = es.MonoLoader(filename=str(path), sampleRate=44100)()
    bpm, ess_beats, conf, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    dur = len(audio) / 44100
    pulse = bool(conf >= MIN_CONF)
    grid = phase_locked_grid(path, float(bpm), dur) if pulse else []
    out = Path(a.out) if a.out else Path(f"{path.stem}_beats.json")
    out.write_text(json.dumps({"track": str(path), "bpm": round(float(bpm), 2), "confidence": round(float(conf), 3),
                               "pulse": pulse, "beats": [round(b, 4) for b in grid],
                               "essentia_beats": [round(float(b), 4) for b in ess_beats]}))
    first = f"first grid beat {grid[0]:.3f}s" if grid else "no pulse: use silent --cut"
    print(f"{path.name}: {bpm:.1f} bpm, confidence {conf:.2f}, {len(grid)} beats, {first} -> {out}")


if __name__ == "__main__":
    main()
