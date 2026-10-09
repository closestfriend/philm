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
#   "scipy",
#   "librosa>=0.11",
#   "soundfile",
#   "pillow",
# ]
# ///
"""embed_cut.py — compose from the EmbeddingGemma 2 index instead of the catalogue.

The index (scripts/embed_local.py) knows which clips RESEMBLE each other. The catalogue never did.
So a cut can MOVE through the archive — drift toward something, or jump away from it — rather than
pull from a pool. Every mode below is one rule for the next cut, applied on a beat grid.

  Theory in one line each (so the recipe can be read later):
    walk       Bergson/Massumi: continuity of becoming; each cut is the nearest unused clip, so the
               picture morphs. --toward adds a destination the walk bends to over the track.
    encounter  Ernst's definition of collage, "the coupling of two realities, irreconcilable in
               appearance, upon a plane which apparently does not suit them" (via Lautréamont,
               Breton's objective chance; Shklovsky's ostranenie). --pattern "nnF" = two near
               steps then a FAR jump: the shock. --plane keeps the pair on one plane (same axis
               score) while the images are irreconcilable (far in the full embedding).
    prompts    a shot list in words; each section of the track casts from clips nearest its prompt,
               ordered by the step pattern so the section still flows (or shocks).
    axis       drives the EXISTING affect_score.py engine with an embedding axis score (dwelling,
               front_stage, poor_image, intensity) in place of Gemini intensity. See PROXY note.
    silent     a walk/encounter at a fixed cut rate with no track, for watching the archive
               reorganise itself.

  PROXY NOTE (axis mode): affect_score.py reads a catalogue of per-clip intensity timecodes. Axis
  mode writes a SYNTHETIC catalogue where "intensity" = the axis score (ranked to 1..10) and then
  runs the real engine on it, with its output and usage ledger redirected to embed_cuts/ so the
  karman-video-art rarity ledger is not polluted. Conclusions about Gemini's affect read do not
  transfer; conclusions about the engine's curve-fitting do.

  Picture: iPhone proxies are 94% portrait (202x360). Default canvas 360x640, STRETCHED to fill
  (--fit stretch, Hunter's call 2026-10-08: "stretch it, we're getting weird"). --fit pad letterboxes.

Examples (run with --script, not plain uv run; the model loads only when text/axis is needed):
  uv run --script scripts/embed_cut.py walk --track T.mp3 --seed-clip IMG_6002 --toward "an empty road at dawn"
  uv run --script scripts/embed_cut.py encounter --track T.mp3 --pattern nnF --plane dwelling
  uv run --script scripts/embed_cut.py prompts --track T.mp3 -p "alone in a hotel" -p "friends in a car at night"
  uv run --script scripts/embed_cut.py axis --track T.mp3 --axis dwelling -- --variations 2 --diversity 0.8
  uv run --script scripts/embed_cut.py silent --seed-clip IMG_6002 --cut 0.5 --duration 60
  add --dry to any of them for the cut sheet only.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import embed_local as E  # noqa: E402  (index + model loader; same dir)
from ez_mv_core import apply_cut_density, detect_beats  # noqa: E402
from media_utils import ffprobe_duration  # noqa: E402

OUT_DIR = Path.home() / "Projects" / "Ecosystems" / "Karman" / "karman-video-art" / "embed_cuts"
SCRATCH = Path("/Volumes/2025_exSSD_2tb/_render_scratch/embed_cut")   # Vault may be unmounted
ANCHORS = SCRIPTS / "affect_anchors.json"
FPS = 24
MAX_HOLD = 8.0
FAR_BAND = 0.12          # "far" = sample from the least-similar 12% (the absolute farthest is junk)


# ----------------------------------------------------------------------------- index
class Index:
    def __init__(self, out: Path, dim: int = 768):
        self.rows, self.mat, self.owner, self.wtimes = E.load_index(out, dim)
        self.owner = np.asarray(self.owner)
        self.wdur = np.array([b - a for a, b in self.wtimes], dtype=float)
        self.n_clips = len(self.rows)
        self.root = E.DEFAULT_ROOT

    def clip_vec(self, substr: str) -> tuple[int, np.ndarray]:
        hits = [i for i, r in enumerate(self.rows) if substr in r["rel"]]
        if not hits:
            sys.exit(f"no embedded clip matches {substr!r}")
        v = self.mat[self.owner == hits[0]].mean(axis=0)
        return hits[0], v / np.linalg.norm(v)

    def rel(self, w: int) -> str:
        return self.rows[self.owner[w]]["rel"]

    def path(self, w: int) -> Path:
        return self.root / self.rel(w)


_model = None


def model():
    global _model
    if _model is None:
        t = time.time()
        _model = E.load_model()
        print(f"model ready in {time.time() - t:.1f}s", file=sys.stderr)
    return _model


def text_vec(s: str) -> np.ndarray:
    v = np.asarray(model().encode(s, prompt_name="SearchQuery", normalize_embeddings=True), dtype=np.float32)
    return v / np.linalg.norm(v)


def axis_scores(idx: Index, axis: str) -> np.ndarray:
    """z-scored (high anchors - low anchors) cosine per window, from affect_anchors.json."""
    spec = json.load(open(ANCHORS))["axes"].get(axis)
    if spec is None:
        sys.exit(f"axis {axis!r} not in {ANCHORS.name}; have {list(json.load(open(ANCHORS))['axes'])}")
    hi = np.stack([text_vec(t) for t in spec["high"]])
    lo = np.stack([text_vec(t) for t in spec["low"]])
    s = (idx.mat @ hi.T).mean(axis=1) - (idx.mat @ lo.T).mean(axis=1)
    return (s - s.mean()) / (s.std() + 1e-9)


# ----------------------------------------------------------------------------- timeline
def beat_timeline(track: Path, density: float) -> tuple[list[tuple[float, float]], float, float]:
    """Cut boundaries on the beat grid. Returns ([(t0, t1), ...], track_dur, bpm)."""
    beats, bpm = detect_beats(track)
    dur = ffprobe_duration(track)
    cuts = [c for c in apply_cut_density(beats, density) if c < dur]
    if not cuts or cuts[0] > 0.5:
        cuts = [0.0] + cuts
    cuts.append(dur)
    fixed = [cuts[0]]
    for a, b in zip(cuts, cuts[1:]):          # no hold longer than MAX_HOLD (beatless tails)
        n = max(1, int(math.ceil((b - a) / MAX_HOLD)))
        fixed.extend(a + (b - a) * k / n for k in range(1, n + 1))
    segs = [(a, b) for a, b in zip(fixed, fixed[1:]) if b - a >= 0.08]
    return segs, dur, bpm


def fixed_timeline(cut: float, duration: float) -> list[tuple[float, float]]:
    n = max(1, int(round(duration / cut)))
    return [(i * cut, min(duration, (i + 1) * cut)) for i in range(n)]


# ----------------------------------------------------------------------------- the step rule
def chain(idx: Index, start: np.ndarray, n: int, pattern: str, rnd: random.Random, *,
          momentum: float = 0.0, toward: np.ndarray | None = None, toward_w: float = 0.0,
          plane: np.ndarray | None = None, plane_tol: float = 0.5, topk: int = 3,
          pool: np.ndarray | None = None, reuse_clips: bool = False) -> list[dict]:
    """Walk the index n steps. pattern cycles over its letters: n = nearest unused (drift),
    F = far jump (sampled from the least-similar FAR_BAND). Returns one dict per step."""
    used_w, used_c = set(), set()
    cur, prev, cur_w = start.copy(), None, None
    out = []
    for i in range(n):
        step = pattern[i % len(pattern)]
        q = cur.copy()
        if prev is not None and momentum > 0:
            q += momentum * (cur - prev)
        if toward is not None and toward_w > 0:
            w = toward_w * (i / max(1, n - 1))
            q = (1 - w) * q + w * toward
        q /= np.linalg.norm(q)
        sims = idx.mat @ q
        ok = np.ones(len(sims), dtype=bool)
        if pool is not None:
            ok &= pool
        for w_ in used_w:
            ok[w_] = False
        if not reuse_clips:
            ok &= ~np.isin(idx.owner, list(used_c)) if used_c else ok
        if plane is not None and cur_w is not None:
            ok &= np.abs(plane - plane[cur_w]) <= plane_tol
        cand = np.where(ok)[0]
        if len(cand) == 0:                      # plane/pool exhausted: relax to anything unused
            cand = np.where(~np.isin(np.arange(len(sims)), list(used_w)))[0]
            if len(cand) == 0:
                break
        order = cand[np.argsort(-sims[cand])]
        if step == "F":
            tail = order[-max(1, int(len(order) * FAR_BAND)):]
            pick = int(rnd.choice(list(tail)))
        else:
            pick = int(rnd.choice(list(order[:topk])))
        out.append({"w": pick, "sim": float(sims[pick]), "step": step})
        used_w.add(pick)
        used_c.add(int(idx.owner[pick]))
        prev, cur, cur_w = cur, idx.mat[pick], pick
    return out


def cast(idx: Index, picks: list[dict], segs: list[tuple[float, float]], rnd: random.Random) -> list[dict]:
    """Attach each pick to a timeline segment and choose where inside its window to seek."""
    seq = []
    for p, (t0, t1) in zip(picks, segs):
        w = p["w"]
        a, b = idx.wtimes[w]
        hold = t1 - t0
        seek = a + rnd.uniform(0, max(0.0, (b - a) - hold)) if (b - a) > hold else a
        seq.append({**p, "t0": t0, "t1": t1, "hold": hold, "seek": seek, "rel": idx.rel(w),
                    "win": (a, b)})
    return seq


# ----------------------------------------------------------------------------- render
def next_version(label: str) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n = 1
    while (OUT_DIR / f"{label}_v{n:02d}_rough.mp4").exists() or (OUT_DIR / f"{label}_v{n:02d}_cut.md").exists():
        n += 1
    return f"{label}_v{n:02d}"


def vf_for(fit: str, canvas: tuple[int, int]) -> str:
    w, h = canvas
    if fit == "stretch":
        return f"scale={w}:{h},setsar=1,format=yuv420p"
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"


def ffdur(p: Path) -> float:
    try:
        return ffprobe_duration(p)
    except Exception:
        return 0.0


def render(name: str, idx: Index, seq: list[dict], track: Path | None, fit: str, canvas: tuple[int, int]) -> Path:
    segdir = SCRATCH / name
    segdir.mkdir(parents=True, exist_ok=True)
    vf = vf_for(fit, canvas)
    listfile = segdir / "list.txt"
    with open(listfile, "w") as lf:
        for i, s in enumerate(seq):
            nf = max(1, int(round(s["t1"] * FPS)) - int(round(s["t0"] * FPS)))
            seg = segdir / f"seg_{i:04d}.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{s['seek']:.3f}",
                            "-i", str(idx.path(s["w"])), "-frames:v", str(nf), "-vf", vf, "-r", str(FPS),
                            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", str(seg)],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
            got = ffdur(seg)
            planned = nf / FPS
            if got < planned - 0.1:              # short window: freeze the last frame to length
                padded = segdir / f"seg_{i:04d}p.mp4"
                subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(seg), "-vf",
                                f"tpad=stop_mode=clone:stop_duration={max(0.04, planned - max(got, 0)):.3f}",
                                "-r", str(FPS), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                                str(padded)], stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
                if padded.exists() and padded.stat().st_size > 1000:
                    seg = padded
            if seg.exists() and seg.stat().st_size > 1000:
                lf.write(f"file '{seg}'\n")
            if (i + 1) % 25 == 0:
                print(f"  cut {i + 1}/{len(seq)}", file=sys.stderr)
    out = OUT_DIR / f"{name}_rough.mp4"
    cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listfile)]
    if track is not None:
        cmd += ["-i", str(track), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k",
                "-t", f"{ffprobe_duration(track):.3f}"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not out.exists():
        sys.exit(f"concat failed: {r.stderr[-800:]}")
    return out


def sheet(name: str, mode: str, seq: list[dict], track: Path | None, bpm: float | None, notes: list[str]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    far = sum(1 for s in seq if s.get("step") == "F")
    lines = [f"# {name} — embed_cut `{mode}`", "",
             f"{len(seq)} cuts, {sum(s['hold'] for s in seq) / 60:.1f} min, {len({s['rel'] for s in seq})} distinct clips, "
             f"{far} far jumps. Track: `{track.name if track else 'none (silent)'}`"
             + (f", {bpm:.0f} bpm" if bpm else "") + ".", "",
             "**Recipe:** `" + " ".join(a if " " not in a else repr(a) for a in sys.argv[1:]) + "`", ""]
    lines += [f"- {n}" for n in notes] + ["",
              "| # | t | hold | step | sim | clip | window |", "|--:|--:|--:|:--|--:|:--|:--|"]
    for i, s in enumerate(seq, 1):
        a, b = s["win"]
        lines.append(f"| {i} | {s['t0']:.2f}s | {s['hold']:.2f}s | {s.get('step', '')} | {s.get('sim', 0):.3f} | "
                     f"`{s['rel']}` | {a:.0f}-{b:.0f}s @ {s['seek']:.1f}s |")
    p = OUT_DIR / f"{name}_cut.md"
    p.write_text("\n".join(lines) + "\n")
    return p


# ----------------------------------------------------------------------------- modes
def start_vector(idx: Index, a, rnd: random.Random) -> tuple[np.ndarray, str]:
    if getattr(a, "seed_clip", None):
        _, v = idx.clip_vec(a.seed_clip)
        return v, f"start: clip like `{a.seed_clip}`"
    if getattr(a, "prompt", None):
        return text_vec(a.prompt), f"start: prompt {a.prompt!r}"
    w = rnd.randrange(len(idx.mat))
    return idx.mat[w].copy(), f"start: random window of `{idx.rel(w)}` (seed {a.seed})"


def run_chain_mode(a, mode: str, pattern: str):
    idx = Index(Path(a.index))
    rnd = random.Random(a.seed)
    if mode == "silent":
        segs, dur, bpm, track = fixed_timeline(a.cut, a.duration), a.duration, None, None
    else:
        track = Path(a.track).expanduser()
        segs, dur, bpm = beat_timeline(track, a.density)
    start, note = start_vector(idx, a, rnd)
    notes = [note, f"pattern `{pattern}` (n = nearest unused, F = far jump from the least-similar {FAR_BAND:.0%})",
             f"momentum {a.momentum}, top-k {a.topk}"]
    toward = toward_w = None
    if getattr(a, "toward", None):
        toward, toward_w = text_vec(a.toward), a.toward_weight
        notes.append(f"bending toward {a.toward!r} (weight {a.toward_weight} by the end)")
    plane = None
    if getattr(a, "plane", None):
        plane = axis_scores(idx, a.plane)
        notes.append(f"plane: `{a.plane}` axis, pairs stay within ±{a.plane_tol} z of each other (Ernst)")
    picks = chain(idx, start, len(segs), pattern, rnd, momentum=a.momentum, toward=toward,
                  toward_w=toward_w or 0.0, plane=plane, plane_tol=a.plane_tol, topk=a.topk)
    seq = cast(idx, picks, segs, rnd)
    finish(a, mode, idx, seq, track, bpm, notes)


def run_prompts(a):
    idx = Index(Path(a.index))
    rnd = random.Random(a.seed)
    track = Path(a.track).expanduser()
    segs, dur, bpm = beat_timeline(track, a.density)
    n = len(segs)
    bounds = [round(n * k / len(a.prompt)) for k in range(len(a.prompt) + 1)]
    seq, notes = [], [f"{len(a.prompt)} prompt sections, pattern `{a.pattern}` inside each"]
    taken = np.zeros(len(idx.mat), dtype=bool)
    for k, text in enumerate(a.prompt):
        count = bounds[k + 1] - bounds[k]
        if count <= 0:
            continue
        q = text_vec(text)
        sims = idx.mat @ q
        order = np.argsort(-sims)
        pool = np.zeros(len(sims), dtype=bool)
        want, seen_clips = count * a.pool_mult, set()
        for w in order:                          # nearest distinct clips, enough to choose among
            if taken[w]:
                continue
            c = int(idx.owner[w])
            if c in seen_clips:
                continue
            pool[w] = True
            seen_clips.add(c)
            if len(seen_clips) >= want:
                break
        picks = chain(idx, q, count, a.pattern, rnd, topk=a.topk, pool=pool)
        for p in picks:
            taken[p["w"]] = True
            p["prompt"] = k
        seq += cast(idx, picks, segs[bounds[k]:bounds[k + 1]], rnd)
        notes.append(f"section {k + 1}: {text!r} → cuts {bounds[k] + 1}-{bounds[k + 1]} "
                     f"({segs[bounds[k]][0]:.0f}-{segs[bounds[k + 1] - 1][1]:.0f}s)")
    finish(a, "prompts", idx, seq, track, bpm, notes)


def run_axis(a):
    """PROXY: synthetic catalogue (intensity := axis rank 1..10) fed to the real affect_score engine."""
    import affect_score as AS
    idx = Index(Path(a.index))
    z = axis_scores(idx, a.axis)
    if a.invert:
        z = -z
    ranks = z.argsort().argsort() / max(1, len(z) - 1)      # 0..1 quantile across windows
    lvl = np.clip(np.floor(1 + 9 * ranks).astype(int), 1, 10)
    cat = Path(a.index) / "axis_catalog" / (a.axis + ("_inv" if a.invert else ""))
    cat.mkdir(parents=True, exist_ok=True)
    for f in cat.glob("*.json"):
        f.unlink()
    for ci, row in enumerate(idx.rows):
        ws = np.where(idx.owner == ci)[0]
        tcs = []
        for w in ws:
            t0, t1 = idx.wtimes[w]
            for t in (t0, max(t0, t1 - 1.0)):          # two samples per window so best_window has a span
                tcs.append({"time": f"{int(t // 60)}:{int(t % 60):02d}", "intensity": int(lvl[w]),
                            "atmosphere": f"{a.axis} {'high' if z[w] > 0.5 else 'low' if z[w] < -0.5 else 'mid'}",
                            "vector": "static"})
        (cat / f"{row['key']}.json").write_text(json.dumps({
            "video": Path(row["rel"]).name, "path": str(idx.root / row["rel"]), "uid": row["key"],
            "proxy": str(idx.root / row["rel"]), "modes": ["affect"],
            "analyses": {"affect": {"video_description": f"synthetic: {a.axis} axis from EmbeddingGemma 2",
                                    "timecodes": tcs},
                         "sizzle": {"dominant_tone": "", "best_for": [], "overall_energy": int(lvl[ws].max())}}}))
    AS.CATALOG = cat
    AS.OUT = OUT_DIR / "axis"
    AS.USAGE_MANIFEST = AS.OUT / "usage_manifest.jsonl"
    AS.SCRATCH = SCRATCH / "affect_score"
    AS.SEG_VF = vf_for(a.fit, tuple(a.canvas))
    label = f"{a.axis.upper()}{'_INV' if a.invert else ''}"
    sys.argv = ["affect_score.py", "--audio", str(Path(a.track).expanduser()), "--label", label] \
        + (["--dry"] if a.dry else []) + list(a.extra)
    print(f"PROXY: synthetic catalogue {cat} ({len(idx.rows)} clips) → affect_score {sys.argv[1:]}", file=sys.stderr)
    return AS.main()


def finish(a, mode, idx, seq, track, bpm, notes):
    label = a.label or (mode.upper() if track is None else f"{Path(track).stem[:28].upper().replace(' ', '_')}_{mode.upper()}")
    name = next_version(label)
    notes.append(f"fit `{a.fit}` on {a.canvas[0]}x{a.canvas[1]}")
    sp = sheet(name, mode, seq, track, bpm, notes)
    print(f"sheet  -> {sp}")
    if a.dry:
        return
    t = time.time()
    out = render(name, idx, seq, track, a.fit, tuple(a.canvas))
    print(f"render -> {out}  ({ffdur(out):.1f}s, {time.time() - t:.0f}s to render)")


# ----------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    def common(p, track=True):
        p.add_argument("--index", default=str(E.DEFAULT_OUT), help="embedding index folder")
        if track:
            p.add_argument("--track", required=True)
            p.add_argument("--density", type=float, default=0.5, help="cuts per beat: 1=every beat, 0.5=every 2nd, 2=half-beats")
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--label", default=None)
        p.add_argument("--dry", action="store_true", help="cut sheet only")
        p.add_argument("--fit", choices=["stretch", "pad"], default="stretch")
        p.add_argument("--canvas", type=int, nargs=2, default=[360, 640], metavar=("W", "H"))

    def chain_args(p, default_pattern):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--seed-clip", help="start from the clip whose path contains this")
        g.add_argument("--prompt", help="start from a text prompt")
        p.add_argument("--pattern", default=default_pattern, help="step letters, cycled: n=nearest, F=far jump")
        p.add_argument("--momentum", type=float, default=0.3, help="keep moving in the direction of the last step")
        p.add_argument("--topk", type=int, default=3, help="sample among the K nearest (1 = strict)")
        p.add_argument("--toward", default=None, help="text destination the walk bends toward")
        p.add_argument("--toward-weight", type=float, default=0.6)
        p.add_argument("--plane", default=None, help="axis from affect_anchors.json the pairs must share")
        p.add_argument("--plane-tol", type=float, default=0.5, help="z-score band for --plane")

    w = sub.add_parser("walk"); common(w); chain_args(w, "n"); w.set_defaults(fn=lambda a: run_chain_mode(a, "walk", a.pattern))
    e = sub.add_parser("encounter"); common(e); chain_args(e, "nnF"); e.set_defaults(fn=lambda a: run_chain_mode(a, "encounter", a.pattern))
    s = sub.add_parser("silent"); common(s, track=False); chain_args(s, "n")
    s.add_argument("--cut", type=float, default=0.5, help="seconds per cut")
    s.add_argument("--duration", type=float, default=60.0)
    s.set_defaults(fn=lambda a: run_chain_mode(a, "silent", a.pattern))
    pr = sub.add_parser("prompts"); common(pr)
    pr.add_argument("-p", "--prompt", action="append", required=True, help="one per section, in order")
    pr.add_argument("--pattern", default="n")
    pr.add_argument("--topk", type=int, default=3)
    pr.add_argument("--pool-mult", type=int, default=3, help="candidate clips per section = cuts × this")
    pr.set_defaults(fn=run_prompts)
    ax = sub.add_parser("axis"); common(ax)
    ax.add_argument("--axis", required=True, help="axis name from affect_anchors.json")
    ax.add_argument("--invert", action="store_true", help="low pole = intensity 10")
    ax.add_argument("extra", nargs="*", help="passed to affect_score after --  (e.g. -- --variations 2)")
    ax.set_defaults(fn=run_axis)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
