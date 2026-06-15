#!/usr/bin/env python3
"""Re-collect a finished cloud-batch run from its still-alive jobs — $0, no re-analysis.

The first collect() aligned responses to keys by position, but batch returns them OUT of
submission order, so analyses were mislabeled by mode. This re-fetches the jobs and rebuilds
the catalog using the FIXED collect() (which aligns by each response's metadata key).

Usage:
  uv run python scripts/recollect_from_jobs.py --log /tmp/catalog_run2.log \
      --out "/Volumes/.../_cloud_catalog"
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from dotenv import load_dotenv

from video_analyzer.analyzer import configure_genai, get_client
from video_analyzer.batch_cloud import JobSpec, collect, select_clips

load_dotenv()
DRIVE = "/Volumes/2025_exSSD_2tb/Photography + Video"
MODES = ["sizzle", "affect", "zizek", "hauntology", "sontag"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="run log containing batches/... job names")
    ap.add_argument("--out", default=str(Path(DRIVE) / "_cloud_catalog"))
    ap.add_argument("--root", default=DRIVE)
    args = ap.parse_args()
    out = Path(args.out)

    configure_genai()
    client = get_client()

    job_names = list(dict.fromkeys(re.findall(r"(batches/\w+)", Path(args.log).read_text())))
    print(f"jobs: {len(job_names)}")

    # uid -> Clip mapping (superset; skip_analyzed=False so the full run set resolves)
    clips = select_clips(Path(args.root), MODES, out, skip_analyzed=False)
    print(f"clip mapping: {len(clips)} clips")

    specs = []
    for jn in job_names:
        j = client.batches.get(name=jn)
        specs.append(JobSpec(job=j, keys=[]))  # keys unused; collect aligns by metadata
        n = len(j.dest.inlined_responses) if (j.dest and j.dest.inlined_responses) else 0
        print(f"  {jn} {j.state.name} ({n} responses)")

    # clear the mislabeled raw sidecars before rebuild
    raw = out / "_raw"
    if raw.exists():
        shutil.rmtree(raw)

    summary = collect(specs, clips, out)
    print(f"\nRECOLLECTED -> {out}")
    print(f"clean={summary['n_ok']}  salvaged={summary['n_salvaged']}  err={summary['n_err']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
