#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "sentence-transformers>=6.1",
#   "transformers",
#   "torch",
#   "torchvision",
#   "torchcodec",
#   "numpy",
#   "pillow",
# ]
# ///
"""Embed a folder of video proxies with EmbeddingGemma 2 (fully local), then search them.

Why this exists: the SQLite archive is searched by keyword and facet only. EmbeddingGemma 2
(released 2026-10-06) puts text, image, video and audio in ONE 768-d space, so a text query
("a kitchen at night"), a still, or another clip can retrieve footage with no catalogue pass.
Nothing leaves this machine: only the model weights are downloaded, from Hugging Face.

Runs with its own dependencies (PEP 723), deliberately NOT part of the project env, because
torch is heavy. Run it with `uv run --script`, not plain `uv run`:

  # embed (resumable; re-run the same command to continue)
  uv run --script scripts/embed_local.py embed --limit 100          # pilot
  uv run --script scripts/embed_local.py embed                      # everything

  # search what you embedded
  uv run --script scripts/embed_local.py search "someone laughing in a car" --top 12 --sheet /tmp/hits.jpg
  uv run --script scripts/embed_local.py search --like "IMG_4079.mp4" --top 12

Design notes
  * Input is the 360p PROXIES that batch_cloud already built, not the originals: the video
    encoder sees a handful of frames either way, and proxies decode fast.
  * The video processor samples 1 frame/s and CAPS at 32 frames (processor_config.json:
    fps=1, max_frames=32, overflow_strategy=uniform; ~140 tokens per frame). A clip longer than
    WINDOW seconds is therefore cut into windows so no stretch is skipped, and each window is
    embedded separately. A clip's search score is its best window.
  * The audio encoder is NOT loaded (config_kwargs audio_config=None, 740M -> 440M params).
    Audio can be added later; the vectors stay in the same space.
  * Vectors are stored L2-normalised, float16, full 768-d. Matryoshka truncation (512/256/128)
    can be applied at search time by slicing and re-normalising.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

MEDIA = Path("/Volumes/2025_exSSD_2tb/Photography + Video")
DEFAULT_ROOT = MEDIA / "_proxies" / "_found_footage_wer_iphone"
DEFAULT_OUT = MEDIA / "_embeddings" / "_found_footage_wer_iphone"
MODEL_ID = "google/embeddinggemma-2"
WINDOW = 32.0          # seconds per window = 32 frames at 1 fps, the processor's max_frames cap
MIN_TAIL = 8.0         # a trailing window shorter than this is merged into the previous one


def load_model(dtype: str = "bfloat16", device: str | None = None, text_only: bool = False):
    import torch
    from sentence_transformers import SentenceTransformer

    device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
    # The model card warns against float16; bfloat16 or float32 only.
    td = {"bfloat16": torch.bfloat16, "float32": torch.float32}[dtype]
    config = {"audio_config": None, **({"vision_config": None} if text_only else {})}
    return SentenceTransformer(MODEL_ID, device=device, config_kwargs=config,
                               model_kwargs={"torch_dtype": td})


def cmd_query_vector(a):
    """Emit only a SearchQuery vector, for the lightweight local browser."""
    model = load_model(a.dtype, text_only=True)
    vector = np.asarray(model.encode(a.query, prompt_name="SearchQuery", normalize_embeddings=True),
                        dtype=np.float32)
    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise RuntimeError("invalid query embedding")
    print(json.dumps(vector.tolist()))


def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def windows_for(dur: float) -> list[tuple[float, float]]:
    if dur <= WINDOW + MIN_TAIL:
        return [(0.0, dur)]
    wins, t = [], 0.0
    while t < dur:
        end = min(dur, t + WINDOW)
        wins.append((t, end))
        t = end
    if len(wins) > 1 and wins[-1][1] - wins[-1][0] < MIN_TAIL:
        last = wins.pop()
        wins[-1] = (wins[-1][0], last[1])
    return wins


def cut_window(src: Path, t0: float, t1: float, dst: Path) -> bool:
    r = subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t",
                        f"{t1 - t0:.3f}", "-i", str(src), "-an", "-c:v", "libx264", "-preset",
                        "ultrafast", "-crf", "30", str(dst)], capture_output=True)
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000


def key_for(rel: str) -> str:
    return hashlib.sha1(rel.encode()).hexdigest()[:12]


def read_manifest(out: Path) -> dict[str, dict]:
    m = out / "manifest.jsonl"
    rows = {}
    if m.exists():
        for line in m.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                rows[d["key"]] = d
    return rows


# ---------------------------------------------------------------- embed
def cmd_embed(a):
    root, out = Path(a.root), Path(a.out)
    (out / "clips").mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in root.rglob("*.mp4") if not p.name.startswith("._"))
    rels = [str(p.relative_to(root)) for p in files]
    if a.shuffle:
        random.Random(a.shuffle).shuffle(rels)
    if a.first:  # process these first (one relative path per line), then the rest
        # no .strip(): some iPhone folders really do start with a space (" iphone feb vid 3")
        pri = [l for l in Path(a.first).read_text().splitlines() if l]
        have, pset = set(rels), set(pri)
        rels = [r for r in pri if r in have] + [r for r in rels if r not in pset]
    done = read_manifest(out)
    todo = [r for r in rels if key_for(r) not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(files)} proxies | {len(done)} already embedded | {len(todo)} to do this run -> {out}")
    if not todo:
        return
    t_load = time.time()
    model = load_model(a.dtype)
    print(f"model ready in {time.time() - t_load:.1f}s")
    t_run, n_ok, n_win = time.time(), 0, 0
    with open(out / "manifest.jsonl", "a") as mf, open(out / "errors.jsonl", "a") as ef, \
            tempfile.TemporaryDirectory(prefix="embed_win_") as tmp:
        for i, rel in enumerate(todo, 1):
            src = root / rel
            try:
                dur = probe_duration(src)
                wins = windows_for(dur)
                vecs = []
                for (t0, t1) in wins:
                    if len(wins) == 1:
                        path = src
                    else:
                        path = Path(tmp) / "w.mp4"
                        if not cut_window(src, t0, t1, path):
                            raise RuntimeError(f"ffmpeg could not cut {t0:.0f}-{t1:.0f}s")
                    v = model.encode({"text": "<|video|>", "video": str(path)}, normalize_embeddings=True)
                    v = np.asarray(v, dtype=np.float32)
                    if not np.isfinite(v).all():
                        raise RuntimeError("non-finite embedding (try --dtype float32)")
                    vecs.append(v)
                np.save(out / "clips" / f"{key_for(rel)}.npy", np.stack(vecs).astype(np.float16))
                mf.write(json.dumps({"key": key_for(rel), "rel": rel, "dur": round(dur, 2),
                                     "windows": [[round(x, 2), round(y, 2)] for x, y in wins]}) + "\n")
                mf.flush()
                n_ok += 1
                n_win += len(wins)
            except Exception as e:  # keep going; one bad file must not stop a 3-hour run
                ef.write(json.dumps({"rel": rel, "error": f"{type(e).__name__}: {str(e)[:300]}"}) + "\n")
                ef.flush()
            if i % 10 == 0 or i == len(todo):
                el = time.time() - t_run
                eta = el / i * (len(todo) - i)
                print(f"[{i}/{len(todo)}] ok={n_ok} windows={n_win} {el / 60:.1f} min elapsed, ~{eta / 60:.0f} min left",
                      flush=True)
    print(f"done: {n_ok} clips, {n_win} windows. errors: {(out / 'errors.jsonl').stat().st_size > 0 and 'see errors.jsonl' or 'none'}")


# ---------------------------------------------------------------- search
def load_index(out: Path, dim: int):
    man = read_manifest(out)
    mats, owner, wtimes, rows = [], [], [], list(man.values())
    for ci, row in enumerate(rows):
        v = np.load(out / "clips" / f"{row['key']}.npy").astype(np.float32)[:, :dim]
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        mats.append(v)
        owner += [ci] * len(v)
        wtimes += row["windows"]
    return rows, np.concatenate(mats), np.array(owner), wtimes


def rank_clips(q: np.ndarray, mat: np.ndarray, owner: np.ndarray, n_clips: int):
    sims = mat @ q
    best = np.full(n_clips, -9.0)
    bw = np.zeros(n_clips, dtype=int)
    for wi, (s, o) in enumerate(zip(sims, owner)):
        if s > best[o]:
            best[o], bw[o] = s, wi
    order = np.argsort(-best)
    return order, best, bw


def make_sheet(hits, root: Path, dst: Path):
    from PIL import Image
    thumbs = []
    for (rel, t) in hits:
        tmp = Path(tempfile.mkstemp(suffix=".jpg")[1])
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i",
                        str(root / rel), "-frames:v", "1", "-vf", "scale=320:-2", str(tmp)], capture_output=True)
        if tmp.exists() and tmp.stat().st_size > 0:
            thumbs.append(Image.open(tmp).convert("RGB"))
    if not thumbs:
        return
    cols = 4
    h = max(t.height for t in thumbs)
    rowsn = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 320, rowsn * h), (20, 20, 24))
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * 320, (i // cols) * h))
    sheet.save(dst, quality=85)
    print(f"contact sheet -> {dst}")


def cmd_search(a):
    out, root = Path(a.out), Path(a.root)
    rows, mat, owner, wtimes = load_index(out, a.dim)
    print(f"{len(rows)} clips / {len(mat)} windows in index")
    if a.like:
        hit = [i for i, r in enumerate(rows) if a.like in r["rel"]]
        if not hit:
            sys.exit(f"no embedded clip matches {a.like!r}")
        q = mat[owner == hit[0]].mean(axis=0)
        q /= np.linalg.norm(q)
        print(f"query: clips like {rows[hit[0]]['rel']}")
    else:
        model = load_model(a.dtype)
        q = np.asarray(model.encode(a.query, prompt_name="SearchQuery", normalize_embeddings=True),
                       dtype=np.float32)[: a.dim]
        q /= np.linalg.norm(q)
        print(f"query: {a.query!r}")
    order, best, bw = rank_clips(q, mat, owner, len(rows))
    sheet_hits = []
    for rank, ci in enumerate(order[: a.top + (1 if a.like else 0)], 1):
        if a.like and rows[ci]["rel"] == rows[hit[0]]["rel"]:
            continue
        t0, t1 = wtimes[bw[ci]]
        print(f"{rank:2d}. {best[ci]:.3f}  {rows[ci]['rel']}  [{t0:.0f}-{t1:.0f}s of {rows[ci]['dur']:.0f}s]")
        sheet_hits.append((rows[ci]["rel"], (t0 + t1) / 2))
    if a.sheet:
        make_sheet(sheet_hits[: a.top], root, Path(a.sheet))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("embed", "search"):
        p = sub.add_parser(name)
        p.add_argument("--root", default=str(DEFAULT_ROOT), help="folder of video proxies")
        p.add_argument("--out", default=str(DEFAULT_OUT), help="where embeddings are stored")
        p.add_argument("--dtype", choices=["bfloat16", "float32"], default="bfloat16")
    e = sub.choices["embed"]
    e.add_argument("--limit", type=int, default=0, help="embed at most N new clips this run")
    e.add_argument("--shuffle", type=int, default=0, help="seed: random order instead of alphabetical")
    e.add_argument("--first", default=None, help="file of relative paths to process first")
    e.set_defaults(fn=cmd_embed)
    s = sub.choices["search"]
    s.add_argument("query", nargs="?", default=None, help="text query")
    s.add_argument("--like", default=None, help="find clips similar to this embedded clip (path substring)")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--dim", type=int, default=768, choices=[128, 256, 512, 768], help="Matryoshka truncation")
    s.add_argument("--sheet", default=None, help="write a contact sheet JPG of the hits")
    s.set_defaults(fn=cmd_search)
    q = sub.add_parser("query-vector", help="write a text search vector as JSON to stdout")
    q.add_argument("query")
    q.add_argument("--dtype", choices=["bfloat16", "float32"], default="bfloat16")
    q.set_defaults(fn=cmd_query_vector)
    a = ap.parse_args()
    if a.cmd == "search" and not (a.query or a.like):
        ap.error("search needs a text query or --like")
    a.fn(a)


if __name__ == "__main__":
    main()
