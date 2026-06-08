"""OpenRouter provider: native video_url transport + structured-output requests."""
from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from ..analyzer import strip_audio
from ..local import extract_frames
from ..modes import AnalysisMode
from ..models import BaseAnalysisResult
from .base import VideoHandle
from .schema import pydantic_to_strict_schema

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"
SYSTEM_INSTRUCTION = (
    "You are a sophisticated video analysis system. When given a video and "
    "analytical framework, provide structured insights following the schema "
    "precisely. Be theoretically rigorous but practically clear."
)

_MIME_BY_EXT = {
    ".mp4": "video/mp4",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    ".mov": "video/mov",
    ".webm": "video/webm",
}


def _inline_threshold_bytes() -> int:
    # Empirical, configurable knob — NOT an OpenRouter-documented limit.
    mb = float(os.getenv("OPENROUTER_INLINE_MAX_MB", "25"))
    return int(mb * 1024 * 1024)


def _data_url(path: Path) -> str:
    mime = _MIME_BY_EXT.get(path.suffix.lower(), "video/mp4")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found. Set it in .env.")
        self.model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)

    # -- transport -------------------------------------------------------
    def _compress(self, path: Path) -> Path:
        """Downscale to 720p + cap bitrate to shrink the base64 payload."""
        fd, out = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        out_path = Path(out)
        print("  Compressing for OpenRouter...", file=sys.stderr, flush=True)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(path),
             "-vf", "scale='min(1280,iw)':-2",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
             "-c:a", "aac", "-b:a", "96k", str(out_path)],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            out_path.unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg compress failed: {result.stderr[-500:]}")
        return out_path

    def prepare(self, video_path: Path, *, no_audio: bool = False) -> VideoHandle:
        threshold = _inline_threshold_bytes()
        temp_files: list[Path] = []
        source = video_path
        if no_audio:
            source = strip_audio(video_path)
            temp_files.append(source)

        if source.stat().st_size <= threshold:
            return VideoHandle(
                provider="openrouter",
                payload={"kind": "video_url", "data_url": _data_url(source)},
                meta={"transport": "native", "temp_files": [str(p) for p in temp_files]},
            )

        compressed = self._compress(source)
        temp_files.append(compressed)
        if compressed.stat().st_size <= threshold:
            return VideoHandle(
                provider="openrouter",
                payload={"kind": "video_url", "data_url": _data_url(compressed)},
                meta={"transport": "native", "temp_files": [str(p) for p in temp_files]},
            )

        # Last resort: frame sampling (degraded — warn loudly).
        n = int(os.getenv("OPENROUTER_FALLBACK_FRAMES", "12"))
        print(
            f"  WARNING: {video_path.name} too large even after compression; "
            f"falling back to {n}-frame sampling (temporal fidelity lost).",
            file=sys.stderr, flush=True,
        )
        frames = extract_frames(compressed, num_frames=n)
        frame_urls = []
        for fr in frames:
            b64 = base64.b64encode(Path(fr).read_bytes()).decode("ascii")
            frame_urls.append(f"data:image/jpeg;base64,{b64}")
        return VideoHandle(
            provider="openrouter",
            payload={"kind": "frames", "image_urls": frame_urls},
            meta={"transport": "frames", "temp_files": [str(p) for p in temp_files]},
        )

    def cleanup(self, handle: VideoHandle) -> None:
        for p in handle.meta.get("temp_files", []):
            Path(p).unlink(missing_ok=True)

    # -- request ---------------------------------------------------------
    def _media_part(self, handle: VideoHandle) -> dict | list:
        payload = handle.payload
        if payload["kind"] == "video_url":
            return {"type": "video_url", "video_url": {"url": payload["data_url"]}}
        return [{"type": "image_url", "image_url": {"url": u}}
                for u in payload["image_urls"]]

    def _build_body(self, handle: VideoHandle, mode: AnalysisMode,
                    prompt_prefix: str) -> dict:
        media = self._media_part(handle)
        media_parts = media if isinstance(media, list) else [media]
        return {
            "model": self.model,
            "stream": False,
            "temperature": 0.5,
            "provider": {"require_parameters": True},
            "plugins": [{"id": "response-healing"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": mode.name.replace("-", "_"),
                    "strict": True,
                    "schema": pydantic_to_strict_schema(mode.result_model),
                },
            },
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt_prefix + mode.prompt},
                    *media_parts,
                ]},
            ],
        }

    def analyze(self, handle: VideoHandle, mode: AnalysisMode,
                prompt_prefix: str = "") -> BaseAnalysisResult:
        body = self._build_body(handle, mode, prompt_prefix)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/philm",
            "X-Title": "philm",
        }
        max_retries = int(os.getenv("OPENROUTER_MAX_RETRIES", "2"))
        last_error: Exception | None = None
        raw = ""
        for attempt in range(max_retries + 1):
            print(f"Analyzing with mode: {mode.name} (OpenRouter, attempt "
                  f"{attempt + 1})...", file=sys.stderr, flush=True)
            resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=300)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            try:
                return mode.result_model.model_validate_json(raw)
            except Exception as exc:  # schema-adherence failure healing can't fix
                last_error = exc
        raise RuntimeError(
            f"Failed to parse OpenRouter response after {max_retries + 1} attempts: "
            f"{last_error}\n\nRaw response: {raw}"
        )
