# Quick Start Guide

## 1. Install Dependencies

```bash
cd /Users/hnsk/video-analyzer-v2
uv sync
```

This will:
- Create a virtual environment in `.venv/`
- Install all dependencies (google-generativeai, typer, pydantic, rich, python-dotenv)
- Lock the dependency versions in `uv.lock`

## 2. Test the CLI

```bash
# Show help
uv run vanalyze --help

# Test with your existing video
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --affect

# Try deep mode with technical analysis
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --camera --deep

# Custom prompt
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --custom "analyze moments of movement"

# JSON output
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --affect --json

# Save to file
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --affect --output analysis.json
```

## 3. Install Globally (Optional)

```bash
# Install as a global CLI tool
uv tool install .

# Then use directly without `uv run`
vanalyze --help
vanalyze video.mp4 --affect
```

## 4. Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Format code
uv run ruff format .

# Run tests (when we add them)
uv run pytest
```

## Key Differences from TypeScript Version

1. **Cleaner CLI**: `vanalyze video.mp4 --affect` instead of `npx tsx cli.ts video.mp4 --affect`
2. **Pydantic Models**: Type-safe, validated data structures for all philosophical frameworks
3. **Rich Output**: Beautiful terminal formatting by default
4. **uv Speed**: Faster dependency resolution and execution
5. **Same Functionality**: All modes from v1, same Gemini integration, same FFmpeg technical analysis

## Available Modes

- `--captions` - A/V captions with spoken text
- `--paragraph` - 3-5 sentence summary
- `--key-moments` - Key moment extraction
- `--table` - 5 key shots with objects
- `--affect` - Massumi affect theory analysis
- `--camera` - Camera kinetics (Tarkovsky → Safdie scale)
- `--levinas` - Levinasian ethical encounters
- `--gaze` - Mulvey gaze analysis
- `--sublime` - Kant/Burke sublime classification
- `--rhythm` - Deleuzian rhythm analysis
- `--chart <type>` - Numeric charts (excitement, importance, people)
- `--custom "prompt"` - Custom analysis

## Next Steps

Want to add:
- Batch folder processing
- Progress bars for long videos
- Result caching
- Comparative analysis across multiple videos
- Export to different formats (Markdown, HTML)
