#!/usr/bin/env python3
"""Catalogue clips with a LOCAL (or RunPod-hosted) Ollama vision model.

Writes the SAME ``_cloud_catalog/{uid}.json`` shape the Gemini batch pipeline produces
(``{video, path, uid, modes, analyses}``), so ``scripts/affect_score.py`` and the archive
treat locally-analyzed clips identically to cloud-analyzed ones.

Why this exists: SENSITIVE footage (e.g. the iPhone archive) that Gemini's safety layer would
*refuse* (→ holes in the catalogue exactly at the most affectively-loaded memories) or that you
simply don't want on Google's servers. Nothing leaves this machine — unless ``OLLAMA_HOST``
points at a remote pod (e.g. RunPod), in which case only the 360p proxies travel.

Reuses the cloud pipeline's infra (selection, dedup, uid, proxy build, salvage) and only swaps
the Gemini Batch call for the local ``OllamaProvider`` frame-based call.

Examples:
  # 30-clip iPhone sample, fully local, richer affect curve (10 frames):
  uv run python scripts/catalog_local.py \
      --root "/Volumes/2025_exSSD_2tb/Photography + Video/_found_footage_wer_iphone" \
      --proxy-dir "/Volumes/2025_exSSD_2tb/Photography + Video/_proxies/_found_footage_wer_iphone" \
      --model qwen2.5-vl:7b --frames 10 --limit 30

  # full run on a RunPod pod (same script, remote weights):
  OLLAMA_HOST=https://<pod-id>-11434.proxy.runpod.net \
  uv run python scripts/catalog_local.py --root "<staging>" --proxy-dir "<...>" --model qwen2.5-vl:72b
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# reuse the cloud pipeline's tested infra — selection/dedup/uid, proxy build, salvage, logging
from video_analyzer.batch_cloud import (
    build_proxies, salvage_parse, select_clips, ART_SIZZLE_PREFIX, _log)
from video_analyzer.local import _chat_json
from video_analyzer.modes import get_mode
from video_analyzer.providers.ollama import OllamaProvider

DRIVE = "/Volumes/2025_exSSD_2tb/Photography + Video"


def preflight(provider: OllamaProvider) -> None:
    """Fail fast (before building proxies) if the Ollama server or model isn't reachable."""
    url = provider.config.ollama_url
    hdrs = {}
    if os.getenv("OLLAMA_BEARER"):  # token-gated endpoint (e.g. HF Jobs exposed port)
        hdrs["Authorization"] = f"Bearer {os.environ['OLLAMA_BEARER']}"
    try:
        r = requests.get(f"{url}/api/tags", timeout=30, headers=hdrs)
        r.raise_for_status()
        names = {m.get("name", "") for m in r.json().get("models", [])}
    except Exception as e:
        raise SystemExit(f"Ollama not reachable at {url} ({e}). "
                         f"Start it (`ollama serve`) or set OLLAMA_HOST.")
    model = provider.config.model
    # ollama tags may carry a :latest suffix; match on the base name too
    if model not in names and f"{model}:latest" not in names and \
            not any(n.split(":")[0] == model.split(":")[0] for n in names):
        raise SystemExit(f"Model '{model}' not found on {url}. Pull it first: "
                         f"`ollama pull {model}`  (available: {sorted(names) or 'none'})")
    _log(f"ollama OK: {model} @ {url} | frames={provider.config.num_frames}")


