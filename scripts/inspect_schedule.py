#!/usr/bin/env python3
"""
inspect_schedule.py — Reconstruct a carti_cut schedule deterministically from its seed.

Given the same music + clip pool + seed (printed at render time and saved in the render's
.json sidecar) we re-derive the exact cut plan WITHOUT rendering.
Reports: beat reading, lip-sync placement, effect distribution, clip frequency.
"""

import argparse
import random
from pathlib import Path

import carti_cut as cc


def build_pool(clips_dir: Path, exclude: str, lipsync: Path | None, lipsync_weight: float,
               seed: int, lipsync_offset: float):
    """Same pool carti_cut.main() builds for this seed (order, weights AND B-roll offsets)."""
    clip_files = sorted(
        p for p in clips_dir.rglob("*")
        if p.suffix.lower() in cc.VIDEO_EXTS
        and (not exclude or exclude not in str(p))
    )
    pool, _ = cc.build_clip_pool(clip_files, [lipsync] if lipsync else None, lipsync_weight,
                                 random.Random(seed),
                                 lipsync_offsets=[lipsync_offset] if lipsync else None)
    return pool, len(clip_files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", required=True, type=Path)
    ap.add_argument("--clips", required=True, type=Path)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--lipsync", type=Path)
    ap.add_argument("--lipsync-weight", type=float, default=3.0)
    ap.add_argument("--lipsync-offset", type=float, default=0.0,
                    help="Song second at which the take begins (from the render's .json sidecar)")
    ap.add_argument("--seed", required=True, type=int)
    args = ap.parse_args()

    video_duration = cc.probe_duration(args.music)
    beat_times, _tempo = cc.detect_beats(args.music, video_duration)

    pool, n_broll = build_pool(args.clips, args.exclude, args.lipsync, args.lipsync_weight,
                               args.seed, args.lipsync_offset)
    schedule = cc.build_cut_schedule(beat_times, pool, seed=args.seed)

    # ── Report ──────────────────────────────────────────────────────────────
    ls_id = args.lipsync.stem if args.lipsync else None
    ls_hits = [e for e in schedule if e.get("lip_sync")]
    from collections import Counter
    eff = Counter(e["effect"] for e in schedule)
    freq = Counter(e["clip_id"] for e in schedule)

    print(f"\n{'='*64}")
    print(f"SCHEDULE RECONSTRUCTION — seed {args.seed}")
    print(f"{'='*64}")
    print(f"Track duration : {video_duration:.1f}s")
    print(f"B-roll clips   : {n_broll}  (+1 lip-sync)" if ls_id else f"B-roll clips   : {n_broll}")
    print(f"Total cuts     : {len(schedule)}")
    print(f"Avg cut length : {sum(e['duration'] for e in schedule)/len(schedule):.3f}s")
    print(f"Effects        : {dict(eff)}")
    print(f"Flash frames   : {sum(1 for e in schedule if e['flash_before'])}")
    print(f"Stutters       : {sum(1 for e in schedule if e['stutter'])}")

    if ls_id:
        pct = 100 * len(ls_hits) / len(schedule)
        print(f"\nLIP-SYNC ('{ls_id}'):")
        print(f"  Appearances  : {len(ls_hits)} / {len(schedule)} cuts ({pct:.1f}%)")
        print(f"  Song-locked at (first 15): " +
              ", ".join(f"{e['beat_time']:.1f}s" for e in ls_hits[:15]))
        # Longest unbroken lip-sync runs (consecutive beats)
        runs, cur = [], 0
        for e in schedule:
            if e.get("lip_sync"):
                cur += 1
            else:
                if cur: runs.append(cur)
                cur = 0
        if cur: runs.append(cur)
        if runs:
            print(f"  Consecutive runs: {sorted(runs, reverse=True)[:8]} (beats in a row)")

    print("\nTOP 10 MOST-USED CLIPS:")
    for cid, n in freq.most_common(10):
        tag = "  ← LIP-SYNC" if cid == ls_id else ""
        print(f"  {n:3d}×  {cid}{tag}")


if __name__ == "__main__":
    main()
