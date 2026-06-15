"""Asynchronous Gemini **Batch API** archive scan (50%-off, low-res proxies).

Pipeline: select unique clips -> transcode tiny 360p proxies -> project+assert cost
-> upload proxies to the File API -> submit inlined batch jobs -> poll -> collect
structured JSON results + reconcile actual token cost.

Why proxies: the File API caps a project at ~20 GB (48 h expiry); the source archive is
~327 GB. At media_resolution=LOW the model only ever sees low-res frames, so 360p/~0.4 Mbps
proxies (~10 GB for the whole archive) are lossless *for cataloguing* and fit in one wave.

Why inlined requests with native Pydantic schemas: a batch request carries only a
``file_uri`` reference (video bytes live in the File API and do NOT count toward the 20 MB
inlined cap), so we hand the SDK ``response_schema=mode.result_model`` and let it convert —
no manual REST/JSONL schema building. Verified against google-genai==1.61.0.

Guardrails: model is HARD-PINNED to gemini-2.5-flash-lite; ``project_cost`` is asserted
under a ceiling (against the conservative *full-price* total) before any upload/submit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import typing
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from google.genai import types
from pydantic import BaseModel, ValidationError

from .analyzer import configure_genai, get_client
from .modes import get_mode

# --- hard pin: the ONLY model this module may ever bill against ---------------
MODEL = "gemini-2.5-flash-lite"

SYSTEM_INSTRUCTION = (
    "You are a sophisticated video analysis system. When given a video and "
    "analytical framework, provide structured insights following the schema precisely. "
    "Be theoretically rigorous but practically clear."
)

# Verified pricing, per 1M tokens (Standard tier) — ai.google.dev/gemini-api/docs/pricing
PRICE_IN, PRICE_OUT = 0.10, 0.40  # gemini-2.5-flash-lite

# Measured rates (worst-of-two metered runs: random-stratified vs LA-Fires).
# video tok/sec is mode-independent at LOW; output tok/clip is the cost driver.
VIDEO_TOK_PER_SEC = 103.0
_MEASURED = {  # output_tok_per_clip (worst sample), text_overhead
    "sizzle": (2882.8, 692),
    "affect": (1381.4, 188),
    "zizek": (1455.0, 452),
}
_DEFAULT_RATE = (1800.0, 450)  # fallback for unmetered modes (conservative)
OUTPUT_HEADROOM = 1.30  # +30% on output for the unsampled verbose tail

VID_EXT = {".mov", ".mp4", ".mpg", ".mpeg", ".avi", ".mkv", ".m4v", ".mts", ".m2ts", ".webm"}
RESULT_DIR_MARKERS = ("vanalysis_results", "sizzle_results", "metered_results",
                      "local_results", "freeform_results", "_cloud_analysis",
                      "_cloud_catalog", "_proxies")

# Curation: keep the catalog to HUNTER'S OWN footage. Drop clear third-party downloads
# and screen-captures wherever they appear. Folder-level + filename-pattern exclusions.
EXCLUDE_DIR_NAMES = {"photography_shot_by_me"}  # a dump of downloads (real footage moved out)
EXCLUDE_NAME_RE = re.compile(
    r"(screen[ _-]?recording|screenrecording|snaptik|^movie on \d|^output_|"
    r"^single_source_|videooptimized)", re.I)


def _is_excluded(path: Path) -> bool:
    """True for files that are not Hunter's own camera work (downloads / screen-caps)."""
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    return bool(EXCLUDE_NAME_RE.search(path.name))

