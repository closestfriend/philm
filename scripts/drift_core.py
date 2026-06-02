#!/usr/bin/env python3
"""
drift_core.py — Pure functions for contemplative decay montage.
Extracted from drift_cut.py for use by ez_mv_app.py Streamlit UI.
drift_cut.py remains the CLI entry point and is unchanged.
"""

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from media_utils import VIDEO_EXTENSIONS, ffprobe_duration, ffprobe_resolution, get_video_files  # noqa: F401


def extract_clip(video_path, start, duration, output_path,
                 saturation=1.0, speed=1.0, fps=30, crf=20,
                 width=1920, height=1080):
    filters = []
    if speed != 1.0:
        filters.append(f"setpts={1.0/speed}*PTS")
    filters.append(
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    if saturation != 1.0:
        filters.append(f"eq=saturation={saturation:.2f}")

    subprocess.run([
        'ffmpeg', '-loglevel', 'warning',
        '-ss', str(start), '-i', str(video_path), '-t', str(duration),
        '-vf', ','.join(filters),
        '-r', str(fps), '-fps_mode', 'cfr', '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf),
        '-an', '-y', str(output_path)
    ], check=True)


def generation_loss(input_path, output_path, passes=3):
    """Re-encode through multiple passes to accumulate compression artifacts."""
    current = str(input_path)
    for i in range(passes):
        crf = 28 + (i * 6)
        is_last = (i == passes - 1)
        out = str(output_path) if is_last else str(input_path) + f'.loss_{i}.mp4'
        subprocess.run([
            'ffmpeg', '-loglevel', 'warning',
            '-i', current,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf),
            '-pix_fmt', 'yuv420p', '-an', '-y', out
        ], check=True)
        if current != str(input_path) and os.path.exists(current):
            os.remove(current)
        current = out


def create_split_screen(clip_a_path, clip_b_path, output_path,
                        slow_factor=2.0, zoom=1.4):
    dur = ffprobe_duration(str(clip_a_path))
    filter_complex = (
        f"[0:v]scale=960:1080,setsar=1[left];"
        f"[1:v]scale={int(1920*zoom)}:{int(1080*zoom)},"
        f"crop=1920:1080,"
        f"scale=960:1080,setsar=1,"
        f"setpts={slow_factor}*PTS[right];"
        f"[left][right]hstack=inputs=2"
    )
    subprocess.run([
        'ffmpeg', '-loglevel', 'warning',
        '-i', str(clip_a_path), '-i', str(clip_b_path),
        '-filter_complex', filter_complex,
        '-t', str(dur),
        '-r', '30', '-fps_mode', 'cfr', '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-an', '-y', str(output_path)
    ], check=True)


def create_pip(main_path, pip_path, output_path,
               pip_scale=0.22, position='bottom_right'):
    dur = ffprobe_duration(str(main_path))
    pip_w = int(1920 * pip_scale)
    pip_h = int(1080 * pip_scale)
    margin = 40
    positions = {
        'bottom_right': (1920 - pip_w - margin, 1080 - pip_h - margin),
        'bottom_left':  (margin, 1080 - pip_h - margin),
        'top_right':    (1920 - pip_w - margin, margin),
        'top_left':     (margin, margin),
    }
    x, y = positions.get(position, positions['bottom_right'])
    filter_complex = (
        f"[1:v]scale={pip_w}:{pip_h}[pip];"
        f"[0:v][pip]overlay=x={x}:y={y}"
    )
    subprocess.run([
        'ffmpeg', '-loglevel', 'warning',
        '-i', str(main_path), '-i', str(pip_path),
        '-filter_complex', filter_complex,
        '-t', str(dur),
        '-r', '30', '-fps_mode', 'cfr', '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-an', '-y', str(output_path)
    ], check=True)


def decay_curve(position, intensity=0.7) -> tuple[float, int, int, int]:
    """Map timeline position (0.0–1.0) to (saturation, crf, fps, loss_passes)."""
    sat_floor = max(0.05, 0.4 - (0.35 * intensity))
    saturation = max(sat_floor, 1.0 - (position ** 1.5) * intensity)

    crf_range = int(20 * intensity)
    crf = int(18 + position * crf_range)

    if position > 0.85:
        fps_drop = (position - 0.85) / 0.15
        fps = max(8, int(30 - fps_drop * 18 * intensity))
    else:
        fps = 30

    if position < 0.3:
        loss_passes = 0
    elif position < 0.6:
        loss_passes = 1 if intensity > 0.3 else 0
    elif position < 0.85:
        loss_passes = 2 if intensity > 0.5 else 1
    else:
        loss_passes = 3 if intensity > 0.6 else 2

    return saturation, crf, fps, loss_passes


def plan_segments(audio_duration, min_hold, max_hold,
                  split_chance, pip_chance, seed=None) -> list[dict]:
    """Divide audio into hold/split/pip segments with randomised durations."""
    rng = random.Random(seed)
    segments = []
    current_time = 0.0

    while current_time < audio_duration:
        remaining = audio_duration - current_time
        if remaining < 2.0:
            break

        duration = min(rng.uniform(min_hold, max_hold), remaining)
        position = current_time / audio_duration

        roll = rng.random()
        if roll < pip_chance and duration >= 6.0:
            seg_type = 'pip'
        elif roll < pip_chance + split_chance and duration >= 6.0:
            seg_type = 'split'
        else:
            seg_type = 'hold'

        segments.append({
            'type': seg_type,
            'start_time': current_time,
            'duration': duration,
            'position': position,
        })
        current_time += duration

    return segments


