# v1 (TypeScript) → v2 (Python) Migration

## Why Python?

The v1 TypeScript implementation was excellent for the **web UI**, but for pure **CLI/research workflows**, Python offers substantial advantages:

### 1. **SDK Maturity**
- `google-generativeai` (Python) is more mature than `@google/genai` (TypeScript)
- Better structured output support
- More consistent API surface

### 2. **FFmpeg Integration**
- Python's `subprocess` is cleaner than Node's `execSync`
- Better error handling and timeout management
- More natural for complex video processing pipelines

### 3. **Scientific Ecosystem**
- Future: pandas for analyzing results across videos
- Future: matplotlib/seaborn for visualizing affect patterns
- Future: scipy for temporal correlation analysis

### 4. **Type Safety with Pydantic**
- Runtime validation of LLM outputs
- Beautiful error messages when schemas mismatch
- Automatic JSON schema generation from Python classes
- Philosophy → Code is more direct

### 5. **Speed with uv**
- Faster than npm install
- Better dependency resolution
- Cleaner project structure

## Architectural Improvements

### v1 (TypeScript)
```
cli.ts                    # 700+ lines, everything in one file
├── Video upload logic
├── FFmpeg integration  
├── Mode definitions
├── Gemini API calls
├── Output formatting
└── CLI argument parsing
```

### v2 (Python)
```
src/video_analyzer/
├── models.py          # Pure Pydantic models (philosophical schemas)
├── modes.py           # Mode definitions (prompts + models)
├── analyzer.py        # Gemini API integration
├── technical.py       # FFmpeg analysis
├── output.py          # Rich formatting
└── cli.py             # Typer CLI
```

**Separation of concerns:**
- Models define *what* (structure)
- Modes define *how* (interpretation) 
- Analyzer handles *execution*
- Output handles *presentation*

## Side-by-Side Comparison

### Defining a New Mode

**v1 (TypeScript):**
```typescript
// Add to MODES object
affect: {
  name: 'Affect Analysis',
  fn: 'analyze_affect',
  prompt: `...long prompt...`,
}

// Add to FUNCTIONS array
{
  name: 'analyze_affect',
  description: '...',
  parameters: {
    type: Type.OBJECT,
    properties: {
      timecodes: {
        type: Type.ARRAY,
        items: { /* manually define schema */ }
      }
    }
  }
}
```

**v2 (Python):**
```python
# models.py - Define structure
class AffectMoment(BaseModel):
    time: str
    intensity: int = Field(..., ge=1, le=10)
    atmosphere: str
    vector: str
    captures: bool

class AffectResult(BaseAnalysisResult):
    timecodes: list[AffectMoment]

# modes.py - Define interpretation
AFFECT = AnalysisMode(
    name="affect",
    description="Massumi affect theory",
    result_model=AffectResult,
    prompt="""...long prompt..."""
)
```

The Python version is:
- More declarative
- Type-safe at runtime
- Schema auto-generates from Pydantic
- Philosophy → Code is clearer

### Running Analysis

**v1:**
```bash
npx tsx cli.ts video.mp4 --affect --deep
```

**v2:**
```bash
vanalyze video.mp4 --affect --deep
```

### Output Quality

**v1:** Plain text formatting
**v2:** Rich terminal UI with colors, tables, panels

## What We Kept

- All philosophical frameworks (Levinas, Massumi, Deleuze, Mulvey, etc.)
- FFmpeg technical analysis with chaos index
- Same Gemini 2.5 Flash integration
- Batch processing capability
- Custom prompts
- Deep mode

## What We Improved

- **Type safety**: Pydantic validates LLM outputs
- **Modularity**: Clean separation of concerns
- **Extensibility**: Add new modes in 10 lines
- **Output**: Rich formatting, JSON export
- **Speed**: uv is faster than npm
- **DX**: Better error messages, cleaner code

## Migration Path for Users

If you're using the TypeScript version's web UI, **keep it**. The React interface is valuable for interactive exploration.

If you're using the CLI for:
- Batch processing videos
- Research workflows
- Automated analysis pipelines

→ Switch to Python v2 for better ergonomics and future-proofing.

## Future Enhancements (Python-Specific)

1. **Result Analysis**
   ```python
   import pandas as pd
   df = load_analysis_results('videos/*.json')
   df.groupby('mode')['intensity'].mean()
   ```

2. **Temporal Visualization**
   ```python
   import matplotlib.pyplot as plt
   plot_affect_over_time(result)
   ```

3. **Comparative Analysis**
   ```python
   compare_camera_styles(['video1.json', 'video2.json'])
   ```

4. **Statistical Clustering**
   ```python
   cluster_similar_videos(corpus, mode='affect')
   ```

These become trivial with Python's scientific stack.

## Coexistence Strategy

- **v1 (TypeScript)**: Web UI, interactive exploration, one-off analyses
- **v2 (Python)**: CLI, batch processing, research, automation, analysis of analyses

Both use the same Gemini API, same philosophical frameworks, same core insights. Pick the right tool for the job.
