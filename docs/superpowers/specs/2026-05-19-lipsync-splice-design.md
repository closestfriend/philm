# Lip-Sync Splice — Design Spec

**Date:** 2026-05-19  
**Scope:** `scripts/ez_mv_core.py`, `scripts/carti_cut.py`, `scripts/ez_mv_app.py`

---

## Goal

Enable a contemporary music video feel by weaving performer lip-sync footage into the beat-sync B-roll pool with a slightly elevated probability weight. The performer appears naturally throughout — not locked to any section — with lips in sync wherever the clip lands.

---

## Core Insight

A lip-sync clip is shot while the track plays on set, so **clip timecode = song timecode**. When the scheduler places the clip at beat time T, it starts playback at second T in the clip file. No manual alignment, no offset math. Each occurrence is independently song-locked.

---

## Clip Dict Schema

Two optional fields added to the existing clip dict:

```python
{
    "path": Path,
    "offset": float,     # existing — initial playhead for B-roll
    "lip_sync": bool,    # NEW — default False
    "weight": float,     # NEW — default 1.0
}
```

Backward compatibility: when all clips have `lip_sync=False` and `weight=1.0`, the scheduler is identical to today.

---

## Scheduler Change (`ez_mv_core.py: build_cut_schedule`)

**Condition:** if any clip in the pool has `lip_sync=True` or `weight != 1.0`, switch selection mode.

- **Round-robin mode** (current, unchanged): all clips at default weight → existing behaviour
- **Weighted mode** (new): use `random.choices(pool, weights=[c["weight"] for c in pool])` at each beat

**Offset rule:**
- B-roll clip selected → `start_offset = sequential playhead[clip]` (unchanged)
- Lip-sync clip selected → `start_offset = beat_time` (song-locked; no playhead tracking)

**Stutter + lip-sync:** if the stutter path repeats a lip-sync clip, its offset is still `beat_time` (not `prev_start + prev_duration`). Song-lock is unconditional for lip-sync clips.

No other changes to segment extraction or assembly.

---

## Suggested Default Weight

A weight of `3.0` against a typical pool of 6–10 B-roll clips at `1.0` puts the performer at roughly 23–33% of cuts — present and recognisable, never overwhelming.

---

## CLI Surface (`carti_cut.py`)

```
--lipsync <path>        Path to lip-sync clip (repeatable for multiple angles)
--lipsync-weight <float>  Weight for all lip-sync clips (default: 3.0)
```

Example:
```bash
python scripts/carti_cut.py \
  --music track.wav \
  --clips ./footage \
  --lipsync ./performer_take1.mp4 \
  --lipsync-weight 3
```

When `--lipsync` is omitted, the script behaves exactly as today.

---

## Streamlit Surface (`ez_mv_app.py`)

A **"Lip-sync clip (optional)"** section above the B-roll grid:

- Native folder-picker button + file path text input
- Weight slider: 1–10, default 3, labelled "Appearance frequency"
- Thumbnail preview once a valid path is entered
- When empty: section is visually collapsed / greyed out; no effect on generation

---

## What Does NOT Change

- Segment extraction (`extract_segment`) — untouched
- Assembly (`assemble`) — untouched
- Flash frame, stutter, shrink, zoom effects — untouched
- B-roll sequential playhead — untouched
- All existing CLI flags — untouched
- Output format — untouched

---

## Files Touched

| File | Change |
|------|--------|
| `scripts/ez_mv_core.py` | `build_cut_schedule`: weighted selection + lip-sync offset rule |
| `scripts/carti_cut.py` | `--lipsync`, `--lipsync-weight` args; build lip-sync clip dicts |
| `scripts/ez_mv_app.py` | Lip-sync section UI; pass lip-sync clips into core |
