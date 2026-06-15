#!/usr/bin/env python3
"""Affect Scores — compose an intensity curve, render it from the affect catalog.

Pushes SINGLE_SOURCE's "affect-intensity as edit curve" method further. Instead of one
hand-placed peak per clip, this uses the full per-clip affect time-series (~23 samples/clip),
Massumi's `vector` (affect DIRECTION), and `atmosphere`, and fits the catalog to a TARGET
CURVE: it walks a timeline, and at each step picks the clip-SUB-WINDOW whose mean intensity,
internal slope, and vector best match the target level + slope at that moment. Editing as
curve-fitting against feeling.

Usage:
  uv run python scripts/affect_score.py --score swell [--dry]
  uv run python scripts/affect_score.py --score all
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path("/Volumes/2025_exSSD_2tb/Photography + Video")   # media source (read-only)
PROXY_ROOT = ROOT / "_proxies"                              # pipeline data, stays by footage
CATALOG = ROOT / "_cloud_catalog"                          # per-clip analysis JSONs (source of truth)
OUT = Path.home() / "Projects" / "karman-video-art" / "affect_scores"  # deliverables -> project

RISE = {"expanding", "forward", "toward", "outward", "upward", "approaching", "rising", "ascending"}
FALL = {"contracting", "receding", "away", "inward", "withdrawing", "downward", "falling", "descending"}
FLAT = {"static", "stable", "neutral", "steady", "still"}

BLOCKS = "▁▂▃▄▅▆▇█"


def tc_to_sec(tc: str) -> float:
    parts = [p for p in str(tc).replace(";", ":").split(":") if p != ""]
    try:
        n = [float(p) for p in parts]
    except ValueError:
        return 0.0
    if len(n) == 1:
        return n[0]
    if len(n) == 2:
        return n[0] * 60 + n[1]
    if len(n) == 3:
        return n[0] * 3600 + n[1] * 60 + n[2]
    return n[0] * 3600 + n[1] * 60 + n[2] + n[3] / 1000.0  # H:M:S:ms


# --------------------------------------------------------------------------- #
# target curves: u in [0,1] -> intensity in [0,10]
# --------------------------------------------------------------------------- #
def swell(u: float) -> float:
    return 1.0 if u >= 0.93 else 2.0 + 8.0 * (u / 0.93)


def heartbeat(u: float) -> float:
    # accelerating pulse: instantaneous frequency ramps up with u
    phase = 2 * math.pi * (5 * u + 7 * u * u)
    return 3.0 + 5.0 * (max(0.0, math.sin(phase)) ** 0.55)


def flatline_spike(u: float) -> float:
    if 0.60 <= u <= 0.66:
        return 10.0
    if 0.57 <= u < 0.60 or 0.66 < u <= 0.69:
        return 6.0  # the shoulders of the spike
    return 1.5


def double_climax(u: float) -> float:
    pts = [(0.0, 2), (0.30, 7), (0.45, 3), (0.62, 5), (0.80, 10), (0.92, 8), (1.0, 1)]
    for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
        if u0 <= u <= u1:
            return v0 + (v1 - v0) * (u - u0) / (u1 - u0)
    return pts[-1][1]


CURVES = {"swell": swell, "heartbeat": heartbeat,
          "flatline_spike": flatline_spike, "double_climax": double_climax}
DURATION = {"swell": 210, "heartbeat": 165, "flatline_spike": 200, "double_climax": 210}


def slope_of(f, u: float) -> float:
    du = 0.01
    return (f(min(1, u + du)) - f(max(0, u - du))) / (2 * du)


def sgn(x: float, th: float = 1.5) -> int:
    return 1 if x > th else (-1 if x < -th else 0)


def hold_for(level: float, score: str) -> float:
    if score == "flatline_spike":  # exaggerate stillness vs shock
        return max(0.9, min(9.0, 9.0 - 0.78 * level))
    return max(1.3, min(7.0, 6.8 - 0.52 * level))


# --------------------------------------------------------------------------- #
@dataclass
class Clip:
    vid: int
    proxy: Path
    times: list           # seconds per sample
    intens: list          # intensity per sample
    dom_vector: str
    dom_atmo: str
    dur: float = -1.0     # ffprobed lazily

    def best_window(self, level: float, k: int = 3):
        """Return (start_sec, mean_intensity, internal_slope) of the k-sample window
        whose mean intensity is closest to `level`."""
        n = len(self.intens)
        if n == 0:
            return 0.0, 0.0, 0.0
        if n <= k:
            mean = sum(self.intens) / n
            return self.times[0], mean, self.intens[-1] - self.intens[0]
        best = None
        for i in range(0, n - k + 1):
            w = self.intens[i:i + k]
            mean = sum(w) / k
            cost = abs(mean - level)
            if best is None or cost < best[0]:
                best = (cost, self.times[i], mean, w[-1] - w[0])
        return best[1], best[2], best[3]


def proxy_for(path: str) -> Path | None:
    try:
        rel = os.path.relpath(path, ROOT)
    except ValueError:
        return None
    if rel.startswith(".."):
        return None
    p = PROXY_ROOT / (os.path.splitext(rel)[0] + ".mp4")
    return p if p.exists() else None


def load_clips() -> list[Clip]:
    """Build the clip pool from the catalog JSONs (source of truth). Honors an explicit
    ``proxy`` field (segment chunks) and skips clips flagged ``segmented`` (long takes that
    have been replaced by their chunks)."""
    clips = []
    for f in sorted(CATALOG.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("segmented"):  # superseded by its chunks
            continue
        af = d.get("analyses", {}).get("affect")
        if not isinstance(af, dict) or "error" in af:
            continue
        samples = []
        for t in (af.get("timecodes") or []):
            iv = t.get("intensity")
            if isinstance(iv, int):
                samples.append((tc_to_sec(t.get("time", "0")), iv,
                                (t.get("atmosphere") or "").strip(),
                                (t.get("vector") or "").lower().strip()))
        if len(samples) < 2:
            continue
        proxy = Path(d["proxy"]) if d.get("proxy") else proxy_for(d.get("path", ""))
        if proxy is None or not proxy.exists():
            continue
        samples.sort(key=lambda s: s[0])
        vecs = [s[3] for s in samples if s[3]]
        atmos = [s[2] for s in samples if s[2]]
        clips.append(Clip(vid=d.get("uid", f.stem),
                          proxy=proxy,
                          times=[s[0] for s in samples],
                          intens=[s[1] for s in samples],
                          dom_vector=Counter(vecs).most_common(1)[0][0] if vecs else "neutral",
                          dom_atmo=Counter(atmos).most_common(1)[0][0] if atmos else ""))
    return clips


def ffdur(p: Path) -> float:
    try:
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30).stdout.strip())
    except Exception:
        return 0.0


def vector_pen(dom_vector: str, target_slope: int) -> float:
    if target_slope > 0:
        return 0.0 if dom_vector in RISE else (0.4 if dom_vector in FLAT else 1.0)
    if target_slope < 0:
        return 0.0 if dom_vector in FALL else (0.4 if dom_vector in FLAT else 1.0)
    return 0.0 if dom_vector in FLAT else 0.5


def compose(score: str, clips: list[Clip]):
    f = CURVES[score]
    dur = DURATION[score]
    rnd = random.Random(score)
    used: set[int] = set()
    last_atmo = ""
    seq = []
    pos = 0.0
    while pos < dur and len(seq) < 120:
        u = pos / dur
        level = f(u)
        tslope = sgn(slope_of(f, u))
        hold = hold_for(level, score)
        best = None
        for c in clips:
            if c.vid in used:
                continue
            start, wmean, wslope = c.best_window(level)
            cost = (abs(wmean - level)
                    + 0.6 * (0 if sgn(wslope, 0.5) == tslope or tslope == 0 else 1)
                    + 0.7 * vector_pen(c.dom_vector, tslope)
                    + 0.25 * (0 if c.dom_atmo == last_atmo else 1)
                    + 0.5 * rnd.random())
            if best is None or cost < best[0]:
                best = (cost, c, start, wmean, wslope)
        if best is None:
            break
        _, c, start, wmean, wslope = best
        if c.dur < 0:
            c.dur = ffdur(c.proxy)
        seek = max(0.0, min(start, max(0.0, c.dur - hold))) if c.dur > 0 else max(0.0, start)
        seq.append({"clip": c, "seek": round(seek, 2), "hold": round(hold, 2),
                    "target": round(level, 1), "achieved": round(wmean, 1),
                    "tslope": tslope, "vector": c.dom_vector, "atmo": c.dom_atmo})
        used.add(c.vid)
        last_atmo = c.dom_atmo
        pos += hold
    return seq


def pick_clip(clips, used, level, tslope, last_atmo, rnd, jitter=0.5):
    """Best unused clip + sub-window for a target (level, slope). `jitter` controls how much
    near-equal-fit clips get reshuffled — the iteration/diversity knob."""
    best = None
    for c in clips:
        if c.vid in used:
            continue
        start, wmean, wslope = c.best_window(level)
        cost = (abs(wmean - level)
                + 0.6 * (0 if sgn(wslope, 0.5) == tslope or tslope == 0 else 1)
                + 0.7 * vector_pen(c.dom_vector, tslope)
                + 0.25 * (0 if c.dom_atmo == last_atmo else 1)
                + jitter * rnd.random())
        if best is None or cost < best[0]:
            best = (cost, c, start, wmean, wslope)
    return best  # (cost, clip, start, wmean, wslope) or None


def audio_curve(path: Path):
    """Extract the target intensity envelope (perceptual loudness, scaled 1-10) and the
    beat grid from an audio track. The track's energy IS the affect score."""
    import numpy as np
    import librosa
    y, sr = librosa.load(str(path), mono=True)
    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    db = librosa.amplitude_to_db(rms + 1e-9)
    win = max(1, int(round(0.35 * sr / hop)))           # ~0.35s smoothing
    db_s = np.convolve(db, np.ones(win) / win, mode="same")
    times = librosa.frames_to_time(np.arange(len(db_s)), sr=sr, hop_length=hop)
    p5, p95 = np.percentile(db_s, [5, 95])
    rng = max(1e-6, p95 - p5)

    def level_at(t: float) -> float:
        v = float(np.interp(t, times, db_s))
        return max(1.0, min(10.0, 1.0 + 9.0 * (v - p5) / rng))

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
    beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop)
    dur = float(librosa.get_duration(y=y, sr=sr))
    return dur, level_at, list(beat_times), float(np.atleast_1d(tempo)[0])


