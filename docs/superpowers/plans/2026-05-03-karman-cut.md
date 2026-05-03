# karman_cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trance/hyperpop beat-sync video editor stack — a shared core plus three cut scripts (pure DSP, AI-informed hybrid, fully AI-directed) — that understands phrase structure, normalizes double-time BPM, and routes Gemini perception through Claude planning.

**Architecture:** `karman_core.py` holds all shared FFmpeg utilities and an expanded effects palette (strobe burst, speed ramp, zoom pulse). Three scripts import from it: `karman_cut_rave.py` (librosa section detection, no API), `karman_cut_hybrid.py` (Gemini tags audio + clips once, Python cuts), `karman_cut_ai.py` (Gemini perceives, Claude writes a section-level `CutPlan`, Python expands to frames). All three emit versioned output files and accept `--compress` for proxy caching.

**Tech Stack:** Python 3.11+, librosa, scipy, google-genai SDK, anthropic SDK, pydantic, ffmpeg/ffprobe, uv

---

## Phase 1 — Foundation (Tasks 1–5): karman_core + karman_cut_rave

After Task 5 you have a fully working beat-sync cut tool with no API dependency.

---

### Task 1: Add anthropic dependency + create test file

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/test_karman_core.py`
- Create: `tests/test_karman_cut_rave.py`

- [ ] **Step 1: Add anthropic to pyproject.toml**

In `pyproject.toml`, add `"anthropic>=0.40.0"` to the `dependencies` list:

```toml
dependencies = [
    "google-genai>=1.0.0",
    "typer>=0.12.0",
    "pydantic>=2.0.0",
    "rich>=13.0.0",
    "python-dotenv>=1.0.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.12",
    "librosa>=0.11.0",
    "streamlit>=1.55.0",
    "anthropic>=0.40.0",
]
```

- [ ] **Step 2: Install**

```bash
uv sync
```

Expected: resolves and installs anthropic package, no errors.

- [ ] **Step 3: Create empty test files**

Create `tests/test_karman_core.py`:

```python
"""Tests for karman_core pure functions."""
```

Create `tests/test_karman_cut_rave.py`:

```python
"""Tests for karman_cut_rave logic functions."""
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock tests/test_karman_core.py tests/test_karman_cut_rave.py
git commit -m "chore: add anthropic dependency, scaffold karman test files"
```

---

### Task 2: karman_core — pure logic functions

**Files:**
- Create: `scripts/karman_core.py`
- Modify: `tests/test_karman_core.py`

- [ ] **Step 1: Write failing tests for normalize_bpm and versioned_output**

Replace `tests/test_karman_core.py` with:

```python
"""Tests for karman_core pure functions."""
import pytest
from pathlib import Path
from unittest.mock import patch


def test_normalize_bpm_doubles_slow():
    from scripts.karman_core import normalize_bpm
    assert normalize_bpm(78.0) == pytest.approx(156.0)


def test_normalize_bpm_already_in_range():
    from scripts.karman_core import normalize_bpm
    assert normalize_bpm(156.0) == pytest.approx(156.0)


def test_normalize_bpm_halves_fast():
    from scripts.karman_core import normalize_bpm
    assert normalize_bpm(320.0) == pytest.approx(160.0)


def test_normalize_bpm_very_slow():
    from scripts.karman_core import normalize_bpm
    assert normalize_bpm(40.0) == pytest.approx(160.0)


def test_normalize_bpm_custom_range():
    from scripts.karman_core import normalize_bpm
    assert normalize_bpm(60.0, target_range=(100.0, 140.0)) == pytest.approx(120.0)


def test_versioned_output_first(tmp_path):
    from scripts.karman_core import versioned_output
    result = versioned_output(tmp_path, "karman_rave")
    assert result == tmp_path / "karman_rave_v01.mp4"


def test_versioned_output_increments(tmp_path):
    from scripts.karman_core import versioned_output
    (tmp_path / "karman_rave_v01.mp4").touch()
    (tmp_path / "karman_rave_v02.mp4").touch()
    result = versioned_output(tmp_path, "karman_rave")
    assert result == tmp_path / "karman_rave_v03.mp4"


def test_get_clip_files_from_dir(tmp_path):
    from scripts.karman_core import get_clip_files
    (tmp_path / "a.mov").touch()
    (tmp_path / "b.mp4").touch()
    (tmp_path / "c.txt").touch()
    result = get_clip_files(clips_dir=tmp_path, files=None)
    names = {p.name for p in result}
    assert names == {"a.mov", "b.mp4"}


def test_get_clip_files_from_list(tmp_path):
    from scripts.karman_core import get_clip_files
    f = tmp_path / "clip.mov"
    f.touch()
    result = get_clip_files(clips_dir=None, files=[f])
    assert result == [f]


def test_get_clip_files_requires_one_source():
    from scripts.karman_core import get_clip_files
    with pytest.raises(ValueError):
        get_clip_files(clips_dir=None, files=None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_karman_core.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `karman_core` doesn't exist yet.

- [ ] **Step 3: Create karman_core.py with pure functions**

Create `scripts/karman_core.py`:

```python
#!/usr/bin/env python3
"""
karman_core.py — Shared utilities for the karman_cut stack.

FFmpeg helpers, proxy machinery, effects palette, BPM normalization.
"""

import random
import subprocess
from pathlib import Path

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

VIDEO_EXTS = {".mov", ".mp4", ".mpg", ".mpeg", ".mxf", ".avi", ".mkv", ".m4v"}
TARGET_FPS = 30
OUTPUT_SIZE = "1920:1080"
OUTPUT_SIZE_LAVFI = "1920x1080"
FLASH_DURATION = 0.04

TARGET_BPM_RANGE: tuple[float, float] = (120.0, 180.0)

PROXY_DIR = Path.home() / ".ez_mv_proxies"
KARMAN_ANALYSIS_DIR = Path.home() / ".karman_analysis"
KARMAN_CLIP_TAGS_DIR = Path.home() / ".karman_clip_tags"


# ─── BPM ──────────────────────────────────────────────────────────────────────

def normalize_bpm(raw_bpm: float, target_range: tuple[float, float] = TARGET_BPM_RANGE) -> float:
    """Double or halve until BPM lands inside target_range."""
    bpm = raw_bpm
    while bpm < target_range[0]:
        bpm *= 2
    while bpm > target_range[1]:
        bpm /= 2
    return bpm


# ─── OUTPUT VERSIONING ────────────────────────────────────────────────────────

def versioned_output(output_dir: Path, prefix: str) -> Path:
    """Return next non-existing versioned path: {prefix}_v01.mp4, v02, …"""
    existing = sorted(output_dir.glob(f"{prefix}_v*.mp4"))
    next_v = len(existing) + 1
    return output_dir / f"{prefix}_v{next_v:02d}.mp4"


# ─── CLIP DISCOVERY ───────────────────────────────────────────────────────────

def get_clip_files(clips_dir: Path | None, files: list[Path] | None) -> list[Path]:
    """Return sorted clip list from a folder or explicit file list."""
    if clips_dir is None and not files:
        raise ValueError("Provide either clips_dir or files")
    if files:
        return list(files)
    return sorted(p for p in clips_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS)


# ─── FFMPEG HELPERS ───────────────────────────────────────────────────────────

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


# ─── PROXY MACHINERY ──────────────────────────────────────────────────────────

def get_proxy_path(source: Path) -> Path:
    key = f"{source.parent.name}_{source.stem}"
    return PROXY_DIR / f"{key}.mp4"


def compress_to_proxy(source: Path, proxy: Path) -> None:
    run([
        "ffmpeg", "-y", "-i", str(source),
        "-vf", f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an",
        str(proxy),
    ])


def ensure_proxies(clip_files: list[Path]) -> list[Path]:
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    proxies = []
    for source in clip_files:
        proxy = get_proxy_path(source)
        if proxy.exists():
            print(f"  ✓ cached: {source.name}")
        else:
            print(f"  compressing: {source.name}...")
            compress_to_proxy(source, proxy)
        proxies.append(proxy)
    return proxies


# ─── ASSEMBLY ─────────────────────────────────────────────────────────────────

def build_concat_list(segments: list[Path], concat_file: Path) -> None:
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg.absolute()}'\n")


def final_assemble(concat_file: Path, music: Path, output: Path, video_duration: float) -> None:
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(music),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(video_duration),
        "-movflags", "+faststart",
        str(output),
    ])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_karman_core.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/karman_core.py tests/test_karman_core.py
git commit -m "feat: add karman_core — BPM normalization, versioning, clip utils, proxy machinery"
```

---

### Task 3: karman_core — effects palette

**Files:**
- Modify: `scripts/karman_core.py`
- Modify: `tests/test_karman_core.py`

- [ ] **Step 1: Write failing tests for effects functions**

Append to `tests/test_karman_core.py`:

```python
def test_generate_flash_frame_creates_file(tmp_path):
    from scripts.karman_core import generate_flash_frame
    out = tmp_path / "flash.mp4"
    result = generate_flash_frame("white", 0.04, out)
    assert result == out
    assert out.exists()


def test_strobe_burst_count(tmp_path):
    from scripts.karman_core import strobe_burst
    frames = strobe_burst(n_flashes=4, interval=0.04, tmp_dir=tmp_path)
    assert len(frames) == 4
    for f in frames:
        assert f.exists()


def test_speed_ramp_creates_file(tmp_path):
    from scripts.karman_core import speed_ramp_segment
    # Use a synthetic source: create a tiny test clip via ffmpeg lavfi
    src = tmp_path / "src.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=blue:s=64x64:d=2",
        "-c:v", "libx264", "-t", "2", str(src)
    ], check=True, capture_output=True)
    out = tmp_path / "ramped.mp4"
    speed_ramp_segment(src, start=0.0, duration=1.0, speed=0.5, output=out)
    assert out.exists()


def test_zoom_pulse_creates_file(tmp_path):
    from scripts.karman_core import zoom_pulse_segment
    src = tmp_path / "src.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=red:s=64x64:d=2",
        "-c:v", "libx264", "-t", "2", str(src)
    ], check=True, capture_output=True)
    out = tmp_path / "zoomed.mp4"
    zoom_pulse_segment(src, start=0.0, duration=1.0, zoom_factor=1.3, output=out)
    assert out.exists()
```

Also add `import subprocess` to the top of `tests/test_karman_core.py`.

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_karman_core.py::test_generate_flash_frame_creates_file -v
```

Expected: `ImportError` — functions not defined yet.

- [ ] **Step 3: Add effects functions to karman_core.py**

Append to `scripts/karman_core.py` after the assembly section:

```python
# ─── EFFECTS PALETTE ──────────────────────────────────────────────────────────

def generate_flash_frame(color: str, duration: float, output: Path) -> Path:
    """Single solid-color frame clip."""
    run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color={color}:s={OUTPUT_SIZE_LAVFI}:d={duration:.4f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-r", str(TARGET_FPS), str(output),
    ])
    return output


