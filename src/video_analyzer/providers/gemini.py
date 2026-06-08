"""Gemini provider: thin adapter over the existing analyzer.py implementation."""
from __future__ import annotations

from pathlib import Path

from ..analyzer import (
    analyze_video,
    configure_genai,
    delete_video,
    upload_video,
)
from ..modes import AnalysisMode
from ..models import BaseAnalysisResult
from .base import VideoHandle


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        configure_genai()  # raises ValueError if GEMINI_API_KEY missing

    def prepare(self, video_path: Path, *, no_audio: bool = False) -> VideoHandle:
        file_obj = upload_video(video_path, no_audio=no_audio)
        return VideoHandle(provider="gemini", payload=file_obj,
                           meta={"transport": "native"})

    def analyze(self, handle: VideoHandle, mode: AnalysisMode,
                prompt_prefix: str = "") -> BaseAnalysisResult:
        return analyze_video(handle.payload, mode, prompt_prefix)

    def cleanup(self, handle: VideoHandle) -> None:
        delete_video(handle.payload)
