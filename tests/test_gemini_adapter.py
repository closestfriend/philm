from pathlib import Path
from unittest.mock import MagicMock, patch

from video_analyzer.providers.base import VideoHandle


def test_gemini_adapter_lifecycle(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    with patch("video_analyzer.providers.gemini.configure_genai"), \
         patch("video_analyzer.providers.gemini.upload_video") as up, \
         patch("video_analyzer.providers.gemini.analyze_video") as an, \
         patch("video_analyzer.providers.gemini.delete_video") as dl:
        from video_analyzer.providers.gemini import GeminiProvider
        up.return_value = "FILEOBJ"
        an.return_value = "RESULT"
        p = GeminiProvider()
        assert p.name == "gemini"

        handle = p.prepare(Path("/tmp/x.mp4"), no_audio=True)
        assert isinstance(handle, VideoHandle)
        assert handle.payload == "FILEOBJ"
        assert handle.meta["transport"] == "native"
        up.assert_called_once_with(Path("/tmp/x.mp4"), no_audio=True)

        mode = MagicMock()
        assert p.analyze(handle, mode, "prefix ") == "RESULT"
        an.assert_called_once_with("FILEOBJ", mode, "prefix ")

        p.cleanup(handle)
        dl.assert_called_once_with("FILEOBJ")
