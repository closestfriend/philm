# video-praxis — Consolidation Design

**Date:** 2026-06-01
**Status:** Design — awaiting review before implementation plan

**One-line vision:** Fold the two scattered repos (`philm`/`video-analyzer-v2` and `av-pair`)
into a single, semantically-named home — **`video-praxis`** — where *theory* (philosophical
video analysis) and *practice* (montage / MV generation) live as sibling modules over one
deduplicated montage engine.

> "praxis": the synthesis of theory and practice. `philm` reads video through critical theory;
> `montage` cuts and makes video. The repo name names the whole.

---

## Decisions locked (from brainstorming)

1. **One repo, not two + shared library.** It's a solo creative practice — one person, one
   brain, no separate teams or release cadences. A shared library across two repos would add
   cognitive surface (version sync, three places to look), which fights the actual goal of
   *less* sprawl. Monorepo wins for a solo workshop. (YAGNI on the product boundary.)
2. **`philm` survives as a named module + CLI**, not erased by the rename. It has real brand
   equity (thesis, README, the `vanalyze`/`philm` commands). The *umbrella/repo* is renamed;
   the analysis tool keeps its identity inside it.
3. **`av-pair` is the outlier that folds in.** The current repo already holds the newer montage
   engines (`carti_cut`, `ez_mv`, `drift`) alongside the analysis modes — so the merge direction
   is av-pair → here, not the reverse.
4. **Source media and renders live OUTSIDE git.** The 8.2 GB of footage and all render output
   are referenced by path, never committed.
5. **Sequencing: clean first, merge second.** The low-risk cleanup
   (`2026-05-31-drive-consolidation.md`, Phases 1–6) runs to completion *before* this merge, so
   we combine two clean repos rather than two messy ones. This spec is the "then merge" design.

---

## Target structure

```
video-praxis/                  ← renamed from video-analyzer-v2 (remote: …/philm → …/video-praxis)
├── philm/                     ← analysis module (was src/video_analyzer/), keeps `vanalyze`/`philm` CLI
│   ├── analyzer.py  modes.py  models.py  archive*.py  local.py  output.py …
│   └── web/                   ← FastAPI + Jinja UI (was templates/ + ui*.py)
├── montage/                   ← ONE montage engine + its generators
│   ├── engine/                ← deduped core: clip extraction, beat detection, ffmpeg assembly
│   ├── strobe.py              ← canonical beat-sync rapid-cut (ez_mv_core engine + carti_cut CLI)
│   ├── drift.py               ← canonical contemplative-decay (drift_core engine + drift_cut CLI)
│   ├── random_montage.py      ← KEEPER from av-pair: non-beat + aspect modes (letterbox/stretch/native)
│   └── beat_strobe.py         ← KEEPER from av-pair: manual BPM, beat-influence, --drift
├── cursed/                    ← av-pair's FeverDreamGenerator (distinct creative tool)
├── mcp/                       ← av-pair's two MCP servers
│   ├── av_studio/             ← media library + ffmpeg analysis (15 tools)
│   └── replicate/             ← Replicate AI job management (15 tools)
├── replicate_client/          ← av-pair's optional Replicate integration (shared by montage/cursed)
├── apps/                      ← UIs, collapsed from av-pair's ~6 entry points
│   ├── streamlit/             ← single multi-page Streamlit app
│   └── gradio_hf/             ← HuggingFace Spaces deploy target (the "secure" variant)
├── scripts/                   ← batch pipelines (Zeiss, Glass Orchard) — repointed to new paths
├── shared/                    ← ffmpeg/librosa/ffprobe helpers used across philm + montage
├── docs/                      ← specs, plans, LANDSCAPE.md
└── pyproject.toml             ← single project def; `vanalyze`/`philm` entry points preserved

# OUTSIDE the repo (gitignored, referenced by path):
#   <drive>/video-praxis-source/   ← footage + audio (was av-pair/assets, philm/input)
#   <drive>/video-praxis-output/   ← all renders (was carti_cuts*, av-pair/output, etc.)
```

---

## Module responsibilities & boundaries

- **`philm/`** — *theory.* Takes video → structured philosophical/production analysis (Gemini +
  Ollama), persists to the SQLite archive, serves the web UI. Depends on `shared/`. Unchanged in
  behavior; this is a relocation + namespace, not a rewrite. `vanalyze`/`philm` CLI must keep working.
- **`montage/`** — *practice.* Four generators over one engine:
  - `engine/` — the single source of truth for clip extraction, beat detection, and ffmpeg
    assembly. Resolves the duplication documented in `LANDSCAPE.md` (drift family ×3, strobe
    family ×4).
  - `strobe.py`, `drift.py` — the canonical beat-synced generators (philm's evolved `*_core`
    engines + the CLIs lifted from `carti_cut.py` / `drift_cut.py`).
  - `random_montage.py`, `beat_strobe.py` — retained av-pair generators covering cases the
    beat-synced tools *cannot* (non-beat random montage, aspect modes, manual BPM, drift timing).
