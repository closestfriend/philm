#!/usr/bin/env python3
"""Metered low-resolution scan: measure REAL token cost of cataloguing the archive.

Runs N representative clips through several modes at media_resolution=LOW, captures
Gemini's actual usage_metadata (prompt/output tokens), writes the analyses for review,
and extrapolates measured per-second / per-clip rates to the full archive.

Usage:
  uv run python scripts/metered_scan.py --n 20 --modes sizzle,affect,zizek \
      --root "/Volumes/2025_exSSD_2tb/Photography + Video" --out ./metered_results
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from google.genai import types

from video_analyzer.analyzer import configure_genai, get_client, upload_video, delete_video
from video_analyzer.modes import get_mode

MODEL = "gemini-2.5-flash-lite"
SYSTEM_INSTRUCTION = (
    "You are a sophisticated video analysis system. When given a video and "
    "analytical framework, provide structured insights following the schema precisely. "
    "Be theoretically rigorous but practically clear."
)
VID_EXT = {".mov", ".mp4", ".mpg", ".mpeg", ".avi", ".mkv", ".m4v", ".mts", ".m2ts", ".webm"}

# Verified pricing (per 1M tokens, Standard tier) — ai.google.dev/gemini-api/docs/pricing
PRICES = {
    "2.5 Flash-Lite": (0.10, 0.40),
    "2.0 Flash":      (0.10, 0.40),
    "2.5 Flash":      (0.30, 2.50),
}


def ffdur(p: str) -> float:
    try:
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", p], capture_output=True, text=True, timeout=30).stdout.strip())
    except Exception:
        return 0.0


def gather(root: str) -> list[tuple[str, float]]:
    out = []
    for dp, _, fns in os.walk(root):
        if any(x in dp for x in ("vanalysis_results", "sizzle_results", "metered_results")):
            continue
        for fn in fns:
            if Path(fn).suffix.lower() in VID_EXT:
                out.append(os.path.join(dp, fn))
    return out


def stratified_sample(files: list[str], n: int, seed: int = 11) -> list[tuple[str, float]]:
    """Sample n clips spread across top-folders and short/medium/long durations."""
    random.seed(seed)
    random.shuffle(files)
    picked, durs = [], []
    buckets = {"short": 0, "med": 0, "long": 0}  # <15s, 15-90s, >90s
    target = max(1, n // 3)
    for p in files:
        if len(picked) >= n:
            break
        d = ffdur(p)
        if d <= 0:
            continue
        b = "short" if d < 15 else ("med" if d <= 90 else "long")
        # fill buckets roughly evenly, but don't stall if a bucket is rare
        if buckets[b] >= target and len([x for x in buckets.values() if x >= target]) < 3 and len(picked) < n - 1:
            continue
        picked.append((p, d)); buckets[b] += 1
    return picked[:n]


def analyze(video_file, mode_name: str):
    mode = get_mode(mode_name)
    client = get_client()
    resp = client.models.generate_content(
        model=MODEL,
        contents=[mode.prompt, video_file],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=mode.result_model,
            temperature=0.5,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
        ),
    )
    u = resp.usage_metadata
    result = mode.result_model.model_validate_json(resp.text)
    return result.model_dump(), {
        "prompt_tokens": u.prompt_token_count or 0,
        "output_tokens": u.candidates_token_count or 0,
        "total_tokens": u.total_token_count or 0,
    }


def text_overhead(mode_name: str) -> int:
    """Count tokens of the fixed text prompt (system + mode prompt) once per mode."""
    mode = get_mode(mode_name)
    client = get_client()
    try:
        r = client.models.count_tokens(model=MODEL, contents=[SYSTEM_INSTRUCTION + "\n" + mode.prompt])
        return r.total_tokens or 0
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--modes", default="sizzle,affect,zizek")
    ap.add_argument("--root", default="/Volumes/2025_exSSD_2tb/Photography + Video")
    ap.add_argument("--out", default="./metered_results")
    # Full-archive figures (measured earlier): total seconds + clip count
    ap.add_argument("--archive-seconds", type=float, default=215662.0)
    ap.add_argument("--archive-clips", type=int, default=3611)
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    configure_genai()

    overhead = {m: text_overhead(m) for m in modes}
    print(f"text overhead tokens/mode: {overhead}", file=sys.stderr)

    print(f"Sampling {args.n} clips from {args.root} ...", file=sys.stderr)
    clips = stratified_sample(gather(args.root), args.n)
    print(f"Selected {len(clips)} clips "
          f"({sum(d for _, d in clips)/60:.1f} min total).", file=sys.stderr)

    rows = []   # per (clip,mode): dict
    per_clip_out = {}
    t0 = time.time()
    for i, (path, dur) in enumerate(clips, 1):
        name = Path(path).stem
        print(f"[{i}/{len(clips)}] {name} ({dur:.0f}s) uploading...", file=sys.stderr)
        try:
            vf = upload_video(Path(path), no_audio=False)  # keep audio (cheap, helps art modes)
        except Exception as e:
            print(f"  upload failed: {e}", file=sys.stderr); continue
        clip_record = {"clip": name, "path": path, "duration_s": round(dur, 2), "analyses": {}, "usage": {}}
        for m in modes:
            try:
                result, usage = analyze(vf, m)
                clip_record["analyses"][m] = result
                clip_record["usage"][m] = usage
                vid_tok = max(0, usage["prompt_tokens"] - overhead[m])
                rows.append({"clip": name, "mode": m, "dur": dur,
                             "prompt": usage["prompt_tokens"], "video_tok": vid_tok,
                             "output": usage["output_tokens"]})
                print(f"    {m:8} prompt={usage['prompt_tokens']:>6}  "
                      f"video≈{vid_tok:>6} ({vid_tok/max(dur,1):.0f}/s)  out={usage['output_tokens']:>5}",
                      file=sys.stderr)
            except Exception as e:
                print(f"    {m}: FAILED {e}", file=sys.stderr)
        try:
            delete_video(vf)
        except Exception:
            pass
        per_clip_out[name] = clip_record
        json.dump(clip_record, open(outdir / f"{name}.json", "w"), indent=2)

    elapsed = time.time() - t0
    # ---- aggregate measured rates ----
    report = {"model_run": MODEL, "clips_metered": len(clips),
              "seconds_metered": round(sum(d for _, d in clips), 1),
              "elapsed_s": round(elapsed, 1), "per_mode": {}, "extrapolation": {}}

    def agg(mode):
        r = [x for x in rows if x["mode"] == mode]
        if not r:
            return None
        vid_rate = sum(x["video_tok"] for x in r) / max(1e-9, sum(x["dur"] for x in r))  # tok/sec
        out_per_clip = sum(x["output"] for x in r) / len(r)
        return {"n": len(r), "video_tok_per_sec": round(vid_rate, 1),
                "output_tok_per_clip": round(out_per_clip, 1),
                "text_overhead": overhead[mode]}

    AS, AC = args.archive_seconds, args.archive_clips
    print("\n" + "=" * 70)
    print(f"METERED on {MODEL}, media_resolution=LOW, {len(clips)} clips / "
          f"{report['seconds_metered']/60:.1f} min, {elapsed/60:.1f} min wall.")
    print(f"Extrapolating to full archive: {AS/3600:.1f} h video, {AC} clips.\n")

    grand = {pm: 0.0 for pm in PRICES}
    for m in modes:
        a = agg(m)
        if not a:
            continue
        report["per_mode"][m] = a
        in_tok = AS * a["video_tok_per_sec"] + AC * a["text_overhead"]
        out_tok = AC * a["output_tok_per_clip"]
        report["extrapolation"][m] = {"input_tokens": int(in_tok), "output_tokens": int(out_tok), "cost": {}}
        print(f"### {m}: {a['video_tok_per_sec']:.0f} video tok/s, "
              f"{a['output_tok_per_clip']:.0f} out tok/clip")
        for pm, (ip, op) in PRICES.items():
            c = in_tok / 1e6 * ip + out_tok / 1e6 * op
            report["extrapolation"][m]["cost"][pm] = round(c, 2)
            grand[pm] += c
            print(f"     {pm:16} ${c:6.2f}")
        print()
    print("=" * 70)
    print("FULL ARCHIVE, all modes combined:")
    for pm in PRICES:
        print(f"   {pm:16} ${grand[pm]:6.2f}   (Batch API ≈ ${grand[pm]/2:.2f})")
    report["grand_total"] = {pm: round(v, 2) for pm, v in grand.items()}

    json.dump(report, open(outdir / "_cost_report.json", "w"), indent=2)
    print(f"\nAnalyses + cost report written to: {outdir}")


if __name__ == "__main__":
    main()
