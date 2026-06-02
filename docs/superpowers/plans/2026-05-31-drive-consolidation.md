# Drive Consolidation Implementation Plan

> **For agentic workers:** This is an operations/cleanup plan, not a feature build. Steps use checkbox (`- [ ]`) syntax for tracking. Each phase is independently valuable and has a **STOP POINT** — you can halt after any phase with a clean, consistent result. Execute top-to-bottom; safest + highest-value first.

**Goal:** Reclaim ~3 GB of git garbage, remove dead/duplicated code across the `philm` and `av-pair` repos, and corral disposable render iterations — without destroying any irreplaceable source material.

**Approach:** Work in strict safety order: (1) zero-risk space reclaim, (2) remove provably-dead code after backing it up, (3) corral renders to a review area instead of deleting, (4) prevent recurrence, (5) optional deep history rewrite. A separate deferred phase covers the real code merge (unifying the montage engine), which is a refactor and should not block the cleanup.

**Tech stack:** `git`, `bash`, `du`, `ffmpeg` (smoke test only). macOS (`darwin`), zsh.

**Repos referenced (absolute paths):**
- `PHILM = /Volumes/2025_exSSD_2tb/video-analyzer-v2`
- `AVPAIR = /Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair`

---

## Safety preamble — read before starting

**Backup/archive area (created in Phase 0, lives OUTSIDE both repos):**
`/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/`

Nothing in this plan hard-deletes source media. Disposable code is copied to the archive
area before removal. Renders are *moved* (not deleted) to a review folder you cull later.

**Global rollback:** every destructive step below names its own rollback. If in doubt, stop —
the archive area holds copies of everything removed.

**What is genuinely irreplaceable (NEVER delete in this plan):**
- `AVPAIR/assets/source_videos/` (8.2 G) and `assets/source_audio/` (31 M)
- `PHILM/input/` (187 M)
- Any `.git` *commit history on a branch* (only unreachable/reflog garbage is pruned)

---

## Phase 0: Pre-flight

**Files:** none modified; creates the archive directory.

- [ ] **Step 1: Create the archive area**

```bash
mkdir -p "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/code-backups"
mkdir -p "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/renders-to-review"
ls -la "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/"
```

Expected: two empty subdirectories `code-backups/` and `renders-to-review/`.

- [ ] **Step 2: Record the starting sizes (baseline to measure wins against)**

```bash
{ echo "=== BASELINE $(date) ==="
  du -sh "/Volumes/2025_exSSD_2tb/video-analyzer-v2" \
        "/Volumes/2025_exSSD_2tb/video-analyzer-v2/.git" \
        "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair" \
        "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair/.git"
} | tee "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/baseline.txt"
```

Expected (approx): philm 11G / philm/.git 1.5G / av-pair 12G / av-pair/.git 1.2G.

- [ ] **Step 3: Stash or commit in-progress work in philm (so the tree is clean & attributable)**

`git gc` does NOT touch your working tree, but committing now keeps things tidy.

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
git status --short
# If you want to keep the WIP for later without committing:
# git stash push -u -m "pre-consolidation WIP 2026-05-31"
```

Expected: you see the modified/untracked files. Decide commit vs stash. Not blocking for Phase 1.

**✅ STOP POINT 0:** archive area ready, baseline recorded. Nothing changed yet.

---

## Phase 1: Reclaim philm's 1.5 GB of git garbage (zero risk, biggest instant win)

**Why safe:** verified 2026-05-31 — 76 blobs (largest 345 MB) are unreachable from any
branch or tag; they are pinned only by reflog entries for commits that no longer exist on
any branch. Expiring those reflog entries and pruning frees the space. Your branch history
is untouched.

**Files:** `PHILM/.git/` internals only.

- [ ] **Step 1: Confirm the garbage is still there and branch history is clean**

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
echo "unreachable-without-reflog blobs:"; git fsck --no-reflogs --unreachable 2>/dev/null | grep -c blob
echo "largest blob reachable from BRANCHES (should be tiny, ~0.1MB):"
git rev-list --objects --all | git cat-file --batch-check='%(objectsize) %(rest)' \
  | sort -rn | head -1 | awk '{printf "%.1f MB  %s\n", $1/1048576, $2}'
```