- **`cursed/`** — the fever-dream / Elsagate-critique generator. Independent; depends on `shared/`
  and optionally `replicate_client/`.
- **`mcp/`** — the two MCP servers, registerable with Claude. Independent of the apps.
- **`apps/`** — thin UI layer over `philm/` + `montage/`. Collapses av-pair's redundant
  Streamlit/Gradio entry points to one local app + one deploy target.
- **`shared/`** — small, dependency-free helpers (ffprobe duration/resolution, the standard
  1920×1080 normalize+pad filter, the audio filter chain). Both `philm/` and `montage/` import it;
  nothing in `shared/` imports back up. This kills the copy-pasted `ffprobe_duration` / filter
  strings currently duplicated across every montage script.

**Interface test for each module:** you can state what it does, how you invoke it, and what it
depends on — without reading its internals. Generators are CLIs + importable functions; `engine/`
and `shared/` are pure libraries; `philm/` is a CLI + web app; `mcp/` servers are stdio entry points.

---

## Migration approach (phased, each independently valuable)

This runs *after* the `2026-05-31-drive-consolidation.md` cleanup completes. High level — the
implementation plan (next step) turns each into bite-sized, verified tasks.

1. **Stand up `shared/`** — extract the duplicated ffprobe/filter helpers into one module; point
   the existing philm montage scripts at it. Smoke-test a render still works. (No av-pair yet.)
2. **Build `montage/engine/` + canonical `strobe.py`/`drift.py`** — fold `carti_cut.py`'s effects
   (zoom/shrink/flash/proxies — the features `ez_mv_core` lacks) into the core, then make the CLIs
   thin wrappers. ⚠️ Mind the **seed gotcha** (drift_cut vs drift_core RNG) and the **feature gap**
   (ez_mv_core is *not* a superset of carti_cut) — both documented in `LANDSCAPE.md`.
3. **Bring in av-pair's keepers** — move `random_montage.py`, `beat_strobe.py` into `montage/`;
   `cursed_generator` → `cursed/`; `replicate_client` → `replicate_client/`. Drop the byte-identical
   `drift_composition.py` (superseded; archived in cleanup).
4. **Bring in `mcp/` and `apps/`** — relocate the two MCP servers; collapse the ~6 UI entry points
   to one Streamlit app + one Gradio/HF deploy. Update `sys.path` shims to the new layout.
5. **Relocate source + output outside git** — move av-pair `assets/` and philm `input/` to
   `video-praxis-source/`; renders to `video-praxis-output/`. Gitignore both. Repoint the Zeiss /
   Glass Orchard batch scripts to the new source + script paths (they're currently stale anyway).
6. **Rename + archive** — rename the repo/dir to `video-praxis`, update the GitHub remote, keep
   `vanalyze`/`philm` entry points in `pyproject.toml`. Push `av-pair` once more, then mark its
   GitHub repo archived (read-only).

---

## Constraints & risks

- **Don't break the CLI.** `vanalyze` / `philm` entry points must survive the `src/video_analyzer/`
  → `philm/` move (update `pyproject.toml` `[project.scripts]` + `packages`).
- **GitHub remotes.** Repo has `origin` (closestfriend) + `memetica` (Memetica-Corporation). Renaming
  is a GitHub-side rename + local remote URL update; coordinate if anything depends on the old URL.
- **Montage merge is a real refactor, not a move** — the feature gap and seed gotcha mean naive
  copying loses behavior. This is why it's staged with smoke tests, not a bulk `mv`.
- **Stale batch-script paths** point at `~/Projects/Development/av-pair/…` (a location that no longer
  exists). They must be repointed, not just relocated.
- **Source footage is irreplaceable** (8.2 GB). It is *moved with verification*, never deleted, and
  excluded from git.

## Out of scope (YAGNI)

- A shared library across multiple repos (rejected — monorepo chosen).
- Rewriting the analysis modes, the web UI, or the MCP servers' behavior (relocation only).
- Reproducing old renders or reconciling past seeds (renders are disposable; seeds weren't persisted).
- Consolidating the `documentary/` project — it's a creative output project, not tooling; leave it
  as a sibling dir or its own thing (revisit separately if desired).

## Testing / verification

- After `shared/` extraction and after the engine merge: render a short clip through each generator
  (`strobe`, `drift`, `random_montage`, `beat_strobe`) and assert output exists with expected duration.
- After the philm move: `vanalyze --help` works; one analysis run against a sample clip succeeds; the
  web UI starts.
- After MCP relocation: each server starts and lists its tools.
- Each migration phase ends on a working, committed state (no half-migrated repo).
