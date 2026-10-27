# Philm

Philosophical video analysis. A CLI tool that reads video through critical theory.

## Thesis

Every recording technology contains its own ideology. Philm makes that ideology legible.

The tool pairs **hard structural constraints** (Pydantic schemas) with **rich interpretive prompts** (theoretical frameworks) to produce structured readings of video content. The orthogonality is the point: the same schema can be filled by Baudrillard or Virilio, the same footage can be read through Mulvey or Benjamin. The apparatus doesn't privilege one framework over another—it treats theory as a parameter.

```
vanalyze main video.mp4 --virilio --baudrillard --hauntology
```

## What It Does

Philm uploads video to Gemini 2.5 Flash and returns structured philosophical analysis. Each mode applies a specific theoretical framework:

| Mode | Framework | Asks |
|------|-----------|------|
| `--affect` | Massumi | What pre-cognitive intensities move through this? |
| `--camera` | Tarkovsky→Safdie | Where does this sit on the contemplative↔frenetic spectrum? |
| `--gaze` | Mulvey | Who looks at whom, and with what power? |
| `--sublime` | Kant/Burke | What overwhelms representation here? |
| `--levinas` | Levinas | Where does the face of the Other emerge? |
| `--rhythm` | Deleuze | What territorializes, what escapes? |
| `--baudrillard` | Baudrillard | Which order of simulacra? Does the model precede the real? |
| `--virilio` | Virilio | What speed regime governs? Where is the accident? |
| `--foucault` | Foucault | What power operates? What subject is produced? |
| `--epistemic` | - | What truth claims are made? What counts as evidence? |
| `--zizek` | Žižek/Lacan | Where is the parallax gap? What ideology operates? |
| `--barthes` | Barthes | What wounds (punctum)? What myths naturalize? |
| `--benjamin` | Benjamin | What is the aura status? Where is the dialectical image? |
| `--hauntology` | Fisher/Han/Curtis | What futures were cancelled? What smoothness conceals? |
| `--sizzle` | Production | Analysis for sizzle reel editing (shots, pacing, emotion). |

Plus basic extraction modes: `--captions`, `--paragraph`, `--key-moments`, `--table`, `--chart`

## Installation

```bash
# Clone and install with uv
git clone https://github.com/closestfriend/philm.git
cd philm
uv sync

# Set your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# Run
uv run vanalyze main video.mp4 --affect
```

Or install globally:

```bash
uv tool install .
vanalyze main video.mp4 --virilio
```

## Usage

```bash
# Single mode
vanalyze main video.mp4 --baudrillard

# Multiple modes (one upload, parallel analysis)
vanalyze main video.mp4 --virilio --baudrillard --hauntology

# JSON output
vanalyze main video.mp4 --affect --json --output results.json

# Batch processing
vanalyze main --folder ./videos --gaze --recursive

# Strip audio (reduces upload size ~25%)
vanalyze main video.mp4 --affect --no-audio

# Include FFmpeg technical analysis
vanalyze main video.mp4 --camera --deep

# Custom prompt
vanalyze main video.mp4 --custom "find moments where time dilates"
```

## Local Analysis (Ollama)

Philm supports local analysis using Ollama (default model: `qwen3-vl:4b`). This runs entirely on your machine, extracting frames from the video and passing them to the local VLM.

```bash
# Run with local model
vanalyze main video.mp4 --local

# Specify model and frame count
vanalyze main video.mp4 --local --model llava:latest --frames 8
```

## Example Output

From FPV drone strike footage, `--baudrillard`:

```
1:15 | [fourth] | pure_simulacrum | PRECESSION
     sign: Content virality, channel growth, impact
     implosion: Event/media, content/platform, war/entertainment

     Drone footage shows strikes on buildings with a prominent
     YouTube 'SUBSCRIBE' button overlay, indicating the video's
     status as media content.
```

From personal footage in an empty commercial plaza, `--hauntology`:

```
0:49 | [hauntological] | smooth: negative | SUFFERING INDIVIDUALIZED
     capitalist realism: precarity_normalized
     lost future: Successful small businesses, community leisure

     The camera pans to reveal neon signs for 'Relax Spa' and
     'Tropical Fiyah Jamaican Restaurant.' These names evoke
     promises of leisure and vibrancy that are conspicuously
     absent from the desolate scene, highlighting failed
     capitalist aspirations.
```

