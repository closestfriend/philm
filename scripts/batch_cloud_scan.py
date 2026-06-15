#!/usr/bin/env python3
"""Run an asynchronous Gemini Batch API scan over an archive (50%-off, low-res proxies).

Pipeline lives in ``video_analyzer.batch_cloud``. This is the thin runner (mirrors
metered_scan.py). Model is hard-pinned to gemini-2.5-flash-lite; a cost ceiling is
asserted before any spend.

Examples:
  # Stage-1 pilot — ~30 clips, tiny ceiling, full run:
  uv run python scripts/batch_cloud_scan.py \
      --root "/Volumes/2025_exSSD_2tb/Photography + Video/Photography-by-Hunter-Karman/100CANON/home session 2026" \
      --limit 30 --modes sizzle,affect,zizek --ceiling 1 --yes

  # Dry-run projection only (no --yes): prints projected cost and exits.
  uv run python scripts/batch_cloud_scan.py --root "<path>" --modes sizzle,affect,zizek
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from video_analyzer.batch_cloud import run_cloud_batch

load_dotenv()  # picks up GEMINI_API_KEY from .env (mirrors cli.py); contents never printed

DRIVE = "/Volumes/2025_exSSD_2tb/Photography + Video"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DRIVE, help="folder to scan (recursively)")
    ap.add_argument("--modes", default="sizzle,affect",
                    help="base modes applied to EVERY clip")
    ap.add_argument("--rotate-theory", default="zizek,hauntology,sontag",
                    help="theory lenses rotated one-per-clip across the archive "
                         "(empty string to disable)")
    ap.add_argument("--art", dest="art", action="store_true", default=True,
                    help="apply the contemporary-art reframing to sizzle (default on)")
    ap.add_argument("--no-art", dest="art", action="store_false",
                    help="use the original commercial sizzle prompt")
    ap.add_argument("--ceiling", type=float, default=20.0,
                    help="abort if projected full-price cost exceeds this (USD)")
    ap.add_argument("--limit", type=int, default=None, help="cap clip count (pilot)")
    ap.add_argument("--yes", action="store_true",
                    help="proceed past projection to upload + submit (else dry-run)")
    ap.add_argument("--no-skip-analyzed", action="store_true",
                    help="re-analyze clips even if a result JSON already exists")
    ap.add_argument("--include-prior", action="store_true",
                    help="include clips earlier (non-cloud) philm runs touched — closes the "
                         "gap from old runs while still resume-skipping this catalog")
    ap.add_argument("--proxy-dir", default=str(Path(DRIVE) / "_proxies"))
    ap.add_argument("--out", default=str(Path(DRIVE) / "_cloud_catalog"))
    ap.add_argument("--proxy-workers", type=int, default=6)
    ap.add_argument("--upload-workers", type=int, default=4)
    ap.add_argument("--max-per-job", type=int, default=1000)
    args = ap.parse_args()

    base_modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    rotate = [m.strip() for m in args.rotate_theory.split(",") if m.strip()] or None
    summary = run_cloud_batch(
        root=Path(args.root), base_modes=base_modes,
        rotate_theory=rotate, art=args.art,
        proxy_root=Path(args.proxy_dir), out_dir=Path(args.out),
        ceiling=args.ceiling, limit=args.limit,
        skip_analyzed=not args.no_skip_analyzed,
        skip_prior_runs=(False if args.include_prior else None),
        assume_yes=args.yes,
        proxy_workers=args.proxy_workers, upload_workers=args.upload_workers,
        max_per_job=args.max_per_job,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "errors"},
                     indent=2, default=str))
    return 0 if summary.get("status") in {"done", "dry-run", "empty"} else 1


if __name__ == "__main__":
    sys.exit(main())
