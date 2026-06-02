#!/usr/bin/env python3
"""
carti_cut.py — Playboi Carti-style rapid music video cut from Canon footage.

Beat-synced hard cuts, flash frames, stutter effects. No fades.
"""

import argparse
import random
import subprocess
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


def detect_beats(music_path: Path, video_duration: float, density: float = 1.0) -> list[float]:
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
    return beat_times


# ─── STEP 2: BUILD CUT SCHEDULE ────────────────────────────────────────────────

def build_cut_schedule(beat_times: list[float], clip_pool: list) -> list[dict]:
    """
    Assign each beat interval a clip from the pool.
    Returns list of dicts: {clip_id, start_offset, duration, flash_before, stutter, beat_time, effect, lip_sync}

    Clips with lip_sync=True are song-locked: start_offset = beat_time on every occurrence.
    Weighted selection activates when any clip has lip_sync=True or weight != 1.0.
    """
    seed = random.randint(0, 9999)
    print(f"Random seed: {seed} (rerun with this to reproduce)")
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

        if stutter and len(schedule) > 0:
            prev = schedule[-1]
            prev_is_ls = prev.get("lip_sync", False)
            clip_id = prev["clip_id"]
            start_offset = beat_t if prev_is_ls else prev["start_offset"] + prev["duration"]
            is_lip_sync = prev_is_ls
        else:
            if use_weights:
                weights = [c.get("weight", 1.0) for c in pool]
                entry = rng.choices(pool, weights=weights, k=1)[0]
            else:
                entry = pool[pool_idx % len(pool)]
                pool_idx += 1
            clip_id = entry["clip_id"]
            is_lip_sync = entry.get("lip_sync", False)
            start_offset = beat_t if is_lip_sync else entry["offset"]

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
        })

    return schedule


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
    args = parser.parse_args()

    if not args.clips and not args.files:
        parser.error("Provide either --clips (folder) or --files (individual files)")

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
    else:
        scanner = args.clips.rglob("*") if args.recursive else args.clips.iterdir()
        clip_files = sorted(
            p for p in scanner
            if p.suffix.lower() in VIDEO_EXTS
            and (not args.exclude or args.exclude not in str(p))
        )
    if not clip_files:
        raise FileNotFoundError("No video files found")

    # Optionally compress to proxies for faster processing
    if args.compress:
        print(f"Creating proxies ({len(clip_files)} clips)...")
        clip_files = ensure_proxies(clip_files)
        print(f"✓ All proxies ready at {PROXY_DIR}\n")

    # Build clip pool with random start offsets within each clip
    clip_paths = {p.stem: p for p in clip_files}
    CLIP_POOL = []
    for p in clip_files:
        dur = probe_duration(p)
        max_start = max(0, dur * 0.75)
        offset = random.uniform(0, max_start)
        CLIP_POOL.append({"clip_id": p.stem, "offset": offset, "name": p.name, "lip_sync": False, "weight": 1.0})

    # Add lip-sync clips (song-locked — offset is overridden by beat_time at schedule time)
    if args.lipsync:
        for lsp in args.lipsync:
            if not lsp.exists():
                raise FileNotFoundError(f"Lip-sync clip not found: {lsp}")
            clip_paths[lsp.stem] = lsp
            CLIP_POOL.append({"clip_id": lsp.stem, "offset": 0.0, "name": lsp.name, "lip_sync": True, "weight": args.lipsync_weight})
        print(f"✓ {len(args.lipsync)} lip-sync clip(s) added (weight {args.lipsync_weight})\n")

    print(f"✓ {len(clip_files)} source clips found\n")

    # Get track duration
    video_duration = probe_duration(music_track)

    # Step 1: Beat detection
    beat_times = detect_beats(music_track, video_duration, density=args.density)

    # Step 2: Cut schedule
    schedule = build_cut_schedule(beat_times, CLIP_POOL)
    flash_count = sum(1 for s in schedule if s["flash_before"])
    stutter_count = sum(1 for s in schedule if s["stutter"])
    shrink_count = sum(1 for s in schedule if s.get("effect") == "shrink")
    zoom_count = sum(1 for s in schedule if s.get("effect") == "zoom")
    print(f"✓ {len(schedule)} cuts planned ({flash_count} flash, {stutter_count} stutter, {shrink_count} shrink, {zoom_count} zoom)\n")

    # Versioned output filename — never overwrite
    existing = sorted(output_dir.glob("carti_cut_v*.mp4"))
    next_v = len(existing) + 1
    OUTPUT = output_dir / f"carti_cut_v{next_v:02d}.mp4"
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
                start = entry["beat_time"]
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

    # Report
    duration = probe_duration(OUTPUT)
    size_result = subprocess.run(["du", "-h", str(OUTPUT)], capture_output=True, text=True)

    size = size_result.stdout.split()[0]

    print("\n╭────────────────────────────────────────────╮")
    print("│  DONE!                                     │")
    print("╰────────────────────────────────────────────╯")
    print(f"Output : {OUTPUT}")
    print(f"Duration: {duration:.1f}s")
    print(f"Size    : {size}\n")


if __name__ == "__main__":
    main()
