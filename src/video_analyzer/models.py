"""
Pydantic models for philosophical video analysis schemas.

Each model represents a theoretical framework for understanding video content.
The models enforce structural constraints while prompts provide interpretive depth.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================================
# BASIC MODELS
# ============================================================================

class Timecode(BaseModel):
    """Simple timecode with text description."""
    time: str = Field(..., description="Timestamp in video (e.g., '00:05')")
    text: str = Field(..., description="Description or caption")


class TimecodeWithObjects(BaseModel):
    """Timecode with visual object list."""
    time: str
    text: str = Field(..., max_length=50, description="Brief description (10 words or less)")
    objects: list[str] = Field(..., description="Objects visible with emojis")


class NumericTimecode(BaseModel):
    """Timecode with numeric value for charting."""
    time: str
    value: float = Field(..., ge=0, le=10, description="Numeric value (0-10 scale)")


# ============================================================================
# LEVINAS - ETHICAL ENCOUNTER
# ============================================================================

class LevinasMode(str, Enum):
    """Modes of ethical encounter in Levinas's phenomenology."""
    REVELATION = "revelation"  # Face appears directly, demanding response
    CONCEALMENT = "concealment"  # Other is obscured, instrumentalized, reduced
    TRACE = "trace"  # Other has passed, leaving absence that speaks


class LevinasianMoment(BaseModel):
    """Moment where the face of the Other emerges."""
    time: str
    encounter: str = Field(..., description="Description of ethical encounter")
    intensity: int = Field(..., ge=1, le=10, description="Weight of ethical responsibility invoked")
    mode: LevinasMode


# ============================================================================
# MASSUMI - AFFECT THEORY
# ============================================================================

class AffectMoment(BaseModel):
    """Affective intensity mapping using Massumi's framework."""
    time: str
    intensity: int = Field(..., ge=1, le=10, description="Raw pre-cognitive affective charge")
    atmosphere: str = Field(..., description="Qualitative felt sense before cognition")
    vector: str = Field(..., description="Direction of affective movement")
    captures: bool = Field(..., description="Does affect freeze into recognizable emotion?")


# ============================================================================
# DELEUZE - RHYTHM AND DETERRITORIALIZATION
# ============================================================================

class DeleuzianMovement(str, Enum):
    """Types of territorial movement."""
    TERRITORIALIZING = "territorializing"
    DETERRITORIALIZING = "deterritorializing"
    RETERRITORIALIZING = "reterritorializing"
    LINE_OF_FLIGHT = "line_of_flight"


class RhythmMoment(BaseModel):
    """Deleuzian rhythm and tempo analysis."""
    time: str
    tempo: int = Field(..., ge=1, le=10, description="Speed of deterritorialization")
    movement: DeleuzianMovement
    refrain: Optional[str] = Field(None, description="Rhythmic motif that anchors/releases")
    description: str


# ============================================================================
# MULVEY - GAZE ANALYSIS
# ============================================================================

class GazeType(str, Enum):
    """Mulvey's scopophilic structures."""
    VOYEURISTIC = "voyeuristic"  # Pleasure in looking at unaware subject
    FETISHISTIC = "fetishistic"  # Fragmenting/objectifying the body
    IDENTIFICATORY = "identificatory"  # Camera aligned with character perspective
    RETURNED = "returned"  # Subject looks back, challenging viewer
    REFUSED = "refused"  # Subject denies visual access
    DECONSTRUCTED = "deconstructed"  # Apparatus of looking made visible


class GazeMoment(BaseModel):
    """Analysis of visual pleasure and politics of looking."""
    time: str
    gaze_type: GazeType
    subject_position: str = Field(..., description="Who/what is looked at")
    power_dynamic: str = Field(..., description="Politics of the look")
    breaks_fourth_wall: bool = False


# ============================================================================
# KANT/BURKE - SUBLIME
# ============================================================================

class SublimeType(str, Enum):
    """Categories of aesthetic overwhelm."""
    MATHEMATICAL = "mathematical"  # Overwhelm through scale, vastness
    DYNAMIC = "dynamic"  # Overwhelm through power, force
    TECHNOLOGICAL = "technological"  # Overwhelm through machinic complexity
    MUNDANE = "mundane"  # Uncanny sublime of everyday made strange
    NEGATIVE = "negative"  # Sublime of absence, void, withdrawal


class SublimeMoment(BaseModel):
    """Moments of aesthetic overwhelm."""
    time: str
    sublime_type: SublimeType
    description: str
    overwhelm_source: str = Field(..., description="What exceeds comprehension")
    recovery: bool = Field(..., description="Does reason reassert mastery?")


# ============================================================================
# BAUDRILLARD - SIMULACRA AND SIMULATION
# ============================================================================

