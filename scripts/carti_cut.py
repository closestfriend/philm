#!/usr/bin/env python3
"""
carti_cut.py — Playboi Carti-style rapid music video cut from Canon footage.

Beat-synced hard cuts, flash frames, stutter effects. No fades.
"""

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import librosa
import numpy as np
from media_utils import ffprobe_duration as probe_duration  # noqa: F401

# ─── CONFIG ────────────────────────────────────────────────────────────────────

VIDEO_EXTS = {".mov", ".mp4", ".mpg", ".mpeg", ".mxf", ".avi", ".mkv", ".m4v"}
TARGET_FPS = 30
OUTPUT_SIZE = "1920:1080"
OUTPUT_SIZE_LAVFI = "1920x1080"  # lavfi uses x, not colon

# Flash frame duration (slightly over 1 frame at 30fps)
FLASH_DURATION = 0.04  # ~1.2 frames

# Beat multiplier — only cut on every Nth beat (1 = every beat, 2 = every other)
# At 130 BPM, every beat ≈ 0.46s. Every beat is ~2x faster than typical rap cuts.
BEAT_DIVISOR = 1  # change to 2 for slower cuts

# Probability of inserting a white flash on beat boundaries
FLASH_PROBABILITY = 0.25  # every ~4th beat

# Probability of stutter (repeat same clip twice)
STUTTER_PROBABILITY = 0.15

# Probability of in-frame resize (video shrunk inside black frame)
SHRINK_PROBABILITY = 0.20

# Probability of zoom-crop (punch in tight on center)
ZOOM_PROBABILITY = 0.12


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def parse_timecode(tc: str) -> float:
    """'0:15' or '0:15:00' → seconds as float"""
    parts = tc.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def run(cmd: list, **kwargs):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)


# ─── PROXY COMPRESSION ────────────────────────────────────────────────────────

PROXY_DIR = Path.home() / ".ez_mv_proxies"


def get_proxy_path(source: Path) -> Path:
    """Deterministic proxy path based on source filename + parent dir name."""
    # Include parent dir to avoid collisions between folders with same filenames
    key = f"{source.parent.name}_{source.stem}"
    return PROXY_DIR / f"{key}.mp4"


def compress_to_proxy(source: Path, proxy: Path):
    """Compress to 1080p H.264 proxy. Strips audio."""
    run([
        "ffmpeg", "-y",
        "-i", str(source),
        "-vf", f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-an",
        str(proxy)
    ])


def ensure_proxies(clip_files: list[Path]) -> list[Path]:
    """Create proxies for all clips, skipping those that already exist. Returns proxy paths."""
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    proxies = []
    for source in clip_files:
        proxy = get_proxy_path(source)
        if proxy.exists():
            print(f"  ✓ cached: {source.name}")
        else:
            print(f"  compressing: {source.name}...")
            compress_to_proxy(source, proxy)
        proxies.append(proxy)
    return proxies


# ─── STEP 1: BEAT DETECTION ────────────────────────────────────────────────────

def apply_cut_density(beat_times: list[float], density: float) -> list[float]:
    """
    density: 1.0 = every beat, 0.25 = every 4th beat, 2.0 = every half-beat.
    Values < 1.0 subsample; values > 1.0 interpolate midpoints between beats.
    """
    if density <= 0 or density == 1.0:
        return beat_times
    if density < 1.0:
        step = max(1, round(1.0 / density))
        return beat_times[::step]
    n_interp = round(density) - 1
    result = []
    for i in range(len(beat_times) - 1):
        result.append(beat_times[i])
        for j in range(1, n_interp + 1):
            t = beat_times[i] + (beat_times[i + 1] - beat_times[i]) * j / (n_interp + 1)
            result.append(t)
    if beat_times:
        result.append(beat_times[-1])
    return result