def strobe_burst(n_flashes: int, interval: float, tmp_dir: Path) -> list[Path]:
    """Alternating white/black flash sequence — rapid strobe between cuts."""
    frames: list[Path] = []
    for i in range(n_flashes):
        color = "white" if i % 2 == 0 else "black"
        out = tmp_dir / f"strobe_{i:03d}.mp4"
        generate_flash_frame(color, interval, out)
        frames.append(out)
    return frames


def extract_segment(
    source: Path,
    start: float,
    duration: float,
    output: Path,
    effect: str = "normal",
    rng: random.Random | None = None,
) -> None:
    """Extract a video-only segment with optional in-frame effect."""
    if effect == "shrink":
        scale_pct = rng.uniform(0.4, 0.7) if rng else 0.55
        inner_w = int(1920 * scale_pct)
        inner_h = int(1080 * scale_pct)
        max_x = 1920 - inner_w
        max_y = 1080 - inner_h
        off_x = rng.randint(0, max_x) if rng else max_x // 2
        off_y = rng.randint(0, max_y) if rng else max_y // 2
        vf = (
            f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:{off_x}:{off_y}:black,fps={TARGET_FPS}"
        )
    elif effect == "zoom":
        crop_pct = rng.uniform(0.4, 0.7) if rng else 0.55
        vf = (
            f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
            f"crop=iw*{crop_pct:.2f}:ih*{crop_pct:.2f}:(iw-iw*{crop_pct:.2f})/2:(ih-ih*{crop_pct:.2f})/2,"
            f"scale={OUTPUT_SIZE},fps={TARGET_FPS}"
        )
    else:
        vf = (
            f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
            f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,fps={TARGET_FPS}"
        )
    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.4f}", "-t", f"{duration:.4f}", "-i", str(source),
        "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an",
        str(output),
    ])


def speed_ramp_segment(
    source: Path, start: float, duration: float, speed: float, output: Path
) -> None:
    """Extract with speed change. speed=0.5 → slo-mo, speed=2.0 → overcranked."""
    pts = 1.0 / speed
    vf = (
        f"setpts={pts:.4f}*PTS,"
        f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,fps={TARGET_FPS}"
    )
    # Read enough source to fill the output duration
    src_duration = duration * speed
    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.4f}", "-t", f"{src_duration:.4f}", "-i", str(source),
        "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an",
        str(output),
    ])


def zoom_pulse_segment(
    source: Path, start: float, duration: float, zoom_factor: float, output: Path
) -> None:
    """Animated push-in crop over the clip duration."""
    # zoompan filter: start at 1.0, end at zoom_factor, centered
    fps = TARGET_FPS
    n_frames = int(duration * fps)
    vf = (
        f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
        f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
        f"zoompan=z='min(zoom+{(zoom_factor-1.0)/n_frames:.6f},zoom)'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={n_frames}:s={OUTPUT_SIZE_LAVFI}:fps={fps}"
    )
    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.4f}", "-t", f"{duration:.4f}", "-i", str(source),
        "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an",
        str(output),
    ])
```

- [ ] **Step 4: Run all core tests**

```bash
uv run pytest tests/test_karman_core.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/karman_core.py tests/test_karman_core.py
git commit -m "feat: add karman_core effects palette — flash, strobe, speed_ramp, zoom_pulse, extract_segment"
```

---

### Task 4: karman_cut_rave — beat detection and section labeling

**Files:**
- Create: `scripts/karman_cut_rave.py`
- Modify: `tests/test_karman_cut_rave.py`

- [ ] **Step 1: Write failing tests for detect_beats_and_sections and label logic**

Replace `tests/test_karman_cut_rave.py` with:

```python
"""Tests for karman_cut_rave logic functions."""
import numpy as np
import pytest


def test_label_section_drop():
    from scripts.karman_cut_rave import _label_section
    # high rms, high onset density → drop
    assert _label_section(avg_rms=0.9, avg_onset=0.9, rms_high=0.7, rms_low=0.3, onset_high=0.7) == "drop"


def test_label_section_breakdown():
    from scripts.karman_cut_rave import _label_section
    assert _label_section(avg_rms=0.1, avg_onset=0.1, rms_high=0.7, rms_low=0.3, onset_high=0.7) == "breakdown"


def test_label_section_build():
    from scripts.karman_cut_rave import _label_section
    assert _label_section(avg_rms=0.5, avg_onset=0.3, rms_high=0.7, rms_low=0.3, onset_high=0.7) == "build"


def test_build_rave_cut_schedule_empty_beats():
    from scripts.karman_cut_rave import build_rave_cut_schedule
    import random
    pool = [("clip_a", 0.0, "clip_a.mp4"), ("clip_b", 1.0, "clip_b.mp4")]
    sections = [{"start": 0.0, "end": 5.0, "type": "drop"}]
    result = build_rave_cut_schedule([], sections, pool, random.Random(42))
    assert result == []


