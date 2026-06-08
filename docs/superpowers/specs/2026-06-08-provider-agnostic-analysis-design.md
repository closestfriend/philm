# Provider-Agnostic Video Analysis — Design

**Date:** 2026-06-08
**Status:** Approved (design); implementation plan pending
**Author:** Hunter + Claude

## 1. Problem & Goal

`philm` (video-analyzer-v2) is hard-wired to Google Gemini for all real analysis.
`analyzer.py` imports `google.genai` directly, hardcodes `model="gemini-2.5-flash"`,
and uploads the whole clip to Gemini's File API to get structured Pydantic output via
`response_schema`. The only alternative, the Ollama `--local` path, is a shallow
bolt-on: it ignores the analysis modes, returns loose dicts instead of the Pydantic
schemas, and is not wired into batch or archive.

The trigger: an **expired `GEMINI_API_KEY` walled off the entire footage pipeline** —
a single-vendor key should not be a single point of failure.

**Goal:** Introduce a provider abstraction so analysis can run through **OpenRouter
(the new default)**, **Gemini-direct**, or **Ollama**, all behind one interface, with
OpenRouter preserving the real modes and structured output that make `philm` useful.

### Decisions (locked with user)

- **OpenRouter is the default provider.** Gemini-direct remains available; Ollama too.
- **Full provider abstraction**: a `Provider` interface that Gemini, OpenRouter, and
  Ollama all implement, wired through single-clip, batch, and archive paths.
- **Native video on OpenRouter** (verified — see §3), not frame sampling. Frame
  sampling is only a last-resort fallback for oversized clips.

## 2. Verified Facts (OpenRouter docs, 2026-06-08)

These ground the design; everything here is from current OpenRouter documentation, not
assumption. Sources listed in §11.

1. **Native video input.** Video is sent in the `content` array as a `video_url` part:
   ```json
   { "type": "video_url", "video_url": { "url": "<https URL or base64 data URL>" } }
   ```
   `url` accepts **either a public URL or a base64-encoded data URL**. Supported
   formats: **`video/mp4`, `video/mpeg`, `video/mov`, `video/webm`** — note
   `video/mpeg` covers `.MPG` camcorder footage directly. Routes to any model with the
   video input modality (includes Gemini models via OpenRouter). Duration limits are
   model-dependent.

2. **Structured outputs.** Exact shape:
   ```json
   { "response_format": { "type": "json_schema",
       "json_schema": { "name": "...", "strict": true, "schema": { ... } } } }
   ```
   Supported providers explicitly include Google Gemini, GPT-4o+, Claude Sonnet
   4.5/Opus 4.1+, most open-source models, Fireworks. If a model does **not** support
   structured outputs, the request **fails with an error** (no silent degradation).
   To guarantee routing only to capable models, set provider preference
   **`require_parameters: true`**.

3. **Response Healing plugin** (user has this enabled). Enabled per-request via
   `"plugins": [{ "id": "response-healing" }]`. Activates when `response_format` is
   `json_schema` or `json_object`. It repairs JSON **syntax** (missing brackets/commas,
   markdown fences, surrounding prose), adds <1ms latency, is **non-streaming only**,
   and **cannot** repair `max_tokens`-truncated responses. It does **NOT** fix schema
   adherence — only syntax.

4. **Size limits: undocumented.** OpenRouter publishes **no** payload/base64 size
   limit. It only *recommends direct URLs over base64 for large files*. Therefore any
   size threshold we use is an **empirical, configurable knob — not a documented
   limit**, and must be labelled as such in code and help text.

### Unverified assumption (must validate empirically)

- Whether `json_schema` structured output and **video input work simultaneously** on a
  given model is **not documented**. Both capabilities exist independently for Gemini.
  We treat co-use as an **assumption to verify with a smoke test** before relying on
  it. The healing + Pydantic-validate + retry stack (§5) is the safety net if a model
  balks.

## 3. Architecture: "prepare once, analyze many"

The existing batch already does one upload → many modes
(`batch.analyze_video_multi_mode`). We preserve that lifecycle as the interface shape,
so the "one prep, many modes" optimization survives the refactor.