class SimulacraOrder(str, Enum):
    """Orders of simulacra in Baudrillard's theory."""
    FIRST = "first"  # Counterfeit - imitation of original (pre-industrial)
    SECOND = "second"  # Production - infinite reproducibility (industrial)
    THIRD = "third"  # Simulation - model precedes reality (postmodern)
    FOURTH = "fourth"  # Fractal/viral - pure circulation, no reference


class HyperrealityMode(str, Enum):
    """How the video relates to the real."""
    REPRESENTS = "represents"  # Claims to show reality
    MASKS = "masks"  # Conceals absence of reality
    MASKS_ABSENCE = "masks_absence"  # Masks that there is no reality
    PURE_SIMULACRUM = "pure_simulacrum"  # No relation to reality whatsoever
    GENERATES = "generates"  # Produces its own reality (precession)


class BaudrillardMoment(BaseModel):
    """Analysis of simulacra, hyperreality, and implosion."""
    time: str
    order: SimulacraOrder = Field(..., description="Which order of simulacra operates here")
    hyperreality_mode: HyperrealityMode = Field(..., description="Relation to the real")
    sign_value: str = Field(..., description="What is being exchanged symbolically")
    implosion: Optional[str] = Field(None, description="What distinctions collapse (if any)")
    precession: bool = Field(..., description="Does the model/map precede the territory?")
    description: str


# ============================================================================
# EPISTEMIC - TRUTH AND EVIDENCE
# ============================================================================

class EpistemicMode(str, Enum):
    """How the video relates to truth claims."""
    DOCUMENTARY = "documentary"  # Claims direct access to truth
    TESTIMONIAL = "testimonial"  # Truth through witness/speaker
    EVIDENTIAL = "evidential"  # Presents evidence for claims
    SPECULATIVE = "speculative"  # Hypothetical, uncertain
    PERFORMATIVE = "performative"  # Creates truth through enactment
    DENIALIST = "denialist"  # Rejects established knowledge


class CertaintyLevel(str, Enum):
    """Epistemological certainty."""
    APODICTIC = "apodictic"  # Necessarily true, self-evident
    ASSERTORIC = "assertoric"  # Claimed as fact, could be otherwise
    PROBLEMATIC = "problematic"  # Possible, uncertain
    SKEPTICAL = "skeptical"  # Doubting, questioning


class EpistemicMoment(BaseModel):
    """Analysis of truth claims and knowledge production."""
    time: str
    mode: EpistemicMode = Field(..., description="How truth is claimed")
    certainty: CertaintyLevel = Field(..., description="Degree of epistemological certainty")
    claim: str = Field(..., description="What truth claim is made")
    evidence_type: Optional[str] = Field(None, description="What counts as evidence here")
    verifiable: bool = Field(..., description="Can this claim be independently verified?")
    appeals_to: Optional[str] = Field(None, description="Authority/source invoked (science, tradition, etc.)")
    description: str


# ============================================================================
# FOUCAULT - POWER AND SURVEILLANCE
# ============================================================================

class PowerMode(str, Enum):
    """Foucauldian modes of power."""
    SOVEREIGN = "sovereign"  # Top-down, spectacular, punitive
    DISCIPLINARY = "disciplinary"  # Normalizing, training, examining
    BIOPOLITICAL = "biopolitical"  # Managing populations, life itself
    PASTORAL = "pastoral"  # Caring, confessional, individualizing
    GOVERNMENTALITY = "governmentality"  # Conduct of conduct, self-regulation


class SurveillanceType(str, Enum):
    """Types of watching/monitoring."""
    PANOPTIC = "panoptic"  # Visible, centralized, induces self-discipline
    SYNOPTIC = "synoptic"  # Many watch few (celebrity, spectacle)
    LATERAL = "lateral"  # Peer-to-peer, social surveillance
    ALGORITHMIC = "algorithmic"  # Automated, data-driven
    ABSENT = "absent"  # Surveillance apparatus not visible


class FoucaultMoment(BaseModel):
    """Analysis of power, discipline, and surveillance."""
    time: str
    power_mode: PowerMode = Field(..., description="Which modality of power operates")
    surveillance: SurveillanceType = Field(..., description="Type of watching/monitoring")
    subject_produced: str = Field(..., description="What kind of subject is being produced")
    norm_enforced: Optional[str] = Field(None, description="What norm is being enforced/implied")
    resistance: Optional[str] = Field(None, description="Any resistance or counter-conduct visible")
    apparatus: str = Field(..., description="The dispositif/apparatus at work")
    description: str


# ============================================================================
# VIRILIO - SPEED AND ACCIDENT
# ============================================================================

class SpeedRegime(str, Enum):
    """Virilio's speed classifications."""
    METABOLIC = "metabolic"  # Body speed, walking, natural rhythm
    MECHANICAL = "mechanical"  # Vehicle speed, industrial acceleration
    ELECTRONIC = "electronic"  # Speed of light, instantaneous transmission
    STATIC = "static"  # Inertia, paralysis through speed