Expected: ~76 unreachable blobs; largest branch-reachable blob well under 1 MB (proves the big blobs are NOT live data).

- [ ] **Step 2: Expire unreachable reflog entries, then prune**

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
git reflog expire --expire-unreachable=now --all
git gc --prune=now
```

Expected: gc runs, "Counting objects... done", no errors.

- [ ] **Step 3: Verify the reclaim**

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
du -sh .git
git fsck --no-reflogs --unreachable 2>/dev/null | grep -c blob
git status --short | head   # working tree unchanged
git log --oneline -1        # branch history intact
```

Expected: `.git` drops from ~1.5 G to a few MB; unreachable-blob count → 0; working tree and `git log` unchanged.

**Rollback:** none needed — only already-orphaned objects were removed. (If something looks wrong, your branches/commits/working tree are all still present; nothing reachable was touched.)

**✅ STOP POINT 1 — you just freed ~1.5 GB with three commands.** Update the tally:

```bash
echo "After Phase 1: philm/.git = $(du -sh '/Volumes/2025_exSSD_2tb/video-analyzer-v2/.git' | cut -f1)" \
  >> "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/baseline.txt"
```

---

## Phase 2: Remove the two nested git repos inside av-pair/src/ (tooling hazard)

**Why safe:** verified each contains only a `.DS_Store` (and one stray `.claude/settings.local.json`)
outside its `.git` shell — no working code. Both have live GitHub remotes
(`closestfriend/creative-production-pipeline`, `closestfriend/fever-dream-pipeline`), so the
real code is preserved off-machine.

**Files:**
- Remove: `AVPAIR/src/creative-production-pipeline/`
- Remove: `AVPAIR/src/fever-dream-pipeline/`

- [ ] **Step 1: Confirm remotes (code is safe on GitHub) and that no real code lives here**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
git --git-dir="src/creative-production-pipeline/.git" remote -v
git --git-dir="src/fever-dream-pipeline/.git" remote -v
find src/creative-production-pipeline src/fever-dream-pipeline -type f -not -path '*/.git/*'
```

Expected: GitHub remotes printed; the only files listed are `.DS_Store` / `settings.local.json`.

- [ ] **Step 2: Archive the two stray non-.git files, then remove the nested dirs**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
cp "src/creative-production-pipeline/.claude/settings.local.json" \
   "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/code-backups/cpp-settings.local.json" 2>/dev/null || true
rm -rf "src/creative-production-pipeline" "src/fever-dream-pipeline"
ls src/
```

Expected: `src/` now lists only `av_pair/`, `cursed_generator/`, `replicate_client/`, `__init__.py`, `.DS_Store`.

**Rollback:** `git clone git@github.com:closestfriend/creative-production-pipeline.git src/creative-production-pipeline` (and the fever-dream one) re-fetches them from GitHub.

**✅ STOP POINT 2 — the repo-inside-a-repo hazard is gone.** git tooling on av-pair will behave normally now.

---

## Phase 3: Archive provably-dead code (both repos)

> ⚠️ **CORRECTION (2026-05-31):** an earlier draft of this phase deleted
> `random_montage.py`, `beat_strobe.py`, `drift_composition.py` as "obsolete prototypes."
> That was wrong. Verified usage check shows `random_montage.py` is referenced by 4 shell
> scripts (`batch_random_montage.sh`, `batch_zeiss_montage.sh`, `test_aspect_modes*.sh`) and
> CLAUDE.md, and is the engine behind real named output (*Zeiss*, *Glass Orchard*).
> `beat_strobe.py` has unique creative knobs (manual BPM, beat-influence, drift). They have
> capabilities the philm tools lack (non-beat random montage, stretch/native aspect, drift) and
> were **never committed** (working file is the only copy). **They are KEEPERS — not deleted
> here.** Only clearly-dead artifacts are removed in this phase.

