# karman_cut — Design Spec

**Date:** 2026-05-03  
**Genre target:** Euphoric trance / hyperpop OTT / supersaw polyphony  
**Sits on the spectrum:** `drift_cut` (contemplative) ←→ `carti_cut` (rap hard cuts) ←→ `karman_cut` (phrase-aware, AI-informed, trance/hyperpop)

---

## Context

`carti_cut.py` is flat — every beat gets the same treatment. Trance and hyperpop are *phrase-structured*: the track breathes through builds, drops, and breakdowns, and the edit should feel that arc. Additionally, these genres are often double-time: librosa may detect 78 BPM where the actual grid is 156 BPM. A fixed multiplier is fragile; a **target range normalization** is not.

Three scripts with a shared core cover the design space without forcing compromise between approaches. Each can evolve independently.

---

## Files

```
scripts/
├── karman_core.py         # shared utilities, effects palette
├── karman_cut_rave.py     # pure DSP — free, fast, no API
├── karman_cut_hybrid.py   # Gemini perception + Python cutting
└── karman_cut_ai.py       # Gemini perceives, Claude plans, Python executes
```

---

## karman_core.py

### Lifted from carti_cut.py
- `run()`, `probe_duration()`
- `extract_segment()` with shrink / zoom / normal effects
- Full proxy machinery: `PROXY_DIR`, `get_proxy_path()`, `compress_to_proxy()`, `ensure_proxies()`
- `build_concat_list()`, `final_assemble()`
- `get_clip_files(clips_dir, files_list)`

### New additions

**`normalize_bpm(raw_bpm, target_range)`**  
Keeps doubling or halving until the BPM lands inside `target_range`. Works in combination with a librosa BPM prior centered on the range midpoint for two layers of robustness.

```python
TARGET_BPM_RANGE = (120, 180)

def normalize_bpm(raw_bpm, target_range=TARGET_BPM_RANGE):
    bpm = raw_bpm
    while bpm < target_range[0]: bpm *= 2
    while bpm > target_range[1]: bpm /= 2
    return bpm
```

**Effects palette** — all return a `Path` to an encoded segment, composable by cut scripts:

| Function | Description |
|---|---|
| `generate_flash_frame(color, duration, size, output)` | Generalized flash; accepts any color string |
| `strobe_burst(n_flashes, interval, tmp_dir)` | Rapid alternating white/black frames; used between cuts during drops |
| `speed_ramp_segment(source, start, duration, speed, output)` | `speed < 1.0` = slo-mo; `speed > 1.0` = overcranked |
| `zoom_pulse_segment(source, start, duration, zoom_factor, output)` | Animated crop push-in over clip duration, timed to beat hit |

**`versioned_output(output_dir, prefix)`**  
Shared naming convention: `{prefix}_v01.mp4`, `{prefix}_v02.mp4`, etc. Used by all three scripts.

---

## karman_cut_rave.py — Pure DSP

No API cost. Maximum iteration speed.

### Audio analysis
1. Librosa beat tracking with `start_bpm` hint at range midpoint + `normalize_bpm()` post-detection
2. `librosa.onset.onset_strength` envelope, median-filtered
3. Self-similarity / recurrence matrix + checkerboard kernel → structural boundaries
4. Section labeling by RMS energy + onset density: **build** (rising), **drop** (high + dense), **breakdown** (low + sparse)

### Per-section cut logic

| Section | Cut grid | Flash | Strobe | Effects |
|---|---|---|---|---|
| build | 2-beat, tightening toward section end | occasional | none | zoom_pulse probability increases |
| drop | 16th-note (4× normalized beat) | heavy | burst on transient peaks | all effects, high probability |
| breakdown | 4–8 bar holds | none | none | speed_ramp 0.5× slo-mo |