def analyze_clip(provider: OllamaProvider, clip, modes_for_clip: list[str], art: bool) -> dict:
    """Run every mode for one clip off a single frame extraction; salvage-parse each.
    A mode that errors is recorded as {"error": ...} and never kills the clip."""
    handle = provider.prepare(clip.proxy)
    analyses: dict = {}
    try:
        for m in modes_for_clip:
            mode = get_mode(m)
            prefix = ART_SIZZLE_PREFIX if (art and m == "sizzle") else ""
            try:
                raw = _chat_json(
                    model=provider.config.model,
                    prompt=prefix + mode.prompt,
                    image_paths=handle.payload["frames"],
                    ollama_url=provider.config.ollama_url,
                    schema=mode.result_model.model_json_schema(),
                    timeout=provider.config.timeout,
                    num_ctx=provider.config.num_ctx,
                )
                parsed, salvaged = salvage_parse(mode.result_model, raw)
                analyses[m] = parsed.model_dump()
                if salvaged:
                    analyses[m]["_salvaged"] = True
            except Exception as e:
                analyses[m] = {"error": str(e)}
    finally:
        provider.cleanup(handle)
    return analyses


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="folder of clips to catalogue (recursively)")
    ap.add_argument("--proxy-dir", default=str(Path(DRIVE) / "_proxies"),
                    help="proxy mirror root; aim it so proxies land where affect_score expects")
    ap.add_argument("--out", default=str(Path(DRIVE) / "_cloud_catalog"))
    ap.add_argument("--modes", default="sizzle,affect", help="base modes applied to every clip")
    ap.add_argument("--rotate-theory", default="zizek,hauntology,sontag",
                    help="theory lenses rotated one-per-clip (empty string to disable)")
    ap.add_argument("--art", dest="art", action="store_true", default=True)
    ap.add_argument("--no-art", dest="art", action="store_false")
    ap.add_argument("--model", default=None, help="ollama model id (else OLLAMA_MODEL env)")
    ap.add_argument("--frames", type=int, default=None,
                    help="frames sampled per clip (else OLLAMA_FRAMES; bump for a richer affect curve)")
    ap.add_argument("--num-ctx", type=int, default=16384,
                    help="Ollama context window; vision tokens are large so >6 frames + long "
                         "prompts overflow the default 4096. 0 = model default.")
    ap.add_argument("--timeout", type=int, default=600,
                    help="per-request timeout (s); the long modes (sizzle) need headroom")
    ap.add_argument("--proxies-only", action="store_true",
                    help="build proxies and exit (pre-stage locally; analyze later via OLLAMA_HOST)")
    ap.add_argument("--limit", type=int, default=None, help="cap clip count (sample runs)")
    ap.add_argument("--concurrency", type=int, default=1,
                    help="clips analyzed in parallel; match the server's OLLAMA_NUM_PARALLEL")
    ap.add_argument("--proxy-workers", type=int, default=6)
    ap.add_argument("--no-skip-analyzed", action="store_true",
                    help="re-analyze clips even if a {uid}.json already exists")
    args = ap.parse_args()

    # OllamaProvider reads these at construction; flags win over pre-set env
    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model
    if args.frames is not None:
        os.environ["OLLAMA_FRAMES"] = str(args.frames)
    if args.num_ctx is not None:
        os.environ["OLLAMA_NUM_CTX"] = str(args.num_ctx)
    if args.timeout is not None:
        os.environ["OLLAMA_TIMEOUT"] = str(args.timeout)

    base_modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    rotate = [m.strip() for m in args.rotate_theory.split(",") if m.strip()]
    all_modes = base_modes + rotate
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    proxy_root = Path(args.proxy_dir)

    provider = OllamaProvider()
    if not args.proxies_only:
        preflight(provider)  # proxies-only needs no model/server

    _log(f"[1/3] selecting clips under {args.root} ...")
    clips = select_clips(Path(args.root), all_modes, out_dir,
                         skip_analyzed=not args.no_skip_analyzed, limit=args.limit)
    plan = f"base{base_modes}" + (f" + rotate{rotate}" if rotate else "") + (" [art]" if args.art else "")
    _log(f"      {len(clips)} clips :: {plan}")
    if not clips:
        _log("Nothing to do.")
        return 0

    _log(f"[2/3] building proxies -> {proxy_root} ...")
    clips = build_proxies(clips, proxy_root, workers=args.proxy_workers)
    _log(f"      {len(clips)} proxies ready.")
    if args.proxies_only:
        _log("--proxies-only: done (skip analysis). Run again with OLLAMA_HOST set to analyze.")
        return 0

    _log(f"[3/3] analyzing via {provider.config.ollama_url} "
         f"({len(clips)} clips, concurrency={args.concurrency}) ...")

    def _process(i, c):
        """Analyze one clip (its modes serially) and write its catalog JSON. Thread-safe:
        each clip owns its frames (unique tempdir) and writes its own {uid}.json."""
        modes_for_clip = list(base_modes) + ([rotate[i % len(rotate)]] if rotate else [])
        try:
            analyses = analyze_clip(provider, c, modes_for_clip, args.art)
        except Exception as e:  # clip-level (e.g. frame extraction) failure
            analyses = {m: {"error": f"clip-level: {e}"} for m in modes_for_clip}
        rec = {"video": c.src.name, "path": str(c.src), "uid": c.uid,
               "modes": modes_for_clip, "analyses": analyses}
        json.dump(rec, open(out_dir / f"{c.uid}.json", "w"), indent=2)
        n_ok = sum(1 for a in analyses.values() if "error" not in a)
        return n_ok, len(modes_for_clip)

    t0 = time.time()
    done = ok_clips = mode_errors = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = [ex.submit(_process, i, c) for i, c in enumerate(clips)]
        for fut in as_completed(futs):
            try:
                n_ok, n_modes = fut.result()
            except Exception as e:
                _log(f"  worker error: {e}")
                continue
            done += 1
            mode_errors += (n_modes - n_ok)
            if n_ok >= n_modes:
                ok_clips += 1
            if done % 10 == 0 or done == len(clips):
                el = time.time() - t0
                _log(f"  {done}/{len(clips)}  {el/done:.1f}s/clip(wall)  "
                     f"clean={ok_clips} mode-errors={mode_errors}")

    total_min = (time.time() - t0) / 60
    _log(f"\nDONE. {len(clips)} clips -> {out_dir}  "
         f"({total_min:.1f} min, {ok_clips} fully-clean, {mode_errors} mode-errors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