def detect_beats(music_path: Path, video_duration: float,
                 density: float = 1.0) -> tuple[list[float], float]:
    print(f"Loading music: {music_path.name}")
    y, sr = librosa.load(str(music_path))
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # Filter to track duration, apply divisor for slower cuts
    beat_times = [t for t in beat_times if t < video_duration]
    if BEAT_DIVISOR > 1:
        beat_times = beat_times[::BEAT_DIVISOR]

    beat_times = apply_cut_density(beat_times, density)

    tempo_val = float(np.asarray(tempo).flatten()[0])
    print(f"Detected tempo: {tempo_val:.1f} BPM → {len(beat_times)} cut points (density {density})")
    return beat_times, tempo_val


# ─── STEP 2: BUILD CUT SCHEDULE ────────────────────────────────────────────────

def build_cut_schedule(beat_times: list[float], clip_pool: list,
                       seed: int | None = None) -> list[dict]:
    """
    Assign each beat interval a clip from the pool.
    Returns list of dicts: {clip_id, start_offset, duration, flash_before, stutter, beat_time, effect, lip_sync}

    Clips with lip_sync=True are song-locked: start_offset = beat_time - song_start on every
    occurrence, and a take is only eligible for beats its footage actually covers
    (song_start <= beat_time and beat_time + duration <= song_end). Outside that window the
    beat falls back to B-roll. Weighted selection activates when any clip has lip_sync=True
    or weight != 1.0.

    When NO clip covers a beat (performance-only pools past the last take's footage), the
    previous shot is held (its duration extended, ``held``=True) instead of cutting to
    out-of-sync footage; if that happens on the very first beat, the earliest-starting take is
    used clamped to its first frame (``clamped``=True).

    ``seed`` makes the plan reproducible. Note the plan is only fully reproducible when the
    clip pool was ALSO built from the same seed (see build_clip_pool) — B-roll start offsets
    live in the pool, not here.
    """
    if seed is None:
        seed = random.randint(0, 9999)
    print(f"Random seed: {seed} (rerun with --seed {seed} to reproduce)")
    rng = random.Random(seed)
    pool = list(clip_pool)

    use_weights = any(c.get("lip_sync", False) or c.get("weight", 1.0) != 1.0 for c in pool)
    if not use_weights:
        rng.shuffle(pool)

    schedule = []
    pool_idx = 0

    for i, beat_t in enumerate(beat_times):
        if i + 1 < len(beat_times):
            duration = beat_times[i + 1] - beat_t
        else:
            duration = 0.5

        if duration < FLASH_DURATION:
            continue

        stutter = rng.random() < STUTTER_PROBABILITY

        def covers(c):
            return (not c.get("lip_sync", False)
                    or c.get("song_start", 0.0) <= beat_t
                    and beat_t + duration <= c.get("song_end", float("inf")))

        entry = None
        clamped = False
        if stutter and len(schedule) > 0:
            prev = schedule[-1]
            prev_entry = next(c for c in pool if c["clip_id"] == prev["clip_id"])
            if covers(prev_entry):
                entry = prev_entry
                start_offset = prev["start_offset"] + prev["duration"]
            else:
                stutter = False  # take ran out of song; fall through to a normal pick
        if entry is None:
            if use_weights:
                eligible = [c for c in pool if covers(c)]
                if eligible:
                    weights = [c.get("weight", 1.0) for c in eligible]
                    entry = rng.choices(eligible, weights=weights, k=1)[0]
                elif schedule:
                    prev = schedule[-1]
                    if not prev["held"]:
                        prev["held"], prev["held_from"] = True, beat_t
                    prev["duration"] += duration
                    continue
                else:
                    entry = min(pool, key=lambda c: c.get("song_start", 0.0))
                    clamped = True
            else:
                entry = pool[pool_idx % len(pool)]
                pool_idx += 1
            start_offset = entry["offset"]
        clip_id = entry["clip_id"]
        is_lip_sync = entry.get("lip_sync", False)
        if is_lip_sync:
            start_offset = max(0.0, beat_t - entry.get("song_start", 0.0)) if clamped \
                else beat_t - entry.get("song_start", 0.0)

        flash_before = rng.random() < FLASH_PROBABILITY

        roll = rng.random()
        if roll < SHRINK_PROBABILITY:
            effect = "shrink"
        elif roll < SHRINK_PROBABILITY + ZOOM_PROBABILITY:
            effect = "zoom"
        else:
            effect = "normal"

        schedule.append({
            "clip_id": clip_id,
            "start_offset": start_offset,
            "duration": duration,
            "flash_before": flash_before,
            "stutter": stutter,
            "beat_time": beat_t,
            "effect": effect,
            "lip_sync": is_lip_sync,
            "held": False,
            "held_from": None,
            "clamped": clamped,
        })

    return schedule