def test_build_rave_cut_schedule_assigns_clips():
    from scripts.karman_cut_rave import build_rave_cut_schedule
    import random
    pool = [("clip_a", 0.0, "clip_a.mp4"), ("clip_b", 0.5, "clip_b.mp4")]
    beat_times = [0.0, 0.46, 0.92, 1.38, 1.84]
    sections = [{"start": 0.0, "end": 2.0, "type": "drop"}]
    schedule = build_rave_cut_schedule(beat_times, sections, pool, random.Random(42))
    assert len(schedule) > 0
    for entry in schedule:
        assert entry["clip_id"] in {"clip_a", "clip_b"}
        assert entry["duration"] > 0
        assert entry["effect"] in {"normal", "zoom", "shrink"}


def test_build_rave_cut_schedule_breakdown_uses_slo_mo():
    from scripts.karman_cut_rave import build_rave_cut_schedule
    import random
    pool = [("clip_a", 0.0, "clip_a.mp4")]
    # breakdown section with beats far apart (4-beat hold = ~2s at 120bpm)
    beat_times = [0.0, 0.5, 1.0, 1.5, 2.0, 4.0, 8.0]
    sections = [{"start": 0.0, "end": 10.0, "type": "breakdown"}]
    schedule = build_rave_cut_schedule(beat_times, sections, pool, random.Random(1))
    slo_mo = [e for e in schedule if e.get("speed_ramp") is not None]
    assert len(slo_mo) > 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_karman_cut_rave.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create karman_cut_rave.py with detection + schedule logic**

Create `scripts/karman_cut_rave.py`:

```python
#!/usr/bin/env python3
"""
karman_cut_rave.py — Trance/hyperpop beat-sync cut, pure DSP.

Phrase-aware: builds, drops, breakdowns get different cut density and effects.
No API cost. Uses target range BPM normalization for double-time tracks.
"""

import argparse
import random
import tempfile
from pathlib import Path
from typing import Any

import librosa
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

from karman_core import (
    TARGET_BPM_RANGE,
    normalize_bpm,
    versioned_output,
    get_clip_files,
    probe_duration,
    ensure_proxies,
    generate_flash_frame,
    strobe_burst,
    extract_segment,
    speed_ramp_segment,
    zoom_pulse_segment,
    build_concat_list,
    final_assemble,
    FLASH_DURATION,
    TARGET_FPS,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

DROP_DENSITY    = 4      # 16th note = 4× normalized beat
STROBE_PROB     = 0.35   # strobe burst probability during drops
FLASH_PROB      = 0.20   # flash frame probability
ZOOM_PROB       = 0.25   # zoom_pulse probability
SLO_MO_FACTOR   = 0.5    # speed during breakdowns
MIN_SECTION_SEC = 4.0    # minimum section duration to detect


# ─── SECTION DETECTION ────────────────────────────────────────────────────────

def _label_section(
    avg_rms: float,
    avg_onset: float,
    rms_high: float,
    rms_low: float,
    onset_high: float,
) -> str:
    if avg_rms >= rms_high and avg_onset >= onset_high:
        return "drop"
    if avg_rms <= rms_low:
        return "breakdown"
    return "build"


def detect_beats_and_sections(
    music_path: Path,
) -> tuple[list[float], list[dict[str, Any]]]:
    """Return (beat_times, sections) with BPM normalized to TARGET_BPM_RANGE."""
    y, sr = librosa.load(str(music_path))
    mid_bpm = (TARGET_BPM_RANGE[0] + TARGET_BPM_RANGE[1]) / 2.0

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, start_bpm=mid_bpm)
    raw_bpm = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])
    bpm = normalize_bpm(raw_bpm)
    print(f"BPM: {raw_bpm:.1f} → normalized: {bpm:.1f}")

    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    track_duration = librosa.get_duration(y=y, sr=sr)

    # Onset novelty curve → section boundaries
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    hop = 512
    smooth_frames = int(sr / hop)  # ~1 second
    smoothed = uniform_filter1d(onset_env.astype(float), size=smooth_frames)
    min_dist = int(MIN_SECTION_SEC * sr / hop)
    peaks, _ = find_peaks(smoothed, distance=min_dist, prominence=smoothed.std())
    bound_times = librosa.frames_to_time(peaks, sr=sr).tolist()

    # RMS for section labeling
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    rms_smooth = uniform_filter1d(rms.astype(float), size=smooth_frames)
    frame_times = librosa.frames_to_time(np.arange(len(rms_smooth)), sr=sr, hop_length=hop)
    onset_smooth = uniform_filter1d(onset_env.astype(float), size=smooth_frames)

    rms_high = float(np.percentile(rms_smooth, 65))
    rms_low  = float(np.percentile(rms_smooth, 35))
    onset_high = float(np.percentile(onset_smooth, 65))

    all_bounds = sorted({0.0} | set(bound_times) | {track_duration})
    sections: list[dict[str, Any]] = []
    for i in range(len(all_bounds) - 1):
        start, end = all_bounds[i], all_bounds[i + 1]
        if end - start < MIN_SECTION_SEC / 2:
            continue
        mask = (frame_times >= start) & (frame_times < end)
        if not np.any(mask):
            continue
        avg_rms    = float(np.mean(rms_smooth[mask]))
        mask_onset = mask[:len(onset_smooth)]
        avg_onset  = float(np.mean(onset_smooth[mask_onset])) if np.any(mask_onset) else 0.0
        stype = _label_section(avg_rms, avg_onset, rms_high, rms_low, onset_high)
        sections.append({"start": start, "end": end, "type": stype})

    counts = {t: sum(1 for s in sections if s["type"] == t) for t in ("build", "drop", "breakdown")}
    print(f"Sections: {len(sections)} — {counts}")
    return beat_times, sections


# ─── CUT SCHEDULE ─────────────────────────────────────────────────────────────

def _section_for_time(t: float, sections: list[dict]) -> str:
    for s in sections:
        if s["start"] <= t < s["end"]:
            return s["type"]
    return "build"


def build_rave_cut_schedule(
    beat_times: list[float],
    sections: list[dict[str, Any]],
    clip_pool: list[tuple[str, float, str]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Build cut entries from beat grid, applying per-section logic."""
    if not beat_times or not clip_pool:
        return []

    pool = list(clip_pool)
    rng.shuffle(pool)
    pool_idx = 0
    schedule: list[dict[str, Any]] = []

    # Expand beat_times: insert 16th-note subdivisions during drops
    expanded: list[tuple[float, str]] = []
    for i, bt in enumerate(beat_times):
        stype = _section_for_time(bt, sections)
        if stype == "drop" and i + 1 < len(beat_times):
            interval = (beat_times[i + 1] - bt) / DROP_DENSITY
            for sub in range(DROP_DENSITY):
                expanded.append((bt + sub * interval, "drop"))
        elif stype == "breakdown":
            # Hold for 4 beats: skip to every 4th beat
            if i % 4 == 0:
                expanded.append((bt, "breakdown"))
        else:
            expanded.append((bt, stype))

    for idx, (beat_t, stype) in enumerate(expanded):
        if idx + 1 < len(expanded):
            duration = expanded[idx + 1][0] - beat_t
        else:
            duration = 0.5

        if duration < FLASH_DURATION:
            continue

        clip_id, start_offset, _ = pool[pool_idx % len(pool)]
        pool_idx += 1

        flash_before = rng.random() < FLASH_PROB
        do_strobe    = stype == "drop" and rng.random() < STROBE_PROB

        if stype == "breakdown":
            effect = "normal"
            speed_ramp = SLO_MO_FACTOR
        elif rng.random() < ZOOM_PROB:
            effect = "zoom"
            speed_ramp = None
        elif rng.random() < 0.20:
            effect = "shrink"
            speed_ramp = None
        else:
            effect = "normal"
            speed_ramp = None

        schedule.append({
            "clip_id":     clip_id,
            "start_offset": start_offset,
            "duration":    duration,
            "effect":      effect,
            "flash_before": flash_before,
            "strobe":      do_strobe,
            "speed_ramp":  speed_ramp,
            "beat_time":   beat_t,
            "section_type": stype,
        })

    return schedule
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_karman_cut_rave.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/karman_cut_rave.py tests/test_karman_cut_rave.py
git commit -m "feat: karman_cut_rave — section detection, BPM normalization, cut schedule builder"
```

