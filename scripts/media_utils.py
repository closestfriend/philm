# scripts/media_utils.py
"""media_utils.py — shared ffprobe/ffmpeg helpers for the montage scripts.

Single source of truth for clip probing, video-file discovery, and the canonical
1920x1080 normalize (scale+pad) filter. Previously copy-pasted into drift_core.py,
drift_cut.py, ez_mv_core.py, and carti_cut.py.

Relocates to shared/media.py during the video-praxis rename phase.
"""

import json
import subprocess
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mov", ".mp4", ".avi", ".mkv", ".mpg", ".mpeg", ".mts", ".m4v", ".mxf", ".webm",
}


def ffprobe_duration(path) -> float:
    """Return container duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def ffprobe_resolution(path) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def get_video_files(path) -> list[Path]:
    """A directory -> sorted video files within it; otherwise a comma-separated list of paths."""
    p = Path(path)
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS)
    return [Path(v.strip()) for v in str(path).split(",")]


def normalize_filter(width: int = 1920, height: int = 1080) -> str:
    """Canonical scale-to-fit + pad-to-frame filter string."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
