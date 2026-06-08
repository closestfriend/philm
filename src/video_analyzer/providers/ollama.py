"""Ollama provider: local frame-based analysis upgraded to real modes + schemas."""
from __future__ import annotations

import os
from pathlib import Path

from ..local import LocalConfig, _chat_json, extract_frames
from ..modes import AnalysisMode
from ..models import BaseAnalysisResult
from .base import VideoHandle


class OllamaProvider:
    name = "ollama"

    def __init__(self) -> None:
        self.config = LocalConfig(
            model=os.getenv("OLLAMA_MODEL", "qwen3-vl:4b"),
            num_frames=int(os.getenv("OLLAMA_FRAMES", "4")),
        )

    def prepare(self, video_path: Path, *, no_audio: bool = False) -> VideoHandle:
        frames = extract_frames(video_path, num_frames=self.config.num_frames)
        return VideoHandle(provider="ollama", payload={"frames": frames},
                           meta={"transport": "frames"})

    def analyze(self, handle: VideoHandle, mode: AnalysisMode,
                prompt_prefix: str = "") -> BaseAnalysisResult:
        raw = _chat_json(
            model=self.config.model,
            prompt=prompt_prefix + mode.prompt,
            image_paths=handle.payload["frames"],
            ollama_url=self.config.ollama_url,
            schema=mode.result_model.model_json_schema(),
            timeout=self.config.timeout,
        )
        return mode.result_model.model_validate_json(raw)

    def cleanup(self, handle: VideoHandle) -> None:
        for fr in handle.payload.get("frames", []):
            Path(fr).unlink(missing_ok=True)
