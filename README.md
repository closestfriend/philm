# video-analyzer v2

Philosophical video analysis using Gemini 2.5 Flash. Python rewrite with `uv` for speed and elegance.

## Philosophy

> "The orthogonality is the magic: hard structural constraints + rich interpretive prompts = usable philosophical analysis."

This tool provides **schemas** (Pydantic models enforcing structure) and **modes** (theoretical frameworks guiding interpretation) for analyzing video through various philosophical lenses:

- **Levinas**: Ethical encounters and the face of the Other
- **Massumi**: Affective intensities and atmospheric analysis  
- **Deleuze**: Rhythms, deterritorialization, and lines of flight
- **Mulvey**: Gaze structures and visual pleasure
- **Kant/Burke**: The sublime and aesthetic overwhelm
- **Camera Analysis**: Kinetic energy from Tarkovsky to Safdie/Death Grips

## Installation

```bash
# Install with uv
uv sync

# Or install globally with uv tool
uv tool install .
```

## Usage

```bash
# Basic analysis modes
vanalyze video.mp4 --captions
vanalyze video.mp4 --affect
vanalyze video.mp4 --camera

# Deep mode (includes FFmpeg technical analysis)
vanalyze video.mp4 --affect --deep

# Batch processing
vanalyze --folder /path/to/videos --affect --recursive

# Custom prompts
vanalyze video.mp4 --custom "analyze moments of stillness"

# Output options
vanalyze video.mp4 --affect --json
vanalyze video.mp4 --affect --output results.json
```

## Available Modes

- `--captions`: A/V captions with spoken text
- `--paragraph`: 3-5 sentence summary
- `--key-moments`: Bullet point extraction
- `--affect`: Massumi affect theory analysis
- `--camera`: Camera kinetics (Tarkovsky → Safdie scale)
- `--levinas`: Ethical encounters and the face
- `--gaze`: Mulvey gaze analysis
- `--sublime`: Kant/Burke sublime classification
- `--rhythm`: Deleuzian tempo/deterritorialization
- `--custom "prompt"`: Custom analysis

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run the CLI during development
uv run vanalyze --help

# Format code
uv run ruff format .
```

## Environment

Create a `.env` file:

```
GEMINI_API_KEY=your_key_here
```

## Architecture

- **models.py**: Pydantic schemas for all philosophical frameworks
- **analyzer.py**: Gemini API integration with structured outputs
- **technical.py**: FFmpeg scene detection and chaos metrics
- **modes.py**: Theoretical prompt definitions
- **cli.py**: Typer-based CLI with rich output
- **output.py**: Formatting (human-readable, JSON, etc.)

---

Built with `uv` for speed. Theory-first, implementation-clean.
