"""Agreement statistics for the affect reliability study (design §5).

Run files live at docs/reliability/runs/<arm>/<run>/<clip_id>.json with the shape
  {"clip_id", "arm", "run", "model", "temperature", "parsed": bool,
   "result": AffectResult dict | null, "raw": str, "usage": {...}}
A run whose `parsed` is false contributes nothing for that clip: the clip is MISSING in
that run, never zero.

All agreement is chance-corrected (Krippendorff's alpha; interval for intensity, nominal
for vector and captures). Units are (clip, bin); raters are runs. Confidence intervals
are bootstrapped over CLIPS, because bins within a clip are not independent.

  uv run python scripts/reliability/score.py --arm A0           # describe one arm
  uv run python scripts/reliability/score.py --arm B --boot 1000  # with CIs
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import krippendorff
import numpy as np
from scipy.stats import spearmanr

from .align import Bins, moments_from_result, to_bins

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "docs" / "reliability" / "runs"
MANIFEST = REPO / "docs" / "reliability" / "sample_manifest.json"

VECTOR_CODES = {v: i for i, v in enumerate([
    "expanding", "outward", "forward", "toward", "upward",
    "contracting", "inward", "receding", "away", "downward", "static", "neutral",
])}

# ---------------------------------------------------------------- loading


@dataclass
class ClipRun:
    clip_id: str
    bins: Optional[Bins]  # None when the run did not parse for this clip


def load_manifest(path: Path = MANIFEST) -> dict[str, dict]:
    m = json.loads(path.read_text())
    return {c["clip_id"]: c for c in m["clips"]}


def bins_from_run_file(rec: dict, duration: float, *, normalize_vectors: bool) -> Optional[Bins]:
    if not rec.get("parsed") or not rec.get("result"):
        return None
    moments, flags = moments_from_result(rec["result"], normalize_vectors=normalize_vectors)
    return to_bins(moments, duration, flags)


def load_run(arm: str, run: str, clips: dict[str, dict], *, root: Path = RUNS) -> dict[str, ClipRun]:
    """One run of one arm: {clip_id: ClipRun}. A0 rows carry free-text vectors."""
    out: dict[str, ClipRun] = {}
    for cid, c in clips.items():
        f = root / arm / run / f"{cid}.json"
        if not f.exists():
            continue
        rec = json.loads(f.read_text())
        out[cid] = ClipRun(cid, bins_from_run_file(rec, c["duration"], normalize_vectors=(arm == "A0")))
    return out


def load_arm(arm: str, clips: dict[str, dict], *, root: Path = RUNS) -> dict[str, dict[str, ClipRun]]:
    d = root / arm
    if not d.exists():
        return {}
    return {r.name: load_run(arm, r.name, clips, root=root) for r in sorted(d.iterdir()) if r.is_dir()}


# ---------------------------------------------------------------- matrices


def _units(clip_ids: Iterable[str], clips: dict[str, dict]) -> list[tuple[str, int]]:
    from .align import n_bins
    return [(cid, b) for cid in clip_ids for b in range(n_bins(clips[cid]["duration"]))]


def matrix(runs: list[dict[str, ClipRun]], clip_ids: list[str], clips: dict[str, dict], field: str) -> np.ndarray:
    """raters x units, np.nan where a run lacks a value. `field` in intensity|vector|captures."""
    units = _units(clip_ids, clips)
    M = np.full((len(runs), len(units)), np.nan)
    for i, run in enumerate(runs):
        for j, (cid, b) in enumerate(units):
            cr = run.get(cid)
            if cr is None or cr.bins is None or b >= cr.bins.n:
                continue
            v = getattr(cr.bins, field)[b]
            if v is None:
                continue
            if field == "vector":
                v = VECTOR_CODES.get(v)
                if v is None:
                    continue
            elif field == "captures":
                v = 1.0 if v else 0.0
            M[i, j] = float(v)
    return M


def alpha(M: np.ndarray, level: str) -> float:
    """Krippendorff's alpha; nan when undefined (no variance, or fewer than two paired values)."""
    paired = (~np.isnan(M)).sum(axis=0) >= 2
    if paired.sum() < 2:
        return float("nan")
    try:
        return float(krippendorff.alpha(reliability_data=M[:, paired], level_of_measurement=level))
    except (ValueError, ZeroDivisionError, FloatingPointError):
        return float("nan")


