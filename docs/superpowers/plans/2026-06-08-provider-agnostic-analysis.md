# Provider-Agnostic Video Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `philm` run video analysis through Gemini-direct (default), OpenRouter (opt-in, native `video_url`), or Ollama, all behind one `Provider` interface selectable by `--provider`.

**Architecture:** A `Provider` Protocol with a `prepare → analyze → cleanup` lifecycle ("prepare once, analyze many"). Gemini and Ollama get thin **adapters** wrapping the existing `analyzer.py` / `local.py` modules (lower-risk than relocating bodies). OpenRouter is new code: base64 `video_url` transport (with compress / frame-sample fallbacks), `strict` json_schema structured output hardened by `require_parameters`, the response-healing plugin, and a Pydantic validate+retry loop. A registry (`get_provider`) resolves `--provider` flag → `VANALYZE_PROVIDER` env → `gemini`.

**Tech Stack:** Python 3, Typer, Pydantic v2, `requests`, ffmpeg, pytest. Spec: `docs/superpowers/specs/2026-06-08-provider-agnostic-analysis-design.md`.

**Deviation from spec §7 (deliberate):** `analyzer.py` and `local.py` are NOT gutted into `providers/`. They stay as the Gemini/Ollama *implementations*; `providers/gemini.py` and `providers/ollama.py` are adapters that import and wrap them. This delivers the same abstraction with minimal churn and no shim risk. All other spec sections stand.

---

## File Structure

```
src/video_analyzer/
  providers/
    __init__.py      # CREATE: registry + get_provider()
    base.py          # CREATE: VideoHandle dataclass + Provider Protocol
    schema.py        # CREATE: pydantic_to_strict_schema()
    gemini.py        # CREATE: GeminiProvider (wraps analyzer.py)
    openrouter.py    # CREATE: OpenRouterProvider (new transport + request)
    ollama.py        # CREATE: OllamaProvider (wraps + upgrades local.py)
  analyzer.py        # UNCHANGED (Gemini implementation)
  local.py           # MODIFY: expose reusable helpers (no behavior change)
  batch.py           # MODIFY: route through get_provider()
  cli.py             # MODIFY: --provider, generalize --model, --local alias
  archive_cli.py     # MODIFY: route through get_provider()
tests/
  test_providers_registry.py     # CREATE
  test_schema_adapter.py         # CREATE
  test_openrouter_transport.py   # CREATE
  test_openrouter_analyze.py     # CREATE
  test_gemini_adapter.py         # CREATE
  test_integration_smoke.py      # CREATE (auto-skip without keys)
  fixtures/tiny.mp4              # CREATE (≈1s clip)
pyproject.toml      # MODIFY: declare requests
```

---

## Task 1: Declare `requests` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, inside the `dependencies = [ ... ]` list, add a line after `"python-dotenv>=1.0.0",`:

```toml
    "requests>=2.31",
```

- [ ] **Step 2: Sync and verify import**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2 && uv sync && uv run python -c "import requests; print(requests.__version__)"`
Expected: prints a version ≥ 2.31, no error.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: declare requests dependency (used by providers + local)"
```

---

## Task 2: Provider interface + registry

**Files:**
- Create: `src/video_analyzer/providers/__init__.py`
- Create: `src/video_analyzer/providers/base.py`
- Test: `tests/test_providers_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_providers_registry.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2 && uv run pytest tests/test_providers_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: video_analyzer.providers`.

- [ ] **Step 3: Create `base.py`**

```python
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
```

- [ ] **Step 4: Create `__init__.py` registry**

```python
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
```

> Note: `test_default_is_gemini`, `test_env_selects_provider`, `test_explicit_arg_overrides_env`, and `test_local_is_alias_for_ollama` depend on the provider classes from Tasks 3–7. They will pass once those exist. To unblock this task now, the registry + base + unknown/handle tests must pass; the provider-construction tests are expected to error until their tasks land — mark them xfail temporarily:

Add at the top of the four construction-dependent tests the decorator:
```python
@pytest.mark.xfail(reason="provider class lands in a later task", raises=Exception, strict=False)
```
Remove these xfail markers in Task 8 Step 1.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_providers_registry.py -v`
Expected: `test_unknown_provider_raises` and `test_videohandle_shape` PASS; the four xfail tests report `xfail`.

- [ ] **Step 6: Commit**

```bash
git add src/video_analyzer/providers/__init__.py src/video_analyzer/providers/base.py tests/test_providers_registry.py
git commit -m "feat(providers): add Provider interface + get_provider registry"
```

---

## Task 3: Strict JSON-schema adapter

**Files:**
- Create: `src/video_analyzer/providers/schema.py`
- Test: `tests/test_schema_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema_adapter.py
from video_analyzer.providers.schema import pydantic_to_strict_schema
from video_analyzer.models import SizzleResult