def compose_audio(path: Path, clips, seed=None, jitter=0.5):
    """Tile [0, track] on a beat-aligned grid; cut rate driven by loudness (fewer beats per
    cut when loud). Each segment's clip-window matches the track's intensity+slope at that
    moment, vector matched to the loudness slope. Cuts land on the beat. `seed` varies the
    cut while holding the curve; `jitter` widens the candidate pool per placement."""
    dur, level_at, beats, tempo = audio_curve(path)
    rnd = random.Random(seed if seed is not None else path.stem)
    # build beat-aligned cut boundaries; beats-per-cut shrinks as loudness rises
    cuts = [0.0]
    i = 0
    while i < len(beats) - 1:
        lvl = level_at(beats[i])
        bpc = int(max(1, min(8, round(8.5 - 0.78 * lvl))))
        j = min(i + bpc, len(beats) - 1)
        cuts.append(beats[j])
        i = j
    if cuts[-1] < dur - 0.5:
        cuts.append(dur)

    used, last_atmo, seq = set(), "", []
    for a, b in zip(cuts, cuts[1:]):
        hold = b - a
        if hold < 0.25:
            continue
        level = level_at(a)
        tslope = sgn(level_at(min(dur, a + 0.4)) - level_at(max(0, a - 0.4)), 0.4)
        best = pick_clip(clips, used, level, tslope, last_atmo, rnd, jitter)
        if best is None:
            break
        _, c, start, wmean, wslope = best
        if c.dur < 0:
            c.dur = ffdur(c.proxy)
        seek = max(0.0, min(start, max(0.0, c.dur - hold))) if c.dur > 0 else max(0.0, start)
        seq.append({"clip": c, "seek": round(seek, 2), "hold": round(hold, 2),
                    "target": round(level, 1), "achieved": round(wmean, 1),
                    "tslope": tslope, "vector": c.dom_vector, "atmo": c.dom_atmo})
        used.add(c.vid)
        last_atmo = c.dom_atmo
    print(f"  track {dur:.0f}s, tempo~{tempo:.0f} BPM, {len(beats)} beats -> {len(seq)} cuts")
    return seq


