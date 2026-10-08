#!/usr/bin/env python3
"""Local VLM benchmark — same clips as the Gemini meter, head-to-head.

Reads the exact clips the Gemini meter used (from its results dir), runs them
through philm's Ollama provider (frame-based) for the same modes, and records
wall-time + structured-output success rate. Cost is $0 (local); the metrics that
matter here are SPEED and whether a small local model can hold the schema.

Usage:
  OLLAMA_MODEL=qwen3-vl:4b OLLAMA_FRAMES=8 \
  uv run python scripts/local_bench.py \
    --gemini-dir "/path/metered_results" --out "/path/local_results" \
    --modes sizzle,affect,zizek --archive-clips 3611
"""
from __future__ import annotations

import argparse, glob, json, os, time
from pathlib import Path

from video_analyzer.providers import get_provider
from video_analyzer.modes import get_mode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini-dir", required=True, help="dir of Gemini meter results (for identical clip set)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--modes", default="sizzle,affect,zizek")
    ap.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen3-vl:4b"))
    ap.add_argument("--frames", type=int, default=int(os.getenv("OLLAMA_FRAMES", "8")))
    ap.add_argument("--archive-clips", type=int, default=3611)
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    os.environ["OLLAMA_MODEL"] = args.model
    os.environ["OLLAMA_FRAMES"] = str(args.frames)

    clips = []
    for f in glob.glob(args.gemini_dir + "/*.json"):
        if "_cost_report" in f:
            continue
        d = json.load(open(f))
        clips.append((d["clip"], d["path"], d.get("duration_s", 0)))
    clips.sort()
    print(f"Benchmarking {args.model} ({args.frames} frames) on {len(clips)} clips\n", flush=True)

    prov = get_provider("ollama")
    rows = []
    t_start = time.time()
    for i, (name, path, dur) in enumerate(clips, 1):
        if not os.path.exists(path):
            print(f"[{i}] {name}: MISSING source, skip", flush=True); continue
        t0 = time.time()
        try:
            handle = prov.prepare(Path(path))
        except Exception as e:
            print(f"[{i}] {name}: prepare failed: {e}", flush=True); continue
        rec = {"clip": name, "duration_s": dur, "analyses": {}, "timing": {}, "ok": {}}
        for m in modes:
            ts = time.time()
            try:
                res = prov.analyze(handle, get_mode(m))
                rec["analyses"][m] = res.model_dump()
                rec["ok"][m] = True
            except Exception as e:
                rec["analyses"][m] = {"error": str(e)[:300]}
                rec["ok"][m] = False
            rec["timing"][m] = round(time.time() - ts, 1)
        prov.cleanup(handle)
        rec["clip_total_s"] = round(time.time() - t0, 1)
        json.dump(rec, open(outdir / f"{name}.json", "w"), indent=2)
        rows.append(rec)
        print(f"[{i}/{len(clips)}] {name} ({dur:.0f}s)  "
              f"{rec['clip_total_s']:.0f}s  ok={ {m: rec['ok'][m] for m in modes} }", flush=True)

    elapsed = time.time() - t_start
    # ---- summary ----
    n = len(rows)
    succ = {m: sum(1 for r in rows if r["ok"].get(m)) for m in modes}
    mean_clip = sum(r["clip_total_s"] for r in rows) / max(1, n)
    per_mode_time = {m: sum(r["timing"].get(m, 0) for r in rows) / max(1, n) for m in modes}
    AC = args.archive_clips
    print("\n" + "=" * 64)
    print(f"LOCAL: {args.model}, {args.frames} frames, {n} clips, {elapsed/60:.1f} min wall.")
    print(f"mean {mean_clip:.0f}s/clip (3 modes) | per-mode avg s: "
          f"{ {m: round(per_mode_time[m],1) for m in modes} }")
    print("schema success rate (valid structured output):")
    for m in modes:
        print(f"   {m:8} {succ[m]}/{n}  ({100*succ[m]/max(1,n):.0f}%)")
    full_h = mean_clip * AC / 3600
    print(f"\nExtrapolated full archive ({AC} clips, sequential, 1 process): "
          f"~{full_h:.0f} h wall  ({full_h/24:.1f} days)")
    print("Cost: $0 (local compute). Parallelism would cut wall-time ~linearly.")
    summary = {"model": args.model, "frames": args.frames, "clips": n,
               "wall_min": round(elapsed/60, 1), "mean_s_per_clip": round(mean_clip, 1),
               "per_mode_avg_s": {m: round(per_mode_time[m], 1) for m in modes},
               "schema_success": {m: f"{succ[m]}/{n}" for m in modes},
               "full_archive_hours_seq": round(full_h, 1)}
    json.dump(summary, open(outdir / "_bench_summary.json", "w"), indent=2)
    print(f"\nOutputs + summary -> {outdir}")


if __name__ == "__main__":
    main()