TERMINAL_STATES = {
    "JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED", "JOB_STATE_PARTIALLY_SUCCEEDED",
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _hash8(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:8]


# --- creative framing -------------------------------------------------------- #
# Theory lens rotates across clips so the archive gets a DIVERSE philosophical
# reading (≈1/3 each) instead of one lens on everything, at the same per-clip cost.
THEORY_CYCLE = ["zizek", "hauntology", "sontag"]

# Prepended to the `sizzle` prompt to reinterpret the (unchanged) structured fields
# through a contemporary-art / artist's-moving-image lens instead of commercial promo.
ART_SIZZLE_PREFIX = (
    "REFRAME — you are not cutting a commercial promo. You are an artist and curator "
    "selecting footage for a CONTEMPORARY ART moving-image work: gallery video "
    "installation, experimental nonfiction, the essay film. Read each shot for its "
    "aesthetic, atmospheric, and conceptual charge — not its salesmanship. Keep filling "
    "the exact structured fields below, but interpret them through that lens:\n"
    "- 'hook' = the arresting, uncanny, hypnotic, or quietly sublime image that holds a "
    "gallery viewer — NOT the loudest moment.\n"
    "- 'energy' = affective / visual intensity: stillness, duration, and slowness can "
    "score HIGH here, not low. A 'boring' static shot may be the most valuable.\n"
    "- 'tone' = the work's emotional/aesthetic register (a slow contemplative shot may "
    "read as 'dramatic' or 'aspirational' in an art sense).\n"
    "- 'best_for' = where this sits in an ART edit (hook=opening image, establish="
    "world-building, montage=textural passage, climax=affective peak).\n"
    "Value duration, texture, ambiguity, mood, grain, the everyday-sublime, and the "
    "accidental over conventional production polish.\n\n"
)


def _repair_truncated_json(raw: str) -> Optional[dict]:
    """Recover a dict from JSON cut off mid-stream (the model exceeded the output cap on a
    very long clip, truncating inside an array). Trims to the last position where an array
    element was complete, then closes the open brackets. Keeps the head fields + every
    complete list item. Returns None if nothing coherent can be recovered."""
    stack: list[str] = []
    in_str = esc = False
    last_safe: Optional[int] = None
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if stack:
                stack.pop()
            # just closed an element inside an array → safe cut point
            if ch == "}" and stack and stack[-1] == "[":
                last_safe = i + 1
    if last_safe is None:
        return None
    head = raw[:last_safe]
    depth: list[str] = []
    in_str = esc = False
    for ch in head:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            depth.append(ch)
        elif ch in "]}" and depth:
            depth.pop()
    closers = "".join("]" if c == "[" else "}" for c in reversed(depth))
    try:
        return json.loads(head + closers)
    except json.JSONDecodeError:
        return None


def _backfill_summary(model_cls: type[BaseModel], data: dict) -> dict:
    """Derive a model's top-level summary fields from its recovered timecodes when they
    were lost to truncation (they sit AFTER the array in schema order). Specific to
    SizzleResult's overall_energy / dominant_tone / best_for — a no-op for other models.
    These fields ARE summaries of the moments, so deriving them is faithful, not invented."""
    from collections import Counter
    fields = model_cls.model_fields
    tcs = data.get("timecodes") or []
    if "overall_energy" in fields and data.get("overall_energy") is None:
        energies = [t.get("energy") for t in tcs if isinstance(t.get("energy"), int)]
        data["overall_energy"] = max(1, min(10, round(sum(energies) / len(energies)))) if energies else 5
    if "dominant_tone" in fields and not data.get("dominant_tone"):
        tones = Counter(t["tone"] for t in tcs if t.get("tone"))
        if tones:
            data["dominant_tone"] = tones.most_common(1)[0][0]
    if "best_for" in fields and not data.get("best_for"):
        pos = Counter(p for t in tcs for p in (t.get("sizzle_position") or []))
        data["best_for"] = [p for p, _ in pos.most_common(4)] or ["montage"]
    return data


def salvage_parse(model_cls: type[BaseModel], raw: str) -> tuple[BaseModel, bool]:
    """Parse a model response, tolerating two batch-mode failures: (1) the model omits
    required fields inside list items (incomplete ``timecodes`` entry), and (2) the JSON is
    truncated because output exceeded the cap on a very long clip. Strict first; else repair
    truncation and/or drop invalid list items, keeping the head fields + every complete item.
    Returns (model, salvaged). Raises only if nothing coherent (or a top-level required
    field) can be recovered."""
    salvaged = False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = _repair_truncated_json(raw)  # truncated mid-array → recover the complete prefix
        if data is None:
            raise
        salvaged = True
    if not salvaged:
        try:
            return model_cls.model_validate(data), False
        except ValidationError:
            pass
    for fname, finfo in model_cls.model_fields.items():
        val = data.get(fname)
        if not isinstance(val, list):
            continue
        item_cls = next((a for a in typing.get_args(finfo.annotation)
                         if isinstance(a, type) and issubclass(a, BaseModel)), None)
        if item_cls is None:
            continue
        good = []
        for it in val:
            try:
                item_cls.model_validate(it)
                good.append(it)
            except ValidationError:
                pass
        data[fname] = good
    try:
        return model_cls.model_validate(data), True
    except ValidationError:
        # last resort: derive summary fields lost to truncation from the recovered items
        return model_cls.model_validate(_backfill_summary(model_cls, data)), True


@dataclass
class Clip:
    """One unique source clip and its derived proxy / identity."""
    src: Path
    root: Path
    proxy: Optional[Path] = None
    uploaded: Any = None  # File API object
    seconds: float = 0.0

    @property
    def rel(self) -> str:
        try:
            return str(self.src.relative_to(self.root))
        except ValueError:
            return self.src.name

    @property
    def uid(self) -> str:
        # path-keyed so same-named clips across shoots never collide
        return f"{self.src.stem}__{_hash8(self.rel)}"


# --------------------------------------------------------------------------- #
# 1. selection (dedupe by name+size; skip result dirs + already-analyzed)
# --------------------------------------------------------------------------- #
def _is_result_path(p: str) -> bool:
    return any(m in p for m in RESULT_DIR_MARKERS)


# legacy result dirs (any prior philm run) — keyed by clip stem, not uid
_LEGACY_RESULT_MARKERS = tuple(m for m in RESULT_DIR_MARKERS if m not in ("_cloud_analysis", "_proxies"))


def _analyzed_stems(root: Path) -> set[str]:
    """Stems of clips already analyzed by ANY prior philm run (vanalysis_results,
    sizzle_results, metered_results, ...). Each legacy result JSON is named ``{stem}.json``.
    We match on stem (not stored path) because the archive was reorganized after those
    runs — stored paths are stale (/tmp staging, old locations). The caller guards stem
    collisions by only skipping stems that are unambiguous in the current archive."""
    stems: set[str] = set()
    for dp, _, fns in os.walk(root):
        if not any(m in dp for m in _LEGACY_RESULT_MARKERS):
            continue
        for fn in fns:
            if fn.endswith(".json") and not fn.startswith("_"):
                stems.add(Path(fn).stem)
    return stems


def select_clips(root: Path, modes: list[str], out_dir: Path,
                 skip_analyzed: bool = True, limit: Optional[int] = None,
                 skip_prior_runs: Optional[bool] = None,
                 done_min_modes: int = 3) -> list[Clip]:
    """Unique clips under ``root`` (dedup by name+size, canonical = not the 📷 tree).
    Two independent skips:
      • resume-skip (governed by ``skip_analyzed``): drop clips already cataloged in
        ``out_dir`` (a {uid}.json with >= ``done_min_modes`` non-error analyses).
      • prior-run-skip (governed by ``skip_prior_runs``, defaults to ``skip_analyzed``):
        drop clips an EARLIER philm run touched (legacy result dirs). Set False to close
        the gap left by old runs while still resume-skipping this catalog."""
    skip_prior = skip_analyzed if skip_prior_runs is None else skip_prior_runs
    groups: dict[tuple[str, int], list[Path]] = {}
    for dp, _, fns in os.walk(root):
        if _is_result_path(dp):
            continue
        for fn in fns:
            if Path(fn).suffix.lower() in VID_EXT:
                p = Path(dp) / fn
                if _is_excluded(p):  # third-party downloads / screen-caps
                    continue
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                groups.setdefault((fn.lower(), sz), []).append(p)

    clips: list[Clip] = []
    for paths in groups.values():
        canonical = sorted(paths, key=lambda p: (1 if "📷 Camera Footage" in str(p) else 0,
                                                 len(str(p)), str(p)))[0]
        clips.append(Clip(src=canonical, root=root))
    clips.sort(key=lambda c: c.rel)

    if skip_analyzed or skip_prior:
        from collections import Counter
        legacy = _analyzed_stems(root) if skip_prior else set()
        stem_counts = Counter(c.src.stem for c in clips) if skip_prior else {}
        kept, skipped_legacy = [], 0
        for c in clips:
            # prior-run-skip: stem seen in an earlier run AND unique in the archive
            # (colliding stems get re-done — cheap, avoids false skips)
            if skip_prior and c.src.stem in legacy and stem_counts[c.src.stem] == 1:
                skipped_legacy += 1
                continue
            # resume-skip: already cataloged here with its full per-clip plan
            if skip_analyzed:
                done = out_dir / f"{c.uid}.json"
                if done.exists():
                    try:
                        an = json.load(open(done)).get("analyses", {})
                        ok = [m for m, a in an.items() if isinstance(a, dict) and "error" not in a]
                        if len(ok) >= done_min_modes:
                            continue
                    except Exception:
                        pass
            kept.append(c)
        clips = kept
        if skipped_legacy:
            _log(f"      skipped {skipped_legacy} clips already analyzed by a prior run.")

    if limit is not None:
        clips = clips[:limit]
    return clips


# --------------------------------------------------------------------------- #
# 2. proxies (360p / ~0.4 Mbps / no audio) — persistent, reusable
# --------------------------------------------------------------------------- #
def make_proxy(src: Path, dst: Path, height: int = 360, bitrate: str = "400k") -> Path:
    """Transcode one clip to a tiny low-res proxy. Idempotent (skips if dst exists)."""
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
        "-vf", f"scale=-2:{height}", "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", bitrate, "-maxrate", "600k", "-bufsize", "800k",
        "-pix_fmt", "yuv420p", "-an", str(tmp),
    ]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    if r.returncode != 0 or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"ffmpeg proxy failed for {src.name}: {r.stderr[:300]}")
    tmp.rename(dst)
    return dst