FIELD_LEVEL = {"intensity": "interval", "vector": "nominal", "captures": "nominal"}


def bootstrap_alpha(runs: list[dict[str, ClipRun]], clip_ids: list[str], clips: dict[str, dict],
                    field: str, n_boot: int, seed: int = 0) -> tuple[float, float, float]:
    """(alpha, lo, hi) with a 95% percentile interval from resampling clips."""
    point = alpha(matrix(runs, clip_ids, clips, field), FIELD_LEVEL[field])
    if n_boot <= 0 or len(clip_ids) < 2:
        return point, float("nan"), float("nan")
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        sample = [rng.choice(clip_ids) for _ in clip_ids]
        # duplicate clips must be distinct units, so give each draw its own id suffix
        fake_clips = {f"{cid}#{k}": clips[cid] for k, cid in enumerate(sample)}
        fake_runs = [{f"{cid}#{k}": run[cid] for k, cid in enumerate(sample) if cid in run} for run in runs]
        a = alpha(matrix(fake_runs, list(fake_clips), fake_clips, field), FIELD_LEVEL[field])
        if not np.isnan(a):
            draws.append(a)
    if len(draws) < 20:
        return point, float("nan"), float("nan")
    draws.sort()
    return point, draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


# ---------------------------------------------------------------- permutation floor


def shuffled_run(run: dict[str, ClipRun], seed: int) -> dict[str, ClipRun]:
    """The run with clip ids permuted (no clip keeps its own id), each donor's bins tiled
    or cut to the receiver's length. Agreement with the original is what unrelated clips
    score, i.e. the floor every alpha is read against."""
    ids = [c for c, cr in run.items() if cr.bins]
    perm = ids[:]
    random.Random(seed).shuffle(perm)
    for i, (a, b) in enumerate(zip(ids, perm)):  # break fixed points by swapping with a neighbour
        if a == b:
            j = (i + 1) % len(perm)
            perm[i], perm[j] = perm[j], perm[i]
    out = {}
    for src, dst in zip(ids, perm):
        b = run[src].bins
        n = run[dst].bins.n
        k = n // b.n + 1
        out[dst] = ClipRun(dst, Bins((b.intensity * k)[:n], (b.vector * k)[:n], (b.captures * k)[:n], set(b.flags)))
    return out


def permutation_floor(run: dict[str, ClipRun], clip_ids: list[str], clips: dict[str, dict],
                      field: str, n_perm: int = 50) -> dict:
    """Mean and sd of alpha between `run` and `n_perm` clip-permuted copies of itself."""
    vals = []
    for s in range(n_perm):
        a = alpha(matrix([run, shuffled_run(run, s)], clip_ids, clips, field), FIELD_LEVEL[field])
        if not np.isnan(a):
            vals.append(a)
    if len(vals) < 5:
        return {"mean": float("nan"), "sd": float("nan"), "n": len(vals)}
    return {"mean": statistics.fmean(vals), "sd": statistics.pstdev(vals), "n": len(vals)}


# ---------------------------------------------------------------- clip level


def clip_summary(run: dict[str, ClipRun], clip_ids: list[str]) -> dict[str, tuple[float, float]]:
    """{clip_id: (mean intensity, peak intensity)} for the clips this run parsed."""
    out = {}
    for cid in clip_ids:
        cr = run.get(cid)
        if cr is None or cr.bins is None:
            continue
        vals = [v for v in cr.bins.intensity if v is not None]
        if vals:
            out[cid] = (statistics.fmean(vals), max(vals))
    return out