# ─── STEP 2b: CLIP POOL ───────────────────────────────────────────────────────

def build_clip_pool(
    clip_files: list[Path],
    lipsync_files: list[Path] | None,
    lipsync_weight: float,
    rng: random.Random,
    probe=probe_duration,
    lipsync_offsets: list[float] | None = None,
) -> tuple[list[dict], dict[str, Path]]:
    """Build the scheduler's clip pool and a clip_id -> source path map.

    B-roll clips get a random start offset within the first 75% of their duration, drawn from
    ``rng`` so a seeded run reproduces the same offsets. Lip-sync takes carry the song window
    their footage covers: ``song_start`` is the song second at which the take begins
    (``lipsync_offsets``, one per take, negative if the camera rolled before the track) and
    ``song_end`` = song_start + take duration. A take that also appears in ``clip_files`` is
    cast once, as lip-sync only. ``probe`` is injectable for tests.
    """
    lipsync_files = list(lipsync_files or [])
    if lipsync_offsets is None:
        lipsync_offsets = [0.0] * len(lipsync_files)
    ls_resolved = {p.resolve() for p in lipsync_files}
    clip_files = [p for p in clip_files if p.resolve() not in ls_resolved]

    clip_paths = {p.stem: p for p in clip_files}
    pool = []
    for p in clip_files:
        dur = probe(p)
        max_start = max(0, dur * 0.75)
        pool.append({"clip_id": p.stem, "offset": rng.uniform(0, max_start), "name": p.name,
                     "lip_sync": False, "weight": 1.0})
    for lsp, song_start in zip(lipsync_files, lipsync_offsets):
        clip_paths[lsp.stem] = lsp
        pool.append({"clip_id": lsp.stem, "offset": 0.0, "name": lsp.name,
                     "lip_sync": True, "weight": lipsync_weight,
                     "song_start": song_start, "song_end": song_start + probe(lsp)})
    return pool, clip_paths


# ─── STEP 2c: LIP-SYNC SONG ALIGNMENT ─────────────────────────────────────────
#
# A take shot to playback has the song bleeding into the camera mic, so where the take sits in
# the song can be read off the audio. We shell out to the BBC's audio-offset-finder via uvx
# rather than adding it as a dependency (it pins numpy<2). Confidence below MIN_ALIGN_SCORE is
# treated as "not found" — pass --lipsync-offset by hand in that case.

MIN_ALIGN_SCORE = 10.0
ALIGN_TOOL = ["uvx", "--python", "3.12", "--from", "audio-offset-finder", "audio-offset-finder"]