**Files:**
- Remove (untracked, philm — orphaned TypeScript ancestor): `PHILM/cli.ts`, `PHILM/functions.ts`, `PHILM/modes.ts`
- Remove (empty, philm): `PHILM/100CANON_results/`, `PHILM/101CANON_results/`
- Remove (TRACKED, av-pair): `AVPAIR/legacy/av_pair/create_composition.py`
- **KEEP** (av-pair, do NOT delete): `random_montage.py`, `beat_strobe.py` (live creative instruments)
- **DEFER** to Phase 7 (av-pair): `drift_composition.py` — the only true duplicate, but av-pair's sole drift engine; decide alongside the canonical-home question.

- [ ] **Step 1: Back up the philm orphans (untracked → not in git, backup is the only safety net)**

```bash
ARCH="/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/code-backups"
mkdir -p "$ARCH"
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
cp cli.ts functions.ts modes.ts "$ARCH"/
ls -la "$ARCH"
```

Expected: `cli.ts`, `functions.ts`, `modes.ts` present in the archive.

- [ ] **Step 2: Confirm the `.ts` files really are the orphaned Google ancestor (not something live)**

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
head -6 cli.ts modes.ts functions.ts
grep -rln -E 'cli\.ts|functions\.ts|modes\.ts' . --include='*.json' --include='*.md' --include='*.py' 2>/dev/null \
  | grep -v LANDSCAPE | grep -v drive-consolidation || echo "  (no project references — confirmed orphan)"
```

Expected: Apache/Google-LLC headers; no package.json/tsconfig referencing them (no Node project) → confirmed orphan.

- [ ] **Step 3: Remove the philm orphans (untracked → plain rm) and empty dirs**

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
rm -f cli.ts functions.ts modes.ts
rmdir 100CANON_results 101CANON_results
ls *.ts 2>/dev/null || echo "no .ts files remain (correct)"
```

Expected: "no .ts files remain"; the two CANON dirs gone (`rmdir` only succeeds if truly empty — a built-in safety check).

- [ ] **Step 4: Remove the tracked av-pair legacy copy via git (recoverable from history)**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
git rm legacy/av_pair/create_composition.py
git commit -m "chore: remove obsolete legacy create_composition.py

Superseded by src/av_pair/create_composition.py. Recoverable from git history.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Expected: one commit; `legacy/av_pair/` now empty or gone.

**Rollback:** philm `.ts` → copy back from the archive area. legacy file → `git revert HEAD` or `git checkout HEAD~1 -- legacy/av_pair/create_composition.py`.

**✅ STOP POINT 3 — only genuinely-dead code removed, all backed up.** The orphaned TypeScript
ancestor (philm) and the tracked `legacy/` duplicate are gone. `random_montage.py` and
`beat_strobe.py` are intentionally retained as live creative instruments.

---

## Phase 4: Corral disposable render iterations (move, don't delete)