def _walk_objects(node):
    """Yield every object-typed subschema (including under $defs)."""
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for v in node.values():
            yield from _walk_objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_objects(v)


def test_every_object_is_strict():
    schema = pydantic_to_strict_schema(SizzleResult)
    objs = list(_walk_objects(schema))
    assert objs, "expected at least one object schema"
    for obj in objs:
        assert obj.get("additionalProperties") is False
        assert set(obj["required"]) == set(obj.get("properties", {}).keys())


def test_defs_are_strictified():
    schema = pydantic_to_strict_schema(SizzleResult)
    # SizzleResult nests per-moment objects in $defs
    assert "$defs" in schema
    for d in schema["$defs"].values():
        if d.get("type") == "object":
            assert d["additionalProperties"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schema_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: ...providers.schema`.

- [ ] **Step 3: Implement the adapter**

```python
# src/video_analyzer/providers/schema.py
"""Convert Pydantic JSON schemas to OpenAI/OpenRouter strict-mode schemas.

strict:true requires every object to set additionalProperties:false and list
all of its properties in `required`. Pydantic's model_json_schema() does neither.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _strictify(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            props = node.get("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(props.keys())
            for sub in props.values():
                _strictify(sub)
        if isinstance(node.get("items"), dict):
            _strictify(node["items"])
        for combinator in ("anyOf", "oneOf", "allOf"):
            for sub in node.get(combinator, []):
                _strictify(sub)
    elif isinstance(node, list):
        for sub in node:
            _strictify(sub)


def pydantic_to_strict_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    _strictify(schema)
    for definition in schema.get("$defs", {}).values():
        _strictify(definition)
    return schema
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_schema_adapter.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/video_analyzer/providers/schema.py tests/test_schema_adapter.py
git commit -m "feat(providers): strict json-schema adapter for structured outputs"
```

---

## Task 4: Gemini adapter

**Files:**
- Create: `src/video_analyzer/providers/gemini.py`
- Test: `tests/test_gemini_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gemini_adapter.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from video_analyzer.providers.base import VideoHandle


def test_gemini_adapter_lifecycle(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    with patch("video_analyzer.providers.gemini.configure_genai"), \
         patch("video_analyzer.providers.gemini.upload_video") as up, \
         patch("video_analyzer.providers.gemini.analyze_video") as an, \
         patch("video_analyzer.providers.gemini.delete_video") as dl:
        from video_analyzer.providers.gemini import GeminiProvider
        up.return_value = "FILEOBJ"
        an.return_value = "RESULT"
        p = GeminiProvider()
        assert p.name == "gemini"

        handle = p.prepare(Path("/tmp/x.mp4"), no_audio=True)
        assert isinstance(handle, VideoHandle)
        assert handle.payload == "FILEOBJ"
        assert handle.meta["transport"] == "native"
        up.assert_called_once_with(Path("/tmp/x.mp4"), no_audio=True)

        mode = MagicMock()
        assert p.analyze(handle, mode, "prefix ") == "RESULT"
        an.assert_called_once_with("FILEOBJ", mode, "prefix ")

        p.cleanup(handle)
        dl.assert_called_once_with("FILEOBJ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gemini_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: ...providers.gemini`.

- [ ] **Step 3: Implement the adapter**

```python
# src/video_analyzer/providers/gemini.py
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_gemini_adapter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/video_analyzer/providers/gemini.py tests/test_gemini_adapter.py
git commit -m "feat(providers): Gemini adapter behind Provider interface"
```

---

## Task 5: OpenRouter transport (`prepare`)

**Files:**
- Modify: `src/video_analyzer/local.py` (expose `extract_frames` — already top-level; no change needed beyond confirming import works)
- Create: `src/video_analyzer/providers/openrouter.py` (partial — transport only)
- Test: `tests/test_openrouter_transport.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_openrouter_transport.py
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    from video_analyzer.providers.openrouter import OpenRouterProvider
    return OpenRouterProvider()


def test_small_file_inlined(provider, tmp_path, monkeypatch):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00" * 1024)  # 1 KB, well under threshold
    handle = provider.prepare(f)
    assert handle.meta["transport"] == "native"
    assert handle.payload["kind"] == "video_url"
    assert handle.payload["data_url"].startswith("data:video/mp4;base64,")


def test_mpeg_mime_used_for_mpg(provider, tmp_path):
    f = tmp_path / "clip.mpg"
    f.write_bytes(b"\x00" * 1024)
    handle = provider.prepare(f)
    assert handle.payload["data_url"].startswith("data:video/mpeg;base64,")


def test_oversize_triggers_compress(provider, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_INLINE_MAX_MB", "0")  # force "over threshold"
    f = tmp_path / "big.mp4"
    f.write_bytes(b"\x00" * 2048)
    small = tmp_path / "compressed.mp4"
    small.write_bytes(b"\x00" * 16)
    with patch("video_analyzer.providers.openrouter.OpenRouterProvider._compress",
               return_value=small) as comp:
        handle = provider.prepare(f)
        comp.assert_called_once()
        assert handle.meta["transport"] == "native"


def test_frame_fallback_when_still_too_big(provider, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_INLINE_MAX_MB", "0")
    f = tmp_path / "huge.mp4"
    f.write_bytes(b"\x00" * 4096)
    # compress returns something still over the 0 MB threshold
    with patch("video_analyzer.providers.openrouter.OpenRouterProvider._compress",
               return_value=f), \
         patch("video_analyzer.providers.openrouter.extract_frames",
               return_value=[tmp_path / "f0.jpg"]) as ef:
        (tmp_path / "f0.jpg").write_bytes(b"\xff" * 8)
        handle = provider.prepare(f)
        ef.assert_called_once()
        assert handle.meta["transport"] == "frames"
        assert handle.payload["kind"] == "frames"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_openrouter_transport.py -v`
Expected: FAIL — `ModuleNotFoundError: ...providers.openrouter`.

- [ ] **Step 3: Implement the transport half of the provider**

```python
# src/video_analyzer/providers/openrouter.py
"""OpenRouter provider: native video_url transport + structured-output requests."""
from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ..analyzer import strip_audio
from ..local import extract_frames
from .base import VideoHandle

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"

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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_openrouter_transport.py -v`
Expected: PASS (all four).

- [ ] **Step 5: Commit**

```bash
git add src/video_analyzer/providers/openrouter.py tests/test_openrouter_transport.py
git commit -m "feat(openrouter): native video_url transport with compress/frame fallback"
```

---

## Task 6: OpenRouter `analyze` (structured output + healing + retry)

**Files:**
- Modify: `src/video_analyzer/providers/openrouter.py` (add `analyze` + request builder)
- Test: `tests/test_openrouter_analyze.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_openrouter_analyze.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_openrouter_analyze.py -v`
Expected: FAIL — `AttributeError: 'OpenRouterProvider' object has no attribute 'analyze'`.

- [ ] **Step 3: Add imports, request builder, and `analyze`**

At the top of `src/video_analyzer/providers/openrouter.py`, add to the imports:

```python
import requests

from ..modes import AnalysisMode
from ..models import BaseAnalysisResult
from .schema import pydantic_to_strict_schema
```

Add this module-level constant near `DEFAULT_MODEL`:

```python
SYSTEM_INSTRUCTION = (
    "You are a sophisticated video analysis system. When given a video and "
    "analytical framework, provide structured insights following the schema "
    "precisely. Be theoretically rigorous but practically clear."
)
```

Add these methods to `OpenRouterProvider`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_openrouter_analyze.py -v`
Expected: PASS (all five).

- [ ] **Step 5: Commit**

```bash
git add src/video_analyzer/providers/openrouter.py tests/test_openrouter_analyze.py
git commit -m "feat(openrouter): structured-output analyze with healing + validate/retry"
```

---

## Task 7: Ollama adapter (modes + structured output)

**Files:**
- Modify: `src/video_analyzer/local.py` (add a structured analyze helper; keep existing funcs)
- Create: `src/video_analyzer/providers/ollama.py`
- Test: `tests/test_ollama_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ollama_adapter.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from video_analyzer.modes import get_mode
from video_analyzer.providers.base import VideoHandle


def test_ollama_prepare_extracts_frames(monkeypatch, tmp_path):
    from video_analyzer.providers.ollama import OllamaProvider
    p = OllamaProvider()
    frames = [tmp_path / "f0.jpg"]
    (tmp_path / "f0.jpg").write_bytes(b"\xff")
    with patch("video_analyzer.providers.ollama.extract_frames", return_value=frames):
        handle = p.prepare(Path("/tmp/x.mp4"))
        assert handle.provider == "ollama"
        assert handle.meta["transport"] == "frames"
        assert handle.payload["frames"] == frames


def test_ollama_analyze_validates(monkeypatch, tmp_path):
    from video_analyzer.providers.ollama import OllamaProvider
    mode = get_mode("captions")
    valid = mode.result_model(video_description="x", timecodes=[]).model_dump_json()
    handle = VideoHandle(provider="ollama",
                         payload={"frames": [tmp_path / "f0.jpg"]},
                         meta={"transport": "frames"})
    (tmp_path / "f0.jpg").write_bytes(b"\xff")
    with patch("video_analyzer.providers.ollama._chat_json", return_value=valid):
        result = OllamaProvider().analyze(handle, mode)
        assert isinstance(result, mode.result_model)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ollama_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: ...providers.ollama`.

- [ ] **Step 3: Add a structured chat helper to `local.py`**

Append to `src/video_analyzer/local.py`:

```python
def _chat_json(model: str, prompt: str, image_paths, ollama_url: str,
               schema: dict, timeout: int = 180) -> str:
    """POST a vision chat request to Ollama with JSON-schema-constrained output.

    Returns the raw JSON string from the model's message content.
    """
    import base64 as _b64

    images = [_b64.b64encode(Path(p).read_bytes()).decode("ascii") for p in image_paths]
    resp = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": schema,  # Ollama accepts a JSON schema object for structured output
            "messages": [{"role": "user", "content": prompt, "images": images}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
```

- [ ] **Step 4: Implement the Ollama provider**

```python
# src/video_analyzer/providers/ollama.py
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_ollama_adapter.py -v`
Expected: PASS (both).

- [ ] **Step 6: Commit**

```bash
git add src/video_analyzer/local.py src/video_analyzer/providers/ollama.py tests/test_ollama_adapter.py
git commit -m "feat(ollama): provider adapter with real modes + structured output"
```

---

## Task 8: Route batch + single-clip through providers; wire CLI

**Files:**
- Modify: `src/video_analyzer/batch.py:46-67` (`analyze_video_multi_mode`), `:146-196` (per-video loop in `run_batch`)
- Modify: `src/video_analyzer/cli.py` (add `--provider`; generalize `--model`; `--local` alias; route paths through provider)
- Modify: `tests/test_providers_registry.py` (remove xfail markers from Task 2)
- Test: `tests/test_batch_provider.py`

- [ ] **Step 1: Remove the xfail markers**

In `tests/test_providers_registry.py`, delete the four `@pytest.mark.xfail(...)` lines added in Task 2. Run:
`uv run pytest tests/test_providers_registry.py -v` → Expected: all six PASS (provider classes now exist; keys are set via monkeypatch).

- [ ] **Step 2: Write the failing batch test**

```python
# tests/test_batch_provider.py
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_batch_provider.py -v`
Expected: FAIL — `analyze_video_multi_mode() got an unexpected keyword argument 'provider'`.

- [ ] **Step 4: Update `analyze_video_multi_mode`**

Replace the body of `analyze_video_multi_mode` in `src/video_analyzer/batch.py` (lines ~46–67) with:

```python
def analyze_video_multi_mode(
    handle: Any,
    modes: list[str],
    technical_context: str = "",
    provider: Any = None,
) -> dict[str, Any]:
    """Run multiple analysis modes on one prepared video handle."""
    from .providers import get_provider
    if provider is None:
        provider = get_provider()

    results = {}
    for mode_name in modes:
        try:
            mode = get_mode(mode_name)
            result = provider.analyze(handle, mode, technical_context)
            results[mode_name] = result.model_dump()
        except Exception as e:
            console.print(f"  [red]Error in {mode_name}:[/red] {e}")
            results[mode_name] = {"error": str(e)}
    return results
```

Update the top import in `batch.py` — remove `analyze_video` from `from .analyzer import ...` (keep `VIDEO_MIME_TYPES`):

```python
from .analyzer import VIDEO_MIME_TYPES
```

- [ ] **Step 5: Update `run_batch` per-video loop**

In `run_batch` (lines ~146–196), replace the `upload once / run modes / delete` block. Add a provider near the top of `run_batch` (after the modes-validation block, ~line 116):

```python
    from .providers import get_provider
    provider = get_provider(os.getenv("VANALYZE_PROVIDER"))
```

(ensure `import os` is present at top of `batch.py`). Then in the loop replace:

```python
                video_file = upload_video(video_path, no_audio=no_audio)
                video_results = analyze_video_multi_mode(
                    video_file, modes, technical_context
                )
```
…and the later `delete_video(video_file)` with:

```python
                handle = provider.prepare(video_path, no_audio=no_audio)
                video_results = analyze_video_multi_mode(
                    handle, modes, technical_context, provider=provider
                )
```
and
```python
                provider.cleanup(handle)
```

Remove now-unused `upload_video` / `delete_video` imports from `batch.py` if present.

- [ ] **Step 6: Run batch test**

Run: `uv run pytest tests/test_batch_provider.py -v`
Expected: PASS.

- [ ] **Step 7: Add CLI flags**

In `src/video_analyzer/cli.py`, in the `main` option list (near the Local-mode options, ~line 119), add:

```python
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Backend: gemini (default) | openrouter | ollama"),
```
Change the existing `--model` help to: `"Model id for the active provider"`. Keep `--local` and `--frames`.

- [ ] **Step 8: Resolve provider once in CLI and replace upload/delete calls**

In `cli.py`, replace the `# Configure Gemini` block (~lines 337–342) with provider resolution:

```python
    import os
    from .providers import get_provider
    # --local is a back-compat alias for --provider ollama
    provider_name = provider or ("ollama" if local else None) or os.getenv("VANALYZE_PROVIDER")
    if model and provider_name in ("ollama", None) and local:
        os.environ["OLLAMA_MODEL"] = model
    if model and provider_name == "openrouter":
        os.environ["OPENROUTER_MODEL"] = model
    try:
        active_provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
```

Replace `video_file = upload_video(video, no_audio=no_audio)` (~line 357) with:

```python
        handle = active_provider.prepare(video, no_audio=no_audio)
```

In the multi-mode branch (~line 369), change the call to:

```python
        results = analyze_video_multi_mode(handle, active_modes, technical_context,
                                           provider=active_provider)
```
and `delete_video(video_file)` → `active_provider.cleanup(handle)`.

In the single-mode branch (~line 405) change `analyze_video(video_file, mode, technical_context)` to:

```python
            result = active_provider.analyze(handle, mode, technical_context)
```
For the `chart`/`custom` branches that call `analyze_with_custom_prompt(video_file, ...)`: gate them to Gemini only for now (custom prompts are out of scope for the provider abstraction). Before those branches add:

```python
        if active_provider.name != "gemini":
            console.print("[yellow]--chart/--custom currently require --provider gemini[/yellow]")
            raise typer.Exit(1)
```
and keep passing `video_file = handle.payload` to the existing custom calls:
```python
            result = analyze_with_custom_prompt(handle.payload, chart_prompt, NumericResult, technical_context)
```
(For the Gemini provider, `handle.payload` is the uploaded file object, so the existing functions work unchanged.)

Find the final `delete_video(video_file)` at the end of the single path and change to `active_provider.cleanup(handle)`.

Remove the dedicated `LOCAL MODE (Ollama)` block (the `if local:` branch, ~lines 226–325) since `--local` now routes through the unified provider path. Keep the batch `if folder:` branch but it already calls `run_batch`, which now resolves a provider internally.

- [ ] **Step 9: Smoke-run the CLI help + a mocked unit pass**

Run: `uv run vanalyze main --help` → Expected: shows `--provider` option, no traceback.
Run: `uv run pytest tests/ -v` → Expected: all non-integration tests PASS.

- [ ] **Step 10: Commit**

```bash
git add src/video_analyzer/batch.py src/video_analyzer/cli.py tests/test_batch_provider.py tests/test_providers_registry.py
git commit -m "feat(cli): route single + batch through provider registry; add --provider"
```

---

## Task 9: Route archive through providers

**Files:**
- Modify: `src/video_analyzer/archive_cli.py` (and `archive.py` if it calls Gemini directly)
- Test: covered by manual smoke (archive uses the same `analyze_video_multi_mode` path)

- [ ] **Step 1: Find archive's analysis call site**

Run: `grep -n "upload_video\|analyze_video\|delete_video\|configure_genai" src/video_analyzer/archive*.py`
Expected: lists the lines to change.

- [ ] **Step 2: Replace with provider lifecycle**

For each `upload_video(...) / analyze_video(...) / delete_video(...)` sequence found, mirror the Task 8 batch pattern: at the start of the processing function add
```python
from .providers import get_provider
provider = get_provider()
```
then `handle = provider.prepare(video_path, no_audio=no_audio)`, run modes via `analyze_video_multi_mode(handle, modes, technical_context, provider=provider)`, and `provider.cleanup(handle)`. Remove direct `configure_genai()` calls (the provider handles its own configuration).

- [ ] **Step 3: Verify import + help**

Run: `uv run python -c "import video_analyzer.archive_cli"` → Expected: no error.
Run: `uv run vanalyze archive --help` → Expected: subcommands listed, no traceback.

- [ ] **Step 4: Commit**

```bash
git add src/video_analyzer/archive_cli.py src/video_analyzer/archive.py
git commit -m "feat(archive): route processing through provider registry"
```

---

## Task 10: Integration smoke tests + docs

**Files:**
- Create: `tests/fixtures/tiny.mp4`
- Create: `tests/test_integration_smoke.py`
- Modify: `/Users/hnsk/.claude/skills/philm/SKILL.md` (document `--provider`)

- [ ] **Step 1: Create a tiny fixture clip**

Run:
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
mkdir -p tests/fixtures
ffmpeg -y -f lavfi -i testsrc=duration=1:size=320x240:rate=10 \
  -pix_fmt yuv420p tests/fixtures/tiny.mp4
```
Expected: `tests/fixtures/tiny.mp4` exists (a ~1s test pattern).

- [ ] **Step 2: Write the gated smoke tests**

```python
# tests/test_integration_smoke.py
import os
from pathlib import Path

import pytest

from video_analyzer.modes import get_mode
from video_analyzer.providers import get_provider

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.mp4"


@pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"),
                    reason="no OPENROUTER_API_KEY")
def test_openrouter_video_plus_schema_works():
    """Empirically validates spec §2 assumption: video + json_schema together."""
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
```

- [ ] **Step 3: Run (skips cleanly without keys)**

Run: `uv run pytest tests/test_integration_smoke.py -v`
Expected: both SKIP if no keys; if `OPENROUTER_API_KEY` is set, the OpenRouter test PASSES — this is the §2 assumption validation.

- [ ] **Step 4: Document `--provider` in the skill**

In `/Users/hnsk/.claude/skills/philm/SKILL.md`, under the existing "Local/private" example block, add:

```bash
# Provider selection (Gemini default; OpenRouter opt-in)
vanalyze main video.mp4 --sizzle --provider openrouter
vanalyze main video.mp4 --sizzle --provider gemini   # explicit default
# Env: VANALYZE_PROVIDER, OPENROUTER_API_KEY, OPENROUTER_MODEL (default google/gemini-2.5-flash)
```
Update the Environment section to list `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `VANALYZE_PROVIDER`, and `OPENROUTER_INLINE_MAX_MB` (empirical inline-base64 knob, default 25).

- [ ] **Step 5: Full test run + commit**

Run: `uv run pytest tests/ -v` → Expected: all pass or skip (no failures).
```bash
git add tests/fixtures/tiny.mp4 tests/test_integration_smoke.py
git commit -m "test: integration smoke tests (gated) + document --provider"
# SKILL.md lives outside the repo; commit separately if it is under version control
```

---

## Self-Review Notes

- **Spec coverage:** §3 interface → Task 2; §4 transport → Task 5; §4 request/structured-output stack → Task 6; §4 schema adapter → Task 3; §5 Gemini/Ollama adapters → Tasks 4 & 7; §6 config/CLI → Task 8; archive → Task 9; §9 testing (unit + gated smoke incl. the §2-assumption validation) → all tasks + Task 10; §8 deps → Task 1.
- **Out of scope honored (§10):** no public-URL hosting; non-streaming only; `--chart`/`--custom` remain Gemini-only (gated in Task 8 Step 8) rather than ported.
- **Type consistency:** `VideoHandle(provider, payload, meta)`, `Provider.prepare/analyze/cleanup`, `get_provider(name)`, `analyze_video_multi_mode(handle, modes, technical_context, provider)`, `pydantic_to_strict_schema(model)`, and `_chat_json(...)` are used consistently across tasks.
- **Known risk:** Task 8 Steps 8 edits a large `cli.py` by description + anchors rather than full rewrite; the executor must read the surrounding code. Verify with `uv run vanalyze main --help` and a mocked test pass before committing.
