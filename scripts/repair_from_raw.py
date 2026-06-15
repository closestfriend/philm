#!/usr/bin/env python3
"""Re-salvage errored analyses from saved raw responses — no new API spend.

When a cloud-batch analysis fails to parse, collect() saves the raw model output under
``_raw/{uid}__{mode}.txt``. This re-runs the (improved) salvage_parse over those raws and
patches the per-clip JSON in place, recovering analyses for free.

Usage:
  uv run python scripts/repair_from_raw.py --out "/path/_cloud_catalog"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_analyzer.batch_cloud import salvage_parse
from video_analyzer.modes import get_mode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="catalog dir (holds clip JSONs + _raw/)")
    args = ap.parse_args()
    out = Path(args.out)
    raw_dir = out / "_raw"

    recovered = still_err = no_raw = 0
    for f in out.glob("*.json"):
        if f.name.startswith("_"):
            continue
        d = json.load(open(f))
        changed = False
        for mode_name, a in list(d["analyses"].items()):
            if not (isinstance(a, dict) and "error" in a):
                continue
            raw_f = raw_dir / f"{d['uid']}__{mode_name}.txt"
            if not raw_f.exists():
                no_raw += 1
                continue
            try:
                parsed, _ = salvage_parse(get_mode(mode_name).result_model, raw_f.read_text())
                rec = parsed.model_dump()
                rec["_salvaged"] = True
                rec["_repaired_from_raw"] = True
                d["analyses"][mode_name] = rec
                recovered += 1
                changed = True
            except Exception:
                still_err += 1
        if changed:
            json.dump(d, open(f, "w"), indent=2)

    print(f"recovered: {recovered} | still error: {still_err} | no raw saved: {no_raw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