def build_proxies(clips: list[Clip], proxy_root: Path, workers: int = 6) -> list[Clip]:
    """Transcode proxies in parallel, mirroring source tree under ``proxy_root``.
    Drops clips whose proxy fails. Returns clips with ``.proxy`` set."""
    proxy_root.mkdir(parents=True, exist_ok=True)

    def _one(c: Clip) -> Optional[Clip]:
        dst = (proxy_root / c.rel).with_suffix(".mp4")
        try:
            c.proxy = make_proxy(c.src, dst)
            return c
        except Exception as e:
            _log(f"  proxy FAIL {c.rel}: {e}")
            return None

    out: list[Clip] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(_one, c) for c in clips]):
            c = fut.result()
            done += 1
            if c:
                out.append(c)
            if done % 25 == 0 or done == len(clips):
                _log(f"  proxies {done}/{len(clips)}")
    out.sort(key=lambda c: c.rel)
    return out


def ffdur(p: Path) -> float:
    try:
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60).stdout.strip())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# 3. cost projection + ceiling assertion (pre-flight guardrail)
# --------------------------------------------------------------------------- #
def project_cost(n_clips: int, total_seconds: float, modes: list[str]) -> dict:
    """Project token cost from measured rates. Returns per-mode + grand totals at
    full price and batched (50%). Output uses +OUTPUT_HEADROOM for the verbose tail."""
    per_mode = {}
    in_tok_total = out_tok_total = 0.0
    for m in modes:
        out_per_clip, overhead = _MEASURED.get(m, _DEFAULT_RATE)
        in_tok = total_seconds * VIDEO_TOK_PER_SEC + n_clips * overhead
        out_tok = n_clips * out_per_clip * OUTPUT_HEADROOM
        cost = in_tok / 1e6 * PRICE_IN + out_tok / 1e6 * PRICE_OUT
        per_mode[m] = {"input_tokens": int(in_tok), "output_tokens": int(out_tok),
                       "cost_full": round(cost, 2), "cost_batched": round(cost / 2, 2)}
        in_tok_total += in_tok
        out_tok_total += out_tok
    full = in_tok_total / 1e6 * PRICE_IN + out_tok_total / 1e6 * PRICE_OUT
    return {"model": MODEL, "n_clips": n_clips, "total_seconds": round(total_seconds, 1),
            "modes": modes, "per_mode": per_mode,
            "grand_full": round(full, 2), "grand_batched": round(full / 2, 2)}