def build_composition(
    videos: str,
    audio: str,
    output_dir: str,
    decay_intensity: float = 0.7,
    min_hold: float = 8.0,
    max_hold: float = 20.0,
    split_chance: float = 0.15,
    pip_chance: float = 0.10,
    seed: int | None = None,
    progress_callback=None,
) -> Path:
    """
    Build the drift composition. Returns the output Path.
    progress_callback(current, total) is called after each segment and at
    concat/audio-mix steps. total = len(segments) + 2.
    """
    video_files = get_video_files(videos)
    if not video_files:
        raise ValueError("No video files found.")

    audio_duration = ffprobe_duration(audio)

    segments = plan_segments(
        audio_duration, min_hold, max_hold,
        split_chance, pip_chance, seed
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("drift_cut_v*.mp4"))
    next_v = len(existing) + 1
    output_path = out_dir / f"drift_cut_v{next_v:02d}.mp4"

    grand_total = len(segments) + 2
    rng = random.Random(seed)

    temp_dir = Path(tempfile.mkdtemp(prefix='drift_cut_'))
    try:
        segment_files = []
        durations_by_video = {vf: ffprobe_duration(str(vf)) for vf in video_files}

        for i, seg in enumerate(segments):
            sat, crf, fps, loss_passes = decay_curve(seg['position'], decay_intensity)
            seg_path = temp_dir / f'seg_{i:04d}.mp4'

            if seg['type'] == 'hold':
                video = rng.choice(video_files)
                vid_dur = durations_by_video[video]
                clip_dur = seg['duration']
                start = rng.uniform(0, max(0, vid_dur - clip_dur))
                extract_clip(video, start, clip_dur, seg_path,
                             saturation=sat, fps=fps, crf=crf)
                if loss_passes > 0:
                    degraded = Path(str(seg_path) + '.degraded.mp4')
                    generation_loss(seg_path, degraded, passes=loss_passes)
                    degraded.replace(seg_path)

            elif seg['type'] == 'split':
                vids = rng.sample(video_files, min(2, len(video_files)))
                vid_a = vids[0]
                vid_b = vids[1] if len(vids) > 1 else vids[0]
                clip_dur = seg['duration']
                tmp_a = temp_dir / f'split_a_{i}.mp4'
                tmp_b = temp_dir / f'split_b_{i}.mp4'
                slow = rng.uniform(1.5, 2.5)
                start_a = rng.uniform(0, max(0, durations_by_video[vid_a] - clip_dur))
                needed_b = clip_dur / slow
                start_b = rng.uniform(0, max(0, durations_by_video[vid_b] - needed_b * 2))
                extract_clip(vid_a, start_a, clip_dur, tmp_a,
                             saturation=sat, fps=fps, crf=crf)
                extract_clip(vid_b, start_b, clip_dur * 2, tmp_b,
                             saturation=sat * 0.85, fps=fps, crf=crf)
                zoom = rng.uniform(1.2, 1.6)
                create_split_screen(tmp_a, tmp_b, seg_path, slow_factor=slow, zoom=zoom)
                if loss_passes > 0:
                    degraded = Path(str(seg_path) + '.degraded.mp4')
                    generation_loss(seg_path, degraded, passes=loss_passes)
                    degraded.replace(seg_path)

            elif seg['type'] == 'pip':
                vids = rng.sample(video_files, min(2, len(video_files)))
                vid_main = vids[0]
                vid_pip = vids[1] if len(vids) > 1 else vids[0]
                clip_dur = seg['duration']
                tmp_main = temp_dir / f'pip_main_{i}.mp4'
                tmp_pip  = temp_dir / f'pip_sub_{i}.mp4'
                start_main = rng.uniform(0, max(0, durations_by_video[vid_main] - clip_dur))
                start_pip  = rng.uniform(0, max(0, durations_by_video[vid_pip]  - clip_dur))
                extract_clip(vid_main, start_main, clip_dur, tmp_main,
                             saturation=sat, fps=fps, crf=crf)
                extract_clip(vid_pip, start_pip, clip_dur, tmp_pip,
                             saturation=sat * 0.7, fps=fps, crf=max(crf, 24))
                pip_scale = rng.uniform(0.18, 0.28)
                corner = rng.choice(['bottom_right', 'bottom_left', 'top_right', 'top_left'])
                create_pip(tmp_main, tmp_pip, seg_path, pip_scale=pip_scale, position=corner)
                if loss_passes > 0:
                    degraded = Path(str(seg_path) + '.degraded.mp4')
                    generation_loss(seg_path, degraded, passes=loss_passes)
                    degraded.replace(seg_path)

            segment_files.append(seg_path)
            if progress_callback:
                progress_callback(i + 1, grand_total)

        # Concatenate
        concat_file = temp_dir / 'concat.txt'
        concat_file.write_text('\n'.join(f"file '{s}'" for s in segment_files))
        concat_video = temp_dir / 'concat.mp4'
        subprocess.run([
            'ffmpeg', '-loglevel', 'warning',
            '-f', 'concat', '-safe', '0', '-i', str(concat_file),
            '-c', 'copy', '-y', str(concat_video)
        ], check=True)
        if progress_callback:
            progress_callback(grand_total - 1, grand_total)

        # Mix audio
        subprocess.run([
            'ffmpeg', '-loglevel', 'warning',
            '-i', str(concat_video), '-i', audio,
            '-c:v', 'copy',
            '-af', 'highpass=f=30,lowpass=f=16000,volume=0.85',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest', '-y', str(output_path)
        ], check=True)
        if progress_callback:
            progress_callback(grand_total, grand_total)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return output_path
