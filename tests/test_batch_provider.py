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


def test_run_batch_passes_provider_name(monkeypatch, tmp_path):
    from unittest.mock import MagicMock, patch
    import video_analyzer.batch as batch

    called = {}

    def fake_get_provider(name=None):
        called["name"] = name
        p = MagicMock()
        p.name = "openrouter"
        p.prepare.return_value = object()
        p.analyze.return_value.model_dump.return_value = {"ok": True}
        return p

    # one fake video
    vid = tmp_path / "a.mp4"
    vid.write_bytes(b"\x00")
    with patch("video_analyzer.batch.find_videos", return_value=[vid]), \
         patch("video_analyzer.providers.get_provider", side_effect=fake_get_provider):
        batch.run_batch(folder=tmp_path, modes=["captions"],
                        output_dir=tmp_path / "out", provider_name="openrouter")
    assert called["name"] == "openrouter"
