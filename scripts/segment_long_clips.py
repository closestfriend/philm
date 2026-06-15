#!/usr/bin/env python3
"""Segment long takes into chunks, analyze each, fold them into the catalog.

Long source clips (proxy duration > --min-len) are sliced into ~--chunk-len segments. Each
chunk is analyzed (sizzle-art + affect + rotating theory) as its OWN clip — with reliable,
complete timecodes (short clips don't hallucinate) and its own description (so long takes
become searchable at chunk granularity). The original long clip is flagged ``segmented`` so
the affect engine and every future cut use the chunks instead of the one-shot whole.

Reuses the batch_cloud pipeline (upload -> batch -> collect). Chunk proxies live in
``_proxies_segments/``; chunk catalog JSONs carry an explicit ``proxy`` + ``segment_of``.

Usage:
  uv run python scripts/segment_long_clips.py --min-len 300 --chunk-len 150 --yes
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from video_analyzer.batch_cloud import (
    Clip, THEORY_CYCLE, configure_genai, upload_proxies, plan_tasks, submit, poll,
    collect, cleanup_uploads, project_cost, assert_under_ceiling, ffdur)

load_dotenv()
ROOT = Path("/Volumes/2025_exSSD_2tb/Photography + Video")
PROXY_ROOT = ROOT / "_proxies"
CATALOG = ROOT / "_cloud_catalog"
SEG_PROXY = ROOT / "_proxies_segments"
SEG_OUT = ROOT / "_segments_tmp"


def proxy_for(path: str) -> Path | None:
    try:
        rel = os.path.relpath(path, ROOT)
    except ValueError:
        return None
    if rel.startswith(".."):
        return None
    p = PROXY_ROOT / (os.path.splitext(rel)[0] + ".mp4")
    return p if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-len", type=float, default=300.0, help="segment clips longer than this (s)")
    ap.add_argument("--chunk-len", type=float, default=150.0, help="target chunk length (s)")
    ap.add_argument("--ceiling", type=float, default=10.0)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--upload-workers", type=int, default=8)
    args = ap.parse_args()
    configure_genai()

    # 1. find long catalog clips (by real proxy duration); skip already-segmented + chunks
    print(f"scanning catalog for clips > {args.min_len:.0f}s ...")
    longs = []
    for f in sorted(CATALOG.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("segmented") or d.get("segment_of"):
            continue
        proxy = Path(d["proxy"]) if d.get("proxy") else proxy_for(d.get("path", ""))
        if not proxy or not proxy.exists():
            continue
        dur = ffdur(proxy)
        if dur > args.min_len:
            longs.append((f, proxy, dur))
    print(f"long takes found: {len(longs)}  ({sum(x[2] for x in longs)/3600:.1f} h of footage)")
    if not longs:
        return 0

    # 2. slice each proxy into chunks (stream-copy on keyframes), build chunk Clips
    if SEG_PROXY.exists():
        pass
    SEG_PROXY.mkdir(parents=True, exist_ok=True)
    chunks, origin = [], {}
    for f, proxy, dur in longs:
        rel = os.path.relpath(proxy, PROXY_ROOT)            # <reldir>/<stem>.mp4
        reldir, stem = os.path.dirname(rel), Path(rel).stem
        outdir = SEG_PROXY / reldir
        outdir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(proxy),
                        "-c", "copy", "-map", "0", "-f", "segment",
                        "-segment_time", str(args.chunk_len), "-reset_timestamps", "1",
                        str(outdir / f"{stem}_seg%03d.mp4")],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=600)
        origpath = json.load(open(f)).get("path", "")
        for i, seg in enumerate(sorted(outdir.glob(f"{stem}_seg*.mp4"))):
            sl = ffdur(seg)
            if sl < 2.0:
                continue
            fake = ROOT / reldir / f"{stem}__seg{i:02d}.mov"   # → unique uid; proxy is the chunk
            c = Clip(src=fake, root=ROOT)
            c.proxy, c.seconds = seg, sl
            chunks.append(c)
            origin[c.uid] = {"path": str(seg), "proxy": str(seg), "segment_of": origpath,
                             "seg_index": i, "seg_start": round(i * args.chunk_len, 1),
                             "orig_json": str(f)}
    print(f"chunks: {len(chunks)} from {len(longs)} long takes "
          f"(avg {len(chunks)/max(1,len(longs)):.1f} per take)")
    if not chunks:
        return 0

    # 3. cost guard
    total_s = sum(c.seconds for c in chunks)
    proj = project_cost(len(chunks), total_s, ["sizzle", "affect", "zizek"])
    print(f"PROJECTED full ${proj['grand_full']:.2f} / batched ${proj['grand_batched']:.2f} "
          f"(ceiling ${args.ceiling:.2f})")
    assert_under_ceiling(proj, args.ceiling)
    if not args.yes:
        print("pass --yes to upload + analyze the chunks")
        return 0

    # 4. upload chunk proxies + analyze (sizzle-art + affect + rotating theory)
    chunks = upload_proxies(chunks, workers=args.upload_workers)
    uploaded = {c.uid for c in chunks}
    tasks = plan_tasks(chunks, ["sizzle", "affect"], rotate_theory=THEORY_CYCLE, art=True)
    if SEG_OUT.exists():
        shutil.rmtree(SEG_OUT)
    try:
        specs = submit(tasks)
        specs = poll(specs)
        summary = collect(specs, chunks, SEG_OUT)
    finally:
        cleanup_uploads(chunks)

    # 5. inject provenance into chunk JSONs and fold them into the real catalog
    folded = 0
    for c in chunks:
        jf = SEG_OUT / f"{c.uid}.json"
        if not jf.exists() or c.uid not in origin:
            continue
        d = json.load(open(jf))
        d.update({k: v for k, v in origin[c.uid].items() if k != "orig_json"})
        json.dump(d, open(CATALOG / f"{c.uid}.json", "w"), indent=2)
        json.dump(d, open(jf, "w"), indent=2)  # fix staging copy too, so it imports directly
        folded += 1

    # 6. flag the original long takes as segmented (engine + future cuts skip them)
    seg_origins = {Path(o["orig_json"]) for o in origin.values()}
    for f in seg_origins:
        try:
            d = json.load(open(f))
            d["segmented"] = True
            json.dump(d, open(f, "w"), indent=2)
        except Exception:
            pass

    print(f"\nDONE: {summary['n_ok']} ok / {summary.get('n_salvaged', 0)} salvaged / "
          f"{summary['n_err']} err · folded {folded} chunks into catalog · "
          f"flagged {len(seg_origins)} originals segmented")
    print(f"chunk JSONs staged in {SEG_OUT} (for archive import)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