def detect_song_offset(take: Path, song: Path, tmp_dir: Path) -> tuple[float, float]:
    """Return (offset, score): the take begins ``offset`` seconds into the song
    (negative = camera rolled before the track). Raises RuntimeError if the tool fails."""
    take_wav = tmp_dir / f"{take.stem}_align.wav"
    run(["ffmpeg", "-y", "-i", str(take), "-vn", "-ac", "1", "-ar", "22050", str(take_wav)])
    song_wav = tmp_dir / f"{song.stem}_align.wav"
    if not song_wav.exists():
        run(["ffmpeg", "-y", "-i", str(song), "-ac", "1", "-ar", "22050", str(song_wav)])
    res = subprocess.run(ALIGN_TOOL + ["--find-offset-of", str(take_wav), "--within", str(song_wav)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"audio-offset-finder failed on {take.name}:\n{res.stderr[-800:]}")
    offset = score = None
    for line in res.stdout.splitlines():
        if line.startswith("Offset:"):
            offset = float(line.split()[1])
        elif line.startswith("Standard score:"):
            score = float(line.split()[2])
    if offset is None or score is None:
        raise RuntimeError(f"could not parse audio-offset-finder output:\n{res.stdout}")
    return offset, score


def resolve_lipsync_offsets(takes: list[Path], song: Path, manual: list[float] | None,
                            cache_dir: Path) -> list[dict]:
    """One {offset, score, source} per take. ``manual`` (from --lipsync-offset) wins outright;
    otherwise detect, caching per (take, song) pair so re-renders don't pay the detection cost."""
    if manual is not None:
        if len(manual) != len(takes):
            sys.exit(f"--lipsync-offset needs one value per --lipsync take "
                     f"({len(takes)} takes, {len(manual)} offsets given)")
        return [{"offset": o, "score": None, "source": "manual"} for o in manual]

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "song_offsets.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    out = []
    with tempfile.TemporaryDirectory(prefix="carti_align_") as tmp:
        for take in takes:
            key = hashlib.sha1(f"{take.resolve()}|{take.stat().st_mtime_ns}|"
                               f"{song.resolve()}|{song.stat().st_mtime_ns}".encode()).hexdigest()
            if key in cache:
                out.append({**cache[key], "source": "cache"})
                continue
            if shutil.which("uvx") is None:
                sys.exit("uvx not found: install uv, or pass --lipsync-offset by hand")
            print(f"  aligning {take.name} to {song.name}...", end=" ", flush=True)
            offset, score = detect_song_offset(take, song, Path(tmp))
            print(f"take starts at song {offset:+.3f}s (score {score:.1f})")
            if score < MIN_ALIGN_SCORE:
                sys.exit(f"Low-confidence alignment for {take.name} (score {score:.1f} < "
                         f"{MIN_ALIGN_SCORE}). Was the song playing? Pass --lipsync-offset by hand.")
            cache[key] = {"offset": offset, "score": score}
            cache_file.write_text(json.dumps(cache, indent=2))
            out.append({**cache[key], "source": "detected"})
    return out


def reserve_output(output_dir: Path) -> Path:
    """Claim the next carti_cut_vNN.mp4 name. The mp4 only appears at the very end of a render,
    so we count .json sidecars too and write a stub sidecar immediately — that way two renders
    started minutes apart (or a render that dies mid-way) never collide on a version number."""
    taken = set()
    for f in output_dir.glob("carti_cut_v*"):
        if f.suffix in (".mp4", ".json"):
            taken.add(f.with_suffix("").name)
    next_v = 1
    while f"carti_cut_v{next_v:02d}" in taken:
        next_v += 1
    output = output_dir / f"carti_cut_v{next_v:02d}.mp4"
    output.with_suffix(".json").write_text(json.dumps({"output": output.name, "status": "rendering"}))
    return output


def write_sidecar(output: Path, seed: int, tempo: float, args: dict, schedule: list[dict]) -> Path:
    """Write carti_cut_vNN.json next to the render: everything needed to reproduce or compare it."""
    side = output.with_suffix(".json")
    side.write_text(json.dumps({
        "output": output.name,
        "status": "done",
        "seed": seed,
        "tempo_bpm": round(tempo, 2),
        "cuts": len(schedule),
        "flash": sum(1 for s in schedule if s["flash_before"]),
        "stutter": sum(1 for s in schedule if s["stutter"]),
        "shrink": sum(1 for s in schedule if s.get("effect") == "shrink"),
        "zoom": sum(1 for s in schedule if s.get("effect") == "zoom"),
        "lip_sync_cuts": sum(1 for s in schedule if s.get("lip_sync")),
        "held": sum(1 for s in schedule if s.get("held")),
        "clamped": sum(1 for s in schedule if s.get("clamped")),
        "args": args,
    }, indent=2))
    return side


# ─── STEP 3: GENERATE FLASH FRAMES ─────────────────────────────────────────────

def generate_flash_frames(tmp_dir: Path) -> tuple[Path, Path]:
    white = tmp_dir / "white_flash.mp4"
    black = tmp_dir / "black_flash.mp4"

    run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=white:s={OUTPUT_SIZE_LAVFI}:d={FLASH_DURATION:.4f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-r", str(TARGET_FPS), str(white)
    ])
    run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=black:s={OUTPUT_SIZE_LAVFI}:d={FLASH_DURATION:.4f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-r", str(TARGET_FPS), str(black)
    ])
    return white, black


