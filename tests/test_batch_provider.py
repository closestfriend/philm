from unittest.mock import MagicMock, patch

from video_analyzer.batch import analyze_video_multi_mode


def test_multi_mode_uses_injected_provider():
    provider = MagicMock()
    provider.analyze.return_value.model_dump.return_value = {"ok": True}
    handle = object()
    results = analyze_video_multi_mode(handle, ["captions", "paragraph"],
                                       provider=provider)
    assert set(results.keys()) == {"captions", "paragraph"}
    assert provider.analyze.call_count == 2
    assert results["captions"] == {"ok": True}