```python
# providers/base.py
@dataclass
class VideoHandle:
    """Opaque, provider-specific payload returned by prepare()."""
    provider: str
    payload: Any          # Gemini file obj | OpenRouter data URL str | frame paths
    meta: dict            # e.g. {"mode_transport": "native"|"frames", "mime": ...}

class Provider(Protocol):
    name: str
    def prepare(self, video_path: Path, *, no_audio: bool = False) -> VideoHandle: ...
    def analyze(self, handle: VideoHandle, mode: AnalysisMode,
                prompt_prefix: str = "") -> BaseAnalysisResult: ...
    def cleanup(self, handle: VideoHandle) -> None: ...
```

| Provider | `prepare` | `analyze` | `cleanup` |
|---|---|---|---|
| **gemini** | File API upload → file obj | `generate_content([prompt, file], response_schema)` | delete uploaded file |
| **openrouter** | read clip → (maybe compress) → base64 data URL, cached on handle | `POST /chat/completions` with `video_url` + `json_schema` + healing | no-op |
| **ollama** | ffmpeg frame extract (cached on handle) | per-mode prompt over frames + `format: json` | rm frame dir |

This finally lets **Ollama run the real modes with structured output** (today it can't),
and lets a single `prepare()` feed multiple modes for all three providers.

### Provider registry & selection

```python
# providers/__init__.py
def get_provider(name: str | None = None) -> Provider: ...
```

Resolution order: explicit `name` arg (from `--provider`) → `VANALYZE_PROVIDER` env →
default **`openrouter`**.

## 4. OpenRouter provider detail

### Transport (`prepare`)

1. If `no_audio`, strip audio via existing `strip_audio()` (also shrinks payload).
2. Determine size. If under threshold `OPENROUTER_INLINE_MAX_MB` (**default 25, the
   empirical knob from §2.4, configurable**) → base64 data URL inline.
3. Over threshold → **compress** with ffmpeg (downscale to 720p, cap bitrate; reuse
   `scripts/compress_for_gemini.py` logic) then base64.
4. Still over threshold after compress → **frame-sample fallback**: extract N frames,
   send as multiple `image_url` parts, and **`log()` a loud warning** that this clip ran
   degraded (temporal fidelity lost). No silent truncation.

The chosen transport is recorded in `VideoHandle.meta["mode_transport"]` and surfaced
in output so degraded analyses are auditable.

### Request (`analyze`)

```jsonc
{
  "model": "<OPENROUTER_MODEL, default google/gemini-2.5-flash>",
  "messages": [
    { "role": "system", "content": "<existing system instruction>" },
    { "role": "user", "content": [
      { "type": "text", "text": "<prompt_prefix + mode.prompt>" },
      { "type": "video_url", "video_url": { "url": "data:video/mpeg;base64,..." } }
    ]}
  ],
  "response_format": { "type": "json_schema",
    "json_schema": { "name": "<mode.name>", "strict": true,
                     "schema": "<pydantic_to_strict_schema(mode.result_model)>" } },
  "provider": { "require_parameters": true },
  "plugins": [{ "id": "response-healing" }],
  "temperature": 0.5,
  "stream": false
}
```

### Structured-output robustness stack (all doc-grounded, §2)

1. `strict: true` json_schema with the adapted schema.
2. `provider.require_parameters: true` → only route to models that support structured
   outputs (else explicit error, never silent).
3. `response-healing` plugin → repairs JSON **syntax** defects.
4. Pydantic `result_model.model_validate_json(content)` → catches the **schema-
   adherence** gap healing does not cover.
5. On validation failure → **bounded retry** (default 2) with the same request; surface
   the raw response on final failure (mirrors current Gemini `analyze_video` behavior).

### Schema adapter (new, required by `strict: true`)

`providers/schema.py::pydantic_to_strict_schema(model) -> dict`:
- Start from `model.model_json_schema()`.
- Recursively set `additionalProperties: false` on every object.
- Ensure every property is listed in `required` (OpenAI strict-mode requirement).
- Preserve/handle `$defs` and `$ref` (strict mode supports them).
- Unit-tested against representative mode schemas (e.g. `SizzleResult`,
  `HauntologyResult`) which have nested moment lists.

## 5. Gemini & Ollama providers

- **gemini**: move existing `analyzer.py` logic into `providers/gemini.py` behind the
  `Provider` interface. `prepare` = `upload_video`, `analyze` = `analyze_video`,
  `cleanup` = `delete_video`. Behavior unchanged.
- **ollama**: move `local.py` logic into `providers/ollama.py`. Upgrade it to honor
  `mode.prompt` and request structured output (`format: json` / json_schema where the
  model supports it) so it returns the same Pydantic models, with the same
  validate+retry stack. Frame extraction stays as its transport.

## 6. Config & CLI

### Environment

| Var | Purpose | Default |
|---|---|---|
| `VANALYZE_PROVIDER` | default provider | `openrouter` |
| `OPENROUTER_API_KEY` | OpenRouter auth | — (required for openrouter) |
| `OPENROUTER_MODEL` | model id | `google/gemini-2.5-flash` |
| `OPENROUTER_INLINE_MAX_MB` | empirical base64 inline threshold (§2.4) | `25` |
| `GEMINI_API_KEY` | Gemini-direct auth | — (unchanged) |

### CLI

- New `--provider gemini|openrouter|ollama` option.
- `--model` generalized to "model for the active provider" (currently Ollama-only).
- `--local` kept as a **back-compat alias** for `--provider ollama`.
- `--frames` continues to control frame count (ollama, and openrouter fallback).
- Help text states the OpenRouter inline threshold is an empirical knob, not an API
  limit.

## 7. File Layout

```
src/video_analyzer/
  providers/
    __init__.py      # registry + get_provider()
    base.py          # Provider Protocol + VideoHandle
    gemini.py        # moved from analyzer.py
    openrouter.py    # NEW
    ollama.py        # moved from local.py
    schema.py        # NEW: pydantic_to_strict_schema()
  analyzer.py        # thin shim: re-export get_provider/gemini names (back-compat)
  local.py           # thin shim: re-export ollama names (back-compat)
  batch.py           # switch to get_provider(); keep one-prepare/many-modes loop
  archive_cli.py     # switch to get_provider()
  cli.py             # add --provider; generalize --model; --local alias
```

Shims keep `batch.py` / `archive.py` / external imports working during and after the
move.

## 8. Dependencies

- Add **`requests>=2.31`** to `pyproject.toml` (already imported by `local.py` but
  currently undeclared/transitive). Used by the OpenRouter HTTP client. `httpx` is an
  acceptable alternative but `requests` matches existing usage — keep it.
- `ffmpeg` already a runtime assumption (frame extraction, audio strip).

## 9. Testing (TDD)

Unit (no network, mocked HTTP):
- Provider registry resolution order (`--provider` > env > default openrouter).
- `pydantic_to_strict_schema`: `additionalProperties:false` everywhere, all props
  required, `$defs` preserved — against `SizzleResult` + one nested philosophical mode.
- OpenRouter request construction: correct `video_url` part, `response_format`,
  `require_parameters`, healing plugin present.
- Transport branching: under threshold → inline; over → compress; over-after-compress
  → frame fallback + warning emitted.
- Defensive parse + bounded retry on schema-invalid response.

Integration (auto-skip when key absent):
- One live smoke test per cloud provider on a tiny fixture clip. **The OpenRouter smoke
  test is the empirical validation of the §2 assumption** (video + json_schema
  together). Fixture: a small `.mpg`/`.mp4` checked into `tests/fixtures/`.

## 10. Out of Scope

- Public-URL upload/hosting path for very large clips (privacy: footage is local). Big
  clips use compress→base64 or frame fallback instead.
- Streaming responses (healing is non-streaming; we run non-streaming).
- Web UI (`ui.py`/`streamlit`) provider switch — follow-up if desired.

## 11. Sources

- OpenRouter Video Inputs — https://openrouter.ai/docs/guides/overview/multimodal/videos
- OpenRouter Multimodal overview — https://openrouter.ai/docs/guides/overview/multimodal/overview
- OpenRouter Structured Outputs — https://openrouter.ai/docs/guides/features/structured-outputs
- OpenRouter Response Healing — https://openrouter.ai/docs/guides/features/plugins/response-healing
