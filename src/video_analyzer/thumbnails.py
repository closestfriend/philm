"""Thumbnail extraction via ffmpeg."""

import subprocess
from pathlib import Path

THUMB_DIR = Path.home() / ".vanalyze" / "thumbnails"


def extract_thumbnail(video_path: str | Path, video_id: int) -> Path | None:
    """Extract a single frame at 3s into the video as a JPEG."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out_path = THUMB_DIR / f"{video_id}.jpg"
    if out_path.exists():
        return out_path
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", "00:00:03",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "3",
            str(out_path),
        ], capture_output=True, timeout=30)
        return out_path if out_path.exists() else None
    except Exception:
        return None
