from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    from video_analyzer.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider()


def test_small_file_inlined(provider, tmp_path, monkeypatch):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00" * 1024)  # 1 KB, well under threshold
    handle = provider.prepare(f)
    assert handle.meta["transport"] == "native"
    assert handle.payload["kind"] == "video_url"
    assert handle.payload["data_url"].startswith("data:video/mp4;base64,")


def test_mpeg_mime_used_for_mpg(provider, tmp_path):
    f = tmp_path / "clip.mpg"
    f.write_bytes(b"\x00" * 1024)
    handle = provider.prepare(f)
    assert handle.payload["data_url"].startswith("data:video/mpeg;base64,")


def test_oversize_triggers_compress(provider, tmp_path, monkeypatch):
    # Threshold ~1048 bytes: source (2048) is over it → compress; compressed (16) is
    # under it → inline as native. Exercises the genuine compress→native path.
    monkeypatch.setenv("OPENROUTER_INLINE_MAX_MB", "0.001")
    f = tmp_path / "big.mp4"
    f.write_bytes(b"\x00" * 2048)
    small = tmp_path / "compressed.mp4"
    small.write_bytes(b"\x00" * 16)
    with patch("video_analyzer.providers.openrouter.OpenRouterProvider._compress",
               return_value=small) as comp:
        handle = provider.prepare(f)
        comp.assert_called_once()
        assert handle.meta["transport"] == "native"


def test_frame_fallback_when_still_too_big(provider, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_INLINE_MAX_MB", "0")
    f = tmp_path / "huge.mp4"
    f.write_bytes(b"\x00" * 4096)
    # compress returns something still over the 0 MB threshold
    with patch("video_analyzer.providers.openrouter.OpenRouterProvider._compress",
               return_value=f), \
         patch("video_analyzer.providers.openrouter.extract_frames",
               return_value=[tmp_path / "f0.jpg"]) as ef:
        (tmp_path / "f0.jpg").write_bytes(b"\xff" * 8)
        handle = provider.prepare(f)
        ef.assert_called_once()
        assert handle.meta["transport"] == "frames"
        assert handle.payload["kind"] == "frames"


def test_openrouter_cleanup_removes_frame_dir(provider, tmp_path):
    from video_analyzer.providers.base import VideoHandle
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    (frame_dir / "f0.jpg").write_bytes(b"\xff")
    handle = VideoHandle(provider="openrouter",
                         payload={"kind": "frames", "image_urls": ["data:image/jpeg;base64,AA"]},
                         meta={"transport": "frames", "temp_files": [], "frame_dir": str(frame_dir)})
    provider.cleanup(handle)
    assert not frame_dir.exists()