From car accident footage, `--virilio`:

```
3:30-4:00 | [mechanical] | accident: integral | REAL-TIME
     dromology: The flashing lights of emergency vehicles signify
     a disruption of the normal flow of mechanical speed, revealing
     the 'integral accident' inherent in high-speed mobility.
     war machine: Emergency response as 'pure war' in managing
     the accident of speed.
```

## Architecture

```
src/video_analyzer/
├── models.py      # Pydantic schemas (structure)
├── modes.py       # Theoretical prompts (interpretation)
├── analyzer.py    # Gemini API integration
├── local.py       # Ollama local backend
├── cli.py         # Typer CLI
├── output.py      # Rich terminal formatting
├── technical.py   # FFmpeg scene detection
├── batch.py       # Folder processing
├── archive.py     # SQLite corpus database
└── archive_cli.py # Archive subcommands
```

The separation matters: `models.py` defines **what** (the shape of a Baudrillardian reading), `modes.py` defines **how** (the prompt that produces it). Adding a new theoretical framework is ~30 lines of Python.

## Theory

Philm operationalizes the insight that all media analysis is already theoretical—the question is whether the theory is explicit or implicit. By parameterizing the theoretical framework, the tool makes visible what usually remains hidden: the lens through which we read images.

The frameworks included span:
- **Affect theory** (Massumi's pre-cognitive intensity)
- **Apparatus theory** (Mulvey's gaze, Benjamin's aura)
- **Simulation theory** (Baudrillard's hyperreal)
- **Dromology** (Virilio's speed and accident)
- **Power analytics** (Foucault's dispositif)
- **Hauntology** (Fisher's cancelled futures, Han's burnout society)

Running multiple modes on the same footage reveals how different frameworks illuminate different aspects—and how some frameworks find resonance where others find nothing.

## Use Cases

- **Video artists**: Generate structured readings of your own work
- **Researchers**: Produce systematic analyses across corpora
- **Critics**: Supplement close reading with algorithmic analysis
- **Archivists**: Generate rich metadata beyond technical specs
- **Curious**: See what Baudrillard would say about your vacation footage

## Archive

Philm includes a SQLite archive for storing and querying analyses across a corpus.

```bash
# Initialize the database (~/.vanalyze/archive.db)
vanalyze archive init

# Scan a folder and register videos
vanalyze archive scan ./footage --recursive

# Check archive status
vanalyze archive status

# Process unanalyzed videos
vanalyze archive process --folder ./footage --affect --gaze

# Search across the corpus
vanalyze archive search --mode affect --min-intensity 8
vanalyze archive search --mode gaze --type voyeuristic

# Statistics across all analyzed footage
vanalyze archive stats
```

Useful for corpus work: searching for specific theoretical moments across hundreds of videos, or generating statistics on affect intensity, gaze type distribution, etc.

## Web UI

```bash
vanalyze ui
```

Launches a local web interface at `http://localhost:8000` for browsing and analyzing your corpus.

- Card grid with description-first navigation
- Framework coverage per clip - click a hollow pill to trigger analysis
- Drag-and-drop video intake, or point at a folder
- Timecode-synced analysis overlay on the video player

## Scripts

```bash
# Compress video for Gemini upload (720p, optional audio strip)
python scripts/compress_for_gemini.py input.mp4 -o output/ --no-audio
```

## Limitations

- Gemini's visual understanding, not yours—the tool surfaces *its* readings
- Structured output occasionally hallucinates timecodes
- Large files (>500MB) may timeout; use compression script
- Theory is not neutral; each framework has its blindspots

## License

MIT

## Acknowledgments

Built with [uv](https://github.com/astral-sh/uv), [Typer](https://typer.tiangolo.com/), [Rich](https://github.com/Textualize/rich), and [Pydantic](https://docs.pydantic.dev/).

Theoretical frameworks drawn from: Brian Massumi, Laura Mulvey, Gilles Deleuze, Emmanuel Levinas, Immanuel Kant, Edmund Burke, Jean Baudrillard, Paul Virilio, Michel Foucault, Slavoj Žižek, Roland Barthes, Walter Benjamin, Mark Fisher, Byung-Chul Han, and Adam Curtis.

---

*"The orthogonality is the magic."*