def assert_under_ceiling(proj: dict, ceiling: float) -> None:
    """Abort BEFORE any spend if the conservative full-price projection exceeds ceiling."""
    if proj["grand_full"] > ceiling:
        raise RuntimeError(
            f"COST GUARD: projected full-price ${proj['grand_full']:.2f} exceeds ceiling "
            f"${ceiling:.2f} ({proj['n_clips']} clips x {len(proj['modes'])} modes). "
            f"Raise --ceiling deliberately to proceed.")


# --------------------------------------------------------------------------- #
# 4. upload proxies to File API
# --------------------------------------------------------------------------- #
def upload_proxies(clips: list[Clip], workers: int = 4,
                   max_total_gb: float = 18.0) -> list[Clip]:
    """Upload each proxy once; poll until ACTIVE. Asserts total stays under the
    File API headroom. Returns clips with ``.uploaded`` set (drops failures)."""
    total = sum((c.proxy.stat().st_size for c in clips if c.proxy), start=0)
    if total / 1e9 > max_total_gb:
        raise RuntimeError(f"Proxy total {total/1e9:.1f} GB exceeds File API headroom "
                           f"{max_total_gb} GB — split into waves.")
    client = get_client()

    def _one(c: Clip) -> Optional[Clip]:
        try:
            f = client.files.upload(file=str(c.proxy),
                                    config=types.UploadFileConfig(
                                        display_name=c.uid, mime_type="video/mp4"))
            while f.state.name == "PROCESSING":
                time.sleep(3)
                f = client.files.get(name=f.name)
            if f.state.name == "FAILED":
                _log(f"  upload FAILED (processing) {c.rel}")
                return None
            c.uploaded = f
            return c
        except Exception as e:
            _log(f"  upload FAIL {c.rel}: {e}")
            return None

    out, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(_one, c) for c in clips]):
            c = fut.result()
            done += 1
            if c:
                out.append(c)
            if done % 25 == 0 or done == len(clips):
                _log(f"  uploaded {done}/{len(clips)}")
    out.sort(key=lambda c: c.rel)
    return out


