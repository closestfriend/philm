# video-praxis Phase 1 — Shared Media Helpers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the ffprobe/ffmpeg helpers that are copy-pasted across the montage scripts into one tested module, and repoint the existing scripts at it — with zero behavior change.

**Architecture:** Create `scripts/media_utils.py` as the single source of truth for clip probing, the 1920×1080 normalize filter, and video-file discovery. Repoint `drift_core.py`, `drift_cut.py`, `ez_mv_core.py`, and `carti_cut.py` to import from it instead of carrying private copies. This is the first, lowest-risk step of the `video-praxis` consolidation (full design: `docs/superpowers/specs/2026-06-01-video-praxis-consolidation-design.md`). The module is deliberately created in `scripts/` (same dir as its consumers → no import-path changes); it relocates to `shared/media.py` during the later rename phase.

**Tech Stack:** Python 3.11+, `subprocess` + `ffprobe`/`ffmpeg`, `pytest`. No new dependencies.

**Prerequisite:** The `2026-05-31-drive-consolidation.md` cleanup (Phases 1–3 at least) should be done first, but this plan does not depend on it — it only touches `scripts/` + `tests/`.

---

## File Structure

- **Create** `scripts/media_utils.py` — shared helpers: `ffprobe_duration`, `ffprobe_resolution`, `get_video_files`, `normalize_filter`, `VIDEO_EXTENSIONS`. One responsibility: media probing + the canonical scale/pad filter string.
- **Create** `tests/test_media_utils.py` — unit tests using a tiny ffmpeg-generated fixture clip.
- **Modify** `scripts/drift_core.py` — replace its private `ffprobe_duration`/`ffprobe_resolution`/`get_video_files`/`VIDEO_EXTENSIONS` with imports.
- **Modify** `scripts/drift_cut.py` — same.
- **Modify** `scripts/ez_mv_core.py` — import `ffprobe_duration` (aliased to its local name `probe_duration`).
- **Modify** `scripts/carti_cut.py` — import `ffprobe_duration` (aliased to `probe_duration`).

