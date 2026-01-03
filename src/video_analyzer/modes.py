"""
Analysis mode definitions with prompts for each theoretical framework.

Each mode pairs a Pydantic model (structural constraint) with a prompt
(interpretive depth). The orthogonality is the magic.
"""

from dataclasses import dataclass
from typing import Type
from .models import (
    SimpleResult,
    ObjectResult,
    NumericResult,
    LevinasResult,
    AffectResult,
    RhythmResult,
    GazeResult,
    SublimeResult,
    CameraResult,
    BaudrillardResult,
)


@dataclass
class AnalysisMode:
    """Definition of an analysis mode."""
    name: str
    description: str
    result_model: Type
    prompt: str


# ============================================================================
# BASIC MODES
# ============================================================================

CAPTIONS = AnalysisMode(
    name="captions",
    description="A/V captions with spoken text",
    result_model=SimpleResult,
    prompt="""For each scene in this video, generate captions that describe the scene 
along with any spoken text placed in quotation marks. Place each caption into the 
timecodes array with the timestamp."""
)

PARAGRAPH = AnalysisMode(
    name="paragraph",
    description="3-5 sentence summary",
    result_model=SimpleResult,
    prompt="""Generate a paragraph that summarizes this video. Keep it to 3 to 5 sentences. 
Place each sentence into the timecodes array with the timestamp of that sentence in the video."""
)

KEY_MOMENTS = AnalysisMode(
    name="key-moments",
    description="Extract key moments as bullet points",
    result_model=SimpleResult,
    prompt="""Generate bullet points for the video. Place each bullet point into the 
timecodes array with the timestamp of that moment in the video."""
)

TABLE = AnalysisMode(
    name="table",
    description="5 key shots with descriptions and objects",
    result_model=ObjectResult,
    prompt="""Choose 5 key shots from this video and place them in the timecodes array 
with the timestamp, a text description of 10 words or less, and a list of objects 
visible in the scene (with representative emojis)."""
)

# ============================================================================
# PHILOSOPHICAL FRAMEWORKS
# ============================================================================

LEVINAS = AnalysisMode(
    name="levinas",
    description="Levinasian ethical encounter analysis",
    result_model=LevinasResult,
    prompt="""Analyze this video through a Levinasian lens. Identify moments where 
the face of the Other breaks through representation—where the infinite exceeds 
the totality of the image.

For each moment:
- Describe the ethical encounter
- Rate its intensity (1-10) based on the weight of responsibility it invokes
- Classify the mode:
  - "revelation": the face appears directly, demanding response
  - "concealment": the Other is present but obscured, instrumentalized, or reduced
  - "trace": the Other has passed, leaving only an absence that speaks

Focus on moments where the video makes ethical demands on the viewer, where you 
cannot turn away from responsibility."""
)

AFFECT = AnalysisMode(
    name="affect",
    description="Massumi affect theory analysis",
    result_model=AffectResult,
    prompt="""Analyze the affective intensities across this video using Massumi's 
affect theory framework. For each significant moment, map:

- The raw pre-cognitive intensity (1-10 scale)
- The qualitative atmosphere (the felt sense before cognition captures it)
- The vector of movement (direction the affect is pulling - toward/away, up/down, 
  expanding/contracting)
- Whether this moment "captures" or "qualifies" the affect (does it freeze the 
  intensity into recognizable emotion, or does it remain pure potential?)

Focus on transitions, thresholds, and moments where affect escapes capture. 
Distinguish between affect (intensity, autonomic) and emotion (named, personal, 
qualified)."""
)

RHYTHM = AnalysisMode(
    name="rhythm",
    description="Deleuzian rhythm and deterritorialization",
    result_model=RhythmResult,
    prompt="""Analyze this video's rhythm through a Deleuzo-Guattarian lens.

For each shift in tempo or territorial movement:
- Rate the speed of deterritorialization (1-10):
  1 = deeply coded/striated, 10 = smooth space / absolute deterritorialization
- Classify the movement:
  - "territorializing": establishing codes, habits, boundaries
  - "deterritorializing": breaking down, escaping, becoming-other
  - "reterritorializing": recapturing flows into new codes
  - "line_of_flight": pure escape, creation of the new
- Identify the refrain (ritornello): what repetition anchors or releases?

Look for moments where the video creates smooth space, where it escapes its own 
codes, where something genuinely new emerges."""
)

GAZE = AnalysisMode(
    name="gaze",
    description="Mulvey gaze analysis",
    result_model=GazeResult,
    prompt="""Analyze the gaze structure of this video using Laura Mulvey's framework.

For each significant moment of looking:
- Classify the gaze type:
  - "voyeuristic": pleasure in looking at an unaware subject
  - "fetishistic": fragmenting/objectifying the looked-at body
  - "identificatory": camera aligned with a character's perspective
  - "returned": the subject looks back, acknowledging/challenging the viewer
  - "refused": the subject denies visual access
  - "deconstructed": the apparatus of looking is made visible
- Identify who/what occupies the subject position
- Analyze the power dynamic: who controls the look? who is made object?
- Note if the fourth wall is broken

Pay attention to how visual pleasure is constructed and who it serves."""
)

