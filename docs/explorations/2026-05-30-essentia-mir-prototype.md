# Essentia MIR Prototype — Findings

**Date:** 2026-05-30
**Status:** Prototype validated; integration decision pending
**Author:** Hunter + Claude

## Motivation

`carti_cut.py` / `ez_mv_core.py` use **librosa for beat tracking only** —
`librosa.beat.beat_track()` gives beat timestamps + a single global BPM. There's no
higher-level musical understanding (no section structure, no energy curve, no
octave-error robustness). The planned `karman_cut` stack proposed hand-rolling that
(RMS percentiles + scipy `find_peaks` over onset novelty). Before building that by hand,
we surveyed whether existing MIR libraries do it better.

## The trigger observation

The `rav3rz` track ("16th note kicks") cut noticeably *less* energetically than
`nofour - oakley`, despite being a faster track. Diagnosis: **librosa read rav3rz at
half-time (78.3 BPM)**, producing ~0.77s cuts instead of the ~0.39s cuts oakley got at
its correctly-read 152 BPM. The "exciting vs. not" gap was a tempo octave error, not a
musical difference.

## Library survey conclusion

(Full survey in conversation; key points:)

- **Essentia** is the only heavyweight MIR library with a native **cp314 wheel** (macOS
  arm64 — our platform) AND it covers the energy/danceability/onset capabilities we want.
  License: **AGPL-3.0** — fine for personal/internal art tooling; viral if ever shipped
  commercially.
- The deep-learning options (**allin1**, **beat_this**, **demucs**) are more powerful
  (labeled sections, downbeats, stem separation) but are torch-heavy and need a separate
  Python 3.10–3.12 worker process. `allin1` is the "all-in-one brain" if we ever commit
  to that infrastructure.
- **madmom** PyPI (0.16.1) is a trap — Python ≤3.7. Avoid; `beat_this` is the modern,
  madmom-optional replacement.
- **librosa `segment`** (Laplacian structural segmentation) is already a dependency and
  unused — a zero-cost structural upgrade.

## Environment

Essentia installed in an **isolated venv**, kept separate from the main 3.14 env:

```
.venv-mir/            # Python 3.13, essentia 2.1-beta6-dev + librosa 0.11
```

Created with:
```bash
uv venv .venv-mir --python 3.13
.venv-mir/bin/python -m ensurepip --upgrade
.venv-mir/bin/python -m pip install --only-binary=:all: --pre essentia
.venv-mir/bin/python -m pip install librosa
```

Note: the main project is pinned `requires-python >=3.11` but the working venv is 3.14.
Hunter is **not married to 3.14** — if Essentia integration proceeds, dropping the main
env to 3.13 to unify is on the table.

## Prototype

`scripts/essentia_probe.py` — pure analysis, no video/render. Run with `.venv-mir`:

```bash
.venv-mir/bin/python scripts/essentia_probe.py TRACK.wav [TRACK2.wav ...] --json out.json
```

Surfaces per track: tempo cross-check (librosa vs Essentia rhythm2013 vs Percival),
danceability + dynamic complexity, a bucketed energy curve, coarse build/drop/breakdown
labels, and SuperFlux onset activity.

Also created `scripts/inspect_schedule.py` — reconstructs a `carti_cut` schedule
deterministically from its seed (carti_cut doesn't persist schedules, but
`build_cut_schedule` is seeded, so the full cut plan is re-derivable without rendering).

## Results (both project tracks)

```
=== rav3rz (v2) 16th note kicks (139.1s) ===
  tempo: librosa=78.3 | ess2013=156.0 | percival=78.3 | conf=1.19   ← OCTAVE ERROR CAUGHT
  feel:  danceability=1.19  dyn_complexity=2.81
  energy: ▃▂▃▃▃▄▅▄▅▄▅▄▅▄▄▂   (flat/hypnotic plateau)
  onsets: ▁▁▁▁▁▃▅▄▄▄▇▄▅▅▂▁   (502 total)

=== nofour - oakley (101.3s) ===
  tempo: librosa=152.0 | ess2013=153.7 | percival=77.1 | conf=1.09
  feel:  danceability=0.94  dyn_complexity=2.92
  energy: ▃▃▆▆▅▆▆▅▃▄▆▅▅▅▂▁   (lift → sustained body → outro drop-off)
  onsets: ▂▂▁▁▇▄▂▁▁▂▂▁▇▁▁▁   (15 total)
```

### Validated
1. **Octave-error detection works.** Essentia rhythm2013 read rav3rz at its true 156 BPM
   with high confidence — exactly the failure we hit. A 120–180 normalization on the
   chosen estimate would have fixed the energy gap automatically.
2. **Energy curves are real and musically meaningful.** The two tracks have visibly
   different, accurate dynamic shapes — enough to drive per-section cut density + effects.

### Known issues
- **SuperFlux onset totals are miscalibrated** (502 vs 15) — the default threshold
  doesn't suit these masters. Onset *shape* is usable; raw counts are not. Needs tuning.

## Open decision (next step)

1. Tune SuperFlux onset detection so transient counts are trustworthy.
2. **Wire just the tempo octave cross-check into carti_cut** — smallest, highest-value
   change; permanently kills the rav3rz-style error. (Recommended first move.)
3. Design the full section-aware scheduler (energy curve → per-section cut density +
   effects) — the real "smart edit" payoff; supersedes the hand-rolled karman approach.
4. Park it.

## Related
- `docs/superpowers/specs/2026-05-03-karman-cut.md` — the hand-rolled section-detection
  plan this would replace/supersede.
