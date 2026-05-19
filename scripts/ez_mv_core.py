#!/usr/bin/env python3
"""
ez_mv_core.py — Core beat-sync MV composition logic.
No globals, no I/O side effects. All config passed as arguments.
"""

import json
import random
import subprocess
import tempfile
from pathlib import Path

import librosa

TARGET_FPS = 30
OUTPUT_SIZE = "1920:1080"
OUTPUT_SIZE_LAVFI = "1920x1080"
FLASH_DURATION = 0.04


def parse_timecode(tc: str) -> float:
    """'0:15' or '1:05:30' → seconds as float"""
    parts = tc.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def run(cmd: list):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def extract_thumbnail(source: Path, output: Path, at: float = 1.0):
    """Extract a single JPEG frame for UI preview."""
    run([
        "ffmpeg", "-y", "-ss", str(at), "-i", str(source),
        "-vframes", "1", "-q:v", "5",
        "-vf", "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2",
        str(output)
    ])


def detect_beats(music_path: Path) -> tuple[list[float], float]:
    """Returns (beat_times, tempo_bpm)."""
    y, sr = librosa.load(str(music_path))
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    tempo_val = float(tempo) if tempo.ndim == 0 else float(tempo[0])
    return beat_times, tempo_val


def apply_cut_density(beat_times: list[float], density: float) -> list[float]:
    """
    density: float where 1.0 = every beat, 0.25 = every 4th beat, 2.0 = every half-beat.
    Values < 1.0 subsample. Values > 1.0 interpolate midpoints.
    """
    if density <= 0:
        return beat_times
    if density <= 1.0:
        step = max(1, round(1.0 / density))
        return beat_times[::step]
    else:
        # Interpolate: insert n midpoints between each pair of beats
        n_interp = round(density) - 1
        result = []
        for i in range(len(beat_times) - 1):
            result.append(beat_times[i])
            for j in range(1, n_interp + 1):
                t = beat_times[i] + (beat_times[i + 1] - beat_times[i]) * j / (n_interp + 1)
                result.append(t)
        result.append(beat_times[-1])
        return result


def load_philm_offset(analysis_dir: Path, clip_stem: str) -> float | None:
    """
    Check for philm affect/sizzle JSON at analysis_dir/clip_stem.json.
    Returns the timecode (seconds) of the highest-intensity moment, or None.
    """
    json_path = analysis_dir / f"{clip_stem}.json"
    if not json_path.exists():
        return None
    try:
        data = json.loads(json_path.read_text())
        timecodes = data.get("timecodes", [])
        if not timecodes:
            return None
        # Works for affect (intensity) and sizzle (energy) schemas
        best = max(timecodes, key=lambda m: m.get("intensity", m.get("energy", 0)))
        return parse_timecode(best["time"])
    except Exception:
        return None