class AccidentType(str, Enum):
    """Types of technological accident."""
    INTEGRAL = "integral"  # The accident inherent to the technology
    CATASTROPHIC = "catastrophic"  # System-wide failure
    AESTHETIC = "aesthetic"  # Accident as visual/sensory event
    TEMPORAL = "temporal"  # Disruption of time perception
    NONE = "none"  # No accident visible


class VirilioMoment(BaseModel):
    """Analysis of speed, technology, and the accident."""
    time: str
    speed_regime: SpeedRegime = Field(..., description="What speed governs this moment")
    dromology: str = Field(..., description="The logic of speed operating")
    accident: AccidentType = Field(..., description="Type of accident visible/implied")
    territory_collapse: bool = Field(..., description="Does speed collapse geographic distance?")
    real_time: bool = Field(..., description="Is this operating in 'real time' (instantaneous)?")
    war_machine: Optional[str] = Field(None, description="Military/strategic logic visible")
    description: str


# ============================================================================
# CAMERA ANALYSIS - KINETIC ENERGY
# ============================================================================

class CameraStability(str, Enum):
    """Camera stability classifications."""
    TRIPOD = "tripod"
    GIMBAL = "gimbal"
    STEADICAM = "steadicam"
    HANDHELD_CONTROLLED = "handheld_controlled"
    HANDHELD_LOOSE = "handheld_loose"
    HANDHELD_FRENETIC = "handheld_frenetic"
    DRONE = "drone"
    UNCERTAIN = "uncertain"


class CameraMotion(str, Enum):
    """Types of intentional camera movement."""
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    TRACK = "track"
    PUSH = "push"
    PULL = "pull"
    CRANE = "crane"
    WHIP = "whip"
    SEARCHING = "searching"
    REACTIVE = "reactive"


class CameraMoment(BaseModel):
    """Camera behavior analysis on Tarkovsky → Safdie/DG spectrum."""
    time: str
    stability: CameraStability
    frenetic: int = Field(..., ge=1, le=10, description="1=Tarkovsky stillness, 10=DG chaos")
    intentional_motion: CameraMotion
    proximity: Optional[int] = Field(None, ge=1, le=10, description="1=distant, 10=claustrophobic")
    restlessness: Optional[bool] = Field(None, description="Camera wants to move when 'still'")
    operator_presence: Optional[str] = Field(None, description="Evidence of human behind camera")
    description: str


# ============================================================================
# RESPONSE CONTAINERS
# ============================================================================

class BaseAnalysisResult(BaseModel):
    """Base result with video description."""
    video_description: str = Field(
        ..., 
        description="Concise practical description (1-2 sentences) for cataloging"
    )


class SimpleResult(BaseAnalysisResult):
    """Basic timecode result."""
    timecodes: list[Timecode]


class ObjectResult(BaseAnalysisResult):
    """Result with objects."""
    timecodes: list[TimecodeWithObjects]


class NumericResult(BaseAnalysisResult):
    """Numeric chart data."""
    timecodes: list[NumericTimecode]


class LevinasResult(BaseAnalysisResult):
    """Levinasian ethical analysis."""
    timecodes: list[LevinasianMoment]


class AffectResult(BaseAnalysisResult):
    """Massumi affect analysis."""
    timecodes: list[AffectMoment]


class RhythmResult(BaseAnalysisResult):
    """Deleuzian rhythm analysis."""
    timecodes: list[RhythmMoment]


class GazeResult(BaseAnalysisResult):
    """Mulvey gaze analysis."""
    timecodes: list[GazeMoment]


class SublimeResult(BaseAnalysisResult):
    """Sublime moment analysis."""
    timecodes: list[SublimeMoment]


class CameraResult(BaseAnalysisResult):
    """Camera kinetics analysis."""
    timecodes: list[CameraMoment]


class BaudrillardResult(BaseAnalysisResult):
    """Baudrillard simulacra and hyperreality analysis."""
    timecodes: list[BaudrillardMoment]


class EpistemicResult(BaseAnalysisResult):
    """Epistemic analysis of truth claims."""
    timecodes: list[EpistemicMoment]


class FoucaultResult(BaseAnalysisResult):
    """Foucault power and surveillance analysis."""
    timecodes: list[FoucaultMoment]


class VirilioResult(BaseAnalysisResult):
    """Virilio speed and accident analysis."""
    timecodes: list[VirilioMoment]


# ============================================================================
# TECHNICAL ANALYSIS
# ============================================================================

class TechnicalMetrics(BaseModel):
    """FFmpeg-derived technical video metrics."""
    duration: float = Field(..., description="Video duration in seconds")
    framerate: float = Field(..., description="Frames per second")
    scene_changes: int = Field(..., description="Number of detected scene changes")
    change_density: float = Field(..., description="Scene changes per second")
    avg_scene_score: float = Field(..., description="Average frame difference score")
    max_scene_score: float = Field(..., description="Maximum frame difference score")
    chaos_index: float = Field(..., ge=1, le=10, description="Overall technical chaos (1-10)")
