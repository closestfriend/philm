# src/video_analyzer/providers/base.py
"""Provider interface for video analysis backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..modes import AnalysisMode
from ..models import BaseAnalysisResult


@dataclass
class VideoHandle:
    """Opaque payload returned by Provider.prepare(), consumed by analyze()/cleanup()."""
    provider: str
    payload: Any
    meta: dict = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    name: str

    def prepare(self, video_path: Path, *, no_audio: bool = False) -> VideoHandle: ...

    def analyze(
        self, handle: VideoHandle, mode: AnalysisMode, prompt_prefix: str = ""
    ) -> BaseAnalysisResult: ...

    def cleanup(self, handle: VideoHandle) -> None: ...
