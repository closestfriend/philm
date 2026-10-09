#!/usr/bin/env python3
"""Affect Scores — STRUCTURE-AWARE variant. Compose from the affect catalog, but
make the engine HEAR SONG STRUCTURE and change editing grammar per section.

Copy of affect_score.py. The flat audio engine treats every beat the same: cut-rate
and clip-pick are a pure function of instantaneous loudness. This variant adds a
deterministic section detector (`detect_sections`) that labels each span of the track
as breakdown / build / drop / outro from the heavily-smoothed loudness envelope, and
then modulates the editing GRAMMAR per section (`section_grammar`):

  drop/peak  -> shortest holds (fast cuts), target biased HIGH, strongly prefer
                forward/expanding vectors -> footage erupts.
  breakdown  -> longest holds (shots breathe), target biased LOW, prefer
                static/receding vectors -> stillness.
  build      -> holds SHRINK across the span, target RISES, prefer expanding/forward.
  outro      -> holds lengthen, target falls.

Cuts stay beat-aligned. The detected section map is printed.

Usage:
  uv run python scripts/affect_score_struct.py --audio <track.wav>
  uv run python scripts/affect_score_struct.py --score swell [--dry]   # flat curves unchanged
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path("/Volumes/2025_exSSD_2tb/Photography + Video")   # media source (read-only)
PROXY_ROOT = ROOT / "_proxies"                              # pipeline data, stays by footage
CATALOG = ROOT / "_cloud_catalog"                          # per-clip analysis JSONs (source of truth)
OUT = Path.home() / "Projects" / "Ecosystems" / "Karman" / "karman-video-art" / "affect_scores"  # deliverables -> project
USAGE_MANIFEST = OUT / "usage_manifest.jsonl"  # persistent telemetry: every clip placement, every render
SCRATCH = Path("/Volumes/Vault_Σ/_render_scratch/affect_score")  # per-render segment dirs (2026-09-23: was /tmp; internal disk is full)

# Opportunity-cost band (see pick_clip): diversity penalties may only reorder clips whose raw fit is
# within FIT_TOL cost-units of the best candidate. ~0.6 is the tradeoff knee — strong corpus spread
# while sparse-region peaks keep their charge. Overridable per-run via --fit-tol. 0 -> pure best-fit.
FIT_TOL = 0.6

# Per-segment normalize filter. A module constant so other composers (embed_cut.py) can swap it
# (e.g. stretch-to-fill for portrait phone footage) without forking the render path.
SEG_VF = ("scale=854:480:force_original_aspect_ratio=decrease,"
          "pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p")

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
    tone: str = ""        # sizzle.dominant_tone  (content signal, for content-aware selection)
    best_for: tuple = ()  # sizzle.best_for        (content signal)
    salience: float = 1.0  # memorability: how RARE this clip's content fingerprint is in the cast
                           # pool. Computed once in load_clips; scales the rarity/content penalty so
                           # distinctive clips (the flame) pay more per repeat than forgettable filler.

    @property
    def content_key(self):
        """Coarse 'what kind of clip is this' fingerprint, for content-diversity scoring."""
        return (self.tone, self.dom_atmo)

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


def load_clips(min_peak_intensity: int | None = None,
               tones: set[str] | None = None,
               best_for_any: set[str] | None = None,
               min_energy: int | None = None,
               tone_or_best_for: bool = False,
               pool_root: Path | None = None) -> list[Clip]:
    """Build the clip pool from the catalog JSONs (source of truth). Honors an explicit
    ``proxy`` field (chunks) and skips clips flagged ``segmented``.

    STRUCTURED-FACET POOL FILTERING — cast the cut from a curated subset, not the whole pool.
    When any facet filter is given, a clip enters only if it passes ALL of them (AND), each
    reading an aggregate the analysis already wrote: ``min_peak_intensity`` (max affect
    intensity), ``tones`` (sizzle.dominant_tone in set), ``best_for_any`` (sizzle.best_for
    intersects set), ``min_energy`` (sizzle.overall_energy). ``tone_or_best_for`` switches just
    the tone/best_for pair to OR (the cinematic disjunction: peak>=8 AND (tone OR best_for)).
    ``pool_root`` casts only clips whose source path lives under that directory (a single shoot)."""
    filtering = any(v is not None for v in (min_peak_intensity, tones, best_for_any, min_energy,
                                            pool_root))
    clips = []
    full_pool = 0
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
        peak_intensity = 0
        for t in (af.get("timecodes") or []):
            iv = t.get("intensity")
            if isinstance(iv, int):
                samples.append((tc_to_sec(t.get("time", "0")), iv,
                                (t.get("atmosphere") or "").strip(),
                                (t.get("vector") or "").lower().strip()))
                if iv > peak_intensity:
                    peak_intensity = iv
        if len(samples) < 2:
            continue
        proxy = Path(d["proxy"]) if d.get("proxy") else proxy_for(d.get("path", ""))
        if proxy is None or not proxy.exists():
            continue
        full_pool += 1
        sz = d.get("analyses", {}).get("sizzle") or {}

        if filtering:
            if pool_root is not None:
                try:
                    Path(d.get("path", "")).relative_to(pool_root)
                except ValueError:
                    continue
            if min_peak_intensity is not None and peak_intensity < min_peak_intensity:
                continue
            tone_ok = tones is None or (sz.get("dominant_tone") or "") in tones
            bf_ok = best_for_any is None or bool(set(sz.get("best_for") or []) & best_for_any)
            if tone_or_best_for and tones is not None and best_for_any is not None:
                if not (tone_ok or bf_ok):
                    continue
            else:
                if not tone_ok or not bf_ok:
                    continue
            if min_energy is not None:
                oe = sz.get("overall_energy")
                if not isinstance(oe, int) or oe < min_energy:
                    continue

        samples.sort(key=lambda s: s[0])
        vecs = [s[3] for s in samples if s[3]]
        atmos = [s[2] for s in samples if s[2]]
        clips.append(Clip(vid=d.get("uid", f.stem),
                          proxy=proxy,
                          times=[s[0] for s in samples],
                          intens=[s[1] for s in samples],
                          dom_vector=Counter(vecs).most_common(1)[0][0] if vecs else "neutral",
                          dom_atmo=Counter(atmos).most_common(1)[0][0] if atmos else "",
                          tone=(sz.get("dominant_tone") or ""),
                          best_for=tuple(sz.get("best_for") or ())))
    if filtering:
        crit = []
        if pool_root is not None: crit.append(f"under {pool_root.name}/")
        if min_peak_intensity is not None: crit.append(f"peak>={min_peak_intensity}")
        join = " OR " if (tone_or_best_for and tones and best_for_any) else " AND "
        tb = []
        if tones is not None: tb.append(f"tone in {sorted(tones)}")
        if best_for_any is not None: tb.append(f"best_for-any {sorted(best_for_any)}")
        if tb: crit.append(("(" + join.join(tb) + ")") if len(tb) > 1 else tb[0])
        if min_energy is not None: crit.append(f"energy>={min_energy}")
        print(f"  facet cast [{' AND '.join(crit)}]: {len(clips)} cast / {full_pool} full pool "
              f"({100*len(clips)/max(1,full_pool):.0f}%)")

    # EARLIER-LAYER PRECOMPUTE (once, not in the pick loop): salience = how ALONE a clip stands in
    # affect-space, keyed on its PEAK intensity within this cast pool. The pool's peak distribution is a
    # bell centered ~7-8, so a clip peaking at 10 (the flame) or bottoming in a rare trough sits in a
    # thin tail -> high salience (up to 3x); a clip peaking in the fat middle -> ~1x. This makes tail
    # monopolists pay more per repeat while filler recurs cheaply. Only READ when a diversity lever is
    # on (baseline leaves rarity_w=content_w=0 -> salience unused -> byte-identical output).
    if clips:
        peak_of = {c.vid: int(max(c.intens)) for c in clips}
        peak_hist = Counter(peak_of[c.vid] for c in clips)
        maxp = max(peak_hist.values())
        for c in clips:
            dens = peak_hist[peak_of[c.vid]] / maxp      # 1.0 = fat middle, ~0 = thin tail
            c.salience = 1.0 + 2.0 * (1.0 - dens)        # -> [1.0, 3.0]
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


def compose(score: str, clips: list[Clip], jitter=0.5, usage=None,
            rarity_w=0.0, content_w=0.0, topk=1):
    f = CURVES[score]
    dur = DURATION[score]
    rnd = random.Random(score)
    used: set[int] = set()
    used_content: Counter = Counter()
    last_atmo = ""
    seq = []
    pos = 0.0
    while pos < dur and len(seq) < 120:
        u = pos / dur
        level = f(u)
        tslope = sgn(slope_of(f, u))
        hold = hold_for(level, score)
        best = pick_clip(clips, used, level, tslope, last_atmo, rnd, jitter,
                         section_label=None, usage=usage, used_content=used_content,
                         rarity_w=rarity_w, content_w=content_w, topk=topk)
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
        used_content[c.content_key] += 1
        last_atmo = c.dom_atmo
        pos += hold
    return seq


def pick_clip(clips, used, level, tslope, last_atmo, rnd, jitter=0.5, section_label=None,
              usage=None, used_content=None, rarity_w=0.0, content_w=0.0, topk=1):
    """Best unused clip + sub-window for a target (level, slope). `jitter` reshuffles
    near-equal-fit clips.

    DIVERSITY LEVERS — all default off, so the defaults reproduce greedy best-fit exactly:
      • ``rarity_w`` (>0) + ``usage`` Counter: penalize clips used in PRIOR renders → spreads draws
        across the corpus over successive cuts. The penalty is ``rarity_w · salience · sqrt(n)``:
          – ``salience`` : clips in a THIN affect region (the flame's sustained-10, or a rare trough)
                           pay more per repeat than clips in the fat middle — 'overrepresented' is
                           memorability × count, and memorability tracks how alone a clip stands.
          – ``sqrt(n)``  : diminishing returns (0→1 use matters most; the 19th barely more than 18th).
      • ``content_w`` (>0) + ``used_content`` Counter: penalize clips whose content fingerprint
        (tone, atmosphere) is already over-represented in THIS cut → scene/content variety.
      • ``topk`` (>1): sample uniformly among the K lowest-cost candidates instead of taking #1.

    OPPORTUNITY-COST via a FIT-TOLERANCE BAND (the faithful region-awareness): the penalties above may
    only reorder clips whose RAW FIT is within ``FIT_TOL`` of the best-fitting candidate. Dense region →
    many clips share the band → spread freely at ~zero fit cost. Thin tail → only the monopolist fits →
    it survives (charge kept) UNLESS a genuine alternative sits within tolerance, whose accrued penalty
    then displaces it. We never trade real fit for variety — only near-free fit. This replaces a static
    density table (which merely neutralized rarity at the peaks, reproducing the monopoly).

    When ``section_label`` is given, an extra per-section vector penalty pushes toward the section feel."""
    cands = []
    for c in clips:
        if c.vid in used:
            continue
        start, wmean, wslope = c.best_window(level)
        sec_pen = 0.0 if section_label is None else 0.9 * section_vector_pen(section_label, c.dom_vector)
        base = (abs(wmean - level)
                + 0.6 * (0 if sgn(wslope, 0.5) == tslope or tslope == 0 else 1)
                + 0.7 * vector_pen(c.dom_vector, tslope)
                + sec_pen
                + 0.25 * (0 if c.dom_atmo == last_atmo else 1)
                + jitter * rnd.random())
        pen = 0.0
        if rarity_w and usage:
            n = usage.get(c.proxy.stem, 0)
            if n:
                pen += rarity_w * c.salience * math.sqrt(n)
        if content_w and used_content:
            pen += content_w * c.salience * used_content.get(c.content_key, 0)
        cands.append((base, pen, c, start, wmean, wslope))
    if not cands:
        return None
    best_base = min(x[0] for x in cands)
    scored = [(b + (p if b <= best_base + FIT_TOL else 0.0), c, s, wm, ws)
              for (b, p, c, s, wm, ws) in cands]
    if topk and topk > 1:
        scored.sort(key=lambda x: x[0])
        return rnd.choice(scored[:topk])
    return min(scored, key=lambda x: x[0])  # (cost, clip, start, wmean, wslope)


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

    # per-frame level series (1-10), for the section detector
    lvl_series = np.clip(1.0 + 9.0 * (db_s - p5) / rng, 1.0, 10.0)
    return (dur, level_at, list(beat_times), float(np.atleast_1d(tempo)[0]),
            times, lvl_series)


def kick_track(path: Path, dur: float):
    """Isolate the kick (low band ~150 Hz), detect its onsets, and a 0-1 *density* envelope
    (how hard the kick is pumping). Cuts lock to the kick where density is high and relax to
    free holds where it isn't — so the picture pulses with the 4-on-the-floor and breathes
    when the kick drops out. Returns (onset_times, density(t))."""
    import numpy as np
    import librosa
    from scipy.signal import butter, sosfiltfilt
    y, sr = librosa.load(str(path), mono=True)
    sos = butter(4, 150, btype="low", fs=sr, output="sos")
    y_low = sosfiltfilt(sos, y).astype(np.float32)
    hop = 256
    oenv = librosa.onset.onset_strength(y=y_low, sr=sr, hop_length=hop)
    onsets = np.asarray(librosa.onset.onset_detect(onset_envelope=oenv, sr=sr,
                        hop_length=hop, units="time", backtrack=False), dtype=float)
    grid = np.arange(0.0, dur + 0.25, 0.25)
    rate = np.array([np.sum((onsets >= g - 1.0) & (onsets < g + 1.0)) for g in grid], float)
    if rate.max() > 0:
        k = max(1, int(round(1.0 / 0.25)))
        rate = np.convolve(rate, np.ones(k) / k, mode="same")
    hi = max(1.0, float(np.percentile(rate, 85)))

    def density(t: float) -> float:
        return float(np.clip(np.interp(t, grid, rate) / hi, 0.0, 1.0))

    return sorted(float(o) for o in onsets), density


# --------------------------------------------------------------------------- #
# SECTION DETECTION  (structure-aware addition)
# --------------------------------------------------------------------------- #
@dataclass
class Section:
    start: float
    end: float
    label: str            # breakdown | build | drop | outro


def detect_sections(times, lvl_series, dur: float) -> list[Section]:
    """Deterministically label spans of the track as breakdown/build/drop/outro from the
    heavily-smoothed loudness envelope.

    Method (no randomness): smooth `lvl_series` with a ~4s box, compute a slope (per-second)
    on the smoothed curve, then label each frame:
      high sustained energy -> drop, rising over a span -> build, low energy -> breakdown,
      falling tail near the end -> outro. Merge adjacent same-label frames into spans and
      absorb spans shorter than MIN_SEC into their louder/longer neighbour so the map is clean.
    """
    import numpy as np

    n = len(lvl_series)
    if n == 0:
        return [Section(0.0, dur, "drop")]
    dt = float(times[1] - times[0]) if n > 1 else 0.05

    # heavy smoothing -> structural envelope
    hwin = max(1, int(round(4.0 / max(dt, 1e-6))))
    heavy = np.convolve(lvl_series, np.ones(hwin) / hwin, mode="same")
    # slope per second over a ~3s lookahead/back
    sw = max(1, int(round(3.0 / max(dt, 1e-6))))
    slope = np.zeros(n)
    for i in range(n):
        a = max(0, i - sw)
        b = min(n - 1, i + sw)
        slope[i] = (heavy[b] - heavy[a]) / max(dt * (b - a), 1e-6)

    hi = float(np.percentile(heavy, 60))   # "loud" threshold
    lo = float(np.percentile(heavy, 35))   # "quiet" threshold
    RISE_TH = 0.12                          # level units / second to count as a build

    labels = []
    for i in range(n):
        t = times[i]
        h = heavy[i]
        s = slope[i]
        if t >= dur - 18.0 and s < -RISE_TH and h < hi:
            lab = "outro"
        elif s > RISE_TH and h < hi + 1.0:
            lab = "build"
        elif h >= hi:
            lab = "drop"
        elif h <= lo:
            lab = "breakdown"
        else:
            lab = "build" if s > 0 else "breakdown"
        labels.append(lab)

    # merge contiguous same-label frames into spans
    spans = []
    cur = labels[0]
    start_t = float(times[0])
    for i in range(1, n):
        if labels[i] != cur:
            spans.append(Section(start_t, float(times[i]), cur))
            cur = labels[i]
            start_t = float(times[i])
    spans.append(Section(start_t, dur, cur))

    # absorb tiny spans into a neighbour (prefer the louder/longer one)
    MIN_SEC = 6.0

    def mean_lvl(sec):
        m = (times >= sec.start) & (times < sec.end)
        return float(np.mean(heavy[m])) if np.any(m) else 0.0

    changed = True
    while changed and len(spans) > 1:
        changed = False
        for i, sec in enumerate(spans):
            if sec.end - sec.start >= MIN_SEC:
                continue
            left = spans[i - 1] if i > 0 else None
            right = spans[i + 1] if i < len(spans) - 1 else None
            # pick neighbour to merge into
            if left and right:
                tgt = left if mean_lvl(left) >= mean_lvl(right) else right
            else:
                tgt = left or right
            tgt.start = min(tgt.start, sec.start)
            tgt.end = max(tgt.end, sec.end)
            spans.pop(i)
            changed = True
            break

    # final pass: stitch any now-adjacent same-label spans
    merged = [spans[0]]
    for sec in spans[1:]:
        if sec.label == merged[-1].label:
            merged[-1].end = sec.end
        else:
            merged.append(sec)
    return merged


def section_at(sections: list[Section], t: float) -> Section:
    for sec in sections:
        if sec.start <= t < sec.end:
            return sec
    return sections[-1]


def section_span_progress(sec: Section, t: float) -> float:
    """0->1 position of t within section `sec` (for builds where holds shrink across the span)."""
    span = max(1e-6, sec.end - sec.start)
    return max(0.0, min(1.0, (t - sec.start) / span))


# --------------------------------------------------------------------------- #
# PER-SECTION GRAMMAR  (structure-aware addition)
# --------------------------------------------------------------------------- #
# Vector preference buckets per section. Penalty applied on top of the loudness-slope
# vector_pen so the section's "feel" wins where the slope is ambiguous.
def section_vector_pen(label: str, dom_vector: str) -> float:
    if label in ("drop", "build"):              # erupt / climb -> forward/expanding
        if dom_vector in RISE:
            return 0.0
        if dom_vector in FLAT:
            return 0.5
        return 1.0
    if label == "breakdown":                    # stillness -> static/receding
        if dom_vector in FLAT:
            return 0.0
        if dom_vector in FALL:
            return 0.2
        return 1.0
    if label == "outro":                        # let it fall away -> receding/static
        if dom_vector in FALL:
            return 0.0
        if dom_vector in FLAT:
            return 0.3
        return 1.0
    return 0.5


def section_grammar(label: str, base_bpc: int, level: float, span_u: float, bias: float = 1.0):
    """Return (beats_per_cut, target_level) modulated by the current section.

    span_u is the 0->1 progress within the section (used by `build` to SHRINK holds and
    RAISE the target across the span). Cuts stay beat-aligned because we only ever change
    how many beats each cut spans, never where the beats are.
    """
    bpc = base_bpc
    tgt = level
    if label == "drop":                 # fast cuts, target biased HIGH
        bpc = max(1, base_bpc - 2)
        tgt = min(10.0, level + 1.5 * bias)
    elif label == "breakdown":          # longest holds, target biased LOW
        bpc = min(8, base_bpc + 3)
        tgt = max(1.0, level - 1.5 * bias)
    elif label == "build":              # holds shrink across span, target rises
        bpc = max(1, int(round(base_bpc + 2 - 4.0 * span_u)))
        tgt = min(10.0, level + (1.0 + 3.0 * span_u) * bias)
    elif label == "outro":             # lengthen holds, target falls
        bpc = min(8, base_bpc + 2)
        tgt = max(1.0, level - (1.0 + 1.5 * span_u) * bias)
    return max(1, min(8, bpc)), max(1.0, min(10.0, tgt))


def quantile_mapper(lvl_series, clips):
    """Map the song's loudness onto the CORPUS's intensity distribution by quantile: the loudest
    5% of the track asks for the corpus's top 5% of intensity, the median moment for a median
    clip. Without this, a compressed track sits at level 8-10 for its whole drop, the drop
    grammar adds +1.5 and clips to 10, and ~80% of cuts are cast from the ~5% of clips that
    peak at 10 -> the same 200 clips in every film (2026-09-23 recycling diagnosis)."""
    import numpy as np
    song = np.sort(np.asarray(lvl_series, dtype=float))
    corpus = np.sort(np.concatenate([np.asarray(c.intens, dtype=float) for c in clips if c.intens]))

    def qmap(level: float) -> float:
        q = float(np.searchsorted(song, level, side="right")) / max(1, len(song))
        return float(np.clip(np.quantile(corpus, min(1.0, max(0.0, q))), 1.0, 10.0))
    return qmap


def compose_audio(path: Path, clips, seed=None, jitter=0.5, transient=False,
                  usage=None, rarity_w=0.0, content_w=0.0, topk=1, target_map="raw"):
    """STRUCTURE-AWARE tile of [0, track] on a beat-aligned grid. Detect song structure
    (breakdown/build/drop/outro) and change the editing GRAMMAR per section:
    beats-per-cut and the target level are modulated by `section_grammar`, and the
    clip pick is biased toward each section's feel via `section_vector_pen`. Cuts stay
    beat-aligned (we only change how many beats a cut spans). Returns (seq, sections)."""
    dur, level_at, beats, tempo, times, lvl_series = audio_curve(path)
    sections = detect_sections(times, lvl_series, dur)
    qmap = quantile_mapper(lvl_series, clips) if target_map == "quantile" else None
    bias = 0.33 if qmap else 1.0            # quantile map already places the drop; only nudge
    print("  detected sections:")
    for s in sections:
        print(f"    {s.start:6.1f}s -> {s.end:6.1f}s  [{s.label}]  ({s.end - s.start:.1f}s)")

    rnd = random.Random(seed if seed is not None else path.stem)
    if transient:
        # TRANSIENT MAPPING: lock cuts to the kick where it's pumping, relax to free holds
        # where it drops out. target hold shrinks with kick density; each boundary snaps to the
        # nearest kick onset while the kick is active (density>=0.18), else stands as a free hold.
        import numpy as np
        import bisect
        onsets, kdens = kick_track(path, dur)
        MINH = 0.16
        cuts = [0.0]
        t = 0.0
        while t < dur - 0.3:
            d = kdens(t)
            cand = t + max(MINH, 5.2 - 4.8 * d)         # dense kick → ~0.4s, no kick → ~5.2s
            if d >= 0.18 and onsets:
                lo = bisect.bisect_left(onsets, t + MINH)
                best_k, bestd, k = None, 1e9, lo
                while k < len(onsets) and onsets[k] <= cand + 0.6:
                    if abs(onsets[k] - cand) < bestd:
                        bestd, best_k = abs(onsets[k] - cand), onsets[k]
                    k += 1
                if best_k is None and lo < len(onsets):
                    best_k = onsets[lo]
                b = best_k if best_k is not None else cand
            else:
                b = cand
            b = min(max(b, t + MINH), dur)
            cuts.append(b)
            t = b
        prof = [kdens(x) for x in np.linspace(0, dur, 56)]
        print("  kick density " + "".join(BLOCKS[min(7, int(p * 7))] for p in prof))
        print(f"  {len(onsets)} kick onsets -> cutting kick-gated")
    else:
        # STRUCTURE-AWARE beat grid: beats-per-cut shrinks with loudness, reshaped per section
        cuts = [0.0]
        i = 0
        while i < len(beats) - 1:
            t = beats[i]
            lvl = level_at(t)
            base_bpc = int(max(1, min(8, round(8.5 - 0.78 * lvl))))
            sec = section_at(sections, t)
            span_u = section_span_progress(sec, t)
            bpc, _ = section_grammar(sec.label, base_bpc, lvl, span_u)
            j = min(i + bpc, len(beats) - 1)
            cuts.append(beats[j])
            i = j
    if cuts[-1] < dur - 0.5:
        cuts.append(dur)
    # Guard: no single hold longer than MAX_HOLD. A beatless tail (fade-out past the last
    # detected beat) used to become one ~40s hold; pick_clip doesn't check clip length, so a
    # 4s clip got cast into it and `-shortest` then truncated the song (2026-09-23, MIRROR V02/V03).
    MAX_HOLD = 8.0
    fixed = [cuts[0]]
    for a, b in zip(cuts, cuts[1:]):
        n = max(1, int(math.ceil((b - a) / MAX_HOLD)))
        fixed.extend(a + (b - a) * k / n for k in range(1, n + 1))
    cuts = fixed

    used, last_atmo, seq = set(), "", []
    used_content: Counter = Counter()
    for a, b in zip(cuts, cuts[1:]):
        hold = b - a
        if hold < 0.25:
            continue
        level = level_at(a)
        tslope = sgn(level_at(min(dur, a + 0.4)) - level_at(max(0, a - 0.4)), 0.4)
        sec = section_at(sections, a)
        span_u = section_span_progress(sec, a)
        # section grammar shifts the TARGET the clip-window must match
        _, tgt_level = section_grammar(sec.label, 4, qmap(level) if qmap else level, span_u, bias=bias)
        best = pick_clip(clips, used, tgt_level, tslope, last_atmo, rnd, jitter,
                         section_label=sec.label, usage=usage, used_content=used_content,
                         rarity_w=rarity_w, content_w=content_w, topk=topk)
        if best is None:
            break
        _, c, start, wmean, wslope = best
        if c.dur < 0:
            c.dur = ffdur(c.proxy)
        seek = max(0.0, min(start, max(0.0, c.dur - hold))) if c.dur > 0 else max(0.0, start)
        seq.append({"clip": c, "seek": round(seek, 2), "hold": round(hold, 2),
                    "t0": a, "t1": b,                    # exact beat-grid boundaries (frame-count source)
                    "target": round(tgt_level, 1), "achieved": round(wmean, 1),
                    "tslope": tslope, "vector": c.dom_vector, "atmo": c.dom_atmo,
                    "section": sec.label})
        used.add(c.vid)
        used_content[c.content_key] += 1
        last_atmo = c.dom_atmo
    print(f"  track {dur:.0f}s, tempo~{tempo:.0f} BPM, {len(beats)} beats -> {len(seq)} cuts")
    return seq, sections


def spark(vals: list[float]) -> str:
    return "".join(BLOCKS[max(0, min(7, int(round((v - 1) / 9 * 7))))] for v in vals)


def load_usage_counts():
    """Tally how often each clip (by proxy stem) was placed across PRIOR renders, from the usage
    manifest. Returns a Counter (empty if none yet). Feeds the --rarity bias."""
    counts: Counter = Counter()
    if USAGE_MANIFEST.exists():
        for line in open(USAGE_MANIFEST):
            line = line.strip()
            if not line:
                continue
            try:
                stem = json.loads(line).get("clip")
                if stem:
                    counts[stem] += 1
            except Exception:
                continue
    return counts


def append_usage(label: str, seq: list):
    """Append one JSONL row per placement -> persistent usage telemetry + history for --rarity."""
    OUT.mkdir(parents=True, exist_ok=True)
    with open(USAGE_MANIFEST, "a") as fh:
        for s in seq:
            c = s["clip"]
            fh.write(json.dumps({
                "label": label, "clip": c.proxy.stem, "uid": c.vid,
                "hold": s.get("hold"), "target": s.get("target"),
                "achieved": s.get("achieved"), "section": s.get("section"),
                "tone": c.tone, "atmo": c.dom_atmo}) + "\n")


def render(score: str, seq: list, dry: bool, audio: Path | None = None,
           sections: list | None = None):
    OUT.mkdir(parents=True, exist_ok=True)
    name = score.upper()
    tgt = [s["target"] for s in seq]
    ach = [s["achieved"] for s in seq]
    total = sum(s["hold"] for s in seq)
    fit = sum(abs(a - t) for a, t in zip(ach, tgt)) / max(1, len(seq))

    lines = [f"# {name} — affect score (structure-aware)", "",
             f"A data-composed cut: {len(seq)} clips, ~{total/60:.1f} min, fit to the **{score}** "
             f"intensity curve (mean |target−achieved| = {fit:.2f}). Clip sub-windows chosen so the "
             f"piece's affect intensity tracks the target; `vector` matched to the curve's local slope. "
             f"The editing GRAMMAR (cut-rate, target bias, vector preference) shifts per detected song section.",
             "",
             "**Recipe:** `" + " ".join(a if " " not in a else repr(a) for a in sys.argv[1:]) + "`",
             ""]

    if sections:
        # per-section cut-rate summary
        per = {}
        for s in seq:
            lab = s.get("section", "?")
            per.setdefault(lab, []).append(s["hold"])
        lines += ["## Detected section map", "",
                  "| start | end | label | dur | cuts | mean hold | cuts/min |",
                  "|------:|----:|-------|----:|-----:|----------:|---------:|"]
        for sec in sections:
            holds = per.get(sec.label, [])
            ncut = len(holds)
            mh = (sum(holds) / ncut) if ncut else 0.0
            spd = sec.end - sec.start
            cpm = (ncut / spd * 60.0) if spd > 0 else 0.0
            lines.append(f"| {sec.start:.1f}s | {sec.end:.1f}s | **{sec.label}** | "
                         f"{spd:.1f}s | {ncut} | {mh:.2f}s | {cpm:.1f} |")
        lines.append("")

    lines += ["```",
              "target   " + spark(tgt),
              "achieved " + spark(ach),
              "```",
              "",
              "| # | section | clip | seek | hold | tgt | got | slope | vector | atmosphere |",
              "|--:|---------|------|-----:|-----:|:---:|:---:|:-----:|--------|------------|"]
    for i, s in enumerate(seq, 1):
        sl = {1: "↑", -1: "↓", 0: "→"}[s["tslope"]]
        lines.append(f"| {i} | {s.get('section','-')} | `{s['clip'].proxy.stem}` | {s['seek']}s | {s['hold']}s | "
                     f"{s['target']} | {s['achieved']} | {sl} | {s['vector']} | {s['atmo'][:34]} |")
    (OUT / f"{name}_cut.md").write_text("\n".join(lines))
    print(f"[{score}] {len(seq)} clips, ~{total/60:.1f}min, fit={fit:.2f} -> {OUT / (name+'_cut.md')}")
    print("  target   " + spark(tgt))
    print("  achieved " + spark(ach))
    if dry:
        return

    segdir = SCRATCH / f"as_{score}"          # regenerable scratch; keep off the internal drive
    segdir.mkdir(parents=True, exist_ok=True)
    listfile = segdir / "list.txt"
    seglist = []
    FPS = 24
    for i, s in enumerate(seq):
        seg = segdir / f"seg_{i:03d}.mp4"
        # frame count from the cumulative timeline, so per-cut rounding can't accumulate
        if "t0" in s:
            nf = max(1, int(round(s["t1"] * FPS)) - int(round(s["t0"] * FPS)))
        else:
            nf = max(1, int(round(s["hold"] * FPS)))
        s["frames"] = nf
        cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", str(s["seek"]),
               "-i", str(s["clip"].proxy), "-frames:v", str(nf),
               "-vf", SEG_VF,
               "-r", "24", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(seg)]
        subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        if seg.exists() and seg.stat().st_size > 1000 and ffdur(seg) > 0.3:
            got = ffdur(seg)
            planned = s["frames"] / FPS
            if got < planned - 0.15:        # clip shorter than its hold: freeze the last frame out
                padded = segdir / f"seg_{i:03d}p.mp4"   # to the planned length so picture never
                subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(seg),  # runs short of the track
                                "-vf", f"tpad=stop_mode=clone:stop_duration={planned - got:.3f}",
                                "-r", "24", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                                str(padded)], stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
                if padded.exists() and padded.stat().st_size > 1000:
                    seg = padded
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
                        "-c:a", "aac", "-b:a", "256k", "-t", f"{ffdur(audio):.3f}", str(outmp4)],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
        picture.unlink(missing_ok=True)
        print(f"  rendered {len(seglist)} segments + muxed track -> {outmp4}  ({ffdur(outmp4):.0f}s)")
    else:
        print(f"  rendered {len(seglist)} segments -> {picture}  ({ffdur(picture):.0f}s)")


def main() -> int:
    global FIT_TOL
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", choices=list(CURVES) + ["all"], help="synthetic target curve")
    ap.add_argument("--audio", help="drive the curve from an audio track (the music IS the score)")
    ap.add_argument("--variations", type=int, default=1, help="render N distinct cuts of the same track")
    ap.add_argument("--seed", type=int, default=None, help="base RNG seed (variations = seed, seed+1, ...)")
    ap.add_argument("--diversity", type=float, default=0.5, help="0=always best-fit; higher=wilder/varied")
    ap.add_argument("--dry", action="store_true", help="cut sheet + curve only, no render")
    # structured-facet pool casting — curate the subset the cut draws from
    ap.add_argument("--pool-min-intensity", type=int, default=None, help="cast only clips with peak affect intensity >= N (1-10)")
    ap.add_argument("--pool-tone", default=None, help="cast only clips whose sizzle tone in this comma-list (dramatic,exciting,...)")
    ap.add_argument("--pool-best-for", default=None, help="cast only clips whose sizzle best_for intersects this comma-list (hook,climax,...)")
    ap.add_argument("--pool-min-energy", type=int, default=None, help="cast only clips with sizzle overall_energy >= N (1-10)")
    ap.add_argument("--pool-tone-or-best-for", action="store_true", help="combine --pool-tone and --pool-best-for with OR (cinematic disjunction)")
    ap.add_argument("--pool-root", default=None, help="cast only clips whose source path lives under this directory (cut from one shoot)")
    ap.add_argument("--label", default=None, help="suffix on the output basename (e.g. CAST -> RAV3RZ_CAST_*)")
    ap.add_argument("--transient", action="store_true",
                    help="lock cuts to the KICK (low-band onsets) where it's pumping, relax to "
                         "free holds where it drops out (percussion-reactive editing)")
    # --- corpus-utilization levers (all default off -> identical to the original engine) ---
    ap.add_argument("--content-aware", action="store_true",
                    help="bias selection toward content variety (tone/atmosphere) so the cut draws "
                         "broadly instead of collapsing onto the affect-fit 'golden subset'")
    ap.add_argument("--rarity", action="store_true",
                    help="penalize clips used heavily in PRIOR renders (reads the usage manifest) "
                         "-> spreads draws across the whole corpus over successive cuts")
    ap.add_argument("--select", choices=["greedy", "topk"], default="greedy",
                    help="greedy=always best-fit (default); topk=sample among the K best-fit")
    ap.add_argument("--topk", type=int, default=8, help="K for --select topk")
    ap.add_argument("--target-map", choices=["raw", "quantile"], default="quantile",
                    help="raw = track loudness 1-10 is the target (legacy); quantile = map the track's "
                         "loudness quantile onto the corpus's intensity quantile so the whole pool is "
                         "used in proportion to the song's dynamics")
    ap.add_argument("--fit-tol", type=float, default=None,
                    help=f"opportunity-cost band width in cost-units (default {FIT_TOL}): diversity "
                         "penalties only reorder clips within this fit-distance of the best. lower = "
                         "peaks keep more charge / less spread; higher = more spread / softer peaks")
    args = ap.parse_args()
    if not args.score and not args.audio:
        ap.error("pass --score <curve|all> or --audio <track>")

    def _csv_set(v):
        return {x.strip() for x in v.split(",") if x.strip()} if v else None

    # resolve the diversity levers (0 weights / topk=1 -> baseline greedy best-fit)
    if args.fit_tol is not None:
        FIT_TOL = max(0.0, args.fit_tol)
    rarity_w = 0.4 if args.rarity else 0.0
    content_w = 0.6 if args.content_aware else 0.0
    topk = max(1, args.topk) if args.select == "topk" else 1
    usage = load_usage_counts() if args.rarity else None
    if args.rarity:
        print(f"rarity bias ON: {len(usage)} clips have prior-render history to spread away from")

    print("loading affect catalog ...")
    clips = load_clips(min_peak_intensity=args.pool_min_intensity, tones=_csv_set(args.pool_tone),
                       best_for_any=_csv_set(args.pool_best_for), min_energy=args.pool_min_energy,
                       tone_or_best_for=args.pool_tone_or_best_for,
                       pool_root=Path(args.pool_root).expanduser() if args.pool_root else None)
    print(f"{len(clips)} clips with usable affect time-series + proxies")
    if args.audio:
        apath = Path(args.audio)
        base = apath.stem.upper().replace(" ", "_").replace(".", "_")
        if args.label:
            base = f"{base}_{args.label.upper()}"
        n = max(1, args.variations)
        print(f"composing to track: {apath.name}  ({n} variation{'s' if n > 1 else ''}, diversity {args.diversity})")
        for i in range(n):
            seed = (args.seed if args.seed is not None else 1) + i
            label = f"{base}_V{seed:02d}" if (n > 1 or args.seed is not None) else base
            print(f"--- {label} (seed {seed}) ---")
            seq, sections = compose_audio(apath, clips, seed=seed, jitter=args.diversity,
                                          transient=args.transient, usage=usage,
                                          rarity_w=rarity_w, content_w=content_w, topk=topk,
                                          target_map=args.target_map)
            render(label, seq, args.dry, audio=apath, sections=sections)
            if usage is not None:                       # accumulate within this run (rarity)
                usage.update(s["clip"].proxy.stem for s in seq)
            if not args.dry:                            # persist real renders only
                append_usage(label, seq)
        return 0
    scores = list(CURVES) if args.score == "all" else [args.score]
    for sc in scores:
        seq = compose(sc, clips, jitter=args.diversity, usage=usage,
                      rarity_w=rarity_w, content_w=content_w, topk=topk)
        name = f"{sc}_{args.label.upper()}" if args.label else sc
        render(name, seq, args.dry)
        if usage is not None:
            usage.update(s["clip"].proxy.stem for s in seq)
        if not args.dry:
            append_usage(name, seq)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
