# tests/test_media_utils.py
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import media_utils  # noqa: E402


@pytest.fixture
def sample_clip(tmp_path):
    """A real 2-second 640x480 H.264 clip generated with ffmpeg lavfi."""
    out = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=size=640x480:rate=30:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_ffprobe_duration(sample_clip):
    assert media_utils.ffprobe_duration(sample_clip) == pytest.approx(2.0, abs=0.2)


def test_ffprobe_resolution(sample_clip):
    assert media_utils.ffprobe_resolution(sample_clip) == (640, 480)


def test_get_video_files_filters_by_extension(tmp_path, sample_clip):
    (tmp_path / "notes.txt").write_text("not a video")
    files = media_utils.get_video_files(tmp_path)
    assert [f.name for f in files] == ["clip.mp4"]


def test_get_video_files_accepts_comma_list(sample_clip):
    files = media_utils.get_video_files(f"{sample_clip},{sample_clip}")
    assert len(files) == 2 and all(isinstance(f, Path) for f in files)


def test_normalize_filter_default_1080p():
    assert media_utils.normalize_filter() == (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    )