def spark(vals: list[float]) -> str:
    return "".join(BLOCKS[max(0, min(7, int(round((v - 1) / 9 * 7))))] for v in vals)


def render(score: str, seq: list, dry: bool, audio: Path | None = None):
    OUT.mkdir(parents=True, exist_ok=True)
    name = score.upper()
    tgt = [s["target"] for s in seq]
    ach = [s["achieved"] for s in seq]
    total = sum(s["hold"] for s in seq)
    fit = sum(abs(a - t) for a, t in zip(ach, tgt)) / max(1, len(seq))

    lines = [f"# {name} — affect score", "",
             f"A data-composed cut: {len(seq)} clips, ~{total/60:.1f} min, fit to the **{score}** "
             f"intensity curve (mean |target−achieved| = {fit:.2f}). Clip sub-windows chosen so the "
             f"piece's affect intensity tracks the target; `vector` matched to the curve's local slope.",
             "",
             "```",
             "target   " + spark(tgt),
             "achieved " + spark(ach),
             "```",
             "",
             "| # | clip | seek | hold | tgt | got | slope | vector | atmosphere |",
             "|--:|------|-----:|-----:|:---:|:---:|:-----:|--------|------------|"]
    for i, s in enumerate(seq, 1):
        sl = {1: "↑", -1: "↓", 0: "→"}[s["tslope"]]
        lines.append(f"| {i} | `{s['clip'].proxy.stem}` | {s['seek']}s | {s['hold']}s | "
                     f"{s['target']} | {s['achieved']} | {sl} | {s['vector']} | {s['atmo'][:34]} |")
    (OUT / f"{name}_cut.md").write_text("\n".join(lines))
    print(f"[{score}] {len(seq)} clips, ~{total/60:.1f}min, fit={fit:.2f} -> {OUT / (name+'_cut.md')}")
    print("  target   " + spark(tgt))
    print("  achieved " + spark(ach))
    if dry:
        return

    segdir = Path(f"/tmp/as_{score}")
    segdir.mkdir(parents=True, exist_ok=True)
    listfile = segdir / "list.txt"
    seglist = []
    for i, s in enumerate(seq):
        seg = segdir / f"seg_{i:03d}.mp4"
        cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", str(s["seek"]),
               "-t", str(s["hold"]), "-i", str(s["clip"].proxy),
               "-vf", "scale=854:480:force_original_aspect_ratio=decrease,"
                      "pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p",
               "-r", "24", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(seg)]
        subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        if seg.exists() and seg.stat().st_size > 1000 and ffdur(seg) > 0.3:
            seglist.append(seg)
    listfile.write_text("".join(f"file '{s}'\n" for s in seglist))
    picture = OUT / (f"{name}_picture.mp4" if audio else f"{name}_rough.mp4")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(listfile), "-c", "copy", str(picture)],
                   stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    if audio:
        outmp4 = OUT / f"{name}_rough.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                        "-i", str(picture), "-i", str(audio),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "256k", "-shortest", str(outmp4)],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
        picture.unlink(missing_ok=True)
        print(f"  rendered {len(seglist)} segments + muxed track -> {outmp4}  ({ffdur(outmp4):.0f}s)")
    else:
        print(f"  rendered {len(seglist)} segments -> {picture}  ({ffdur(picture):.0f}s)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", choices=list(CURVES) + ["all"], help="synthetic target curve")
    ap.add_argument("--audio", help="drive the curve from an audio track (the music IS the score)")
    ap.add_argument("--variations", type=int, default=1, help="render N distinct cuts of the same track")
    ap.add_argument("--seed", type=int, default=None, help="base RNG seed (variations = seed, seed+1, ...)")
    ap.add_argument("--diversity", type=float, default=0.5, help="0=always best-fit; higher=wilder/varied")
    ap.add_argument("--dry", action="store_true", help="cut sheet + curve only, no render")
    args = ap.parse_args()
    if not args.score and not args.audio:
        ap.error("pass --score <curve|all> or --audio <track>")
    print("loading affect catalog ...")
    clips = load_clips()
    print(f"{len(clips)} clips with usable affect time-series + proxies")
    if args.audio:
        apath = Path(args.audio)
        base = apath.stem.upper().replace(" ", "_").replace(".", "_")
        n = max(1, args.variations)
        print(f"composing to track: {apath.name}  ({n} variation{'s' if n > 1 else ''}, diversity {args.diversity})")
        for i in range(n):
            seed = (args.seed if args.seed is not None else 1) + i
            label = f"{base}_V{seed:02d}" if (n > 1 or args.seed is not None) else base
            print(f"--- {label} (seed {seed}) ---")
            seq = compose_audio(apath, clips, seed=seed, jitter=args.diversity)
            render(label, seq, args.dry, audio=apath)
        return 0
    scores = list(CURVES) if args.score == "all" else [args.score]
    for sc in scores:
        seq = compose(sc, clips)
        render(sc, seq, args.dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