def build_cut_schedule(
    beat_times: list[float],
    clips: list[dict],          # [{"path": Path, "offset": float, "lip_sync"?: bool, "weight"?: float}, ...]
    video_duration: float,
    flash_prob: float,
    stutter_prob: float,
    seed: int | None = None,
) -> tuple[list[dict], int]:
    """
    Returns (schedule, seed_used).
    Each schedule entry: {path, start_offset, duration, flash_before, stutter, beat_time, lip_sync}

    Lip-sync clips (lip_sync=True) are song-locked: start_offset = beat_time on every occurrence,
    including stutters. Weighted selection activates when any clip has lip_sync=True or weight != 1.0;
    otherwise existing round-robin shuffle runs unchanged.
    """
    if seed is None:
        seed = random.randint(0, 9999)
    rng = random.Random(seed)

    pool = list(clips)
    use_weights = any(c.get("lip_sync", False) or c.get("weight", 1.0) != 1.0 for c in pool)

    if not use_weights:
        rng.shuffle(pool)

    beat_times = [t for t in beat_times if t < video_duration]

    schedule = []
    pool_idx = 0

    for i, beat_t in enumerate(beat_times):
        duration = beat_times[i + 1] - beat_t if i + 1 < len(beat_times) else 0.5
        if duration < FLASH_DURATION:
            continue

        stutter = rng.random() < stutter_prob
        if stutter and len(schedule) > 0:
            prev = schedule[-1]
            prev_is_ls = prev.get("lip_sync", False)
            clip = {
                "path": prev["path"],
                "offset": beat_t if prev_is_ls else prev["start_offset"],
                "lip_sync": prev_is_ls,
                "weight": prev.get("weight", 1.0),
            }
        else:
            if use_weights:
                weights = [c.get("weight", 1.0) for c in pool]
                clip = rng.choices(pool, weights=weights, k=1)[0]
            else:
                clip = pool[pool_idx % len(pool)]
                pool_idx += 1

        is_lip_sync = clip.get("lip_sync", False)

        schedule.append({
            "path": clip["path"],
            "start_offset": beat_t if is_lip_sync else clip["offset"],
            "duration": duration,
            "flash_before": rng.random() < flash_prob,
            "stutter": stutter,
            "beat_time": beat_t,
            "lip_sync": is_lip_sync,
        })

    return schedule, seed


def generate_flash_frame(tmp_dir: Path) -> Path:
    white = tmp_dir / "white_flash.mp4"
    run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=white:s={OUTPUT_SIZE_LAVFI}:d={FLASH_DURATION:.4f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-r", str(TARGET_FPS), str(white)
    ])
    return white


def extract_segment(source: Path, start: float, duration: float, output: Path):
    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.4f}",
        "-accurate_seek",
        "-i", str(source),
        "-t", f"{duration:.4f}",
        "-vf", (
            f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={TARGET_FPS}"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-an", str(output)
    ])


def assemble(
    schedule: list[dict],
    white_flash: Path,
    music_path: Path,
    output_path: Path,
    video_duration: float,
    progress_callback=None,
):
    """
    Full assembly pipeline. progress_callback(current, total) called per segment.
    """
    with tempfile.TemporaryDirectory(prefix="ez_mv_") as tmp:
        tmp_dir = Path(tmp)
        segs_dir = tmp_dir / "segs"
        segs_dir.mkdir()

        ordered_segments: list[Path] = []
        playhead: dict[Path, float] = {}

        # Initialize playheads for B-roll clips only (lip-sync clips are song-locked, no playhead needed)
        seen = set()
        for entry in schedule:
            p = entry["path"]
            if p not in seen and not entry.get("lip_sync", False):
                playhead[p] = entry["start_offset"]
                seen.add(p)

        # Cache source durations — avoid N ffprobe calls for repeated clips
        src_durations: dict[Path, float] = {}
        for entry in schedule:
            p = entry["path"]
            if p not in src_durations:
                src_durations[p] = probe_duration(p)

        total = len(schedule)
        for idx, entry in enumerate(schedule):
            if entry["flash_before"]:
                ordered_segments.append(white_flash)

            seg_path = segs_dir / f"seg_{idx:05d}.mp4"
            src = entry["path"]
            duration = entry["duration"]
            src_dur = src_durations[src]

            if entry.get("lip_sync", False):
                start = entry["beat_time"]
                if start + duration > src_dur:
                    start = max(0.0, src_dur - duration - 0.1)
            else:
                start = playhead[src]
                if start + duration > src_dur:
                    start = max(0.0, src_dur - duration - 0.1)
                if not entry["stutter"]:
                    playhead[src] = start + duration

            extract_segment(src, start, duration, seg_path)
            ordered_segments.append(seg_path)

            if progress_callback:
                progress_callback(idx + 1, total)

        # Write concat list
        concat_file = tmp_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for seg in ordered_segments:
                f.write(f"file '{seg.absolute()}'\n")

        # Final assemble with music
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(music_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(video_duration),
            "-movflags", "+faststart",
            str(output_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
