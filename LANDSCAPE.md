# LANDSCAPE — beat-sync montage code across repos

> **What this is:** a home-base map of where the "detect beats → cut clips → render
> montage" idea lives, written because the same engine has been reimplemented across
> multiple repos and interfaces. Read this *before* deciding what's canonical or
> deleting anything. Generated 2026-05-31. Read-only inventory — nothing here has been
> changed or removed.

## TL;DR

One good idea — *beat-synced FFmpeg + LibROSA montage generation* — has been born
**four times** across **two active repos and two abandoned nested repos**, and then
re-wrapped in ~6 user interfaces. None of the duplication is dangerous to clean up:
the bulk of the disk cost is regenerable venvs and media, and the abandoned copies are
empty `.git` shells.

> **Since 2026-06 the idea has a fifth, most-evolved descendant** — `scripts/affect_score.py`,
> an *affect engine* fed by a cloud-catalogued archive. See **[the 2026-06 build](#2026-06--the-archive-became-an-instrument-cloud-catalogue--affect-engine)**
> below. The deliverables it produces live OUTSIDE both repos, in
> `~/Projects/karman-video-art/` (internal drive).

---

## Consolidation status — updated 2026-06-02

**Decision:** unify both repos into one home named **`video-praxis`** (solo creative practice →
monorepo, not a shared library); `philm` survives as the analysis module + `vanalyze`/`philm`
CLI; **organization is the goal — reclaimed space is a bonus, not the point.**
Design: `docs/superpowers/specs/2026-06-01-video-praxis-consolidation-design.md`.

**✅ Done (merged to `main`):**
- **Cleanup:** `git gc` reclaimed ~1.5 GB of dangling committed media; removed the two nested
  `.git` repos inside `av-pair/src/`; pinned Python to 3.11 (the 3.14 venv was broken).
- **Montage dedup:** extracted shared `scripts/media_utils.py` (tested) and repointed drift +
  strobe scripts at it; **drift engine unified** — `drift_cut.py` 343→38 lines, now a thin CLI
  over `drift_core.py` (Phase 2a).
- **Bug fix:** librosa-0.11 `tempo.ndim` crash in `carti_cut`/`ez_mv_core` beat detection.
- Committed the user's in-progress `--density` carti_cut feature as its own checkpoint.
- **Ported 9 theory modes** out of the legacy `modes.ts` into philm (ranciere, sontag, haraway,
  marks, chion, bazin, eisenstein, greenberg, ngai) → **28 modes total**. This harvests the
  unique value that made `modes.ts` worth keeping.

**📋 Planned — gated on user go:**
- **Strobe engine unify (Phase 2b)** — `docs/superpowers/plans/2026-06-02-video-praxis-phase2b-strobe-engine.md`.
  Deferred until the user's active `carti_cut` work is parked + tree clean.
  **Open decision: seed reproducibility — Option A (accept change) vs B (preserve carti seeds);
  plan defaults to B** because `carti_cut` prints its seed and the user may rely on it.

**⏳ Pending / not yet run:**
- **Cleanup Phase 3 — ✅ DONE (2026-06-03):** deleted `cli.ts` / `functions.ts` / `modes.ts`
  (backed up to `_consolidation_2026-05-31/code-backups/` + recoverable from git history; their
  9 unique modes already harvested into philm) and the empty `100CANON_results/`
  `101CANON_results/` dirs. **KEPT** `av-pair/legacy/av_pair/create_composition.py` — it's a
  15-line `runpy` compat *shim* to `src/`, not a duplicate (the 3rd "dead code" item this cleanup
  found to be intentional, after random_montage and modes.ts).
- **Deprioritized (space, not organization):** render corral (cleanup Phase 4), av-pair history
  rewrite (Phase 6).
- **video-praxis P3–P6 (future):** bring in av-pair keepers (`random_montage`, `beat_strobe`,
  `cursed`) → relocate MCP servers → collapse the ~6 apps → rename repo + archive av-pair.

> The detailed redundancy analysis below predates this work — treat the status block above as the
> current source of truth for what's resolved.

---

## 2026-06 — the archive became an instrument (cloud catalogue + affect engine)

A whole new track of work, mostly **additive** to philm (new module + new scripts), that turns the
decade of footage into a *queryable, composable instrument*. This is the evolved end of the montage
lineage — and the thing actually being used day-to-day now. The hand-cut **SINGLE_SOURCE** edit
(intensity-curve by eye) grew a nervous system.

### New code (all in `philm` / video-analyzer-v2)
- **`src/video_analyzer/batch_cloud.py`** (756 lines) — the **cloud catalogue** pipeline. Analyzes the
  *entire* archive (~3,380 unique clips) for **sizzle + affect + a rotating theory lens**
  (žižek→hauntology→sontag) via the **Gemini Flash-Lite Batch API** at the 50% async discount —
  **~$8 for the whole archive.** Two hard-won gotchas baked in: (a) it transcodes to **360p/0.4Mbps
  proxies first** (327 GB → ~10.6 GB) so the archive fits the File API 20 GB cap, since the model only
  consumes `media_resolution=LOW` anyway; (b) it aligns responses by `metadata["key"]`, NOT zip
  position — **the Batch API returns results out of submission order**, a bug that first looked like
  54% failure and was really 99.9% success mis-indexed.
- **`scripts/affect_score.py`** (778 lines) — **THE affect engine** (lineage stage 5; see strobe table
  below). Generalizes SINGLE_SOURCE's hand-placed intensity curve into an algorithm: it **fits clips
  to an affect curve** using three levers — *intensity* (1–10), *vector* (the **direction** of affect:
  rising / falling / held — editing on the derivative of feeling), and *atmosphere*. Curve sources:
  synthetic shapes (`swell` / `heartbeat` / `flatline_spike` / `double_climax`), **a music track's
  loudness envelope** (`--audio` → feeling-sync, not just beat-sync), **structure-aware** section
  grammar (breakdown / build / drop / outro), and **transient mapping** (`--transient` → scipy
  lowpass ≈150 Hz + librosa onset = kick onsets; cuts snap to kicks when kick-density is high and hold
  free when it thins). Pool is filterable by the facets below (`--pool-min-intensity`, `--pool-tone`, …).
- **`scripts/segment_long_clips.py`** — slices the 52 long takes (>5 min, which hold ~22% of the
  footage and produce *hallucinated* timecodes) into ~2.5-min chunks → **318 chunks** with reliable
  timecodes; flags originals `segmented` so the engine skips them.
- **`scripts/recollect_from_jobs.py`** — **$0 repair**: rebuilds a run from still-alive batch jobs
  (jobs persist ~48 h) via metadata alignment. This is what fixed the out-of-order bug for free.
- **`scripts/backfill_facets.py`** — re-derives the facet columns onto existing DB rows.
- **`src/video_analyzer/archive.py` + `archive_cli.py`** — **structured facet search.** The `videos`
  table gained `overall_energy / dominant_tone / best_for / peak_intensity / mean_intensity /
  dominant_atmosphere` columns + a `search_facets()` method + CLI flags (`--min-intensity`, `--tone`,
  `--best-for`, `--min-energy`, `--atmosphere`). So "energy 7, dramatic, best_for hook/climax, peak
  intensity 9" is now a query, not a vibe.

### Where the data lives (media drive, NOT in git)
- **`…/Photography + Video/_proxies/`** — persistent 360p low-res mirror (~10.6 GB), reusable.
- **`…/Photography + Video/_cloud_catalog/`** — per-clip JSON catalogue (sizzle/affect/theory + facets)
  the engine reads. ~$8 of analysis lives here; back it up before any archive reorg.

### Deliverables — OUTSIDE both repos
**`~/Projects/karman-video-art/`** (internal drive, git-versioned, heavy media gitignored): README +
`docs/` (METHOD / FINDINGS / PIPELINE / ESSAY-DRAFT), six concept films (`concepts/`), the affect-curve
& music-video renders (`affect_scores/`, incl. the `--transient`+`--pool-min-intensity 8` *KICKCAST*
cut), and the **anthology** *THE MODERN SUBJECT* (`anthology/`) — six films re-sequenced by their own
collective affect signature (a recursive affect-score, one octave up).

### One finding worth flagging
Running the **same track mastered vs. pre-master** through the engine (same seed, same archive) yields
a **>80% different cut** and a different cut-*rate* — mastering flattens the dynamics the engine reads
as its score. *The mastering chain is also a picture-editing chain.* (Detail in `docs/FINDINGS.md`.)

---

## The two active repos

### 1. `philm` / video-analyzer-v2
- **Path:** `/Volumes/2025_exSSD_2tb/video-analyzer-v2`
- **Remotes:** `origin` → `closestfriend/philm` only. *(The `memetica` → `Memetica-Corporation/philm`
  remote was removed 2026-06-15 — Hunter has left Memetica; never re-add it.)*
- **Real product:** `src/video_analyzer/` — philosophical video analysis CLI (`vanalyze`/`philm`),
  Gemini + Ollama backends, SQLite archive, FastAPI/Jinja web UI, sizzle production mode.
- **The montage code lives in `scripts/`** as a *second-generation* rewrite of av-pair's engine:
  `carti_cut.py`, `ez_mv_app.py` + `ez_mv_core.py`, `drift_cut.py` + `drift_core.py`,
  `inspect_schedule.py`, `essentia_probe.py`.

### 2. `av-pair`
- **Path:** `/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair`
- **Remotes:** `origin` → `closestfriend/av-pair` only. *(The `memetica` remote is also gone — verified
  2026-06-23; never re-add it.)*
- **What it is:** the *original* beat-synced montage generator. FFmpeg + LibROSA core,
  optional Replicate AI integration, two MCP servers, deployed to HuggingFace Spaces.
- **Engine lives in** `src/av_pair/`: `create_composition.py`, `drift_composition.py`,
  `random_montage.py`, `beat_strobe.py`.

### Two abandoned repos nested *inside* av-pair/src/ (cleanup hazard)
- `src/creative-production-pipeline/.git` → `closestfriend/creative-production-pipeline`
- `src/fever-dream-pipeline/.git` → `closestfriend/fever-dream-pipeline`

Both are `.git` scaffolding only (no working files, no reachable commits) — earlier
incarnations of the same idea, now repos-inside-a-repo. This silently breaks tooling and
should be the *first* thing resolved (remove or convert to real submodules).

---

## Proof of duplication (grep across both repos)

- **`librosa.beat.beat_track`** appears in av-pair `create_composition.py` AND philm
  `carti_cut.py`, `ez_mv_core.py`, `essentia_probe.py`.
- **A "drift" decay montage exists in both repos** (see lineage below).
- **Same FFmpeg backbone everywhere:** libx264 / CRF 20 / medium preset, 1920×1080 via
  `scale=…:force_original_aspect_ratio=decrease` + `pad`, `-fps_mode cfr`, concat demuxer.
- **Same audio philosophy:** highpass → lowpass → (compand) → volume normalize.

---

## The `drift` lineage (diffed 2026-05-31)

All three copies share a **byte-for-byte identical core algorithm** — `decay_curve()`,
hold/split/pip planning, `generation_loss()`, split-screen + PiP filter graphs, and the
audio chain `highpass=f=30,lowpass=f=16000,volume=0.85`. Only the scaffolding diverges.

| | `drift_composition.py` (av-pair) | `drift_cut.py` (philm) | `drift_core.py` (philm) |
|---|---|---|---|
| Date | Oct 2025 | Apr 27 2026 | May 19 2026 |
| Generation | 1st (original) | 2nd | **3rd (most evolved)** |
| Paths | `os.path` strings | `pathlib.Path` | `pathlib.Path` + type hints |
| Output | single file, no versioning | auto-versioned `drift_cut_vNN.mp4` | auto-versioned |
| RNG | global `random.seed()` | global `random.seed()` | **isolated `random.Random(seed)`** |
| Interface | argparse CLI | argparse CLI + box-art console | **pure fn + `progress_callback`**, returns Path |
| Has CLI? | yes | yes | no (library only) |

**Keeper:** `drift_core.py` — isolated/reentrant RNG, progress callback, type hints, clean
library API. Its only gap is no CLI. **Canonical = `drift_core.py` engine + the argparse
`main()` lifted from `drift_cut.py`.** That makes `drift_cut.py` and av-pair's
`drift_composition.py` both deletable.

> ⚠️ **Seed gotcha:** `drift_cut.py` and `drift_core.py` are NOT seed-compatible.
> `drift_cut.py` continues one global RNG stream from `plan_segments` into clip selection;
> `drift_core.py` resets a fresh `Random(seed)` for clip selection. **Same `--seed`
> produces different videos.** Any "good seed" rendered from `drift_cut.py` will not
> reproduce in `drift_core.py`.

---

## The `strobe / rapid-cut` lineage (diffed 2026-05-31)

A second montage family, following the same av-pair → philm evolution as drift. The
defining leap here is **MoviePy → raw FFmpeg** and **manual BPM → real beat detection**.

| Stage | File | Engine | Beat sync | Notable |
|---|---|---|---|---|
| 1 (av-pair) | `random_montage.py` | MoviePy | none — random durations fill audio length | aspect modes |
| 2 (av-pair) | `beat_strobe.py` | MoviePy | **manual `--bpm`** (no detection) | `--drift`, `--beat-influence` |
| 3 (philm) | `carti_cut.py` | **raw FFmpeg** | **real `librosa.beat_track`** | flash/stutter/zoom/shrink, proxies, lip-sync, versioned output, CLI |
| 4 (philm) | `ez_mv_core.py` | **raw FFmpeg** | librosa + `apply_cut_density` | pure fn + `progress_callback`; reads philm affect/sizzle JSON to cut on peak-intensity moments |
| 5 (philm) | `affect_score.py` | **raw FFmpeg** | librosa envelope/beats **+ transient (kick) gating** | **the affect engine** — fits clips to an *affect curve* (intensity × vector × atmosphere) from a synthetic shape, a music track, or kick onsets; reads the cloud catalogue + facet pool filters. See the [2026-06 section](#2026-06--the-archive-became-an-instrument-cloud-catalogue--affect-engine). |

**Most-evolved beat-sync engine:** `affect_score.py` (stage 5). It descends directly from
`ez_mv_core.py` — stage 4 already cut on peak-intensity *moments*; stage 5 generalizes that into
fitting a whole *curve*, adds the affect **vector** (direction) and music/transient drive, and pulls
from the cloud catalogue rather than per-clip JSON. `ez_mv_core.py` + `carti_cut.py`'s CLI remain the
canonical *pure beat-sync* pair when you don't want affect-curve fitting.

⚠️ **The av-pair pair are NOT disposable (corrected 2026-05-31).** Earlier framing called
`random_montage.py` / `beat_strobe.py` "obsolete prototypes — strictly superseded." That was
wrong. They are **distinct creative instruments with capabilities the philm tools lack**, and
are never-committed (working file is the only copy):
- `random_montage.py` — aspect modes (`letterbox`/`stretch`/`native`) + **pure random montage,
  no beat sync**. Referenced by 4 shell scripts (`batch_random_montage.sh`,
  `batch_zeiss_montage.sh`, `test_aspect_modes*.sh`) and CLAUDE.md; the engine behind real
  named output (*Zeiss*, *Glass Orchard*). **KEEP.**
- `beat_strobe.py` — manual `--bpm`, `--beat-influence`, `--drift` (the dreamlike-timing idea
  that seeded the whole *drift* family). Documented in CLAUDE.md. **KEEP.**

The philm FFmpeg tools always beat-sync and always letterbox to 1920×1080, so they do **not**
cover non-beat random montage, `stretch`/`native` aspect, manual BPM, or drift. These are real
feature gaps, not redundancy.

> Lesson: untracked + older-lineage ≠ disposable. For creative tooling, judge by what it makes,
> not by code ancestry. Only `drift_composition.py` is a true byte-identical duplicate (of
> philm's drift) — and even that is av-pair's sole drift engine.

So the full montage picture is **two families × the same 3-4 stage av-pair→philm rewrite**:
the philm `scripts/` versions are the evolved survivors in both.

---

## Redundancy ledger

### Cross-repo (the headline)
- Beat-sync montage engine reimplemented in **4 places**: av-pair `src/av_pair/`, philm
  `scripts/`, + the two abandoned nested pipelines.
- `drift`: 1 original (av-pair) + 2 copies (philm `drift_cut.py` / `drift_core.py`).

### Inside philm `scripts/`
- `drift_cut.py` ↔ `drift_core.py` — engine extracted but the CLI original was never
  deleted (its own docstring says *"drift_cut.py remains the CLI entry point and is
  unchanged"*).
- `ez_mv_app.py` ↔ `ez_mv_core.py` — same core/CLI split pattern.

### Inside av-pair (one engine, ~6 interfaces)
- Streamlit: `app/` (multi-page) + `app_av_composition/` (standalone dup) +
  `app_cursed_generator/` (standalone dup)
- Gradio: `app_gradio_replicate.py` + `app_gradio_replicate_secure.py` (near-identical pair)
- CLI/Gooey: `src/av_pair/create_composition.py`
- Bash v1: `scripts/create_composition.sh`
- `create_composition` exists in 3 spots: `src/av_pair/`, `legacy/av_pair/`, `scripts/*.sh`
- 3 deployment docs: `DEPLOY_NOW.md`, `DEPLOYMENT_GUIDE.md`, `DEPLOYMENT_HUGGINGFACE.md`
- 5+ `requirements.txt` scattered across root, each app, each MCP server
- `src/replicate_client/` mixes `.py` and `.js` (`claude_api_fixed.js`, `download_predictions.js`)

---

## Storage audit (measured 2026-05-31)

**Combined ~23 GB across both repos. Source code is ~2 MB of that.** Of the 23 GB, only
~8.5 GB is genuinely irreplaceable source; ~14 GB is regenerable, disposable, or git garbage.

| Bucket | Size | Reclaimable? |
|---|---|---|
| av-pair `assets/source_videos/` | 8.2 G | ⚠️ **Real source** — only large irreplaceable input. Back up, don't delete. |
| philm `carti_cuts/` + `carti_cuts_raw/` + `oakley_cuts/` | 6.3 G | Render iterations — keep best, discard rest (judgment call). NOT reliably reproducible: seeds aren't persisted. |
| venvs (philm `.venv`+`.venv-mir` 994M; av-pair 3 venvs 1.7G) | 2.7 G | ✅ Fully regenerable (pip reinstall) |
| `.git` bloat (philm 1.5G + av-pair 1.2G) | 2.7 G | ✅/⚠️ see below — committed media |
| philm `documentary/` | 1.9 G | Mixed source + output |
| av-pair `output/av_compositions/` | 414 M | Renders — disposable |
| philm `input/` (99M video + 88M audio) | 187 M | Source |
| philm `100CANON_results/`, `101CANON_results/` | 0 B | empty leftover dirs |
| philm `cli.ts` / `functions.ts` / `modes.ts` | 84 K | orphaned TS ancestor, untracked, no build files |

### ⚠️ The `.git` bloat — both repos committed video renders into history

- **philm `.git` = 1.5 GB of *dangling* media.** 362 loose objects; largest blobs are
  471 MB + 329 MB and are **unreachable from any branch** (orphaned by past rebase/amend/
  reset). Not in current history — just uncollected garbage.
  **`git gc --prune=now` reclaims ~1.5 GB with zero history rewrite and zero risk.**
  This is the single easiest big win.
- **av-pair `.git` = 1.2 GB of *reachable* renders.** 305/224/215 MB `montage_*.mp4` blobs
  committed in old `outputs3/`/`outputs23/` commits no longer in the working tree. Still
  referenced by history → reclaiming needs a rewrite (`git filter-repo` or BFG). Do
  deliberately.

> Going forward: add `*.mp4 *.mov *.wav` (or the render/output dirs) to `.gitignore` in
> both repos so renders never re-enter history.

---

## Recommended consolidation order (when ready — not done here)

1. **`git gc --prune=now` on philm** — reclaims ~1.5 GB of dangling committed media, zero
   risk, one command. Do this first.
2. **Resolve the two nested `.git` repos inside av-pair/src/** (remove or make real
   submodules). Highest-risk-to-tooling, smallest effort.
3. **Pick the canonical drift:** `drift_core.py` engine + CLI from `drift_cut.py`; retire the
   other two. Mind the seed gotcha for any saved seeds.
4. **Pick the canonical *beat-synced* strobe/rapid-cut:** `ez_mv_core.py` engine + CLI from
   `carti_cut.py`. **KEEP `random_montage.py` + `beat_strobe.py`** — they cover non-beat /
   aspect-mode / drift cases the beat-synced tools don't, and are tied to real output.
5. **Decide the canonical home for the montage engine** — does it live in `av-pair`, or has
   philm `scripts/` become the real one? Pick one repo; the other imports or is archived.
6. **Collapse av-pair's ~6 interfaces** toward one Streamlit entry + one deploy target.
7. **`.gitignore` render/output dirs** in both repos so media never re-enters git history;
   then rewrite av-pair history (BFG/filter-repo) to reclaim its 1.2 GB.
8. **Delete the safe leftovers:** philm's orphaned `.ts` files, empty `*CANON_results/`,
   `legacy/av_pair/`.

## Open decisions for Hunter
- Is **av-pair** or **philm/scripts** the canonical home for beat-sync montage going forward?
- Keep the Replicate/AI + MCP-server side of av-pair, or is that a separate product?
- Are `carti_cuts*` / `oakley_cuts` renders worth keeping, or are they disposable iterations?
