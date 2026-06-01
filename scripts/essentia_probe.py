#!/usr/bin/env python3
"""
essentia_probe.py — Prototype: what does Essentia "hear" in a track?

Compares Essentia's musical analysis against librosa's current beat-only read.
Run with the .venv-mir interpreter (Python 3.13 + essentia + librosa).

Surfaces:
  • Tempo cross-check (librosa vs Essentia RhythmExtractor2013 + Percival) — catches octave errors
  • Per-section energy curve (RMS/loudness over time) → maps to cut density
  • Danceability + dynamic complexity (global "feel" descriptors)
  • SuperFlux onset rate over time (percussive activity → where to cut harder)
  • Coarse build/drop/breakdown labeling from the energy curve, beat-aligned

No video, no rendering — pure analysis. Emits a readable report + optional JSON.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import essentia
import essentia.standard as es
import librosa

essentia.log.warningActive = False  # quiet the C++ chatter


def analyze(path: Path, n_buckets: int = 16) -> dict:
    # Essentia wants mono 44.1k
    audio = es.MonoLoader(filename=str(path), sampleRate=44100)()
    dur = len(audio) / 44100.0

    # ── TEMPO: three independent estimates ────────────────────────────────────
    # librosa (what the tool uses now)
    y, sr = librosa.load(str(path))
    lib_tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    lib_bpm = float(lib_tempo) if np.ndim(lib_tempo) == 0 else float(lib_tempo[0])

    # Essentia RhythmExtractor2013 (degara/multifeature) — returns confidence
    rhythm = es.RhythmExtractor2013(method="multifeature")
    ess_bpm, beats, beat_conf, _, _ = rhythm(audio)

    # Percival BPM (a second, independent estimator)
    perc_bpm = float(es.PercivalBpmEstimator()(audio))

    # ── GLOBAL FEEL ───────────────────────────────────────────────────────────
    dance, _ = es.Danceability()(audio)
    dyn_complexity, _ = es.DynamicComplexity()(audio)

    # ── TIME-VARYING ENERGY (bucketed loudness) ───────────────────────────────
    # Frame-wise RMS → loudness curve, then downsample into n_buckets time slices
    frame_rms = []
    for frame in es.FrameGenerator(audio, frameSize=2048, hopSize=1024):
        frame_rms.append(float(es.RMS()(frame)))
    frame_rms = np.array(frame_rms)
    # normalize 0..1 for readability
    rms_norm = (frame_rms - frame_rms.min()) / (np.ptp(frame_rms) + 1e-9)
    buckets = np.array_split(rms_norm, n_buckets)
    energy_curve = [float(b.mean()) for b in buckets]

    # ── SUPERFLUX ONSET ACTIVITY (percussive transient density) ───────────────
    superflux = es.SuperFluxExtractor()
    onsets = superflux(audio)  # array of onset times (s)
    onset_buckets = [0] * n_buckets
    for t in onsets:
        idx = min(int(t / dur * n_buckets), n_buckets - 1)
        onset_buckets[idx] += 1

    # ── COARSE SECTION LABELS from energy curve ───────────────────────────────
    hi = np.percentile(energy_curve, 66)
    lo = np.percentile(energy_curve, 33)
    labels = []
    for i, e in enumerate(energy_curve):
        if e >= hi:
            lab = "drop"
        elif e <= lo:
            lab = "breakdown"
        else:
            # rising vs falling → build vs fall
            prev = energy_curve[i - 1] if i else e
            lab = "build" if e >= prev else "fall"
        labels.append(lab)

    return {
        "file": path.name,
        "duration": round(dur, 1),
        "tempo": {
            "librosa": round(lib_bpm, 1),
            "essentia_rhythm2013": round(float(ess_bpm), 1),
            "essentia_percival": round(perc_bpm, 1),
            "beat_confidence": round(float(beat_conf), 2),
            "n_beats_essentia": len(beats),
        },
        "feel": {
            "danceability": round(float(dance), 2),
            "dynamic_complexity": round(float(dyn_complexity), 2),
        },
        "n_buckets": n_buckets,
        "energy_curve": [round(e, 2) for e in energy_curve],
        "onset_buckets": onset_buckets,
        "section_labels": labels,
        "n_onsets_total": len(onsets),
    }


def sparkline(vals, lo=0.0, hi=1.0):
    blocks = "▁▂▃▄▅▆▇█"
    out = ""
    for v in vals:
        idx = int((v - lo) / (hi - lo + 1e-9) * (len(blocks) - 1))
        out += blocks[max(0, min(len(blocks) - 1, idx))]
    return out


def report(a: dict):
    t = a["tempo"]
    print(f"\n{'='*68}")
    print(f"  {a['file']}  ({a['duration']}s)")
    print(f"{'='*68}")
    print("TEMPO (octave-error cross-check):")
    print(f"  librosa            : {t['librosa']:>6.1f} BPM   ← what the tool uses now")
    print(f"  essentia rhythm2013: {t['essentia_rhythm2013']:>6.1f} BPM   (confidence {t['beat_confidence']})")
    print(f"  essentia percival  : {t['essentia_percival']:>6.1f} BPM")
    # flag disagreement
    bpms = [t['librosa'], t['essentia_rhythm2013'], t['essentia_percival']]
    if max(bpms) / min(bpms) > 1.8:
        print(f"  ⚠️  OCTAVE DISAGREEMENT — estimators differ by ~2× (half/double-time ambiguity)")

    f = a["feel"]
    print(f"\nFEEL:")
    print(f"  danceability       : {f['danceability']}   (Essentia DFA, ~0=flat … 3=very danceable)")
    print(f"  dynamic_complexity : {f['dynamic_complexity']}   (loudness variation; higher = more dynamic)")

    print(f"\nENERGY CURVE ({a['n_buckets']} slices over {a['duration']}s):")
    print(f"  {sparkline(a['energy_curve'])}")
    print(f"  labels: " + " ".join(f"{l[:2]}" for l in a["section_labels"]))

    omax = max(a["onset_buckets"]) or 1
    print(f"\nONSET ACTIVITY (SuperFlux transient density, {a['n_onsets_total']} total):")
    print(f"  {sparkline([o/omax for o in a['onset_buckets']])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="+", type=Path)
    ap.add_argument("--buckets", type=int, default=16)
    ap.add_argument("--json", type=Path, help="also dump raw analysis JSON here")
    args = ap.parse_args()

    results = []
    for tr in args.tracks:
        if not tr.exists():
            print(f"skip (not found): {tr}", file=sys.stderr)
            continue
        a = analyze(tr, n_buckets=args.buckets)
        report(a)
        results.append(a)

    if args.json:
        args.json.write_text(json.dumps(results, indent=2))
        print(f"\n→ wrote {args.json}")


if __name__ == "__main__":
    main()
