# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Philm is a philosophical video analysis CLI that reads video through critical theory frameworks. It uploads video to Gemini 2.5 Flash and returns structured analysis using Pydantic schemas.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI (Gemini backend)
uv run vanalyze main video.mp4 --affect

# Local mode (Ollama backend - free, private)
uv run vanalyze main video.mp4 --local
uv run vanalyze main video.mp4 --local --model qwen3-vl:8b --frames 4

# Install globally
uv tool install .
vanalyze main video.mp4 --virilio

# Multiple modes (single upload, parallel analysis)
vanalyze main video.mp4 --virilio --baudrillard --hauntology

# Batch processing
vanalyze main --folder ./videos --gaze --recursive
vanalyze main --folder ./videos --local  # local batch

# Format code
uv run ruff format .

# Run tests
uv run pytest
```

## Architecture

```
src/video_analyzer/
├── models.py      # Pydantic schemas - define WHAT (structure)
├── modes.py       # Theoretical prompts - define HOW (interpretation)
├── analyzer.py    # Gemini API integration, video upload
├── local.py       # Ollama backend - frame extraction + local VLM
├── cli.py         # Typer CLI entry point
├── output.py      # Rich terminal formatting
├── batch.py       # Multi-video processing
├── archive.py     # SQLite persistence layer
├── archive_cli.py # Archive subcommands
└── technical.py   # FFmpeg scene detection
```

The separation between `models.py` (structural constraints) and `modes.py` (interpretive prompts) is fundamental. The same schema can be filled by different theoretical frameworks.

## Adding a New Analysis Mode

1. **Define the schema** in `models.py`:
```python
class NewMoment(BaseModel):
    time: str
    field: str = Field(..., description="What this captures")

class NewResult(BaseAnalysisResult):
    timecodes: list[NewMoment]
```

2. **Define the mode** in `modes.py`:
```python
NEW_MODE = AnalysisMode(
    name="new-mode",
    description="Brief description",
    result_model=NewResult,
    prompt="""Theoretical prompt here..."""
)
```

3. **Register in `ALL_MODES`** dict in `modes.py`

4. **Add CLI flag** in `cli.py` and update `mode_flags` dict

5. **Add output formatting** in `output.py` under `format_for_display()`

## Key Patterns

- **Pydantic for LLM output validation**: All Gemini responses are validated against Pydantic models with `response_schema` parameter
- **Single upload, multiple analyses**: For multi-mode runs, video uploads once and gets analyzed by each mode
- **Archive layer**: SQLite database at `~/.vanalyze/archive.db` stores analyses with dedicated tables per theoretical framework
- **Theoretical orthogonality**: Each mode is independent; same footage can be read through any framework
- **Dual backend**: Gemini (cloud, fast, full video) vs Ollama (local, free, frame-based)

## Environment

- `GEMINI_API_KEY` in `.env` file (for cloud mode)
- Ollama running locally (for `--local` mode): `ollama pull qwen3-vl:4b`