# ─── STEP 4: EXTRACT CLIP SEGMENTS ─────────────────────────────────────────────

def extract_segment(
    source: Path,
    start: float,
    duration: float,
    output: Path,
    effect: str = "normal",
    rng: random.Random | None = None,
):
    """Extract a video-only segment with optional in-frame effects."""
    if effect == "shrink":
        # Shrink to 40-70% and float inside black frame
        scale_pct = (rng.uniform(0.4, 0.7) if rng else 0.55)
        inner_w = int(1920 * scale_pct)
        inner_h = int(1080 * scale_pct)
        # Random position within frame
        max_x = 1920 - inner_w
        max_y = 1080 - inner_h
        off_x = rng.randint(0, max_x) if rng else max_x // 2
        off_y = rng.randint(0, max_y) if rng else max_y // 2
        vf = (
            f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:{off_x}:{off_y}:black,"
            f"fps={TARGET_FPS}"
        )
    elif effect == "zoom":
        # Zoom/crop into center 40-70% of frame
        crop_pct = (rng.uniform(0.4, 0.7) if rng else 0.55)
        vf = (
            f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
            f"crop=iw*{crop_pct:.2f}:ih*{crop_pct:.2f}:(iw-iw*{crop_pct:.2f})/2:(ih-ih*{crop_pct:.2f})/2,"
            f"scale={OUTPUT_SIZE},"
            f"fps={TARGET_FPS}"
        )
    else:
        vf = (
            f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={TARGET_FPS}"
        )

    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.4f}",
        "-accurate_seek",
        "-i", str(source),
        "-t", f"{duration:.4f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-an",
        str(output)
    ])


# ─── STEP 5: ASSEMBLE ──────────────────────────────────────────────────────────

def build_concat_list(segments: list[Path], concat_file: Path):
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg.absolute()}'\n")


