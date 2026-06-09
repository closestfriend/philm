import os
from pathlib import Path

import pytest

from video_analyzer.modes import get_mode
from video_analyzer.providers import get_provider

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.mp4"


@pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"),
                    reason="no OPENROUTER_API_KEY")
def test_openrouter_video_plus_schema_works():
    """Empirically validates: native video + json_schema together on OpenRouter."""
    provider = get_provider("openrouter")
    mode = get_mode("captions")
    handle = provider.prepare(FIXTURE)
    try:
        result = provider.analyze(handle, mode)
        assert isinstance(result, mode.result_model)
    finally:
        provider.cleanup(handle)


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="no GEMINI_API_KEY")
def test_gemini_still_works():
    provider = get_provider("gemini")
    mode = get_mode("captions")
    handle = provider.prepare(FIXTURE)
    try:
        result = provider.analyze(handle, mode)
        assert isinstance(result, mode.result_model)
    finally:
        provider.cleanup(handle)
