from pathlib import Path
from unittest.mock import MagicMock, patch

from video_analyzer.modes import get_mode
from video_analyzer.providers.base import VideoHandle


def test_ollama_prepare_extracts_frames(monkeypatch, tmp_path):
    from video_analyzer.providers.ollama import OllamaProvider
    p = OllamaProvider()
    frames = [tmp_path / "f0.jpg"]
    (tmp_path / "f0.jpg").write_bytes(b"\xff")
    with patch("video_analyzer.providers.ollama.extract_frames", return_value=frames):
        handle = p.prepare(Path("/tmp/x.mp4"))
        assert handle.provider == "ollama"
        assert handle.meta["transport"] == "frames"
        assert handle.payload["frames"] == frames


def test_ollama_analyze_validates(monkeypatch, tmp_path):
    from video_analyzer.providers.ollama import OllamaProvider
    mode = get_mode("captions")
    valid = mode.result_model(video_description="x", timecodes=[]).model_dump_json()
    handle = VideoHandle(provider="ollama",
                         payload={"frames": [tmp_path / "f0.jpg"]},
                         meta={"transport": "frames"})
    (tmp_path / "f0.jpg").write_bytes(b"\xff")
    with patch("video_analyzer.providers.ollama._chat_json", return_value=valid):
        result = OllamaProvider().analyze(handle, mode)
        assert isinstance(result, mode.result_model)