### Config
```python
TARGET_BPM_RANGE = (120, 180)
DROP_DENSITY     = 4        # 16th note = 4× beat grid
STROBE_PROB      = 0.35     # during drops
FLASH_PROB       = 0.20
ZOOM_PROB        = 0.25
SLO_MO_FACTOR    = 0.5      # breakdown speed
```

---

## karman_cut_hybrid.py — AI Perception + Python Cutting

Gemini does perception once per track / per new clip. Python cuts on every run.

### Pipeline
1. Librosa beat grid (same BPM normalization as rave)
2. **Gemini audio analysis** — WAV uploaded → structured section JSON cached to `~/.karman_analysis/{audio_stem}.json`
3. **Clip tagging** — lightweight Gemini vision prompt per clip → `{energy, mood, motion, color}` cached to `~/.karman_clip_tags/{parent}_{stem}.json`
4. **Affinity scoring** — weighted clip-to-section matching (drop → high-energy kinetic, breakdown → contemplative still); probabilistic, not prescriptive
5. FFmpeg execution via karman_core

### Gemini audio response shape
```json
{
  "sections": [{"start": 0, "end": 22.4, "type": "build", "energy": 0.4, "vibe": "anticipatory ascent"}],
  "tempo": 156,
  "key": "F# minor",
  "emotional_arc": "euphoric escalation with two collapses"
}
```

### Config
```python
AFFINITY_WEIGHT = 0.7   # 0.0 = random, 1.0 = strict tag matching
GEMINI_MODEL    = "gemini-2.5-flash"
```

---

## karman_cut_ai.py — Gemini Perceives, Claude Plans, Python Executes

**Model split:** Gemini handles media perception (audio analysis, clip tagging). Claude handles creative reasoning (cut plan). Python handles frame-level execution.

### Pipeline
1. Gemini audio analysis (same as hybrid, same cache)
2. Clip tagging (same as hybrid, same cache)
3. **Claude generates a `CutPlan`** via Anthropic SDK — section-level creative plan, not individual cuts (token-efficient; Python expands to frame-level timing)
4. Python validates the plan, expands each `SectionPlan` into cut entries using the beat grid, executes via FFmpeg

### Pydantic schemas
```python
class EffectProfile(BaseModel):
    zoom_pulse: float = 0.0
    flash: float = 0.0
    strobe: float = 0.0
    speed_ramp: float = 0.0
    slo_mo_factor: float = 1.0

class SectionPlan(BaseModel):
    start: float
    end: float
    section_type: str           # build / drop / breakdown
    cut_density: str            # "beat" / "2-beat" / "16th" / "hold"
    preferred_clips: list[str]  # clip stems, ordered by preference
    effect_profile: EffectProfile
    rationale: str              # printed to terminal during encode

class CutPlan(BaseModel):
    sections: list[SectionPlan]
    overall_vision: str         # printed at run start, like liner notes
```

### Prompt caching
System prompt (genre aesthetic + effects palette description) and song structure context are both cached — re-runs on the same track only pay for output tokens.

### Terminal output
`overall_vision` and each section's `rationale` print before FFmpeg starts. The encode runs while you read Claude's interpretation of the track.

### Config
```python
CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.5-flash"
```

---

## Comparison

| Script | API cost | Speed after first run | Creative driver |
|---|---|---|---|
| `karman_cut_rave` | free | fastest | DSP |
| `karman_cut_hybrid` | Gemini once per track + per new clip | fast | AI-informed Python |
| `karman_cut_ai` | Gemini + Claude per run | moderate | AI-directed |

---

## Verification

After implementation, a successful run of each script should:
- Produce a versioned output file (`karman_rave_v01.mp4`, `karman_hybrid_v01.mp4`, `karman_ai_v01.mp4`)
- Print detected/normalized BPM and confirm it lands in `TARGET_BPM_RANGE`
- Print section count + labels
- For hybrid/ai: confirm cache hits on re-run (no re-analysis)
- For ai: print `overall_vision` and per-section `rationale` before encode
- Final file duration matches music track duration