**Why move not delete:** these renders are NOT reliably reproducible (seeds aren't persisted),
so we relocate them to a review folder. You delete the folder yourself once you've cherry-picked
the keepers. All are untracked in git (verified — `.mp4`/`.mov` are gitignored), so moving them
does not dirty either repo.

**Files (philm, all untracked):**
- Move: `PHILM/carti_cuts/` (5.3 G), `PHILM/carti_cuts_raw/` (779 M), `PHILM/oakley_cuts/` (260 M)

**Files (av-pair):**
- Move: `AVPAIR/output/av_compositions/` (414 M)

- [ ] **Step 1: Re-confirm these dirs are untracked (safety check before moving)**

```bash
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
for d in carti_cuts carti_cuts_raw oakley_cuts; do
  echo "$d tracked files: $(git ls-files "$d" | wc -l | tr -d ' ')"   # expect 0
done
```

Expected: each prints `0`.

- [ ] **Step 2: Move philm render dirs to the review area**

```bash
REVIEW="/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/renders-to-review"
cd "/Volumes/2025_exSSD_2tb/video-analyzer-v2"
mv carti_cuts carti_cuts_raw oakley_cuts "$REVIEW"/
ls "$REVIEW"
```

Expected: the three dirs now under `renders-to-review/`; gone from the philm root.

- [ ] **Step 3: Move av-pair generated output to the review area**

```bash
REVIEW="/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/renders-to-review"
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
mv output/av_compositions "$REVIEW/avpair_av_compositions"
ls output/
```

Expected: `output/` retains `replicate_output/` (and recreates `av_compositions` on next run); the renders are now in review.

**Rollback:** `mv` the dirs back from `renders-to-review/` to their original locations.

**✅ STOP POINT 4 — repo working dirs are clean.** ~6.7 GB of renders are now in one labeled
folder. **Deleting that folder when you're ready reclaims the full ~6.7 GB** — but that delete
is your call, on your timeline.

---

## Phase 5: Prevent recurrence — harden av-pair .gitignore

**Files:**
- Modify: `AVPAIR/.gitignore`

- [ ] **Step 1: Check whether av-pair already ignores media & venvs**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
grep -nE '\*\.mp4|\*\.mov|venv|output/' .gitignore || echo "MISSING — needs entries"
```

Expected: either shows existing rules, or "MISSING".

- [ ] **Step 2: Append media/venv/output ignore rules if missing**

Only run if Step 1 showed gaps. Append the block:

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
cat >> .gitignore <<'EOF'

# Media renders & source (keep out of git history)
*.mp4
*.mov
*.mkv
*.avi
*.m4v
*.webm
*.wav
*.mp3
output/
assets/source_videos/

# Virtualenvs
venv/
venv_gradio/
venv_transcribe/
EOF
git add .gitignore
git commit -m "chore: ignore media renders, source videos, and venvs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Expected: one commit updating `.gitignore`. (philm already ignores `*.mp4`/`*.mov` — no change needed there.)

**Rollback:** `git revert HEAD`.

**✅ STOP POINT 5 — renders can no longer silently re-enter av-pair's history.**

---

## Phase 6 (ADVANCED, OPTIONAL): Rewrite av-pair history to reclaim its 1.2 GB

**Why separate:** av-pair's 1.2 GB lives in *reachable* commits (old `outputs3/`/`outputs23/`
montage blobs of 305/224/215 MB). Removing it rewrites history — different from philm's
garbage-collect. Only do this when you're ready, ideally right after pushing a backup.

**Prerequisite:** install `git-filter-repo` (`brew install git-filter-repo`) or use BFG.

- [ ] **Step 1: Push a full backup of av-pair to its remote FIRST**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
git push origin --all && git push origin --tags
```

Expected: remote is up to date (so history is recoverable if the rewrite goes wrong).

- [ ] **Step 2: Strip the large committed render paths from all history**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
git filter-repo --path outputs3 --path outputs23 --invert-paths
git reflog expire --expire=now --all && git gc --prune=now
du -sh .git
```

Expected: `.git` drops toward ~tens of MB. (Confirm the stripped paths are the right ones first with `git rev-list --objects --all | grep -E 'outputs3|outputs23' | head`.)

- [ ] **Step 3: Force-push the rewritten history**

```bash
cd "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair"
git push origin --force --all
git push origin --force --tags
```

Expected: remote updated. ⚠️ Coordinate if anyone else has clones — they must re-clone.

**Rollback:** re-clone from the backup pushed in Step 1 (before the force-push), or `git reflog`
if you haven't yet expired it.

**✅ STOP POINT 6 — av-pair reclaims ~1.2 GB.**

---

## Phase 7 (DEFERRED — its own future effort): Unify the montage engine

> **This is a code refactor, not cleanup. Do NOT bundle it with the above.** It deserves its
> own session and its own plan because of a feature gap discovered during analysis.

**The gap (important):** `ez_mv_core.py` is the cleaner library API (progress callback, cut
density, philm-JSON peak-intensity offsets) **but it is NOT a strict superset of
`carti_cut.py`.** `carti_cut.py` has visual effects (`shrink`, `zoom`, white-flash variations)
and proxy-compression caching that `ez_mv_core.py` lacks. A correct unification must *port those
features into the core*, then make `carti_cut.py` a thin CLI over it — otherwise you silently
lose the zoom/shrink/proxy behavior.

**Sketch of the eventual plan (fill in when you tackle it):**
1. Add `effect` (normal/shrink/zoom) handling + proxy caching to `ez_mv_core.extract_segment`/`assemble`, behind args defaulting to current behavior.
2. Smoke test: render a 10-second clip through the core and assert the output exists and is the right duration:
   ```bash
   # Expected: exits 0, prints a duration within ~0.5s of the audio clip length
   python -c "from scripts.ez_mv_core import detect_beats; print('import ok')"
   ```
3. Rewrite `carti_cut.py` `main()` to import from `ez_mv_core` (delete its duplicated engine body).
4. Do the same drift unification: `drift_core.py` engine + a CLI lifted from `drift_cut.py`; retire `drift_cut.py`. **Mind the seed gotcha** (documented in `LANDSCAPE.md`): the two are not seed-compatible.
5. Decide the single canonical home (philm `scripts/` vs av-pair `src/av_pair/`) and have the other import or be archived.

**Leave this phase unchecked.** It's a pointer, not a today task.

---

## Final tally

- [ ] **Record the result**

```bash
{ echo "=== AFTER CONSOLIDATION $(date) ==="
  du -sh "/Volumes/2025_exSSD_2tb/video-analyzer-v2" \
        "/Volumes/2025_exSSD_2tb/video-analyzer-v2/.git" \
        "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair" \
        "/Volumes/2025_exSSD_2tb/💻 Development & Code/Development/av-pair/.git" \
        "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/renders-to-review"
} | tee -a "/Volumes/2025_exSSD_2tb/_consolidation_2026-05-31/baseline.txt"
```

**Expected space outcome:**
- Phase 1: **~1.5 GB freed immediately** (philm `.git`).
- Phase 4: **~6.7 GB staged for deletion** (delete `renders-to-review/` when ready).
- Phase 6 (optional): **~1.2 GB freed** (av-pair `.git`).
- **Total reclaimable: ~9.4 GB**, plus a markedly cleaner working tree in both repos.

**Untouched & safe:** av-pair `assets/source_videos` (8.2 G source), philm `input/`, all branch
history, the canonical montage engines (`ez_mv_core.py`, `drift_core.py`, `carti_cut.py`,
`drift_cut.py`), the `philm` product, and av-pair's apps/MCP servers.

---

## Self-review notes (done during authoring)

- **Coverage:** maps to every cleanup item in `LANDSCAPE.md` (git bloat ×2, nested repos,
  orphan `.ts`, empty dirs, obsolete prototypes, render corralling, gitignore hardening). The
  montage-engine *merge* is intentionally deferred (Phase 7) as a refactor, not cleanup.
- **Verified before commands written (2026-05-31):** philm garbage is unreachable-without-reflog
  (76 blobs); render dirs untracked; av-pair prototypes untracked + unimported; nested repos are
  `.DS_Store`-only shells with live GitHub remotes; `legacy/...py` is tracked.
- **Key safety correction:** av-pair prototypes are UNTRACKED (no git recovery) → Phase 3 backs
  them up before `rm`.
