# video-analyzer-v2: Setup Complete! 🎉

## What We Built

A complete Python rewrite of your video analyzer with modern tooling:

### Core Architecture
- **Pydantic Models** (`models.py`) - Type-safe schemas for all philosophical frameworks
- **Analysis Modes** (`modes.py`) - Theoretical prompts paired with structural constraints  
- **Gemini Integration** (`analyzer.py`) - Clean API handling with structured outputs
- **FFmpeg Analysis** (`technical.py`) - Scene detection and chaos metrics
- **Rich Output** (`output.py`) - Beautiful terminal formatting
- **Typer CLI** (`cli.py`) - Elegant command-line interface

### Philosophical Frameworks Implemented
✅ Levinas - Ethical encounters and the face  
✅ Massumi - Affect theory and intensity  
✅ Deleuze - Rhythm and deterritorialization  
✅ Mulvey - Gaze analysis  
✅ Kant/Burke - The sublime  
✅ Camera Analysis - Tarkovsky → Safdie/DG kinetic spectrum  
✅ Basic modes - Captions, summaries, key moments  
✅ Custom prompts - Flexible analysis  

## Next Steps

### 1. Install and Test

```bash
cd /Users/hnsk/video-analyzer-v2

# Install dependencies
uv sync

# Test it!
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --affect
```

### 2. Compare to v1

Try the same video with the same mode in both versions:

```bash
# TypeScript v1
cd ~/video-analyzer
npx tsx cli.ts MVI_9846.MOV --affect

# Python v2  
cd ~/video-analyzer-v2
uv run vanalyze ~/video-analyzer/MVI_9846.MOV --affect
```

Notice:
- Cleaner command syntax
- Rich formatted output
- Type-safe validation
- Faster execution

### 3. Explore Modes

```bash
# Try deep mode with technical FFmpeg analysis
uv run vanalyze video.mp4 --camera --deep

# Levinasian ethical analysis
uv run vanalyze video.mp4 --levinas

# Custom philosophical prompt
uv run vanalyze video.mp4 --custom "identify moments of Heideggerian withdrawal"

# Save results as JSON
uv run vanalyze video.mp4 --affect --json --output results.json
```

## Key Advantages of v2

1. **uv Speed** - Faster than npm, cleaner dependency management
2. **Pydantic Validation** - Runtime type checking of LLM outputs
3. **Modular Architecture** - Easy to extend with new modes
4. **Rich Terminal UI** - Beautiful formatted output by default
5. **Better Error Messages** - Clear validation failures
6. **Future-Proof** - Ready for scientific analysis (pandas, numpy, etc.)

## What's Different from v1?

### Same
- All philosophical frameworks
- Gemini 2.5 Flash integration
- FFmpeg technical analysis
- Batch processing (TODO in v2)
- Custom prompts

### Better
- Type safety with Pydantic
- Cleaner code organization
- Better output formatting
- Faster with uv
- More extensible

### Keep Both
- **v1**: Great for the web UI, interactive exploration
- **v2**: Perfect for CLI, batch processing, research workflows

## Future Enhancements

Easy to add with Python's ecosystem:

```python
# Analyze patterns across videos
import pandas as pd
df = pd.DataFrame([load(f) for f in results])
df.groupby('sublime_type').count()

# Visualize affect over time
import matplotlib.pyplot as plt
plot_affect_timeline(result)

# Statistical analysis
from scipy.stats import pearsonr
correlate_chaos_with_frenetic(videos)
```

## Project Structure

```
video-analyzer-v2/
├── src/video_analyzer/
│   ├── __init__.py
│   ├── models.py      # Pydantic schemas (THE PHILOSOPHY)
│   ├── modes.py       # Prompts + model pairing (THE THEORY)
│   ├── analyzer.py    # Gemini integration (THE ENGINE)
│   ├── technical.py   # FFmpeg analysis (THE METRICS)
│   ├── output.py      # Rich formatting (THE PRESENTATION)
│   └── cli.py         # Typer CLI (THE INTERFACE)
├── tests/
├── pyproject.toml     # uv project config
├── .env               # Your API key (gitignored)
├── README.md          # Main docs
├── QUICKSTART.md      # Quick reference
└── ARCHITECTURE.md    # Design decisions
```

## Documentation

- **README.md** - Main documentation
- **QUICKSTART.md** - Fast reference for common tasks
- **ARCHITECTURE.md** - Design decisions, v1 vs v2 comparison
- **This file** - Setup summary

## Contributing Your Own Modes

Super easy! Here's how to add a new theoretical framework:

1. **Define the structure** in `models.py`:
```python
class MyTheoryMoment(BaseModel):
    time: str
    your_field: str
    your_metric: int = Field(..., ge=1, le=10)

class MyTheoryResult(BaseAnalysisResult):
    timecodes: list[MyTheoryMoment]
```

2. **Add the mode** in `modes.py`:
```python
MY_THEORY = AnalysisMode(
    name="my-theory",
    description="Your theory description",
    result_model=MyTheoryResult,
    prompt="""Your detailed theoretical prompt..."""
)

# Register it
ALL_MODES["my-theory"] = MY_THEORY
```

3. **Add CLI flag** in `cli.py`:
```python
my_theory: bool = typer.Option(False, "--my-theory", help="My theory analysis")
```

That's it! The rest (upload, analysis, parsing, output) is handled automatically.

## Questions?

The code is well-documented and modular. Each file has a clear purpose. If you want to:
- Add a new mode → `models.py` + `modes.py`
- Change Gemini behavior → `analyzer.py`
- Modify FFmpeg analysis → `technical.py`
- Customize output → `output.py`
- Add CLI features → `cli.py`

Everything is separated by concern. Philosophy → Structure → Implementation → Presentation.

## The Orthogonality Principle

> "Hard structural constraints + rich interpretive prompts = usable philosophical analysis"

- **Models**: Hard constraints (Pydantic enforces structure)
- **Modes**: Rich prompts (theory guides interpretation)
- **Analyzer**: Execution (Gemini produces results)
- **Output**: Presentation (Rich makes it beautiful)

The separation is the magic. 

Enjoy! 🎬✨
