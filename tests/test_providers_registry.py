import pytest
from video_analyzer.providers import get_provider
from video_analyzer.providers.base import Provider, VideoHandle


def test_default_is_gemini(monkeypatch):
    monkeypatch.delenv("VANALYZE_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")  # GeminiProvider validates key on init
    assert get_provider().name == "gemini"


def test_env_selects_provider(monkeypatch):
    monkeypatch.setenv("VANALYZE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    assert get_provider().name == "openrouter"


def test_explicit_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("VANALYZE_PROVIDER", "openrouter")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert get_provider("gemini").name == "gemini"


def test_local_is_alias_for_ollama():
    assert get_provider("local").name == "ollama"


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("bogus")


def test_videohandle_shape():
    h = VideoHandle(provider="gemini", payload=object(), meta={"transport": "native"})
    assert h.provider == "gemini" and h.meta["transport"] == "native"
