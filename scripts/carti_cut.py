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


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def parse_timecode(tc: str) -> float:
    """'0:15' or '0:15:00' → seconds as float"""
    parts = tc.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def run(cmd: list, **kwargs):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


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

def detect_beats(music_path: Path, video_duration: float) -> list[float]:
    print(f"Loading music: {music_path.name}")
    y, sr = librosa.load(str(music_path))
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # Filter to track duration, apply divisor for slower cuts
    beat_times = [t for t in beat_times if t < video_duration]
    if BEAT_DIVISOR > 1:
        beat_times = beat_times[::BEAT_DIVISOR]

    tempo_val = float(tempo) if tempo.ndim == 0 else float(tempo[0])
    print(f"Detected tempo: {tempo_val:.1f} BPM → {len(beat_times)} cut points")
    return beat_times


# ─── STEP 2: BUILD CUT SCHEDULE ────────────────────────────────────────────────

def build_cut_schedule(beat_times: list[float], clip_pool: list) -> list[dict]:
    """
    Assign each beat interval a clip from the pool.
    Returns list of dicts: {clip_id, start_offset, duration, flash_before, stutter}
    """
    seed = random.randint(0, 9999)
    print(f"Random seed: {seed} (rerun with this to reproduce)")
    rng = random.Random(seed)
    pool = list(clip_pool)
    rng.shuffle(pool)

    schedule = []
    pool_idx = 0

    for i, beat_t in enumerate(beat_times):
        # Duration = time to next beat (or a short clip at end)
        if i + 1 < len(beat_times):
            duration = beat_times[i + 1] - beat_t
        else:
            duration = 0.5  # tail

        # Skip very short segments (< 1 frame)
        if duration < FLASH_DURATION:
            continue

        # Occasionally double-cut (stutter) — schedule same clip twice
        stutter = rng.random() < STUTTER_PROBABILITY

        # Advance clip (or stutter stays on same clip)
        if not stutter or len(schedule) == 0:
            clip_id, start_offset, _ = pool[pool_idx % len(pool)]
            pool_idx += 1
        else:
            # Repeat last clip
            prev = schedule[-1]
            clip_id = prev["clip_id"]
            start_offset = prev["start_offset"] + prev["duration"]

        # Flash frame before this cut?
        flash_before = rng.random() < FLASH_PROBABILITY

        schedule.append({
            "clip_id": clip_id,
            "start_offset": start_offset,
            "duration": duration,
            "flash_before": flash_before,
            "stutter": stutter,
            "beat_time": beat_t,
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
):
    """Extract a video-only segment, scaled and padded to OUTPUT_SIZE."""
    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.4f}",
        "-t", f"{duration:.4f}",
        "-i", str(source),
        "-vf", (
            f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={TARGET_FPS}"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-an",  # strip audio — music added at final stage
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
    parser.add_argument("--output", type=Path, default=Path("carti_cuts"), help="Output directory (default: carti_cuts)")
    parser.add_argument("--compress", action="store_true", help="Create 1080p H.264 proxies for faster processing (cached)")
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
        clip_files = sorted(
            p for p in args.clips.iterdir()
            if p.suffix.lower() in VIDEO_EXTS
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
        # Random offset in the first 75% of clip (leave room for beats)
        max_start = max(0, dur * 0.75)
        offset = random.uniform(0, max_start)
        CLIP_POOL.append((p.stem, offset, p.name))
    print(f"✓ {len(clip_files)} source clips found\n")

    # Get track duration
    video_duration = probe_duration(music_track)

    # Step 1: Beat detection
    beat_times = detect_beats(music_track, video_duration)

    # Step 2: Cut schedule
    schedule = build_cut_schedule(beat_times, CLIP_POOL)
    flash_count = sum(1 for s in schedule if s["flash_before"])
    stutter_count = sum(1 for s in schedule if s["stutter"])
    print(f"✓ {len(schedule)} cuts planned ({flash_count} flash frames, {stutter_count} stutters)\n")

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

        # Track clip playhead per clip so segments don't overlap
        clip_playhead: dict[str, float] = {c: off for c, off, _ in CLIP_POOL}

        for entry in schedule:
            clip_id = entry["clip_id"]
            source = clip_paths[clip_id]

            if entry["flash_before"]:
                ordered_segments.append(white_flash)

            seg_path = segments_dir / f"seg_{seg_idx:05d}.mp4"
            start = clip_playhead[clip_id]
            duration = entry["duration"]

            # Safety: don't read past end of source
            src_duration = probe_duration(source)
            if start + duration > src_duration:
                start = max(0.0, src_duration - duration - 0.1)

            extract_segment(source, start, duration, seg_path)
            ordered_segments.append(seg_path)

            # Advance playhead (stutter clips share a short window)
            if not entry["stutter"]:
                clip_playhead[clip_id] = start + duration

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
