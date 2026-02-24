---
name: philm
description: Use when the user wants to analyze video footage, catalog clips, run philosophical analysis, build sizzle reels, search the archive, or work with the Philm CLI tool in any capacity.
---

# Philm

Philosophical video analysis CLI. Uploads video to Gemini 2.5 Flash and returns structured analysis using Pydantic schemas.

> **Setup:** Copy this file to `~/.claude/skills/philm/SKILL.md`. Update the repo path below to match your local clone.

**Repo:** `~/path/to/philm`
**Run:** `uv run vanalyze main video.mp4 --mode` or `vanalyze main video.mp4 --mode` (if installed globally via `uv tool install .`)

## Analysis Modes

### Philosophical
| Flag | Framework | Focus |
|------|-----------|-------|
| `--affect` | Massumi | Pre-cognitive intensity |
| `--camera` | Tarkovsky→Safdie | Contemplative↔frenetic spectrum |
| `--gaze` | Mulvey | Power of looking |
| `--sublime` | Kant/Burke | What overwhelms representation |
| `--levinas` | Levinas | Face of the Other |
| `--rhythm` | Deleuze/Guattari | Territorialization/deterritorialization |
| `--baudrillard` | Baudrillard | Simulacra, hyperreality |
| `--virilio` | Virilio | Speed, accident |
| `--foucault` | Foucault | Power, discipline, subject |
| `--epistemic` | — | Truth claims, evidence |
| `--zizek` | Žižek/Lacan | Parallax gap, ideology |
| `--barthes` | Barthes | Punctum/studium, myth |
| `--benjamin` | Benjamin | Aura, dialectical image |
| `--hauntology` | Fisher/Han/Curtis | Cancelled futures, capitalist realism |

### Production
| Flag | Purpose |
|------|---------|
| `--sizzle` | Shot classification, energy scoring, tone for sizzle reel editing |

### Basic Extraction
`--captions` `--paragraph` `--key-moments` `--table` `--chart excitement|importance|people`

## Common Workflows

```bash
# Single mode
vanalyze main video.mp4 --baudrillard

# Multiple modes (one upload, parallel analysis)
vanalyze main video.mp4 --virilio --baudrillard --hauntology

# JSON output for piping
vanalyze main video.mp4 --affect --json --output results.json

# Batch a folder
vanalyze main --folder ./footage --gaze --recursive

# Local/private (Ollama, no API key needed)
vanalyze main video.mp4 --local
vanalyze main video.mp4 --local --model qwen3-vl:8b --frames 8

# Add FFmpeg technical context
vanalyze main video.mp4 --camera --deep

# Strip audio to reduce upload size ~25%
vanalyze main video.mp4 --affect --no-audio
```

## Sizzle + Storyboard Workflow

```bash
# 1. Analyze footage
vanalyze main footage/*.mp4 --sizzle --json -o ./sizzle_results/

# 2. Match to storyboard
python scripts/match_storyboard.py storyboard.json -r ./sizzle_results/ --top 3 --format md
```

## Archive (SQLite corpus at `~/.vanalyze/archive.db`)

```bash
vanalyze archive init
vanalyze archive scan ./footage --recursive
vanalyze archive status
vanalyze archive process --folder ./footage --affect --gaze
vanalyze archive search --mode affect --min-intensity 8
vanalyze archive search --mode gaze --type voyeuristic
vanalyze archive stats
```

## Adding a New Mode

1. **`models.py`** — Define Pydantic schema (`NewMoment`, `NewResult(BaseAnalysisResult)`)
2. **`modes.py`** — Define `AnalysisMode`, register in `ALL_MODES` dict
3. **`cli.py`** — Add Typer flag, add to `mode_flags` dict
4. **`output.py`** — Add display formatting under `format_for_display()`

## Key File Locations

```
src/video_analyzer/
├── models.py       # Pydantic schemas
├── modes.py        # Theoretical prompts + mode registry
├── analyzer.py     # Gemini API integration
├── local.py        # Ollama backend
├── cli.py          # CLI entry point
├── output.py       # Rich terminal formatting
├── batch.py        # Multi-video processing
├── archive.py      # SQLite persistence
└── archive_cli.py  # Archive subcommands

scripts/
├── match_storyboard.py     # Sizzle→storyboard matching
├── compress_for_gemini.py  # Preprocess video for upload
└── harvest_catalog.py      # Metadata extraction
```

## Environment

- `GEMINI_API_KEY` in `.env` (cloud mode)
- Ollama running locally for `--local` mode: `ollama pull qwen3-vl:4b`
