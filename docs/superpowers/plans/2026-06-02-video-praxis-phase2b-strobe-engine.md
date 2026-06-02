# video-praxis Phase 2b — Unify the Strobe Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development with the FULL two-stage review (spec compliance + code quality) per task. Steps use checkbox (`- [ ]`).
>
> ⛔ **EXECUTION GATE — do NOT start until BOTH are true:**
> 1. The user has finished/parked their active `carti_cut.py` work and the git tree is clean (no uncommitted `carti_cut` changes — if any exist, commit/stash them as their OWN thing first, per the user's choice).
> 2. The user has explicitly said "go" on this plan.
> Run all work on a branch `phase2b-strobe-engine`; merge only when the behavior-preservation gate (Task 6) is green.

**Goal:** Collapse the duplicated beat-sync montage engine so it lives in exactly one place (`ez_mv_core.py`), and make `carti_cut.py` a thin CLI over it — without changing carti_cut's features or output shape.

**Architecture:** `ez_mv_core.py` is already the more evolved engine (lip-sync, cut-density, philm-offset, progress callback, duration caching) but it LACKS four things `carti_cut.py` has: in-frame `shrink`/`zoom` effects, a black flash frame, proxy compression, and per-segment effect assignment in the schedule. We additively port those four into `ez_mv_core` (all gated behind parameters that default to OFF, so existing `ez_mv_app.py` behavior is untouched), then rewrite `carti_cut.py` as a thin CLI that calls the unified engine with effects enabled. `apply_cut_density` (currently duplicated in both files) ends up only in `ez_mv_core`.

**Tech Stack:** Python 3.11, ffmpeg/ffprobe subprocess, librosa, pytest. No new deps.

**Design references:** `docs/superpowers/specs/2026-06-01-video-praxis-consolidation-design.md`, `LANDSCAPE.md` (strobe-lineage table + feature-gap + seed gotcha).

---

## ⚠️ The one design decision to settle BEFORE execution: seed reproducibility

`carti_cut.build_cut_schedule` and `ez_mv_core.build_cut_schedule` draw from their RNG in **different orders**. carti draws: `stutter → clip → flash → effect-roll`. ez_mv draws: `stutter → clip → flash` (no effect roll). carti ALSO seeds per-segment `extract_segment(..., rng=random.Random(seg_idx))` for effect randomization. So routing carti through the unified engine **changes the seed→output mapping** unless we replicate carti's exact draw order.

Unlike drift, **`carti_cut` prints its seed every run** ("Random seed: N — rerun with this to reproduce"), so you *may* have noted good seeds. Two options — pick one before Task 5:

- **Option A (simpler): accept the seed change.** Same as drift. Old printed seeds won't reproduce. Lowest effort.
- **Option B (preserve seeds): replicate carti's exact RNG draw order** in the unified `build_cut_schedule` when effects are enabled (draw the effect-roll in the same position; keep the per-segment `random.Random(seg_idx)` for effect params). More work, but old carti seeds keep reproducing.

**This plan implements Option B by default** (carti's draw order preserved), because seed-printing implies you rely on it. If you'd rather take Option A, drop the effect-roll-ordering note in Task 2 and the per-seg rng in Task 4. Either way, Task 6's gate renders before/after with a fixed seed and compares.

---

## Feature delta (what we're porting INTO ez_mv_core)

| Capability | `ez_mv_core` today | `carti_cut` today | Action |
|---|---|---|---|
| in-frame `shrink` / `zoom` effects | ✗ | ✓ (`extract_segment` branches) | port (Task 1) |
| per-segment effect assignment in schedule | ✗ | ✓ (`effect` in entry) | port (Task 2) |
| black flash frame | white only | white + black | port (Task 3) |
| proxy compression (cached 1080p) | ✗ | ✓ (`ensure_proxies`) | port (Task 3) |
| cut density / philm-offset / progress / lip-sync | ✓ | density only | already in ez_mv_core ✓ |

---

## File Structure

- **Modify** `scripts/ez_mv_core.py` — add: `effect`+`rng` params to `extract_segment`; `shrink_prob`/`zoom_prob` to `build_cut_schedule` (+ `effect` in each entry); `generate_flash_frames` returning white+black; proxy helpers (`PROXY_DIR`, `get_proxy_path`, `compress_to_proxy`, `ensure_proxies`); thread `effect` + optional black-flash through `assemble`.
- **Rewrite** `scripts/carti_cut.py` — thin CLI: arg parsing + pool construction (its `--recursive`/`--exclude`/`--lipsync`/`--compress`/`--density` flags) → call `ez_mv_core` engine with effects enabled. Delete its duplicated engine functions and its copy of `apply_cut_density`.
- **Create** `tests/test_strobe_engine.py` — unit tests for the ported pieces.

All effect/proxy/black-flash code below is taken VERBATIM from the current `carti_cut.py` so the port is behavior-identical.

---

### Task 1: Port `shrink`/`zoom` effects into `ez_mv_core.extract_segment`

**Files:** Modify `scripts/ez_mv_core.py`; Test `tests/test_strobe_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_strobe_engine.py
import random, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import ez_mv_core  # noqa: E402

@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=size=640x480:rate=30:duration=3",
                    "-c:v","libx264","-pix_fmt","yuv420p",str(out)], check=True, capture_output=True)
    return out

@pytest.mark.parametrize("effect", ["normal", "shrink", "zoom"])
def test_extract_segment_effects_produce_1080p(clip, tmp_path, effect):
    out = tmp_path / f"{effect}.mp4"
    ez_mv_core.extract_segment(clip, 0.0, 1.0, out, effect=effect, rng=random.Random(0))
    assert out.exists()
    assert ez_mv_core.ffprobe_resolution(out) == (1920, 1080)
```

Note: this test imports `ffprobe_resolution` via `ez_mv_core` — add `from media_utils import ffprobe_resolution` to `ez_mv_core.py` imports if not already present (it currently imports only `ffprobe_duration as probe_duration`).

- [ ] **Step 2: Run it, expect FAIL** — `uv run --extra dev pytest tests/test_strobe_engine.py -v` → `TypeError: extract_segment() got an unexpected keyword argument 'effect'`.

- [ ] **Step 3: Replace `ez_mv_core.extract_segment` with the effect-aware version** (verbatim port from carti_cut):

```python
def extract_segment(source, start, duration, output, effect="normal", rng=None):
    """Extract a video-only 1920x1080 segment with optional in-frame effect."""
    if effect == "shrink":
        scale_pct = (rng.uniform(0.4, 0.7) if rng else 0.55)
        inner_w = int(1920 * scale_pct)
        inner_h = int(1080 * scale_pct)
        off_x = (rng.randint(0, 1920 - inner_w) if rng else (1920 - inner_w) // 2)
        off_y = (rng.randint(0, 1080 - inner_h) if rng else (1080 - inner_h) // 2)
        vf = (f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
              f"pad=1920:1080:{off_x}:{off_y}:black,fps={TARGET_FPS}")
    elif effect == "zoom":
        crop_pct = (rng.uniform(0.4, 0.7) if rng else 0.55)
        vf = (f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
              f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,"
              f"crop=iw*{crop_pct:.2f}:ih*{crop_pct:.2f}:(iw-iw*{crop_pct:.2f})/2:(ih-ih*{crop_pct:.2f})/2,"
              f"scale={OUTPUT_SIZE},fps={TARGET_FPS}")
    else:
        vf = (f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
              f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2,fps={TARGET_FPS}")
    run([
        "ffmpeg", "-y", "-ss", f"{start:.4f}", "-accurate_seek",
        "-i", str(source), "-t", f"{duration:.4f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-an", str(output),
    ])
```

- [ ] **Step 4: Run tests, expect 3 passed** — `uv run --extra dev pytest tests/test_strobe_engine.py -v`.

- [ ] **Step 5: Commit** — `git add scripts/ez_mv_core.py tests/test_strobe_engine.py && git commit -m "feat: in-frame shrink/zoom effects in ez_mv_core.extract_segment\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"`

---

### Task 2: Add effect assignment to `ez_mv_core.build_cut_schedule` (default OFF)

**Files:** Modify `scripts/ez_mv_core.py`; Test `tests/test_strobe_engine.py`

- [ ] **Step 1: Add the failing test**

```python
def test_schedule_effects_default_off():
    beats = [i * 0.5 for i in range(20)]
    clips = [{"path": Path("a.mp4"), "offset": 0.0}]
    sched, _ = ez_mv_core.build_cut_schedule(beats, clips, 100.0, flash_prob=0, stutter_prob=0, seed=1)
    assert all(e.get("effect", "normal") == "normal" for e in sched)

def test_schedule_effects_when_enabled():
    beats = [i * 0.5 for i in range(60)]
    clips = [{"path": Path("a.mp4"), "offset": 0.0}]
    sched, _ = ez_mv_core.build_cut_schedule(beats, clips, 100.0, flash_prob=0, stutter_prob=0,
                                             seed=1, shrink_prob=0.5, zoom_prob=0.3)
    kinds = {e["effect"] for e in sched}
    assert kinds & {"shrink", "zoom"}  # at least one non-normal assigned
```

- [ ] **Step 2: Run, expect FAIL** — `build_cut_schedule() got an unexpected keyword argument 'shrink_prob'`.

- [ ] **Step 3: Add `shrink_prob`/`zoom_prob` params and effect roll.** In `ez_mv_core.build_cut_schedule`, add to the signature: `shrink_prob: float = 0.0, zoom_prob: float = 0.0`. Then inside the loop, AFTER the `flash_before` draw and BEFORE building the entry dict, add (this draw-order placement matches carti for Option B seed-compat):

```python
        roll = rng.random()
        if roll < shrink_prob:
            effect = "shrink"
        elif roll < shrink_prob + zoom_prob:
            effect = "zoom"
        else:
            effect = "normal"
```

and add `"effect": effect,` to the appended schedule entry dict. With both probs 0, `effect` is always `"normal"` → no behavior change for existing `ez_mv_app` callers.

- [ ] **Step 4: Run, expect 2 new tests passed** (5 total in file).

- [ ] **Step 5: Commit** — `feat: optional per-segment effect assignment in build_cut_schedule`

---

### Task 3: Port black flash + proxy compression into `ez_mv_core`

**Files:** Modify `scripts/ez_mv_core.py`; Test `tests/test_strobe_engine.py`

- [ ] **Step 1: Add failing tests**

```python
def test_generate_flash_frames_white_and_black(tmp_path):
    white, black = ez_mv_core.generate_flash_frames(tmp_path)
    assert white.exists() and black.exists()

def test_ensure_proxies_creates_and_caches(clip, tmp_path, monkeypatch):
    monkeypatch.setattr(ez_mv_core, "PROXY_DIR", tmp_path / "proxies")
    proxies = ez_mv_core.ensure_proxies([clip])
    assert len(proxies) == 1 and proxies[0].exists()
    mtime = proxies[0].stat().st_mtime
    ez_mv_core.ensure_proxies([clip])  # second call should reuse, not rebuild
    assert proxies[0].stat().st_mtime == mtime
```

- [ ] **Step 2: Run, expect FAIL** (`generate_flash_frames`/`PROXY_DIR`/`ensure_proxies` not defined).

- [ ] **Step 3: Add the proxy helpers + replace `generate_flash_frame` with `generate_flash_frames`** (verbatim port from carti_cut). Add near the top of `ez_mv_core.py` after the constants:

```python
PROXY_DIR = Path.home() / ".ez_mv_proxies"


def get_proxy_path(source: Path) -> Path:
    key = f"{source.parent.name}_{source.stem}"
    return PROXY_DIR / f"{key}.mp4"


def compress_to_proxy(source: Path, proxy: Path):
    run([
        "ffmpeg", "-y", "-i", str(source),
        "-vf", f"scale={OUTPUT_SIZE}:force_original_aspect_ratio=decrease,"
               f"pad={OUTPUT_SIZE}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", str(proxy),
    ])


def ensure_proxies(clip_files: list[Path]) -> list[Path]:
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    proxies = []
    for source in clip_files:
        proxy = get_proxy_path(source)
        if not proxy.exists():
            compress_to_proxy(source, proxy)
        proxies.append(proxy)
    return proxies
```

Replace `generate_flash_frame` (white-only) with `generate_flash_frames` returning both (keep a `generate_flash_frame` alias returning just white so `ez_mv_app.py` keeps working):

```python
def generate_flash_frames(tmp_dir: Path) -> tuple[Path, Path]:
    white = tmp_dir / "white_flash.mp4"
    black = tmp_dir / "black_flash.mp4"
    for path, color in ((white, "white"), (black, "black")):
        run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color={color}:s={OUTPUT_SIZE_LAVFI}:d={FLASH_DURATION:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-r", str(TARGET_FPS), str(path),
        ])
    return white, black


def generate_flash_frame(tmp_dir: Path) -> Path:
    """Back-compat: white flash only (used by ez_mv_app)."""
    return generate_flash_frames(tmp_dir)[0]
```

- [ ] **Step 4: Run, expect tests passed.**
- [ ] **Step 5: Commit** — `feat: black flash + proxy compression in ez_mv_core`

---

### Task 4: Thread `effect` through `ez_mv_core.assemble`

**Files:** Modify `scripts/ez_mv_core.py`; Test `tests/test_strobe_engine.py`

- [ ] **Step 1: Add failing integration test** (real render through assemble with an effect-bearing schedule):

```python
def test_assemble_with_effects(clip, tmp_path):
    beats = [i * 0.5 for i in range(8)]
    clips = [{"path": clip, "offset": 0.0}]
    sched, _ = ez_mv_core.build_cut_schedule(beats, clips, 4.0, flash_prob=0, stutter_prob=0,
                                             seed=1, shrink_prob=0.5, zoom_prob=0.3)
    white, _black = ez_mv_core.generate_flash_frames(tmp_path)
    music = tmp_path / "m.wav"
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=200:duration=4",str(music)],
                   check=True, capture_output=True)
    out = tmp_path / "out.mp4"
    ez_mv_core.assemble(sched, white, music, out, 4.0)
    assert out.exists() and ez_mv_core.ffprobe_duration(out) == pytest.approx(4.0, abs=0.3)
```

- [ ] **Step 2: Run, expect FAIL** (assemble ignores `effect`, but the test mainly asserts it still renders; it will pass-but-without-effects — so first assert it currently renders, then in Step 3 wire the effect through and keep it green).

- [ ] **Step 3: In `ez_mv_core.assemble`, pass the per-entry effect + a per-segment rng to `extract_segment`.** Change the non-flash extract call from `extract_segment(src, start, duration, seg_path)` to:

```python
            extract_segment(src, start, duration, seg_path,
                            effect=entry.get("effect", "normal"),
                            rng=random.Random(idx))
```

(`random` is already imported in `ez_mv_core`.) This matches carti's per-segment `random.Random(seg_idx)` effect seeding (Option B).

- [ ] **Step 4: Run, expect passed.**
- [ ] **Step 5: Commit** — `feat: ez_mv_core.assemble honors per-segment effect`

---

### Task 5: Rewrite `carti_cut.py` as a thin CLI over `ez_mv_core`

**Files:** Rewrite `scripts/carti_cut.py`

- [ ] **Step 1: Capture a BEFORE baseline (for the Task 6 gate).** On a clean tree, before editing, render with a fixed seed and record the schedule via the existing `inspect_schedule.py`:

```bash
T=$(mktemp -d)
ffmpeg -y -f lavfi -i testsrc=size=640x480:rate=30:duration=8 -c:v libx264 -pix_fmt yuv420p "$T/v1.mp4" -loglevel error
ffmpeg -y -f lavfi -i "aevalsrc='0.6*sin(2*PI*880*t)*lt(mod(t\,0.5)\,0.04)':d=8:s=44100" "$T/click.wav" -loglevel error
.venv/bin/python scripts/carti_cut.py --music "$T/click.wav" --clips "$T" --output "$T/before"   # note the printed seed N
# save: cp -r "$T" /tmp/carti_before_baseline
```

- [ ] **Step 2: Rewrite `carti_cut.py`.** Keep ALL existing CLI flags (`--music`, `--clips`, `--files`, `--recursive`, `--exclude`, `--density`, `--output`, `--compress`, `--lipsync`, `--lipsync-weight`). Keep the clip-pool construction (random per-clip offsets, lip-sync weighting) and the proxy `--compress` path — but call `ez_mv_core` for the engine work instead of carti's own functions. Map: `detect_beats` → `ez_mv_core.detect_beats` + `ez_mv_core.apply_cut_density`; `build_cut_schedule` → `ez_mv_core.build_cut_schedule(..., shrink_prob=SHRINK_PROBABILITY, zoom_prob=ZOOM_PROBABILITY)`; `ensure_proxies` → `ez_mv_core.ensure_proxies`; assembly → `ez_mv_core.assemble` (passing the white flash; note: carti also used black flash on some beats — if black-flash placement is part of carti's look, extend `assemble` to accept a black flash and an entry flag in a follow-up; for parity-first, keep white-flash behavior and note the black-flash deferral in the commit). DELETE carti_cut's local `extract_segment`, `generate_flash_frames`, `build_cut_schedule`, `apply_cut_density`, `compress_to_proxy`, `ensure_proxies`, `get_proxy_path`, `build_concat_list`, `final_assemble`, `detect_beats`.

> ⚠️ This is the judgment-heavy task — dispatch with a capable model and lean on the spec reviewer. The exact thin-CLI body must be written against the LIVE file at execution time (it depends on the then-current `carti_cut.py`). Do not pre-bake it here; the implementer reads the file, preserves every flag, and verifies via Step 3.

- [ ] **Step 3: Behavior check.** Render AFTER with the SAME seed (`--` carti_cut accepts a printed seed only via rerun; if no `--seed` flag exists, add one OR accept Option A). Compare BEFORE vs AFTER: same number of segments, same total duration, same flash/effect counts. Use `inspect_schedule.py` to diff the cut schedule.

- [ ] **Step 4: Commit** — `refactor: carti_cut is a thin CLI over ez_mv_core (one strobe engine)`

---

### Task 6: Behavior-preservation gate + final verification

**Files:** none modified.

- [ ] **Step 1: Full suite** — `uv run --extra dev pytest -q` → all pass.
- [ ] **Step 2: Both CLIs render end-to-end** — drift (`drift_cut.py`) and strobe (`carti_cut.py`) each produce an mp4 on the click-track fixture.
- [ ] **Step 3: `ez_mv_app.py` still imports + parses** — `python -c "import ez_mv_core; import ast; ast.parse(open('scripts/ez_mv_app.py').read())"`.
- [ ] **Step 4: No duplicate engine remains** — `grep -nE 'def (build_cut_schedule|extract_segment|apply_cut_density|ensure_proxies)' scripts/carti_cut.py` → empty (all now in `ez_mv_core`).
- [ ] **Step 5: BEFORE vs AFTER render comparison** (Option B: identical; Option A: same shape, different seed-mapping — documented). If renders differ in a way not explained by the chosen seed option, the refactor is WRONG — do not merge.
- [ ] **Step 6:** Merge `phase2b-strobe-engine` → `main` only when all above are green.

---

## Self-Review

- **Spec coverage:** implements migration step 2 (strobe half) from the consolidation spec; folds carti_cut's effects/proxies/flash into `ez_mv_core`; removes the duplicate `apply_cut_density`; makes `carti_cut` a thin CLI. Drift half done in 2a.
- **Backward-compat:** all new `ez_mv_core` params default to OFF/white-only, and a `generate_flash_frame` alias is kept, so `ez_mv_app.py` is untouched. Verified in Task 6 Step 3.
- **Placeholder note:** Task 5 Step 2 is intentionally NOT pre-baked code — it must be written against the live `carti_cut.py` at execution time (which the user is actively editing). Every other code step is complete and verbatim-from-source. This is a deliberate, flagged exception, not a vague placeholder.
- **Open decision:** Option A vs B on seed reproducibility (top of doc) — settle before Task 5.
- **Risk:** black-flash placement in carti's look may need a follow-up to fully thread through `assemble`; flagged in Task 5 for parity-first.