def final_assemble(concat_file: Path, music: Path, output: Path, video_duration: float):
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(music),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(video_duration),
        "-movflags", "+faststart",
        str(output)
    ])


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Beat-sync music video maker")
    parser.add_argument("--music", required=True, type=Path, help="Path to music track (WAV/MP3)")
    parser.add_argument("--clips", type=Path, help="Folder containing video clips")
    parser.add_argument("--files", nargs="+", type=Path, help="Individual video file paths")
    parser.add_argument("--recursive", action="store_true", help="Scan clips folder recursively")
    parser.add_argument("--exclude", type=str, metavar="STR", help="Skip clips whose path contains this string")
    parser.add_argument("--density", type=float, default=1.0, metavar="D", help="Cut density: 1.0=every beat, 2.0=half-beat (2x cuts), 0.5=every other beat")
    parser.add_argument("--output", type=Path, default=Path("carti_cuts"), help="Output directory (default: carti_cuts)")
    parser.add_argument("--compress", action="store_true", help="Create 1080p H.264 proxies for faster processing (cached)")
    parser.add_argument("--lipsync", nargs="+", type=Path, metavar="FILE", help="Lip-sync clip(s) — shot to playback, clip time = song time")
    parser.add_argument("--lipsync-weight", type=float, default=3.0, metavar="W", help="Weight for lip-sync clips vs B-roll (default: 3.0)")
    parser.add_argument("--lipsync-offset", nargs="+", type=float, metavar="SEC",
                        help="Song second at which each --lipsync take begins (same order; negative = "
                             "camera rolled first). Skips audio auto-alignment.")
    parser.add_argument("--seed", type=int, metavar="N",
                        help="Reproduce a previous cut (seed is printed and saved in the .json sidecar)")
    args = parser.parse_args()

    if not args.clips and not args.files and not args.lipsync:
        parser.error("Provide --clips (folder), --files (individual files), or --lipsync takes")

    music_track = args.music
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n╭────────────────────────────────────────────╮")
    print("│  CARTI CUT — beat-sync music video maker  │")
    print("╰────────────────────────────────────────────╯\n")

    if not music_track.exists():
        raise FileNotFoundError(f"Music not found: {music_track}")

    # Get clip list from folder or individual files
    if args.files:
        clip_files = []
        for f in args.files:
            if not f.exists():
                raise FileNotFoundError(f"Clip not found: {f}")
            clip_files.append(f)
    elif args.clips:
        scanner = args.clips.rglob("*") if args.recursive else args.clips.iterdir()
        clip_files = sorted(
            p for p in scanner
            if p.suffix.lower() in VIDEO_EXTS
            and (not args.exclude or args.exclude not in str(p))
        )
    else:
        clip_files = []  # performance-only: every cut comes from a lip-sync take
    if not clip_files and not args.lipsync:
        raise FileNotFoundError("No video files found")

    # Optionally compress to proxies for faster processing
    if args.compress:
        print(f"Creating proxies ({len(clip_files)} clips)...")
        clip_files = ensure_proxies(clip_files)
        print(f"✓ All proxies ready at {PROXY_DIR}\n")

    # One seed governs both the pool (B-roll start offsets) and the schedule
    seed = args.seed if args.seed is not None else random.randint(0, 9999)
    for lsp in args.lipsync or []:
        if not lsp.exists():
            raise FileNotFoundError(f"Lip-sync clip not found: {lsp}")
    lipsync_align = []
    if args.lipsync:
        print("Aligning lip-sync takes to the song...")
        lipsync_align = resolve_lipsync_offsets(args.lipsync, music_track, args.lipsync_offset,
                                                cache_dir=PROXY_DIR)
    CLIP_POOL, clip_paths = build_clip_pool(clip_files, args.lipsync, args.lipsync_weight,
                                            random.Random(seed),
                                            lipsync_offsets=[a["offset"] for a in lipsync_align])
    if args.lipsync:
        for c in CLIP_POOL:
            if c["lip_sync"]:
                print(f"  {c['name']}: covers song {c['song_start']:.1f}s → {c['song_end']:.1f}s")
        print(f"✓ {len(args.lipsync)} lip-sync take(s) added (weight {args.lipsync_weight})\n")

    print(f"✓ {len(clip_files)} source clips found\n")

    # Get track duration
    video_duration = probe_duration(music_track)

    # Step 1: Beat detection
    beat_times, tempo = detect_beats(music_track, video_duration, density=args.density)

    # Step 2: Cut schedule
    schedule = build_cut_schedule(beat_times, CLIP_POOL, seed=seed)
    flash_count = sum(1 for s in schedule if s["flash_before"])
    stutter_count = sum(1 for s in schedule if s["stutter"])
    shrink_count = sum(1 for s in schedule if s.get("effect") == "shrink")
    zoom_count = sum(1 for s in schedule if s.get("effect") == "zoom")
    print(f"✓ {len(schedule)} cuts planned ({flash_count} flash, {stutter_count} stutter, {shrink_count} shrink, {zoom_count} zoom)")
    held = [s for s in schedule if s["held"]]
    if held:
        print(f"  ⚠ {len(held)} shot(s) held where no take covers the song "
              f"(from {min(s['held_from'] for s in held):.1f}s)")
    if any(s["clamped"] for s in schedule):
        print("  ⚠ first cut clamped: no take covers the top of the song")
    print()

    # Versioned output filename — never overwrite, safe for concurrent renders
    OUTPUT = reserve_output(output_dir)
    print(f"Output: {OUTPUT}\n")

    with tempfile.TemporaryDirectory(prefix="carti_cut_") as tmp:
        tmp_dir = Path(tmp)
        segments_dir = tmp_dir / "segs"
        segments_dir.mkdir()

        # Step 3: Flash frames
        print("Generating flash frames...")
        white_flash, black_flash = generate_flash_frames(tmp_dir)
        print("✓ Flash frames ready\n")

        # Step 4: Extract segments
        print(f"Extracting {len(schedule)} segments...")
        ordered_segments: list[Path] = []
        seg_idx = 0

        # Track clip playhead per B-roll clip (lip-sync clips are song-locked, no playhead)
        clip_playhead: dict[str, float] = {
            c["clip_id"]: c["offset"] for c in CLIP_POOL if not c.get("lip_sync", False)
        }

        for entry in schedule:
            clip_id = entry["clip_id"]
            source = clip_paths[clip_id]

            if entry["flash_before"]:
                ordered_segments.append(white_flash)

            seg_path = segments_dir / f"seg_{seg_idx:05d}.mp4"
            duration = entry["duration"]
            src_duration = probe_duration(source)

            if entry.get("lip_sync", False):
                start = entry["start_offset"]  # beat_time - song_start, window-checked by scheduler
                if start + duration > src_duration:
                    start = max(0.0, src_duration - duration - 0.1)
            else:
                start = clip_playhead[clip_id]
                if start + duration > src_duration:
                    start = max(0.0, src_duration - duration - 0.1)
                if not entry["stutter"]:
                    clip_playhead[clip_id] = start + duration

            extract_segment(source, start, duration, seg_path,
                            effect=entry.get("effect", "normal"),
                            rng=random.Random(seg_idx))
            ordered_segments.append(seg_path)

            seg_idx += 1

            if seg_idx % 50 == 0:
                print(f"  {seg_idx}/{len(schedule)} segments extracted...")

        print(f"✓ {seg_idx} segments extracted\n")

        # Step 5: Build concat + assemble
        concat_file = tmp_dir / "concat_list.txt"
        build_concat_list(ordered_segments, concat_file)

        print("Assembling final video with music...")
        final_assemble(concat_file, music_track, OUTPUT, video_duration)

    sidecar = write_sidecar(OUTPUT, seed, tempo, {
        "music": str(music_track),
        "clips": str(args.clips) if args.clips else None,
        "files": [str(f) for f in args.files] if args.files else None,
        "recursive": args.recursive,
        "exclude": args.exclude,
        "density": args.density,
        "compress": args.compress,
        "lipsync": [str(f) for f in args.lipsync] if args.lipsync else None,
        "lipsync_weight": args.lipsync_weight,
        "lipsync_offsets": {str(t): a for t, a in zip(args.lipsync or [], lipsync_align)},
    }, schedule)

    # Report
    duration = probe_duration(OUTPUT)
    size_result = subprocess.run(["du", "-h", str(OUTPUT)], capture_output=True, text=True)

    size = size_result.stdout.split()[0]

    print("\n╭────────────────────────────────────────────╮")
    print("│  DONE!                                     │")
    print("╰────────────────────────────────────────────╯")
    print(f"Output : {OUTPUT}")
    print(f"Sidecar: {sidecar}")
    print(f"Seed   : {seed}  (--seed {seed} to reproduce)")
    print(f"Duration: {duration:.1f}s")
    print(f"Size    : {size}\n")


if __name__ == "__main__":
    main()
