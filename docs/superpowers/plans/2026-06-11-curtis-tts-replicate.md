# Curtis TTS Replicate Model — Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the Qwen3-TTS Curtis voice clone as a private Replicate model with a smoke-tested HTTP endpoint.

**Architecture:** A Cog container bakes the Qwen3-TTS-0.6B weights and the Curtis reference audio into the image. `setup()` loads the model and builds the voice-clone prompt once per boot; `predict(text)` splits narration into paragraphs, generates each, and stitches them with 0.8s pauses — the same approach as the proven local `generate_voiceover.py`. Pure text/audio helpers live in `narration.py` so they're unit-testable on the Mac without a GPU.

**Tech Stack:** Cog, Replicate, qwen-tts 0.1.1, PyTorch, soundfile, numpy, pytest.

**Spec:** `docs/superpowers/specs/2026-06-11-curtis-documentary-app-design.md`

**Context for the engineer:**
- This is subsystem 1 of 3. The whole app will live under `curtisdoc/` in this repo: `tts-cog/` (this plan), `worker/` (Plan 2, Fly.io pipeline), `web/` (Plan 3, Vercel frontend).
- The reference voice files live at `/Volumes/2025_exSSD_2tb/adam curtis audio/` (note the spaces in the path — always quote it).
- The local scripts this is based on: `/Volumes/2025_exSSD_2tb/adam curtis audio/scripts/curtis_voice.py` and `generate_voiceover.py`. Read them if anything here is unclear.
- `cog` requires Docker running locally for `cog push`. You cannot run GPU prediction on this Mac — local verification is unit tests + `python -m py_compile`; real inference is verified on Replicate in Task 5.
- Unit tests for this subsystem run with plain `pytest` from `curtisdoc/tts-cog/` (they are not part of philm's `uv run pytest` suite).

## File structure

```
curtisdoc/
└── tts-cog/
    ├── cog.yaml                  # Cog build config; downloads weights at build time
    ├── predict.py                # Replicate Predictor (GPU, runs only on Replicate)
    ├── narration.py              # Pure helpers: paragraph split + audio stitch (testable locally)
    ├── curtis_ref_clean.mp3      # Reference voice (copied from adam curtis audio/)
    ├── smoke_test.py             # Post-deploy verification against the live endpoint
    └── tests/
        └── test_narration.py
```

---

### Task 1: Scaffold directory and reference audio

**Files:**
- Create: `curtisdoc/tts-cog/` (directory)
- Create: `curtisdoc/tts-cog/curtis_ref_clean.mp3` (copy)

- [ ] **Step 1: Create the directory and copy the reference audio**

```bash
mkdir -p /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog/tests
cp "/Volumes/2025_exSSD_2tb/adam curtis audio/curtis_ref_clean.mp3" \
   /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog/curtis_ref_clean.mp3
```

- [ ] **Step 2: Verify the copy is a real audio file**

Run: `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog/curtis_ref_clean.mp3`
Expected: a duration in seconds (a positive number), no errors.

- [ ] **Step 3: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add curtisdoc/tts-cog/curtis_ref_clean.mp3
git commit -m "feat(curtisdoc): scaffold tts-cog with Curtis reference audio"
```

---

### Task 2: Narration helpers (TDD)

**Files:**
- Create: `curtisdoc/tts-cog/narration.py`
- Test: `curtisdoc/tts-cog/tests/test_narration.py`

- [ ] **Step 1: Write the failing tests**

`curtisdoc/tts-cog/tests/test_narration.py`:

```python
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from narration import split_paragraphs, stitch


def test_split_paragraphs_basic():
    text = "This is a zoo.\n\nIt is a place where we go to look at things."
    assert split_paragraphs(text) == [
        "This is a zoo.",
        "It is a place where we go to look at things.",
    ]


def test_split_paragraphs_ignores_extra_blank_lines_and_whitespace():
    text = "\n\n  First.  \n\n\n\nSecond.\n\n"
    assert split_paragraphs(text) == ["First.", "Second."]


def test_split_paragraphs_empty_input():
    assert split_paragraphs("") == []
    assert split_paragraphs("\n\n  \n\n") == []


def test_stitch_inserts_pause_between_clips():
    sr = 10
    a = np.ones(5, dtype=np.float32)
    b = np.ones(3, dtype=np.float32)
    out = stitch([a, b], sample_rate=sr, pause_seconds=1.0)
    assert len(out) == 5 + 10 + 3
    assert (out[5:15] == 0).all()


def test_stitch_single_clip_has_no_pause():
    sr = 10
    a = np.ones(4, dtype=np.float32)
    out = stitch([a], sample_rate=sr, pause_seconds=1.0)
    assert len(out) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog && uv run --with numpy --with pytest pytest tests/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narration'`

- [ ] **Step 3: Write the implementation**

`curtisdoc/tts-cog/narration.py`:

```python
"""Pure text/audio helpers for the Curtis TTS predictor.

Kept free of torch/qwen imports so they can be unit-tested without a GPU.
"""

import numpy as np


def split_paragraphs(text: str) -> list[str]:
    """Split narration into paragraphs on blank lines; drop empties."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def stitch(wavs: list[np.ndarray], sample_rate: int, pause_seconds: float) -> np.ndarray:
    """Concatenate audio chunks with silence between them (not after the last)."""
    pause = np.zeros(int(sample_rate * pause_seconds), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i, wav in enumerate(wavs):
        parts.append(np.asarray(wav, dtype=np.float32))
        if i < len(wavs) - 1:
            parts.append(pause)
    return np.concatenate(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog && uv run --with numpy --with pytest pytest tests/ -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add curtisdoc/tts-cog/narration.py curtisdoc/tts-cog/tests/test_narration.py
git commit -m "feat(curtisdoc): narration split/stitch helpers with tests"
```

---

### Task 3: Cog predictor and build config

**Files:**
- Create: `curtisdoc/tts-cog/predict.py`
- Create: `curtisdoc/tts-cog/cog.yaml`

- [ ] **Step 1: Write cog.yaml**

`curtisdoc/tts-cog/cog.yaml`:

```yaml
build:
  gpu: true
  python_version: "3.11"
  python_packages:
    - "torch==2.4.0"
    - "qwen-tts==0.1.1"
    - "soundfile==0.12.1"
    - "numpy<2"
    - "huggingface_hub>=0.24"
  run:
    # Bake weights into the image so cold starts skip the 3.5GB download.
    # /weights, not /src — /src is overlaid with project files at runtime.
    - "python -c \"from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-TTS-12Hz-0.6B-Base', local_dir='/weights')\""
predict: "predict.py:Predictor"
```

Note: if `cog push` fails resolving `torch==2.4.0` against `qwen-tts==0.1.1`, check qwen-tts's pinned requirements (`curl -s https://pypi.org/pypi/qwen-tts/0.1.1/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['requires_dist'])"`) and align the torch pin to what it requires.

- [ ] **Step 2: Write predict.py**

`curtisdoc/tts-cog/predict.py`:

```python
"""Replicate predictor: Adam Curtis voice clone via Qwen3-TTS.

Mirrors the proven local pipeline in
'/Volumes/2025_exSSD_2tb/adam curtis audio/scripts/generate_voiceover.py':
paragraph-by-paragraph generation, 0.8s default pauses, failed paragraphs
skipped rather than fatal.
"""

import sys

import numpy as np
import soundfile as sf
import torch
from cog import BasePredictor, Input, Path

from narration import split_paragraphs, stitch

WEIGHTS_DIR = "/weights"
REF_AUDIO = "/src/curtis_ref_clean.mp3"
REF_TEXT = (
    "and it was an empire, I mean the Soviet empire was, to an extent, "
    "a growth out of the Russian empire which had been going for a number of years"
)


class Predictor(BasePredictor):
    def setup(self):
        from qwen_tts import Qwen3TTSModel

        self.model = Qwen3TTSModel.from_pretrained(
            WEIGHTS_DIR,
            device_map="cuda",
            torch_dtype=torch.float32,
        )
        self.voice_prompt = self.model.create_voice_clone_prompt(
            ref_audio=REF_AUDIO,
            ref_text=REF_TEXT,
        )

    def predict(
        self,
        text: str = Input(description="Narration text; blank lines separate paragraphs"),
        pause_seconds: float = Input(
            default=0.8, ge=0.0, le=5.0, description="Silence between paragraphs"
        ),
    ) -> Path:
        paragraphs = split_paragraphs(text)
        if not paragraphs:
            raise ValueError("No narration text provided")

        wavs: list[np.ndarray] = []
        sample_rate = None
        for i, para in enumerate(paragraphs):
            try:
                chunks, sr = self.model.generate_voice_clone(
                    text=para,
                    language="English",
                    voice_clone_prompt=self.voice_prompt,
                )
            except Exception as e:
                print(f"paragraph {i + 1}/{len(paragraphs)} failed: {e}", file=sys.stderr)
                continue
            sample_rate = sr
            wavs.append(chunks[0])

        if not wavs:
            raise RuntimeError("All paragraphs failed to generate")

        audio = stitch(wavs, sample_rate, pause_seconds)
        out_path = "/tmp/voiceover.wav"
        sf.write(out_path, audio, sample_rate)
        return Path(out_path)
```

- [ ] **Step 3: Syntax-check predict.py (full run needs GPU; compile check only)**

Run: `python3 -m py_compile /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog/predict.py && echo OK`
Expected: `OK` (the `cog`/`torch` imports are not resolved by py_compile; this catches syntax errors only).

- [ ] **Step 4: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add curtisdoc/tts-cog/predict.py curtisdoc/tts-cog/cog.yaml
git commit -m "feat(curtisdoc): cog predictor and build config for Curtis TTS"
```

---

### Task 4: Create the Replicate model and push

**Prerequisites (human steps — confirm with Hunter before running):**
- Docker Desktop running.
- Replicate account; `REPLICATE_API_TOKEN` available.
- At https://replicate.com/create : create model named `curtis-tts`, visibility **private**, hardware **Nvidia T4** (0.6B fp32 model fits easily; T4 is the cheapest per second).

- [ ] **Step 1: Install cog if missing**

Run: `which cog || brew install cog`
Expected: a path to `cog`.

- [ ] **Step 2: Log in and push**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/curtisdoc/tts-cog
cog login
cog push r8.im/<replicate-username>/curtis-tts
```

Replace `<replicate-username>` with the actual account name (ask Hunter; it is whatever appears in the URL after model creation). Expected: image builds (the weights-download step takes several minutes the first time) and pushes; final output shows the model URL and version id.

- [ ] **Step 3: Record the deployed version**

Copy the version id printed by `cog push` (or from the model page) into the commit message of the next step — Plan 2's worker will pin it.

- [ ] **Step 4: Commit a deploy note**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git commit --allow-empty -m "chore(curtisdoc): curtis-tts pushed to Replicate (version <version-id>)"
```

---

### Task 5: Smoke test the live endpoint

**Files:**
- Create: `curtisdoc/tts-cog/smoke_test.py`

- [ ] **Step 1: Write the smoke test**

`curtisdoc/tts-cog/smoke_test.py`:

```python
#!/usr/bin/env python3
"""Smoke test the deployed curtis-tts Replicate model.

Usage:
  REPLICATE_API_TOKEN=... CURTIS_TTS_MODEL=<user>/curtis-tts \
    uv run --with replicate --with soundfile python smoke_test.py
"""

import os

import replicate
import soundfile as sf

MODEL = os.environ["CURTIS_TTS_MODEL"]

TEXT = """This is a test.

But it was a fantasy. Nothing was real anymore."""

print(f"Running {MODEL} (cold start can take ~90s)...")
output = replicate.run(MODEL, input={"text": TEXT})

out_path = "/tmp/curtis_smoke.wav"
with open(out_path, "wb") as f:
    f.write(output.read())

info = sf.info(out_path)
print(f"duration: {info.duration:.1f}s, sample rate: {info.samplerate}")
assert info.duration > 2.0, f"output suspiciously short: {info.duration:.1f}s"
print(f"OK — listen to {out_path} and judge whether it sounds like Curtis")
```

- [ ] **Step 2: Run it against the live model**

Run (from `curtisdoc/tts-cog/`, with `REPLICATE_API_TOKEN` and `CURTIS_TTS_MODEL` set):
`uv run --with replicate --with soundfile python smoke_test.py`
Expected: prints a duration over 2 seconds and `OK`. First run includes cold start.

- [ ] **Step 3: Human quality gate**

Play `/tmp/curtis_smoke.wav` for Hunter (`afplay /tmp/curtis_smoke.wav`). The voice quality call is his — do not mark this plan done until he confirms it sounds right.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add curtisdoc/tts-cog/smoke_test.py
git commit -m "test(curtisdoc): smoke test for live curtis-tts endpoint"
```

---

### Task 6: Set the Replicate spend limit (manual)

- [ ] **Step 1:** Hunter sets a monthly spend limit at https://replicate.com/account/billing (per the spec's cost-control section; suggest $10–20/month). No code change; note completion in the session.

---

## Self-review notes

- Spec coverage: this plan covers the spec's "Replicate model" component and its cost-control line item; intake/analysis/script/assembly/frontend are Plans 2–3.
- The `qwen-tts==0.1.1` pin is from PyPI today; the exact version the local scripts used could not be determined (env not found, Vault_Σ unmounted). If generation quality differs from the local outputs, compare against `karman_test.wav` / `postmodern_zoo_voiceover.wav` in the adam curtis audio folder and try aligning versions.
- `predict.py` imports `narration` from the project dir — Cog puts project files at `/src` and runs the predictor from there, so the plain import works.