def cleanup_uploads(clips: list[Clip]) -> None:
    client = get_client()
    for c in clips:
        if c.uploaded is not None:
            try:
                client.files.delete(name=c.uploaded.name)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# 5. build requests + submit chunked batch jobs
# --------------------------------------------------------------------------- #
@dataclass
class Task:
    """One (clip, mode) analysis with an optional prompt prefix (e.g. art reframing)."""
    clip: Clip
    mode: str
    prefix: str = ""


@dataclass
class JobSpec:
    job: Any
    keys: list[tuple[str, str]]  # ordered (uid, mode) aligned to inlined_responses


def plan_tasks(clips: list[Clip], base_modes: list[str],
               rotate_theory: Optional[list[str]] = None, art: bool = False) -> list[Task]:
    """Build the per-clip analysis plan. Every clip gets ``base_modes``; if
    ``rotate_theory`` is set, each clip also gets ONE theory mode, rotating across the
    list by clip index. ``art`` applies the contemporary-art prefix to sizzle."""
    tasks: list[Task] = []
    for i, c in enumerate(clips):
        modes = list(base_modes)
        if rotate_theory:
            modes.append(rotate_theory[i % len(rotate_theory)])
        for m in modes:
            prefix = ART_SIZZLE_PREFIX if (art and m == "sizzle") else ""
            tasks.append(Task(clip=c, mode=m, prefix=prefix))
    return tasks


def _request_for(task: Task) -> types.InlinedRequest:
    mode = get_mode(task.mode)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=mode.result_model,
        temperature=0.5,
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
    )
    contents = [types.Content(role="user", parts=[
        types.Part.from_uri(file_uri=task.clip.uploaded.uri,
                            mime_type=task.clip.uploaded.mime_type or "video/mp4"),
        types.Part(text=task.prefix + mode.prompt),
    ])]
    return types.InlinedRequest(contents=contents, config=cfg,
                                metadata={"key": f"{task.clip.uid}|{task.mode}"})


def submit(tasks: list[Task], max_per_job: int = 1000,
           display_prefix: str = "philm-cloud") -> list[JobSpec]:
    """Chunk tasks under the 20 MB inlined cap and submit one batch job per chunk."""
    client = get_client()
    specs: list[JobSpec] = []
    for i in range(0, len(tasks), max_per_job):
        chunk = tasks[i:i + max_per_job]
        reqs = [_request_for(t) for t in chunk]
        keys = [(t.clip.uid, t.mode) for t in chunk]
        job = client.batches.create(
            model=MODEL, src=reqs,
            config=types.CreateBatchJobConfig(
                display_name=f"{display_prefix}-{i // max_per_job + 1}"))
        specs.append(JobSpec(job=job, keys=keys))
        _log(f"  submitted job {i // max_per_job + 1} "
             f"({len(chunk)} requests) -> {job.name} [{job.state.name}]")
    return specs