---

### Task 5: karman_cut_rave — assembly and CLI

**Files:**
- Modify: `scripts/karman_cut_rave.py`

- [ ] **Step 1: Append main() and CLI to karman_cut_rave.py**

Append to `scripts/karman_cut_rave.py`:

```python
# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="karman_cut_rave — trance/hyperpop beat-sync, pure DSP")
    parser.add_argument("--music",   required=True, type=Path)
    parser.add_argument("--clips",   type=Path)
    parser.add_argument("--files",   nargs="+", type=Path)
    parser.add_argument("--output",  type=Path, default=Path("karman_cuts"))
    parser.add_argument("--compress", action="store_true")
    args = parser.parse_args()

    print("\n╭──────────────────────────────────────────────╮")
    print("│  KARMAN CUT RAVE — phrase-aware DSP cutter  │")
    print("╰──────────────────────────────────────────────╯\n")

    if not args.music.exists():
        raise FileNotFoundError(f"Music not found: {args.music}")

    args.output.mkdir(parents=True, exist_ok=True)
    clip_files = get_clip_files(args.clips, args.files)
    if not clip_files:
        raise FileNotFoundError("No video clips found")

    if args.compress:
        print(f"Building proxies for {len(clip_files)} clips...")
        clip_files = ensure_proxies(clip_files)
        print(f"✓ Proxies ready\n")

    clip_paths = {p.stem: p for p in clip_files}

    # Build clip pool with random offsets
    rng_seed = random.randint(0, 9999)
    print(f"Seed: {rng_seed}")
    rng = random.Random(rng_seed)
    clip_pool = []
    for p in clip_files:
        dur = probe_duration(p)
        offset = rng.uniform(0, max(0.0, dur * 0.75))
        clip_pool.append((p.stem, offset, p.name))

    track_duration = probe_duration(args.music)
    beat_times, sections = detect_beats_and_sections(args.music)
    schedule = build_rave_cut_schedule(beat_times, sections, clip_pool, rng)

    flash_n  = sum(1 for e in schedule if e["flash_before"])
    strobe_n = sum(1 for e in schedule if e["strobe"])
    print(f"✓ {len(schedule)} cuts ({flash_n} flash, {strobe_n} strobe)\n")

    output = versioned_output(args.output, "karman_rave")
    print(f"Output: {output}\n")

    with tempfile.TemporaryDirectory(prefix="karman_rave_") as tmp:
        tmp_dir = Path(tmp)
        segs_dir = tmp_dir / "segs"
        segs_dir.mkdir()

        white_flash = tmp_dir / "white.mp4"
        generate_flash_frame("white", FLASH_DURATION, white_flash)

        ordered: list[Path] = []
        clip_playhead: dict[str, float] = {c: off for c, off, _ in clip_pool}

        print(f"Extracting {len(schedule)} segments...")
        for idx, entry in enumerate(schedule):
            cid = entry["clip_id"]
            src = clip_paths[cid]
            start = clip_playhead[cid]
            dur   = entry["duration"]

            # Safety: don't read past clip end
            src_dur = probe_duration(src)
            if start + dur > src_dur:
                start = max(0.0, src_dur - dur - 0.1)

            if entry["strobe"]:
                burst = strobe_burst(n_flashes=4, interval=FLASH_DURATION, tmp_dir=segs_dir)
                ordered.extend(burst)

            if entry["flash_before"]:
                ordered.append(white_flash)

            seg = segs_dir / f"seg_{idx:05d}.mp4"
            if entry["speed_ramp"] is not None:
                speed_ramp_segment(src, start, dur, entry["speed_ramp"], seg)
            elif entry["effect"] == "zoom":
                zoom_pulse_segment(src, start, dur, 1.25, seg)
            else:
                extract_segment(src, start, dur, seg, entry["effect"], rng)
            ordered.append(seg)

            if not entry.get("stutter"):
                clip_playhead[cid] = start + dur

            if (idx + 1) % 50 == 0:
                print(f"  {idx+1}/{len(schedule)} done...")

        print(f"✓ Segments extracted\n")

        concat_file = tmp_dir / "concat.txt"
        build_concat_list(ordered, concat_file)

        print("Assembling with music...")
        final_assemble(concat_file, args.music, output, track_duration)

    dur  = probe_duration(output)
    size = output.stat().st_size / (1024 * 1024)
    print(f"\n╭──────────────────────────────────────────────╮")
    print(f"│  DONE!                                       │")
    print(f"╰──────────────────────────────────────────────╯")
    print(f"Output  : {output}")
    print(f"Duration: {dur:.1f}s  Size: {size:.0f}MB\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test the script with a real clip (manual)**

```bash
uv run python scripts/karman_cut_rave.py \
  --music "input/audio/rav3rz (v2) 16th note kicks + NO OZONE.wav" \
  --clips "/Volumes/2025_exSSD_2tb/📷 Camera Footage & Photography/Photography/LA-Fires" \
  --compress
```

Expected: prints normalized BPM (~156), section labels, segment count, produces `karman_cuts/karman_rave_v01.mp4`.

- [ ] **Step 3: Commit**

```bash
git add scripts/karman_cut_rave.py
git commit -m "feat: karman_cut_rave — CLI and assembly, first working script"
```

---

## Phase 2 — Hybrid (Tasks 6–7): karman_cut_hybrid

---

### Task 6: karman_cut_hybrid — Gemini analysis and clip tagging with cache

**Files:**
- Create: `scripts/karman_cut_hybrid.py`
- Create: `tests/test_karman_cut_hybrid.py`

- [ ] **Step 1: Write failing tests for affinity scoring and cache helpers**

Create `tests/test_karman_cut_hybrid.py`:

```python
"""Tests for karman_cut_hybrid logic."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_score_clip_affinity_drop_prefers_high_energy():
    from scripts.karman_cut_hybrid import score_clip_affinity
    high = score_clip_affinity(
        {"energy": "high", "mood": "euphoric", "motion": "kinetic", "color": "cool"},
        "drop",
    )
    low = score_clip_affinity(
        {"energy": "low", "mood": "contemplative", "motion": "still", "color": "warm"},
        "drop",
    )
    assert high > low


def test_score_clip_affinity_breakdown_prefers_contemplative():
    from scripts.karman_cut_hybrid import score_clip_affinity
    contemplative = score_clip_affinity(
        {"energy": "low", "mood": "contemplative", "motion": "still", "color": "cool"},
        "breakdown",
    )
    frenetic = score_clip_affinity(
        {"energy": "high", "mood": "euphoric", "motion": "kinetic", "color": "warm"},
        "breakdown",
    )
    assert contemplative > frenetic


def test_load_cached_analysis(tmp_path):
    from scripts.karman_cut_hybrid import _load_cached, _save_cached
    data = {"sections": [], "tempo": 156}
    key = "test_track"
    _save_cached(tmp_path, key, data)
    result = _load_cached(tmp_path, key)
    assert result == data


def test_load_cached_returns_none_if_missing(tmp_path):
    from scripts.karman_cut_hybrid import _load_cached
    result = _load_cached(tmp_path, "nonexistent")
    assert result is None
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_karman_cut_hybrid.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create karman_cut_hybrid.py with Gemini analysis and clip tagging**

Create `scripts/karman_cut_hybrid.py`:

```python
#!/usr/bin/env python3
"""
karman_cut_hybrid.py — Gemini perceives, Python cuts.