> Note: `carti_cut.py` keeps its own clip-discovery logic in `main()` (it has `--recursive`/`--exclude` flags the others don't), so we only share `probe_duration` there — not `get_video_files`. DRY where identical; don't force-fit where behavior differs.

---

### Task 1: Create the shared module + tests

**Files:**
- Create: `scripts/media_utils.py`
- Create: `tests/test_media_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_media_utils.py
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import media_utils  # noqa: E402


@pytest.fixture
def sample_clip(tmp_path):
    """A real 2-second 640x480 H.264 clip generated with ffmpeg lavfi."""
    out = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=size=640x480:rate=30:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True,
    )
    return out


def test_ffprobe_duration(sample_clip):
    assert media_utils.ffprobe_duration(sample_clip) == pytest.approx(2.0, abs=0.2)


def test_ffprobe_resolution(sample_clip):
    assert media_utils.ffprobe_resolution(sample_clip) == (640, 480)


def test_get_video_files_filters_by_extension(tmp_path, sample_clip):
    (tmp_path / "notes.txt").write_text("not a video")
    files = media_utils.get_video_files(tmp_path)
    assert [f.name for f in files] == ["clip.mp4"]


def test_get_video_files_accepts_comma_list(sample_clip):
    files = media_utils.get_video_files(f"{sample_clip},{sample_clip}")
    assert len(files) == 2 and all(isinstance(f, Path) for f in files)


def test_normalize_filter_default_1080p():
    assert media_utils.normalize_filter() == (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2 && uv run pytest tests/test_media_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'media_utils'`.

- [ ] **Step 3: Write the module**

```python
# scripts/media_utils.py
"""media_utils.py — shared ffprobe/ffmpeg helpers for the montage scripts.

Single source of truth for clip probing, video-file discovery, and the canonical
1920x1080 normalize (scale+pad) filter. Previously copy-pasted into drift_core.py,
drift_cut.py, ez_mv_core.py, and carti_cut.py.

Relocates to shared/media.py during the video-praxis rename phase.
"""

import json
import subprocess
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mov", ".mp4", ".avi", ".mkv", ".mpg", ".mpeg", ".mts", ".m4v", ".mxf", ".webm",
}


def ffprobe_duration(path) -> float:
    """Return container duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def ffprobe_resolution(path) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def get_video_files(path) -> list[Path]:
    """A directory → sorted video files within it; otherwise a comma-separated list of paths."""
    p = Path(path)
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS)
    return [Path(v.strip()) for v in str(path).split(",")]


def normalize_filter(width: int = 1920, height: int = 1080) -> str:
    """Canonical scale-to-fit + pad-to-frame filter string."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2 && uv run pytest tests/test_media_utils.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add scripts/media_utils.py tests/test_media_utils.py
git commit -m "feat: shared media_utils module for montage scripts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Repoint `drift_core.py` and `drift_cut.py`

**Files:**
- Modify: `scripts/drift_core.py` (remove private helper defs + `VIDEO_EXTENSIONS`; import from `media_utils`)
- Modify: `scripts/drift_cut.py` (same)

- [ ] **Step 1: Edit `drift_core.py` — replace the helper block with an import**

Remove the module-level `VIDEO_EXTENSIONS` set and the `ffprobe_duration`, `ffprobe_resolution`, `get_video_files` function definitions (lines ~16–45). Replace with this import near the top (after `from pathlib import Path`):

```python
from media_utils import VIDEO_EXTENSIONS, ffprobe_duration, ffprobe_resolution, get_video_files  # noqa: F401
```

Leave `extract_clip` etc. untouched (they call `ffprobe_duration` by the same name, now imported).

- [ ] **Step 2: Edit `drift_cut.py` — same replacement**

Remove its `VIDEO_EXTENSIONS` set and the `ffprobe_duration`, `ffprobe_resolution`, `get_video_files` defs (lines ~20–49). Add near the top (after `from pathlib import Path`):

```python
from media_utils import VIDEO_EXTENSIONS, ffprobe_duration, ffprobe_resolution, get_video_files  # noqa: F401
```

- [ ] **Step 3: Verify both still import cleanly**

Run:
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/scripts
python -c "import drift_core; import drift_cut; print('drift imports OK')"
```
Expected: `drift imports OK` (no ImportError, no NameError).

- [ ] **Step 4: Smoke-test a real drift render (behavior unchanged)**

Run (generates a 3s clip + 3s tone, then renders one drift segment set):
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
T=$(mktemp -d)
ffmpeg -y -f lavfi -i testsrc=size=640x480:rate=30:duration=3 -c:v libx264 -pix_fmt yuv420p "$T/v1.mp4" -loglevel error
ffmpeg -y -f lavfi -i sine=frequency=440:duration=3 "$T/a.wav" -loglevel error
python scripts/drift_cut.py --videos "$T" --audio "$T/a.wav" --output-dir "$T/out" --min-hold 1 --max-hold 2 --seed 1
ls "$T/out"/*.mp4 && echo "DRIFT RENDER OK"
rm -rf "$T"
```
Expected: a `drift_cut_v01.mp4` is produced; prints `DRIFT RENDER OK`.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add scripts/drift_core.py scripts/drift_cut.py
git commit -m "refactor: drift scripts use shared media_utils

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Repoint `ez_mv_core.py` and `carti_cut.py`

**Files:**
- Modify: `scripts/ez_mv_core.py` (remove private `probe_duration`; import `ffprobe_duration as probe_duration`)
- Modify: `scripts/carti_cut.py` (same)

- [ ] **Step 1: Edit `ez_mv_core.py`**

Remove the `probe_duration` function definition (lines ~33–39). Add near the top imports (after `import librosa`):

```python
from media_utils import ffprobe_duration as probe_duration  # noqa: F401
```

All existing `probe_duration(...)` call sites keep working unchanged.

- [ ] **Step 2: Edit `carti_cut.py`**

Remove its `probe_duration` function definition (lines ~57–63). Add near the top imports (after `import librosa`):

```python
from media_utils import ffprobe_duration as probe_duration  # noqa: F401
```

- [ ] **Step 3: Verify imports**

Run:
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/scripts
python -c "import ez_mv_core; import carti_cut; print('strobe imports OK')"
```
Expected: `strobe imports OK`.

- [ ] **Step 4: Smoke-test a carti_cut render**

Run:
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
T=$(mktemp -d)
ffmpeg -y -f lavfi -i testsrc=size=640x480:rate=30:duration=4 -c:v libx264 -pix_fmt yuv420p "$T/v1.mp4" -loglevel error
ffmpeg -y -f lavfi -i sine=frequency=200:duration=4 "$T/a.wav" -loglevel error
python scripts/carti_cut.py --music "$T/a.wav" --clips "$T" --output "$T/out"
ls "$T/out"/*.mp4 && echo "CARTI RENDER OK"
rm -rf "$T"
```
Expected: a `carti_cut_v01.mp4` is produced; prints `CARTI RENDER OK`.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2
git add scripts/ez_mv_core.py scripts/carti_cut.py
git commit -m "refactor: strobe scripts use shared media_utils

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Final verification — full suite + no stray duplicates

**Files:** none modified.

- [ ] **Step 1: Run the whole test suite**

Run: `cd /Volumes/2025_exSSD_2tb/video-analyzer-v2 && uv run pytest -q`
Expected: all tests pass (including the new `test_media_utils.py`).

- [ ] **Step 2: Confirm the duplicated defs are gone from the consumers**

Run:
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/scripts
grep -nE 'def ffprobe_duration|def ffprobe_resolution|def probe_duration' \
  drift_core.py drift_cut.py ez_mv_core.py carti_cut.py || echo "No private duplicate defs remain (correct)"
```
Expected: `No private duplicate defs remain (correct)` — the only definitions now live in `media_utils.py`.

- [ ] **Step 3: Confirm `ez_mv_app.py` (the Streamlit UI) still imports its core**

Run:
```bash
cd /Volumes/2025_exSSD_2tb/video-analyzer-v2/scripts
python -c "import ast; ast.parse(open('ez_mv_app.py').read()); print('ez_mv_app parses')"
python -c "import ez_mv_core, drift_core; print('UI cores import OK')"
```
Expected: both print success (the app imports `ez_mv_core`/`drift_core`, which now pull from `media_utils`).

**✅ DONE — Phase 1 complete.** The montage scripts share one tested media-helper module; behavior is unchanged (verified by real renders); the duplication called out in `LANDSCAPE.md` is reduced. Next plan: **Phase 2 — montage engine dedup + canonical `strobe`/`drift`** (folds `carti_cut`'s zoom/shrink/flash/proxy features into the core; minds the seed gotcha + feature gap).

---

## Self-Review

- **Spec coverage:** implements migration step 1 ("Stand up `shared/`") from the consolidation spec. Other steps are explicitly out of scope (their own plans).
- **Placeholder scan:** none — every step has exact code/commands and expected output.
- **Consistency:** `ffprobe_duration` is the canonical name; `ez_mv_core.py`/`carti_cut.py` alias it to their existing `probe_duration` call-name, so no call sites change. `VIDEO_EXTENSIONS` in the shared module is the union of the consumers' sets (superset → no file silently excluded).
- **Risk note:** the shared `ffprobe_duration` uses `-v quiet` (drift's variant) rather than carti/ez_mv's `-v error`; both return the same duration float, and the smoke tests in Tasks 2–3 confirm real renders are unaffected.
