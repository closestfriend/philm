#!/usr/bin/env python3
"""Design §6: drive degenerate readers through the scorer on REAL data before any run is paid for.

  uv run python scripts/reliability/redteam.py --arm A0

Checks, each printed PASS/FAIL with the number behind it:
  copy      the arm's run1 fed back as a second run must give alpha = 1 on every field
  null      a constant reader (5 / neutral / false) against run1 must give alpha <= 0.1
            on intensity and vector (captures may be undefined when run1 is near-constant)
  shuffle   run1 against 50 clip-permuted copies of itself: the MEAN alpha on intensity
            must be <= 0.15. A single permutation is not a check: at n = 40 clips the
            permutation sd is about 0.14, so one draw can land at 0.3 by chance. The mean
            and sd are printed because they are the noise floor every alpha is read against.
  missing   dropping one clip from the copy must show as missing=1, with alpha still 1
  same_time a run with every moment at 00:00 must be FLAGGED (all_same_time), not rejected
"""
from __future__ import annotations

import argparse
import copy
import json
import math

from .align import Bins, moments_from_result, to_bins
from .score import (FIELD_LEVEL, ClipRun, alpha, load_manifest, load_run, matrix,
                    missing_and_flags, permutation_floor)


def null_run(run: dict[str, ClipRun]) -> dict[str, ClipRun]:
    out = {}
    for cid, cr in run.items():
        if cr.bins is None:
            continue
        n = cr.bins.n
        out[cid] = ClipRun(cid, Bins([5.0] * n, ["neutral"] * n, [False] * n, {"null_reader"}))
    return out


def alphas(runs, clip_ids, clips) -> dict[str, float]:
    return {f: alpha(matrix(runs, clip_ids, clips, f), lvl) for f, lvl in FIELD_LEVEL.items()}


def check(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:10s} {detail}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A0")
    ap.add_argument("--run", default="run1")
    args = ap.parse_args()
    clips = load_manifest()
    run1 = load_run(args.arm, args.run, clips)
    clip_ids = sorted(c for c, cr in run1.items() if cr.bins)
    print(f"{args.arm}/{args.run}: {len(clip_ids)} parsed clips, "
          f"{sum(cr.bins.n for cr in run1.values() if cr.bins)} bins")
    results = []

    a = alphas([run1, copy.deepcopy(run1)], clip_ids, clips)
    results.append(check("copy", all(abs(v - 1) < 1e-9 for v in a.values() if not math.isnan(v))
                         and not math.isnan(a["intensity"]), json.dumps({k: round(v, 3) for k, v in a.items()})))

    a = alphas([run1, null_run(run1)], clip_ids, clips)
    results.append(check("null", (a["intensity"] <= 0.1) and (math.isnan(a["vector"]) or a["vector"] <= 0.1),
                         json.dumps({k: round(v, 3) for k, v in a.items()})))

    pf = {f: permutation_floor(run1, clip_ids, clips, f) for f in FIELD_LEVEL}
    results.append(check("shuffle", pf["intensity"]["mean"] <= 0.15,
                         "floor " + json.dumps({k: f"{v['mean']:.3f}±{v['sd']:.3f}" for k, v in pf.items()})))

    partial = copy.deepcopy(run1)
    partial[clip_ids[0]] = ClipRun(clip_ids[0], None)
    mf = missing_and_flags({"run1": run1, "copy": partial}, clip_ids)
    a = alphas([run1, partial], clip_ids, clips)
    results.append(check("missing", mf["copy"]["missing"] == 1 and abs(a["intensity"] - 1) < 1e-9,
                         f"missing={mf['copy']['missing']} alpha_intensity={a['intensity']:.3f}"))

    sample = next(iter(run1.values()))
    same = {"timecodes": [{"time": "00:00", "intensity": 3 + i % 5, "atmosphere": "", "vector": "static",
                           "captures": False} for i in range(4)]}
    m, fl = moments_from_result(same)
    b = to_bins(m, 60.0, fl)
    results.append(check("same_time", "all_same_time" in b.flags and b.n == 12 and b.intensity[0] == b.intensity[-1],
                         f"flags={sorted(b.flags)} bins={b.n} (sample clip {sample.clip_id})"))

    print("all checks passed" if all(results) else "RED-TEAM FAILURES: fix the scorer before running arms")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
