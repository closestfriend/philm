from unittest.mock import MagicMock, patch

import pytest

from video_analyzer.modes import get_mode
from video_analyzer.providers.base import VideoHandle


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    from video_analyzer.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider()


def _resp(content: str):
    m = MagicMock()
    m.json.return_value = {"choices": [{"message": {"content": content}}]}
    m.raise_for_status.return_value = None
    return m


def test_request_payload_shape(provider):
    mode = get_mode("captions")
    handle = VideoHandle(provider="openrouter",
                         payload={"kind": "video_url", "data_url": "data:video/mp4;base64,AA"},
                         meta={"transport": "native"})
    valid = mode.result_model(video_description="x", timecodes=[]).model_dump_json()
    with patch("video_analyzer.providers.openrouter.requests.post",
               return_value=_resp(valid)) as post:
        provider.analyze(handle, mode, "prefix ")
        body = post.call_args.kwargs["json"]
        assert body["model"] == provider.model
        assert body["stream"] is False
        assert body["provider"]["require_parameters"] is True
        assert body["plugins"] == [{"id": "response-healing"}]
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        content = body["messages"][1]["content"]
        assert content[0]["type"] == "text" and content[0]["text"].startswith("prefix ")
        assert content[1]["type"] == "video_url"
        assert content[1]["video_url"]["url"].startswith("data:video/mp4;base64,")
        assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer x"


def test_frames_payload_uses_image_url(provider):
    mode = get_mode("captions")
    handle = VideoHandle(provider="openrouter",
                         payload={"kind": "frames", "image_urls": ["data:image/jpeg;base64,AA"]},
                         meta={"transport": "frames"})
    valid = mode.result_model(video_description="x", timecodes=[]).model_dump_json()
    with patch("video_analyzer.providers.openrouter.requests.post",
               return_value=_resp(valid)) as post:
        provider.analyze(handle, mode)
        content = post.call_args.kwargs["json"]["messages"][1]["content"]
        assert content[1]["type"] == "image_url"


def test_returns_validated_model(provider):
    mode = get_mode("captions")
    handle = VideoHandle(provider="openrouter",
                         payload={"kind": "video_url", "data_url": "data:video/mp4;base64,AA"},
                         meta={"transport": "native"})
    valid = mode.result_model(video_description="x", timecodes=[]).model_dump_json()
    with patch("video_analyzer.providers.openrouter.requests.post", return_value=_resp(valid)):
        result = provider.analyze(handle, mode)
        assert isinstance(result, mode.result_model)


def test_retries_then_succeeds(provider):
    mode = get_mode("captions")
    handle = VideoHandle(provider="openrouter",
                         payload={"kind": "video_url", "data_url": "data:video/mp4;base64,AA"},
                         meta={"transport": "native"})
    valid = mode.result_model(video_description="x", timecodes=[]).model_dump_json()
    responses = [_resp("not json at all"), _resp(valid)]
    with patch("video_analyzer.providers.openrouter.requests.post",
               side_effect=responses) as post:
        result = provider.analyze(handle, mode)
        assert isinstance(result, mode.result_model)
        assert post.call_count == 2


def test_raises_after_max_retries(provider):
    mode = get_mode("captions")
    handle = VideoHandle(provider="openrouter",
                         payload={"kind": "video_url", "data_url": "data:video/mp4;base64,AA"},
                         meta={"transport": "native"})
    with patch("video_analyzer.providers.openrouter.requests.post",
               return_value=_resp("still not json")):
        with pytest.raises(RuntimeError, match="Failed to parse"):
            provider.analyze(handle, mode)