Gemini analyzes the audio once (cached) and tags each clip once (cached).
Python builds the cut schedule using affinity scores to match clips to sections.
"""

import argparse
import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from karman_core import (
    TARGET_BPM_RANGE,
    KARMAN_ANALYSIS_DIR,
    KARMAN_CLIP_TAGS_DIR,
    FLASH_DURATION,
    normalize_bpm,
    versioned_output,
    get_clip_files,
    probe_duration,
    ensure_proxies,
    generate_flash_frame,
    strobe_burst,
    extract_segment,
    speed_ramp_segment,
    zoom_pulse_segment,
    build_concat_list,
    final_assemble,
)
from karman_cut_rave import (
    detect_beats_and_sections,
    SLO_MO_FACTOR,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

AFFINITY_WEIGHT = 0.7   # 0.0 = random, 1.0 = strict
GEMINI_MODEL    = "gemini-2.5-flash"

AUDIO_ANALYSIS_PROMPT = """
Analyze this music track and return a JSON object with this exact structure:
{
  "sections": [
    {"start": 0.0, "end": 22.4, "type": "build", "energy": 0.4, "vibe": "anticipatory ascent"}
  ],
  "tempo": 156,
  "key": "F# minor",
  "emotional_arc": "brief description of the track's overall arc"
}
Section types must be one of: "build", "drop", "breakdown".
Energy is a float 0.0–1.0. Return only valid JSON, no markdown.
"""

CLIP_TAG_PROMPT = """
Analyze this video clip and return a JSON object with this exact structure:
{
  "energy": "high",
  "mood": "euphoric",
  "motion": "kinetic",
  "color": "cool"
}
energy: one of "high", "medium", "low"
mood: one of "euphoric", "contemplative", "raw", "serene", "tense"
motion: one of "kinetic", "moderate", "still"
color: one of "warm", "cool", "neutral", "saturated"
Return only valid JSON, no markdown.
"""


# ─── CACHE HELPERS ────────────────────────────────────────────────────────────

def _load_cached(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _save_cached(cache_dir: Path, key: str, data: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(data, indent=2))


# ─── AFFINITY SCORING ─────────────────────────────────────────────────────────

_AFFINITY_TABLE: dict[str, dict[str, dict[str, float]]] = {
    "drop": {
        "energy":  {"high": 1.0, "medium": 0.5, "low": 0.0},
        "motion":  {"kinetic": 1.0, "moderate": 0.5, "still": 0.0},
        "mood":    {"euphoric": 1.0, "raw": 0.8, "tense": 0.6, "contemplative": 0.2, "serene": 0.1},
    },
    "breakdown": {
        "energy":  {"low": 1.0, "medium": 0.5, "high": 0.0},
        "motion":  {"still": 1.0, "moderate": 0.5, "kinetic": 0.0},
        "mood":    {"contemplative": 1.0, "serene": 0.8, "euphoric": 0.3, "raw": 0.2, "tense": 0.4},
    },
    "build": {
        "energy":  {"medium": 1.0, "high": 0.7, "low": 0.3},
        "motion":  {"moderate": 1.0, "kinetic": 0.7, "still": 0.4},
        "mood":    {"tense": 1.0, "euphoric": 0.8, "raw": 0.6, "contemplative": 0.5, "serene": 0.3},
    },
}


def score_clip_affinity(clip_tag: dict, section_type: str) -> float:
    """Return 0.0–1.0 affinity score for a clip tag against a section type."""
    table = _AFFINITY_TABLE.get(section_type, _AFFINITY_TABLE["build"])
    scores = []
    for attr, mapping in table.items():
        val = clip_tag.get(attr, "")
        scores.append(mapping.get(val, 0.5))
    return sum(scores) / len(scores) if scores else 0.5


# ─── GEMINI API ───────────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not set in environment or .env")
    return genai.Client(api_key=key)


def analyze_audio_gemini(music_path: Path, client: genai.Client) -> dict:
    """Upload audio to Gemini and return section analysis. Cached per track."""
    cache_key = music_path.stem
    cached = _load_cached(KARMAN_ANALYSIS_DIR, cache_key)
    if cached:
        print(f"  ✓ audio analysis cached: {music_path.name}")
        return cached

    print(f"  Uploading audio to Gemini: {music_path.name}...")
    audio_file = client.files.upload(
        file=str(music_path),
        config=types.UploadFileConfig(
            display_name=music_path.name,
            mime_type="audio/wav" if music_path.suffix.lower() == ".wav" else "audio/mpeg",
        ),
    )
    import time
    while audio_file.state.name == "PROCESSING":
        time.sleep(2)
        audio_file = client.files.get(name=audio_file.name)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[audio_file, AUDIO_ANALYSIS_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    result = json.loads(response.text)
    _save_cached(KARMAN_ANALYSIS_DIR, cache_key, result)
    print(f"  ✓ audio analysis complete, cached")
    return result


def tag_clip_gemini(clip_path: Path, client: genai.Client) -> dict:
    """Tag a single video clip with semantic attributes. Cached per clip."""
    cache_key = f"{clip_path.parent.name}_{clip_path.stem}"
    cached = _load_cached(KARMAN_CLIP_TAGS_DIR, cache_key)
    if cached:
        return cached

    print(f"  Tagging: {clip_path.name}...")
    import time
    mime = "video/mp4" if clip_path.suffix.lower() == ".mp4" else "video/quicktime"
    video_file = client.files.upload(
        file=str(clip_path),
        config=types.UploadFileConfig(display_name=clip_path.name, mime_type=mime),
    )
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[video_file, CLIP_TAG_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    result = json.loads(response.text)
    _save_cached(KARMAN_CLIP_TAGS_DIR, cache_key, result)
    return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_karman_cut_hybrid.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/karman_cut_hybrid.py tests/test_karman_cut_hybrid.py
git commit -m "feat: karman_cut_hybrid — Gemini audio analysis, clip tagging, affinity scoring (cached)"
```

---

### Task 7: karman_cut_hybrid — cut schedule and CLI

**Files:**
- Modify: `scripts/karman_cut_hybrid.py`

- [ ] **Step 1: Append cut schedule builder and main() to karman_cut_hybrid.py**

Append to `scripts/karman_cut_hybrid.py`:

```python
# ─── CUT SCHEDULE ─────────────────────────────────────────────────────────────

def build_hybrid_cut_schedule(
    beat_times: list[float],
    sections: list[dict[str, Any]],
    clip_pool: list[tuple[str, float, str]],
    clip_tags: dict[str, dict],
    affinity_weight: float,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    Like rave schedule, but clip selection is weighted by affinity to section type.
    affinity_weight=0.0 → random; affinity_weight=1.0 → always highest-affinity clip.
    """
    from karman_cut_rave import _section_for_time, DROP_DENSITY, STROBE_PROB, FLASH_PROB, ZOOM_PROB

    if not beat_times or not clip_pool:
        return []

    # Expand beats with drop subdivisions (same as rave)
    expanded: list[tuple[float, str]] = []
    for i, bt in enumerate(beat_times):
        stype = _section_for_time(bt, sections)
        if stype == "drop" and i + 1 < len(beat_times):
            interval = (beat_times[i + 1] - bt) / DROP_DENSITY
            for sub in range(DROP_DENSITY):
                expanded.append((bt + sub * interval, "drop"))
        elif stype == "breakdown":
            if i % 4 == 0:
                expanded.append((bt, "breakdown"))
        else:
            expanded.append((bt, stype))

    schedule: list[dict[str, Any]] = []
    clip_playhead: dict[str, float] = {c: off for c, off, _ in clip_pool}

    for idx, (beat_t, stype) in enumerate(expanded):
        if idx + 1 < len(expanded):
            duration = expanded[idx + 1][0] - beat_t
        else:
            duration = 0.5
        if duration < FLASH_DURATION:
            continue

        # Weighted clip selection
        weights = []
        for stem, _, _ in clip_pool:
            tag = clip_tags.get(stem, {})
            affinity = score_clip_affinity(tag, stype)
            # Blend affinity with uniform (1/n) by affinity_weight
            w = affinity_weight * affinity + (1 - affinity_weight) * (1.0 / len(clip_pool))
            weights.append(w)
        total = sum(weights)
        normalized = [w / total for w in weights]
        chosen_idx = rng.choices(range(len(clip_pool)), weights=normalized, k=1)[0]
        clip_id, start_offset, _ = clip_pool[chosen_idx]

        flash_before = rng.random() < FLASH_PROB
        do_strobe    = stype == "drop" and rng.random() < STROBE_PROB
        effect       = "zoom" if rng.random() < ZOOM_PROB else "normal"
        speed_ramp   = SLO_MO_FACTOR if stype == "breakdown" else None

        schedule.append({
            "clip_id":      clip_id,
            "start_offset": start_offset,
            "duration":     duration,
            "effect":       effect,
            "flash_before": flash_before,
            "strobe":       do_strobe,
            "speed_ramp":   speed_ramp,
            "beat_time":    beat_t,
            "section_type": stype,
        })
        clip_playhead[clip_id] = start_offset + duration

    return schedule


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="karman_cut_hybrid — AI-tagged, Python-cut")
    parser.add_argument("--music",    required=True, type=Path)
    parser.add_argument("--clips",    type=Path)
    parser.add_argument("--files",    nargs="+", type=Path)
    parser.add_argument("--output",   type=Path, default=Path("karman_cuts"))
    parser.add_argument("--compress", action="store_true")
    parser.add_argument("--affinity", type=float, default=AFFINITY_WEIGHT,
                        help="Clip-to-section affinity weight 0.0–1.0 (default: 0.7)")
    args = parser.parse_args()

    print("\n╭──────────────────────────────────────────────────╮")
    print("│  KARMAN CUT HYBRID — Gemini tags, Python cuts  │")
    print("╰──────────────────────────────────────────────────╯\n")

    if not args.music.exists():
        raise FileNotFoundError(f"Music not found: {args.music}")

    args.output.mkdir(parents=True, exist_ok=True)
    clip_files = get_clip_files(args.clips, args.files)
    if not clip_files:
        raise FileNotFoundError("No video clips found")

    if args.compress:
        print(f"Building proxies...")
        clip_files = ensure_proxies(clip_files)

    client = _get_client()

    # Gemini analysis (both cached after first run)
    print("Analyzing audio...")
    song_analysis = analyze_audio_gemini(args.music, client)
    sections = song_analysis.get("sections", [])
    print(f"  tempo: {song_analysis.get('tempo')} | arc: {song_analysis.get('emotional_arc')}")

    print(f"\nTagging {len(clip_files)} clips...")
    clip_tags: dict[str, dict] = {}
    for cf in clip_files:
        tag = tag_clip_gemini(cf, client)
        clip_tags[cf.stem] = tag

    # Beat grid from librosa (always fresh — no API cost)
    beat_times, _ = detect_beats_and_sections(args.music)

    rng_seed = random.randint(0, 9999)
    print(f"\nSeed: {rng_seed}")
    rng = random.Random(rng_seed)
    clip_pool = []
    for p in clip_files:
        dur = probe_duration(p)
        offset = rng.uniform(0, max(0.0, dur * 0.75))
        clip_pool.append((p.stem, offset, p.name))
    clip_paths = {p.stem: p for p in clip_files}

    schedule = build_hybrid_cut_schedule(beat_times, sections, clip_pool, clip_tags, args.affinity, rng)
    print(f"✓ {len(schedule)} cuts planned\n")

    track_duration = probe_duration(args.music)
    output = versioned_output(args.output, "karman_hybrid")
    print(f"Output: {output}\n")

    with tempfile.TemporaryDirectory(prefix="karman_hybrid_") as tmp:
        tmp_dir = Path(tmp)
        segs_dir = tmp_dir / "segs"
        segs_dir.mkdir()

        white_flash = tmp_dir / "white.mp4"
        generate_flash_frame("white", FLASH_DURATION, white_flash)
        ordered: list[Path] = []
        clip_playhead = {c: off for c, off, _ in clip_pool}

        print(f"Extracting {len(schedule)} segments...")
        for idx, entry in enumerate(schedule):
            cid = entry["clip_id"]
            src = clip_paths[cid]
            start = clip_playhead[cid]
            dur   = entry["duration"]
            src_dur = probe_duration(src)
            if start + dur > src_dur:
                start = max(0.0, src_dur - dur - 0.1)

            if entry["strobe"]:
                ordered.extend(strobe_burst(4, FLASH_DURATION, segs_dir))
            if entry["flash_before"]:
                ordered.append(white_flash)

            seg = segs_dir / f"seg_{idx:05d}.mp4"
            if entry["speed_ramp"] is not None:
                speed_ramp_segment(src, start, dur, entry["speed_ramp"], seg)
            elif entry["effect"] == "zoom":
                zoom_pulse_segment(src, start, dur, 1.25, seg)
            else:
                extract_segment(src, start, dur, seg, entry["effect"], rng)
            ordered.append(seg)
            clip_playhead[cid] = start + dur

            if (idx + 1) % 50 == 0:
                print(f"  {idx+1}/{len(schedule)} done...")

        concat_file = tmp_dir / "concat.txt"
        build_concat_list(ordered, concat_file)
        print("\nAssembling...")
        final_assemble(concat_file, args.music, output, track_duration)

    dur  = probe_duration(output)
    size = output.stat().st_size / (1024 * 1024)
    print(f"\n╭──────────────────────────────────────────────────╮")
    print(f"│  DONE!                                           │")
    print(f"╰──────────────────────────────────────────────────╯")
    print(f"Output  : {output}")
    print(f"Duration: {dur:.1f}s  Size: {size:.0f}MB\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

```bash
uv run python scripts/karman_cut_hybrid.py \
  --music "input/audio/rav3rz (v2) 16th note kicks + NO OZONE.wav" \
  --clips "/Volumes/2025_exSSD_2tb/📷 Camera Footage & Photography/Photography/LA-Fires" \
  --compress
```

Expected: prints Gemini section analysis + emotional arc, tags clips (or hits cache), produces `karman_cuts/karman_hybrid_v01.mp4`. Re-run should print all cache hits and be significantly faster.

- [ ] **Step 3: Commit**

```bash
git add scripts/karman_cut_hybrid.py
git commit -m "feat: karman_cut_hybrid — affinity-weighted cut schedule and CLI"
```

---

## Phase 3 — AI-Directed (Tasks 8–9): karman_cut_ai

---

### Task 8: karman_cut_ai — Pydantic schemas and Claude cut planning

**Files:**
- Create: `scripts/karman_cut_ai.py`
- Create: `tests/test_karman_cut_ai.py`

- [ ] **Step 1: Write failing tests for schemas and plan expansion**

Create `tests/test_karman_cut_ai.py`:

```python
"""Tests for karman_cut_ai schemas and plan expansion logic."""
import random
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_effect_profile_defaults():
    from scripts.karman_cut_ai import EffectProfile
    ep = EffectProfile()
    assert ep.zoom_pulse == 0.0
    assert ep.slo_mo_factor == 1.0


def test_cut_plan_validates_section_types():
    from scripts.karman_cut_ai import CutPlan, SectionPlan, EffectProfile
    with pytest.raises(Exception):
        SectionPlan(
            start=0.0, end=10.0,
            section_type="invalid_type",
            cut_density="beat",
            preferred_clips=[],
            effect_profile=EffectProfile(),
            rationale="test",
        )


def test_section_plan_valid():
    from scripts.karman_cut_ai import SectionPlan, EffectProfile
    sp = SectionPlan(
        start=0.0, end=22.4,
        section_type="build",
        cut_density="2-beat",
        preferred_clips=["MVI_9536", "MVI_9540"],
        effect_profile=EffectProfile(zoom_pulse=0.3),
        rationale="Sparse opening, let tension build",
    )
    assert sp.section_type == "build"
    assert sp.effect_profile.zoom_pulse == 0.3


def test_expand_section_plan_beat_density(tmp_path):
    from scripts.karman_cut_ai import SectionPlan, EffectProfile, expand_section_plan
    # Create dummy clip files
    (tmp_path / "clip_a.mp4").touch()
    clip_paths = {"clip_a": tmp_path / "clip_a.mp4"}
    beat_times = [0.0, 0.46, 0.92, 1.38, 1.84, 2.30]
    sp = SectionPlan(
        start=0.0, end=2.5,
        section_type="drop",
        cut_density="beat",
        preferred_clips=["clip_a"],
        effect_profile=EffectProfile(flash=0.5),
        rationale="test",
    )
    entries = expand_section_plan(sp, beat_times, clip_paths, random.Random(42))
    assert len(entries) > 0
    for e in entries:
        assert e["clip_id"] in clip_paths
        assert e["duration"] > 0


def test_expand_section_plan_hold_density(tmp_path):
    from scripts.karman_cut_ai import SectionPlan, EffectProfile, expand_section_plan
    (tmp_path / "clip_a.mp4").touch()
    clip_paths = {"clip_a": tmp_path / "clip_a.mp4"}
    beat_times = [i * 0.46 for i in range(20)]
    sp = SectionPlan(
        start=0.0, end=9.0,
        section_type="breakdown",
        cut_density="hold",
        preferred_clips=["clip_a"],
        effect_profile=EffectProfile(speed_ramp=0.5, slo_mo_factor=0.5),
        rationale="test",
    )
    entries = expand_section_plan(sp, beat_times, clip_paths, random.Random(1))
    # hold = one cut every 4 beats → at most 5 from 20 beats
    assert len(entries) <= 5
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_karman_cut_ai.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create karman_cut_ai.py with schemas and expand_section_plan**

Create `scripts/karman_cut_ai.py`:

```python
#!/usr/bin/env python3
"""
karman_cut_ai.py — Gemini perceives, Claude plans, Python executes.

Gemini analyzes audio + tags clips (cached). Claude receives the full picture
and writes a section-level CutPlan. Python expands the plan to frame-level
timing and executes via FFmpeg.
"""

import argparse
import json
import os
import random
import tempfile
from pathlib import Path
from typing import Any, Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

from karman_core import (
    FLASH_DURATION,
    KARMAN_ANALYSIS_DIR,
    KARMAN_CLIP_TAGS_DIR,
    versioned_output,
    get_clip_files,
    probe_duration,
    ensure_proxies,
    generate_flash_frame,
    strobe_burst,
    extract_segment,
    speed_ramp_segment,
    zoom_pulse_segment,
    build_concat_list,
    final_assemble,
)
from karman_cut_hybrid import (
    analyze_audio_gemini,
    tag_clip_gemini,
    _get_client as _get_gemini_client,
)
from karman_cut_rave import detect_beats_and_sections

# ─── CONFIG ───────────────────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.5-flash"

VALID_SECTION_TYPES = {"build", "drop", "breakdown"}
VALID_CUT_DENSITIES = {"beat", "2-beat", "16th", "hold"}


# ─── PYDANTIC SCHEMAS ─────────────────────────────────────────────────────────

class EffectProfile(BaseModel):
    zoom_pulse: float = 0.0    # probability of zoom_pulse_segment
    flash:      float = 0.0    # probability of flash before cut
    strobe:     float = 0.0    # probability of strobe burst
    speed_ramp: float = 0.0    # probability of speed ramp
    slo_mo_factor: float = 1.0 # speed multiplier when speed_ramp fires (< 1 = slo-mo)


class SectionPlan(BaseModel):
    start:           float
    end:             float
    section_type:    str
    cut_density:     str
    preferred_clips: list[str]
    effect_profile:  EffectProfile
    rationale:       str

    @field_validator("section_type")
    @classmethod
    def validate_section_type(cls, v: str) -> str:
        if v not in VALID_SECTION_TYPES:
            raise ValueError(f"section_type must be one of {VALID_SECTION_TYPES}, got: {v!r}")
        return v

    @field_validator("cut_density")
    @classmethod
    def validate_cut_density(cls, v: str) -> str:
        if v not in VALID_CUT_DENSITIES:
            raise ValueError(f"cut_density must be one of {VALID_CUT_DENSITIES}, got: {v!r}")
        return v


class CutPlan(BaseModel):
    sections:       list[SectionPlan]
    overall_vision: str


# ─── PLAN EXPANSION ───────────────────────────────────────────────────────────

def expand_section_plan(
    section: SectionPlan,
    beat_times: list[float],
    clip_paths: dict[str, Path],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Expand a SectionPlan into frame-level cut entries."""
    beats_in_section = [t for t in beat_times if section.start <= t < section.end]
    if not beats_in_section:
        return []

    density = section.cut_density
    ep      = section.effect_profile
    pool    = [c for c in section.preferred_clips if c in clip_paths]
    if not pool:
        pool = list(clip_paths.keys())

    # Build the time grid for this section
    if density == "16th":
        grid: list[float] = []
        for i, bt in enumerate(beats_in_section):
            if i + 1 < len(beats_in_section):
                interval = (beats_in_section[i + 1] - bt) / 4
                grid.extend([bt + j * interval for j in range(4)])
            else:
                grid.append(bt)
    elif density == "2-beat":
        grid = beats_in_section[::2]
    elif density == "hold":
        # One cut every 4 beats
        grid = beats_in_section[::4] or [beats_in_section[0]]
    else:  # "beat"
        grid = beats_in_section

    entries: list[dict[str, Any]] = []
    pool_idx = 0
    for idx, t in enumerate(grid):
        if idx + 1 < len(grid):
            dur = grid[idx + 1] - t
        else:
            dur = min(0.5, section.end - t)
        if dur < FLASH_DURATION:
            continue

        clip_id = pool[pool_idx % len(pool)]
        pool_idx += 1

        entries.append({
            "clip_id":      clip_id,
            "start_offset": 0.0,   # playhead managed in main()
            "duration":     dur,
            "beat_time":    t,
            "section_type": section.section_type,
            "flash_before": rng.random() < ep.flash,
            "strobe":       rng.random() < ep.strobe,
            "zoom":         rng.random() < ep.zoom_pulse,
            "speed_ramp":   ep.slo_mo_factor if rng.random() < ep.speed_ramp else None,
        })

    return entries


# ─── CLAUDE CUT PLANNING ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a creative director for trance and hyperpop music videos.
You write cut plans for an automated video editor.
Your visual language:
- Builds: sparse, anticipatory, accelerating zoom pulses toward the drop
- Drops: maximum density (16th-note cuts), heavy flash and strobe, chaotic clip rotation
- Breakdowns: long holds, slo-mo (speed_ramp < 1.0), no flash, ethereal
You return only valid JSON matching the CutPlan schema. No markdown, no explanation.

CutPlan schema:
{
  "overall_vision": "string — one vivid sentence about the visual arc",
  "sections": [
    {
      "start": float,
      "end": float,
      "section_type": "build" | "drop" | "breakdown",
      "cut_density": "beat" | "2-beat" | "16th" | "hold",
      "preferred_clips": ["clip_stem_1", "clip_stem_2"],
      "effect_profile": {
        "zoom_pulse": float 0-1,
        "flash": float 0-1,
        "strobe": float 0-1,
        "speed_ramp": float 0-1,
        "slo_mo_factor": float (0.25-1.0 for slo-mo, 1.0 = no ramp)
      },
      "rationale": "string — one sentence on why"
    }
  ]
}
"""


def plan_cut_with_claude(
    song_analysis: dict,
    clip_tags: dict[str, dict],
    track_duration: float,
) -> CutPlan:
    """Send song structure + clip tags to Claude, receive and validate CutPlan."""
    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment or .env")

    client = anthropic.Anthropic(api_key=key)

    user_content = json.dumps({
        "song_analysis": song_analysis,
        "available_clips": clip_tags,
        "track_duration_seconds": track_duration,
    }, indent=2)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_content,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    )

    raw = response.content[0].text
    data = json.loads(raw)
    return CutPlan.model_validate(data)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_karman_cut_ai.py -v
```

Expected: all 5 tests PASS. (Note: `test_cut_plan_validates_section_types` expects a `ValidationError` from pydantic — verify it raises.)

- [ ] **Step 5: Commit**

```bash
git add scripts/karman_cut_ai.py tests/test_karman_cut_ai.py
git commit -m "feat: karman_cut_ai — Pydantic CutPlan schemas, expand_section_plan, Claude planning call"
```

---

### Task 9: karman_cut_ai — assembly and CLI

**Files:**
- Modify: `scripts/karman_cut_ai.py`

- [ ] **Step 1: Add ANTHROPIC_API_KEY to .env (if not already present)**

```bash
grep -q ANTHROPIC_API_KEY .env || echo "ANTHROPIC_API_KEY=" >> .env
```

Open `.env` and fill in the key value if not already set.

- [ ] **Step 2: Append main() to karman_cut_ai.py**

Append to `scripts/karman_cut_ai.py`:

```python
# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="karman_cut_ai — Gemini + Claude directed cut")
    parser.add_argument("--music",    required=True, type=Path)
    parser.add_argument("--clips",    type=Path)
    parser.add_argument("--files",    nargs="+", type=Path)
    parser.add_argument("--output",   type=Path, default=Path("karman_cuts"))
    parser.add_argument("--compress", action="store_true")
    args = parser.parse_args()

    print("\n╭────────────────────────────────────────────────────────╮")
    print("│  KARMAN CUT AI — Gemini perceives, Claude plans        │")
    print("╰────────────────────────────────────────────────────────╯\n")

    if not args.music.exists():
        raise FileNotFoundError(f"Music not found: {args.music}")

    args.output.mkdir(parents=True, exist_ok=True)
    clip_files = get_clip_files(args.clips, args.files)
    if not clip_files:
        raise FileNotFoundError("No video clips found")

    if args.compress:
        clip_files = ensure_proxies(clip_files)

    gemini_client = _get_gemini_client()

    print("Step 1/3 — Gemini: analyzing audio...")
    song_analysis = analyze_audio_gemini(args.music, gemini_client)
    print(f"  emotional arc: {song_analysis.get('emotional_arc')}\n")

    print(f"Step 2/3 — Gemini: tagging {len(clip_files)} clips...")
    clip_tags: dict[str, dict] = {}
    for cf in clip_files:
        tag = tag_clip_gemini(cf, gemini_client)
        clip_tags[cf.stem] = tag
    print(f"  ✓ {len(clip_tags)} clips tagged\n")

    track_duration = probe_duration(args.music)
    beat_times, _ = detect_beats_and_sections(args.music)
    clip_paths = {p.stem: p for p in clip_files}

    print("Step 3/3 — Claude: writing cut plan...")
    cut_plan = plan_cut_with_claude(song_analysis, clip_tags, track_duration)

    print(f"\n  Vision: {cut_plan.overall_vision}\n")
    for s in cut_plan.sections:
        print(f"  [{s.section_type.upper():10s}] {s.start:.1f}s–{s.end:.1f}s | "
              f"{s.cut_density} cuts | {s.rationale}")

    # Expand plan into cut entries
    rng_seed = random.randint(0, 9999)
    rng = random.Random(rng_seed)
    print(f"\nSeed: {rng_seed}")

    all_entries: list[dict[str, Any]] = []
    for section in cut_plan.sections:
        entries = expand_section_plan(section, beat_times, clip_paths, rng)
        all_entries.extend(entries)

    print(f"✓ {len(all_entries)} total cuts\n")

    output = versioned_output(args.output, "karman_ai")
    print(f"Output: {output}\n")

    with tempfile.TemporaryDirectory(prefix="karman_ai_") as tmp:
        tmp_dir = Path(tmp)
        segs_dir = tmp_dir / "segs"
        segs_dir.mkdir()

        white_flash = tmp_dir / "white.mp4"
        generate_flash_frame("white", FLASH_DURATION, white_flash)
        ordered: list[Path] = []
        clip_playhead: dict[str, float] = {}

        # Initialize playheads with random offsets
        for p in clip_files:
            dur = probe_duration(p)
            clip_playhead[p.stem] = rng.uniform(0, max(0.0, dur * 0.75))

        print(f"Extracting {len(all_entries)} segments...")
        for idx, entry in enumerate(all_entries):
            cid = entry["clip_id"]
            if cid not in clip_paths:
                continue
            src   = clip_paths[cid]
            start = clip_playhead.get(cid, 0.0)
            dur   = entry["duration"]
            src_dur = probe_duration(src)
            if start + dur > src_dur:
                start = max(0.0, src_dur - dur - 0.1)

            if entry.get("strobe"):
                ordered.extend(strobe_burst(4, FLASH_DURATION, segs_dir))
            if entry.get("flash_before"):
                ordered.append(white_flash)

            seg = segs_dir / f"seg_{idx:05d}.mp4"
            if entry.get("speed_ramp") is not None:
                speed_ramp_segment(src, start, dur, entry["speed_ramp"], seg)
            elif entry.get("zoom"):
                zoom_pulse_segment(src, start, dur, 1.25, seg)
            else:
                extract_segment(src, start, dur, seg, "normal", rng)
            ordered.append(seg)
            clip_playhead[cid] = start + dur

            if (idx + 1) % 50 == 0:
                print(f"  {idx+1}/{len(all_entries)} done...")

        concat_file = tmp_dir / "concat.txt"
        build_concat_list(ordered, concat_file)
        print("\nAssembling with music...")
        final_assemble(concat_file, args.music, output, track_duration)

    dur  = probe_duration(output)
    size = output.stat().st_size / (1024 * 1024)
    print(f"\n╭────────────────────────────────────────────────────────╮")
    print(f"│  DONE!                                                 │")
    print(f"╰────────────────────────────────────────────────────────╯")
    print(f"Output  : {output}")
    print(f"Duration: {dur:.1f}s  Size: {size:.0f}MB\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests across `test_karman_core.py`, `test_karman_cut_rave.py`, `test_karman_cut_hybrid.py`, `test_karman_cut_ai.py` PASS.

- [ ] **Step 4: Smoke test the AI script**

```bash
uv run python scripts/karman_cut_ai.py \
  --music "input/audio/rav3rz (v2) 16th note kicks + NO OZONE.wav" \
  --clips "/Volumes/2025_exSSD_2tb/📷 Camera Footage & Photography/Photography/LA-Fires" \
  --compress
```

Expected: prints Gemini arc, Claude's vision + per-section rationale lines, then assembles `karman_cuts/karman_ai_v01.mp4`.

- [ ] **Step 5: Final commit**

```bash
git add scripts/karman_cut_ai.py .env
git commit -m "feat: karman_cut_ai — Claude-directed cut planning, full CLI and assembly"
```

---

## Verification Checklist

- [ ] `uv run pytest tests/ -v` — all tests green
- [ ] `karman_cut_rave.py` smoke test: BPM normalizes to 120–180, sections labeled, output file produced
- [ ] Re-run `karman_cut_rave.py` — different seed, different cut
- [ ] `karman_cut_hybrid.py` smoke test: Gemini analysis printed, cache hits on re-run
- [ ] `karman_cut_ai.py` smoke test: Claude vision + rationale lines printed, output produced
- [ ] All three scripts produce files in `karman_cuts/` with correct versioning (no overwrites)