SUBLIME = AnalysisMode(
    name="sublime",
    description="Kant/Burke sublime classification",
    result_model=SublimeResult,
    prompt="""Identify moments of the sublime in this video.

For each moment where the visual/sonic experience exceeds ordinary perception:
- Classify the sublime type:
  - "mathematical": overwhelm through scale, number, vastness
  - "dynamic": overwhelm through power, force, potential destruction
  - "technological": overwhelm through machinic complexity, speed, or alienation
  - "mundane": the uncanny sublime of the everyday made strange
  - "negative": the sublime of absence, void, or withdrawal
- Describe what produces the effect
- Identify the source of overwhelm: what exceeds the imagination's capacity?
- Note whether there's a moment of recovery (reason reasserting mastery)

Look for moments that exceed representation, that make you feel small or 
overwhelmed or strange."""
)

CAMERA = AnalysisMode(
    name="camera",
    description="Camera kinetics (Tarkovsky → Safdie/DG)",
    result_model=CameraResult,
    prompt="""Analyze the camera work in this video on a spectrum from 
controlled/contemplative to frenetic/chaotic.

For each distinct camera behavior, classify:

STABILITY:
- "tripod": locked off, no movement
- "gimbal": smooth, mechanical stabilization
- "steadicam": fluid, floating movement
- "handheld_controlled": handheld but deliberate, restrained
- "handheld_loose": casual handheld, natural micro-movements
- "handheld_frenetic": anxious, reactive, Safdie Brothers / Death Grips energy
- "drone": aerial, detached
- "uncertain": ambiguous or mixed

FRENETIC SCALE (1-10):
1-2 = contemplative, Tarkovsky stillness, observational patience
3-4 = controlled, deliberate movement with clear intention
5-6 = energetic but composed, music video polish
7-8 = anxious, searching, can't settle, operator stress visible
9-10 = full chaos, panic-cam, disorienting, the camera itself is distressed

INTENTIONAL MOTION: static, pan, tilt, track, push, pull, crane, whip, searching, reactive

PROXIMITY (1-10):
1-3 = distant, observational, respectful space
4-6 = conversational, standard coverage
7-8 = intimate, slightly uncomfortable closeness
9-10 = claustrophobic, invasive, no escape

Note if the camera shows RESTLESSNESS (micro-adjustments, inability to be still even
when "static"). Describe any evidence of OPERATOR PRESENCE (breathing, footsteps,
shadow, body movement)."""
)

BAUDRILLARD = AnalysisMode(
    name="baudrillard",
    description="Simulacra, hyperreality, and implosion analysis",
    result_model=BaudrillardResult,
    prompt="""Analyze this video through Baudrillard's theory of simulacra and simulation.

For each significant moment, identify:

ORDER OF SIMULACRA:
- "first": Counterfeit - the image is a clear imitation of a real original
- "second": Production - mass reproducibility, infinite copies (industrial logic)
- "third": Simulation - the model/code precedes reality, no original exists
- "fourth": Fractal/viral - pure circulation, signs referring only to other signs

HYPERREALITY MODE - how does this moment relate to "the real"?
- "represents": Claims to faithfully show reality (documentary mode)
- "masks": Actively conceals that reality is different
- "masks_absence": Conceals that there IS no underlying reality
- "pure_simulacrum": Bears no relation to reality whatsoever
- "generates": The representation produces its own reality (precession of simulacra)

For each moment also identify:
- SIGN VALUE: What is being exchanged symbolically? What does consuming this signify?
- IMPLOSION: Do any distinctions collapse? (true/false, real/fake, cause/effect,
  medium/message, map/territory)
- PRECESSION: Does the model come before the territory? Does the simulation
  generate the real rather than represent it?

Pay special attention to:
- Media within media (screens showing screens)
- Claims about reality that cannot be verified
- Signs that only reference other signs (not things)
- Moments where you cannot distinguish real from representation
- The video's own status as simulacrum

This is especially relevant for social media content, news footage, conspiracy
content, and anything that makes truth claims."""
)


# ============================================================================
# CHART MODES
# ============================================================================

@dataclass
class ChartMode:
    """Chart generation mode."""
    name: str
    description: str
    prompt_fragment: str


CHART_MODES = {
    "excitement": ChartMode(
        name="excitement",
        description="Excitement level over time",
        prompt_fragment="for each scene, estimate the level of excitement on a scale of 1 to 10"
    ),
    "importance": ChartMode(
        name="importance", 
        description="Importance to narrative",
        prompt_fragment="for each scene, estimate the level of overall importance to the video on a scale of 1 to 10"
    ),
    "people": ChartMode(
        name="people",
        description="Number of people visible",
        prompt_fragment="for each scene, count the number of people visible"
    ),
}


# ============================================================================
# MODE REGISTRY
# ============================================================================

ALL_MODES = {
    "captions": CAPTIONS,
    "paragraph": PARAGRAPH,
    "key-moments": KEY_MOMENTS,
    "table": TABLE,
    "levinas": LEVINAS,
    "affect": AFFECT,
    "rhythm": RHYTHM,
    "gaze": GAZE,
    "sublime": SUBLIME,
    "camera": CAMERA,
    "baudrillard": BAUDRILLARD,
}


def get_mode(name: str) -> AnalysisMode:
    """Get mode by name."""
    if name not in ALL_MODES:
        raise ValueError(f"Unknown mode: {name}. Available: {', '.join(ALL_MODES.keys())}")
    return ALL_MODES[name]


def get_chart_prompt(chart_type: str) -> str:
    """Generate chart analysis prompt."""
    if chart_type not in CHART_MODES:
        raise ValueError(f"Unknown chart type: {chart_type}. Available: {', '.join(CHART_MODES.keys())}")
    
    chart = CHART_MODES[chart_type]
    return f"""Generate chart data for this video based on the following instructions: 
{chart.prompt_fragment}. Place each data point in the timecodes array with the 
timestamp and numeric value."""