# --------------------------------------------------------------------------- #
# 6. poll + collect
# --------------------------------------------------------------------------- #
def poll(specs: list[JobSpec], interval: int = 30, timeout_h: float = 26.0) -> list[JobSpec]:
    client = get_client()
    deadline = timeout_h * 3600
    waited = 0
    while True:
        states = []
        for s in specs:
            s.job = client.batches.get(name=s.job.name)
            states.append(s.job.state.name)
        pending = [st for st in states if st not in TERMINAL_STATES]
        from collections import Counter
        _log(f"  poll @ {waited}s: {dict(Counter(states))}")
        if not pending:
            return specs
        if waited >= deadline:
            raise TimeoutError(f"Batch poll exceeded {timeout_h} h; states={Counter(states)}")
        time.sleep(interval)
        waited += interval


def collect(specs: list[JobSpec], clips: list[Clip], out_dir: Path) -> dict:
    """Parse every response (lenient salvage), write per-clip JSON (path-keyed) + combined
    index + actual-cost reconciliation. Raw text is persisted under ``_raw/`` whenever a
    response needs salvage or fails outright, so nothing paid-for is ever unrecoverable."""
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "_raw"
    by_uid = {c.uid: c for c in clips}
    results: dict[str, dict] = {}
    errors: list[dict] = []
    in_tok = out_tok = 0
    n_ok = n_salvaged = n_err = 0

    def _save_raw(uid: str, mode_name: str, txt: str) -> None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{uid}__{mode_name}.txt").write_text(txt)

    for s in specs:
        dest = s.job.dest
        responses = (dest.inlined_responses if dest and dest.inlined_responses else []) or []
        if s.keys and len(responses) != len(s.keys):
            _log(f"  WARN job {s.job.name}: {len(responses)} responses vs {len(s.keys)} keys")
        for i, resp in enumerate(responses):
            # CRITICAL: align by the request's own metadata key, NOT by position —
            # batch returns responses out of submission order. Position is a last resort.
            mkey = (getattr(resp, "metadata", None) or {}).get("key")
            if mkey and "|" in mkey:
                uid, mode_name = mkey.rsplit("|", 1)
            elif i < len(s.keys):
                uid, mode_name = s.keys[i]
            else:
                continue
            clip = by_uid.get(uid)
            rec = results.setdefault(uid, {
                "video": clip.src.name if clip else uid,
                "path": str(clip.src) if clip else "",
                "uid": uid, "modes": [], "analyses": {}})
            if mode_name not in rec["modes"]:
                rec["modes"].append(mode_name)
            if getattr(resp, "error", None):
                msg = getattr(resp.error, "message", str(resp.error))
                errors.append({"uid": uid, "mode": mode_name,
                               "code": getattr(resp.error, "code", None), "message": msg})
                rec["analyses"][mode_name] = {"error": msg}
                n_err += 1
                continue
            txt = resp.response.text if getattr(resp, "response", None) else ""
            try:
                mode = get_mode(mode_name)
                parsed, salvaged = salvage_parse(mode.result_model, txt)
                rec["analyses"][mode_name] = parsed.model_dump()
                if salvaged:
                    rec["analyses"][mode_name]["_salvaged"] = True
                    _save_raw(uid, mode_name, txt)
                    n_salvaged += 1
                else:
                    n_ok += 1
            except Exception as e:
                errors.append({"uid": uid, "mode": mode_name, "message": f"parse: {e}"})
                rec["analyses"][mode_name] = {"error": f"parse: {e}"}
                if txt:
                    _save_raw(uid, mode_name, txt)
                n_err += 1
            u = getattr(resp.response, "usage_metadata", None) if getattr(resp, "response", None) else None
            if u:
                in_tok += u.prompt_token_count or 0
                out_tok += u.candidates_token_count or 0

    for uid, rec in results.items():
        json.dump(rec, open(out_dir / f"{uid}.json", "w"), indent=2)
    json.dump({"batch_info": {"model": MODEL, "clips": len(results),
                              "ok": n_ok, "salvaged": n_salvaged, "errors": n_err},
               "videos": results},
              open(out_dir / "_batch_results.json", "w"), indent=2)

    cost_full = in_tok / 1e6 * PRICE_IN + out_tok / 1e6 * PRICE_OUT
    actual = {"model": MODEL, "responses_ok": n_ok, "responses_salvaged": n_salvaged,
              "responses_err": n_err, "input_tokens": in_tok, "output_tokens": out_tok,
              "cost_full_price_equiv": round(cost_full, 4),
              "cost_batched_equiv": round(cost_full / 2, 4),
              "note": "token counts are real (usage_metadata); billed amount is the "
                      "batched figure (~50% of full) — confirm in the billing console"}
    json.dump({"actual": actual, "errors": errors[:200]},
              open(out_dir / "_actual_cost.json", "w"), indent=2)
    _log(f"\nCollected: {n_ok} clean, {n_salvaged} salvaged, {n_err} err. "
         f"ACTUAL tokens: in={in_tok:,} out={out_tok:,}  "
         f"(=${actual['cost_full_price_equiv']:.4f} full / "
         f"~${actual['cost_batched_equiv']:.4f} batched).")
    return {"actual": actual, "errors": errors,
            "n_ok": n_ok, "n_salvaged": n_salvaged, "n_err": n_err}


