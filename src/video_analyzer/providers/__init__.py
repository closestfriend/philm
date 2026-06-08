# src/video_analyzer/providers/__init__.py
"""Provider registry. Resolution: explicit arg > VANALYZE_PROVIDER env > 'gemini'."""
from __future__ import annotations

import os

from .base import Provider, VideoHandle

__all__ = ["Provider", "VideoHandle", "get_provider"]


def get_provider(name: str | None = None) -> Provider:
    name = (name or os.getenv("VANALYZE_PROVIDER") or "gemini").lower()
    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider()
    if name == "openrouter":
        from .openrouter import OpenRouterProvider
        return OpenRouterProvider()
    if name in ("ollama", "local"):
        from .ollama import OllamaProvider
        return OllamaProvider()
    raise ValueError(
        f"Unknown provider: {name!r}. Choose gemini | openrouter | ollama."
    )
