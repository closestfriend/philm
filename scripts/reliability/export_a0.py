#!/usr/bin/env python3
"""Export the incumbent readings (arm A0) from ~/.vanalyze/archive.db into run files.

  uv run python scripts/reliability/export_a0.py

Writes docs/reliability/runs/A0/run1/<clip_id>.json for every manifest clip with
arm_a0 = true, in the same shape every live arm will write, so the scorer treats the
archive as just another run. Vectors are kept as the free text the archive holds; the
scorer normalises them for A0 only (design §2) and counts the unmappable ones.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .score import MANIFEST, RUNS

ARCHIVE_DB = Path(os.path.expanduser("~/.vanalyze/archive.db"))


def main() -> None:
    clips = {c["clip_id"]: c for c in json.loads(MANIFEST.read_text())["clips"] if c["arm_a0"]}
    db = sqlite3.connect(ARCHIVE_DB)
    out_dir = RUNS / "A0" / "run1"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for cid, c in clips.items():
        row = db.execute("SELECT id, description FROM videos WHERE path = ?", (c["path"],)).fetchone()
        if row is None:
            print("  no archive row for", c["rel"])
            continue
        vid, desc = row
        moments = db.execute(
            "SELECT timecode, intensity, atmosphere, vector, captures FROM affect_moments "
            "WHERE video_id = ? ORDER BY id", (vid,)
        ).fetchall()
        rec = {
            "clip_id": cid, "arm": "A0", "run": "run1",
            "model": "gemini-2.5-flash-lite (native batch API, media_resolution=LOW, 2026-06)",
            "temperature": 0.5,
            "parsed": bool(moments),
            "result": {
                "video_description": desc or "",
                "timecodes": [
                    {"time": t, "intensity": i, "atmosphere": a, "vector": v, "captures": bool(cp) if cp is not None else None}
                    for t, i, a, v, cp in moments
                ],
            } if moments else None,
            "raw": "", "usage": {},
        }
        (out_dir / f"{cid}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        written += 1
    print(f"wrote {written} A0 run files to {out_dir}")


if __name__ == "__main__":
    main()
