#!/usr/bin/env python3
"""Backfill clip-level facet columns (sizzle energy/tone/best_for, affect peak/mean intensity,
dominant atmosphere) onto existing archive rows from the catalog JSONs.

These top-level fields are dropped by the normal importer; this re-derives them and UPDATEs the
`videos` rows in place (no moment re-insert → no duplication). Future imports populate them
automatically via the updated store_analysis.

Usage:
  uv run python scripts/backfill_facets.py
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from video_analyzer.archive import Archive

CATALOG = "/Volumes/2025_exSSD_2tb/Photography + Video/_cloud_catalog"


def main() -> int:
    arc = Archive(None)
    arc.init_db()  # runs the migration → facet columns exist
    updated = missing = nofacets = 0
    for f in glob.glob(CATALOG + "/*.json"):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        path = d.get("path")
        if not path:
            continue
        v = arc.get_video_by_path(Path(path))
        if not v:
            missing += 1
            continue
        facets: dict = {}
        for mode, res in d.get("analyses", {}).items():
            if isinstance(res, dict) and "error" not in res:
                facets.update(Archive.compute_facets(mode, res))
        if facets:
            arc.update_video(v["id"], **facets)
            updated += 1
        else:
            nofacets += 1
    arc.close()
    print(f"backfilled facets onto {updated} videos | {missing} JSON paths not in DB | {nofacets} had no facets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