# --------------------------------------------------------------------------- #
# orchestrator
# --------------------------------------------------------------------------- #
def run_cloud_batch(root: Path, base_modes: list[str], proxy_root: Path, out_dir: Path,
                    rotate_theory: Optional[list[str]] = None, art: bool = False,
                    ceiling: float = 20.0, limit: Optional[int] = None,
                    skip_analyzed: bool = True, skip_prior_runs: Optional[bool] = None,
                    assume_yes: bool = False,
                    proxy_workers: int = 6, upload_workers: int = 4,
                    max_per_job: int = 1000) -> dict:
    configure_genai()
    out_dir.mkdir(parents=True, exist_ok=True)
    # modes any clip might receive (base + every rotating theory) — for skip/projection
    all_modes = list(base_modes) + list(rotate_theory or [])

    _log(f"[1/6] selecting clips under {root} ...")
    clips = select_clips(root, all_modes, out_dir, skip_analyzed=skip_analyzed,
                         skip_prior_runs=skip_prior_runs, limit=limit)
    plan_note = f"{base_modes}" + (f" + rotate{rotate_theory}" if rotate_theory else "") + (" [art]" if art else "")
    _log(f"      {len(clips)} clips to analyze :: {plan_note}")
    if not clips:
        _log("Nothing to do.")
        return {"status": "empty"}

    _log(f"[2/6] building proxies -> {proxy_root} ...")
    clips = build_proxies(clips, proxy_root, workers=proxy_workers)
    total_s = sum(c.seconds for c in clips)
    if total_s <= 0:
        for c in clips:
            c.seconds = ffdur(c.proxy)
        total_s = sum(c.seconds for c in clips)
    proxy_gb = sum(c.proxy.stat().st_size for c in clips) / 1e9
    _log(f"      {len(clips)} proxies, {proxy_gb:.2f} GB, {total_s/60:.1f} min footage.")

    tasks = plan_tasks(clips, base_modes, rotate_theory=rotate_theory, art=art)

    _log("[3/6] projecting cost ...")
    # each clip gets len(base)+1 analyses; project with a representative theory mode
    proj_modes = list(base_modes) + ([rotate_theory[0]] if rotate_theory else [])
    proj = project_cost(len(clips), total_s, proj_modes)
    proj["n_tasks"] = len(tasks)
    json.dump(proj, open(out_dir / "_projection.json", "w"), indent=2)
    _log(f"      {len(tasks)} analyses · PROJECTED full ${proj['grand_full']:.2f} / "
         f"batched ${proj['grand_batched']:.2f} (ceiling ${ceiling:.2f})")
    for m in proj_modes:
        pm = proj["per_mode"][m]
        _log(f"        {m:10} full ${pm['cost_full']:.2f}  batched ${pm['cost_batched']:.2f}")
    assert_under_ceiling(proj, ceiling)
    if not assume_yes:
        _log("Pass --yes to proceed with upload + batch submission.")
        return {"status": "dry-run", "projection": proj}

    _log("[4/6] uploading proxies to File API ...")
    clips = upload_proxies(clips, workers=upload_workers)
    _log(f"      {len(clips)} uploaded.")
    uploaded_uids = {c.uid for c in clips}
    tasks = [t for t in tasks if t.clip.uid in uploaded_uids]  # drop tasks for failed uploads

    try:
        _log("[5/6] submitting batch job(s) ...")
        specs = submit(tasks, max_per_job=max_per_job)
        specs = poll(specs)
        _log("[6/6] collecting results ...")
        summary = collect(specs, clips, out_dir)
    finally:
        _log("cleanup: deleting File API copies ...")
        cleanup_uploads(clips)

    summary["projection"] = proj
    summary["status"] = "done"
    return summary