def pairwise_clip_agreement(runs: list[dict[str, ClipRun]], clip_ids: list[str]) -> dict:
    """Mean over run pairs of Spearman rho on clip mean and clip peak, plus the mean
    absolute difference in clip means (in intensity points)."""
    sums = [clip_summary(r, clip_ids) for r in runs]
    rho_mean, rho_peak, mad = [], [], []
    for i in range(len(sums)):
        for j in range(i + 1, len(sums)):
            common = [c for c in clip_ids if c in sums[i] and c in sums[j]]
            if len(common) < 3:
                continue
            a_m = [sums[i][c][0] for c in common]; b_m = [sums[j][c][0] for c in common]
            a_p = [sums[i][c][1] for c in common]; b_p = [sums[j][c][1] for c in common]
            rho_mean.append(float(spearmanr(a_m, b_m).statistic))
            rho_peak.append(float(spearmanr(a_p, b_p).statistic))
            mad.append(statistics.fmean(abs(x - y) for x, y in zip(a_m, b_m)))
    f = lambda xs: statistics.fmean(xs) if xs else float("nan")  # noqa: E731
    return {"rho_mean": f(rho_mean), "rho_peak": f(rho_peak), "mad_mean_points": f(mad), "pairs": len(mad)}


# ---------------------------------------------------------------- reports


def missing_and_flags(runs: dict[str, dict[str, ClipRun]], clip_ids: list[str]) -> dict:
    out = {}
    for name, run in runs.items():
        missing = [c for c in clip_ids if c not in run or run[c].bins is None]
        flags: dict[str, int] = {}
        for c in clip_ids:
            cr = run.get(c)
            if cr and cr.bins:
                for fl in cr.bins.flags:
                    flags[fl] = flags.get(fl, 0) + 1
        out[name] = {"missing": len(missing), "flags": flags}
    return out


def describe_arm(arm: str, clips: dict[str, dict], *, n_boot: int = 0, root: Path = RUNS) -> dict:
    runs = load_arm(arm, clips, root=root)
    if not runs:
        return {"arm": arm, "error": "no runs on disk"}
    clip_ids = sorted({c for r in runs.values() for c in r})
    rep = {"arm": arm, "runs": list(runs), "clips": len(clip_ids),
           "missing_and_flags": missing_and_flags(runs, clip_ids)}
    rl = list(runs.values())
    rep["permutation_floor"] = {f: permutation_floor(rl[0], clip_ids, clips, f) for f in FIELD_LEVEL}
    if len(rl) >= 2:
        rep["test_retest"] = {
            f: dict(zip(("alpha", "lo", "hi"), bootstrap_alpha(rl, clip_ids, clips, f, n_boot)))
            for f in FIELD_LEVEL
        }
        rep["clip_level"] = pairwise_clip_agreement(rl, clip_ids)
    return rep


def cross_arm(arms: list[str], clips: dict[str, dict], *, run: str = "run1", n_boot: int = 0,
              root: Path = RUNS) -> dict:
    """One run per arm, alpha across arms, on the clips every arm parsed."""
    runs = [load_run(a, run, clips, root=root) for a in arms]
    clip_ids = sorted(set.intersection(*(set(c for c, cr in r.items() if cr.bins) for r in runs)))
    rep = {"arms": arms, "run": run, "clips": len(clip_ids)}
    rep["alpha"] = {f: dict(zip(("alpha", "lo", "hi"), bootstrap_alpha(runs, clip_ids, clips, f, n_boot)))
                    for f in FIELD_LEVEL}
    rep["clip_level"] = pairwise_clip_agreement(runs, clip_ids)
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True, help="repeat for a cross-arm comparison")
    ap.add_argument("--boot", type=int, default=0)
    args = ap.parse_args()
    clips = load_manifest()
    if len(args.arm) == 1:
        print(json.dumps(describe_arm(args.arm[0], clips, n_boot=args.boot), indent=1))
    else:
        print(json.dumps(cross_arm(args.arm, clips, n_boot=args.boot), indent=1))


if __name__ == "__main__":
    main()
