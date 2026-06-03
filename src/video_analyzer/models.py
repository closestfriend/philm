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
    appeals_to: Optional[str] = Field(
        None, description="Authority/source invoked (science, tradition, etc.)"
    )
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
# ŽIŽEK - PARALLAX AND THE REAL
# ============================================================================


class ParallaxType(str, Enum):
    """Types of parallax gap."""

    ONTOLOGICAL = "ontological"  # Gap in being itself
    EPISTEMOLOGICAL = "epistemological"  # Gap between knowing positions
    POLITICAL = "political"  # Gap between political positions that cannot be synthesized
    AESTHETIC = "aesthetic"  # Gap between form and content, surface and depth


class LacanianRegister(str, Enum):
    """Lacan's three registers."""

    IMAGINARY = "imaginary"  # Mirror stage, ego, identification, gestalt
    SYMBOLIC = "symbolic"  # Language, law, the big Other, signifiers
    REAL = "real"  # That which resists symbolization, trauma, impossibility


class ZizekMoment(BaseModel):
    """Analysis through Žižek's parallax view and Lacanian framework."""

    time: str
    parallax: ParallaxType = Field(..., description="Type of parallax gap visible")
    register: LacanianRegister = Field(..., description="Which Lacanian register dominates")
    ideology_at_work: str = Field(..., description="What ideological operation is visible")
    obscene_supplement: Optional[str] = Field(
        None, description="The hidden underside that sustains the official narrative"
    )
    gap_between: str = Field(..., description="What two perspectives create the irreducible gap")
    real_intrusion: Optional[str] = Field(None, description="Where does the Real break through?")
    description: str


# ============================================================================
# BARTHES - PUNCTUM AND MYTHOLOGY
# ============================================================================


class BarthesRegister(str, Enum):
    """Barthes' modes of meaning."""

    STUDIUM = "studium"  # Cultural, coded, readable meaning
    PUNCTUM = "punctum"  # The wound, the accident that pricks
    OBTUSE = "obtuse"  # Third meaning, excess beyond signification


class MythOperation(str, Enum):
    """Operations of Barthesian mythology."""

    NATURALIZATION = "naturalization"  # Making historical appear natural
    INOCULATION = "inoculation"  # Admitting small evil to hide systemic one
    PRIVATION = "privation"  # Removing history from the image
    IDENTIFICATION = "identification"  # Reducing Other to Same
    TAUTOLOGY = "tautology"  # "It is because it is"
    NEITHER_NOR = "neither_nor"  # False balance, refusing to choose
    QUANTIFICATION = "quantification"  # Reducing quality to quantity
    STATEMENT_OF_FACT = "statement_of_fact"  # Presenting opinion as natural fact


class BarthesMoment(BaseModel):
    """Analysis through Barthes' semiotics and punctum theory."""

    time: str
    register: BarthesRegister = Field(..., description="Studium, punctum, or obtuse meaning")
    punctum_detail: Optional[str] = Field(None, description="If punctum: what wounds, what pricks?")
    myth_operation: Optional[MythOperation] = Field(
        None, description="If myth operates: which operation?"
    )
    denotation: str = Field(..., description="What does the image literally show")
    connotation: str = Field(..., description="What cultural meanings attach")
    grain: Optional[str] = Field(None, description="The 'grain' - the body in the voice/image")
    death_present: bool = Field(..., description="Is the 'that-has-been' (mortality) visible?")
    description: str


# ============================================================================
# BENJAMIN - AURA AND DIALECTICAL IMAGE
# ============================================================================


class AuraStatus(str, Enum):
    """Status of the aura in mechanical reproduction."""

    AURATIC = "auratic"  # Unique presence, here-and-now, cult value
    DECAYED = "decayed"  # Aura in process of withering
    ABSENT = "absent"  # Post-auratic, exhibition value dominates
    SIMULATED = "simulated"  # Fake aura, nostalgia, aura-effect
    REVOLUTIONARY = "revolutionary"  # Absence of aura as liberation


class DialecticalImageType(str, Enum):
    """Types of dialectical image."""

    CONSTELLATION = "constellation"  # Past and present in sudden alignment
    RUIN = "ruin"  # History visible as decay, allegory
    WISH_IMAGE = "wish_image"  # Utopian content in commodity form
    FOSSIL = "fossil"  # Petrified life, frozen history
    TIGER_LEAP = "tiger_leap"  # Revolutionary citation of the past


class BenjaminMoment(BaseModel):
    """Analysis through Benjamin's theory of aura and mechanical reproduction."""

    time: str
    aura_status: AuraStatus = Field(..., description="Status of the aura")
    aura_source: Optional[str] = Field(None, description="If auratic: what generates the aura?")
    dialectical_image: Optional[DialecticalImageType] = Field(
        None, description="Type of dialectical image"
    )
    optical_unconscious: Optional[str] = Field(
        None, description="What does the camera reveal that the eye cannot?"
    )
    cult_vs_exhibition: str = Field(
        ..., description="Does cult value or exhibition value dominate?"
    )
    reproducibility: str = Field(..., description="How does mechanical reproduction operate here?")
    now_time: Optional[str] = Field(
        None, description="The Jetztzeit - explosive present that blasts open the continuum"
    )
    description: str


# ============================================================================
# FISHER/HAN/CURTIS - HAUNTOLOGY AND CAPITALIST REALISM
# ============================================================================


class TemporalPathology(str, Enum):
    """How late capitalism deforms time (Fisher/Han)."""

    HAUNTOLOGICAL = (
        "hauntological"  # Ghosts of lost futures, retrofuturism, the future that didn't arrive
    )
    ETERNAL_PRESENT = "eternal_present"  # No history, no future, managed now (Curtis)
    BURNOUT_TIME = "burnout_time"  # Exhausted temporality, no pause possible (Han)
    NOSTALGIC = "nostalgic"  # Simulated past, fake memory, weaponized nostalgia
    CANCELLED_FUTURE = "cancelled_future"  # The slow cancellation of the future


class CapitalistRealismMarker(str, Enum):
    """Symptoms of capitalist realism (Fisher)."""

    NO_ALTERNATIVE = "no_alternative"  # "This is just how things are" - TINA
    SELF_EXPLOITATION = "self_exploitation"  # Achievement-subject optimizing themselves (Han)
    COMMODIFIED_RESISTANCE = "commodified_resistance"  # Rebellion as product, dissent as brand
    DEPRESSIVE_HEDONIA = "depressive_hedonia"  # Unable to do anything BUT pursue pleasure
    INTERPASSIVITY = "interpassivity"  # The device enjoys for us (Žižek via Fisher)
    PRECARITY_NORMALIZED = "precarity_normalized"  # Instability as permanent condition


class SmoothnessMode(str, Enum):
    """Han's smooth vs. negative distinction."""

    SMOOTH = "smooth"  # Frictionless, positive, like-able, no negativity allowed
    NEGATIVE = "negative"  # Friction, otherness, genuine encounter, productive pain
    SMOOTH_EVIL = "smooth_evil"  # The violence OF smoothness (elimination of other)
    TOXIC_POSITIVITY = "toxic_positivity"  # Mandatory happiness, prohibited sadness


class HypernormalType(str, Enum):
    """Curtis's hypernormalisation categories."""

    MANAGED_REALITY = "managed_reality"  # Fake but functional reality everyone accepts
    PERCEPTION_MANAGEMENT = "perception_management"  # Reality as PR operation
    NON_LINEAR_WAR = "non_linear_war"  # Surkov-style confusion as control
    CONSPIRACY_WITHOUT_CONSPIRATORS = "conspiracy_without_conspirators"  # System effects, no cabal
    REFLEXIVE_IMPOTENCE = "reflexive_impotence"  # "We know, but we can't do anything"


class HauntologyMoment(BaseModel):
    """Analysis through Fisher's hauntology, Han's burnout society, and Curtis's hypernormalisation."""

    time: str
    temporal_pathology: TemporalPathology = Field(..., description="How is time deformed here?")
    capitalist_realism: Optional[CapitalistRealismMarker] = Field(
        None, description="Which symptom of capitalist realism?"
    )
    smoothness: SmoothnessMode = Field(
        ..., description="Smooth positivity or productive negativity?"
    )
    hypernormal: Optional[HypernormalType] = Field(
        None, description="If hypernormalisation operates: which type?"
    )
    lost_future: Optional[str] = Field(
        None, description="What future has been cancelled/is haunting?"
    )
    suffering_individualized: bool = Field(
        ..., description="Is systemic suffering presented as personal failure?"
    )
    achievement_subject: bool = Field(
        ..., description="Is someone performing self-optimization? (Han)"
    )
    libidinal_capture: Optional[str] = Field(
        None, description="How has desire been captured/redirected?"
    )
    description: str


# ============================================================================
# RANCIÈRE - DISTRIBUTION OF THE SENSIBLE
# ============================================================================


class RancierePartition(str, Enum):
    VISIBLE_INVISIBLE = "visible_invisible"
    AUDIBLE_INAUDIBLE = "audible_inaudible"
    SAYABLE_UNSAYABLE = "sayable_unsayable"
    NOISE = "noise"
    MISCOUNT = "miscount"


class RanciereMoment(BaseModel):
    time: str
    partition: RancierePartition = Field(
        ..., description="Which partition of the sensible is at stake"
    )
    policing_act: str = Field(..., description="How roles/places are enforced")
    dissensus: bool = Field(..., description="Is the sensible order reconfigured?")
    subject_of_politics: Optional[str] = Field(None, description="Who appears/speaks")
    description: str


# ============================================================================
# SONTAG - CAMP
# ============================================================================


class CampMode(str, Enum):
    NAIVE = "naive"
    DELIBERATE = "deliberate"
    BAROQUE = "baroque"
    ANDROGYNOUS = "androgynous"
    GLAM = "glam"
    FAILED_SERIOUSNESS = "failed_seriousness"


class SontagMoment(BaseModel):
    time: str
    camp_mode: CampMode
    stylization: int = Field(..., ge=1, le=10, description="Degree of artifice/stylization")
    seriousness: int = Field(..., ge=1, le=10, description="How seriously it takes itself")
    irony_temperature: int = Field(..., ge=1, le=10, description="Hot to cold irony")
    description: str


# ============================================================================
# HARAWAY - CYBORG / SITUATED KNOWLEDGE
# ============================================================================


class BoundaryTransgression(str, Enum):
    HUMAN_MACHINE = "human_machine"
    NATURE_CULTURE = "nature_culture"
    ORGANIC_SYNTHETIC = "organic_synthetic"
    SPECIES = "species"
    PHYSICAL_VIRTUAL = "physical_virtual"
    NONE = "none"


class TechnocultureTone(str, Enum):
    UTOPIAN = "utopian"
    CRITICAL = "critical"
    AMBIVALENT = "ambivalent"
    APOCALYPTIC = "apocalyptic"


class HarawayMoment(BaseModel):
    time: str
    boundary_transgression: BoundaryTransgression
    partial_perspective: bool = Field(
        ..., description="Situated/acknowledged perspective vs disavowed god-trick"
    )
    kin_making: Optional[str] = Field(None, description="Cross-category kinship/alliance")
    control_infrastructure: Optional[str] = Field(
        None, description="Platforms, protocols, logistics"
    )
    technoculture_tone: TechnocultureTone
    description: str


# ============================================================================
# MARKS - HAPTIC VISUALITY
# ============================================================================


class ScopicMode(str, Enum):
    OPTICAL = "optical"
    HAPTIC = "haptic"
    AURAL_HAPTIC = "aural_haptic"
    OLFACTORY_EVOKED = "olfactory_evoked"


class IndexicalityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MarksMoment(BaseModel):
    time: str
    scopic_mode: ScopicMode
    texture_language: str = Field(..., description="Grain, blur, close detail, tactility")
    proximity: int = Field(..., ge=1, le=10, description="Visual closeness/intimacy")
    indexicality: IndexicalityLevel
    synaesthesia: bool = Field(..., description="Cross-sensory evocation present?")
    description: str


# ============================================================================
# CHION - AUDIO-VISION
# ============================================================================


class SoundRelation(str, Enum):
    EMPATHETIC = "empathetic"
    ANEMPATHETIC = "anempathetic"
    COUNTERPOINT = "counterpoint"
    ACOUSMATIC = "acousmatic"
    ACOUSMETRE_PRESENT = "acousmetre_present"
    SYNCHRESIS_PEAK = "synchresis_peak"


class ChionMoment(BaseModel):
    time: str
    sound_relation: SoundRelation
    voice_of_god: bool = Field(..., description="Disembodied authoritative voice present?")
    audio_leads_image: bool = Field(..., description="Does sound drive the image?")
    perceived_causality: str = Field(..., description="What sound-image causality is felt")
    description: str


# ============================================================================
# BAZIN - REALISM
# ============================================================================


class StagingMode(str, Enum):
    PLAN_SEQUENCE = "plan_sequence"
    DEEP_FOCUS = "deep_focus"
    TABLEAU = "tableau"
    MONTAGE_LIKE = "montage_like"


class FocusDepth(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IndexicalTrust(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BazinMoment(BaseModel):
    time: str
    take_length_sec: Optional[float] = Field(None, description="Approx take length in seconds")
    staging_mode: StagingMode
    depth_focus: FocusDepth
    ambiguity: bool = Field(..., description="Does the action remain interpretively open?")
    indexical_trust: IndexicalTrust
    description: str


# ============================================================================
# EISENSTEIN - MONTAGE
# ============================================================================


class MontageType(str, Enum):
    METRIC = "metric"
    RHYTHMIC = "rhythmic"
    TONAL = "tonal"
    OVERTONAL = "overtonal"
    INTELLECTUAL = "intellectual"


class EisensteinMoment(BaseModel):
    time: str
    montage_type: MontageType
    cut_intensity: int = Field(..., ge=1, le=10, description="Cutting rate/force")
    collision_intensity: int = Field(
        ..., ge=1, le=10, description="Dialectical shock between shots"
    )
    ideogram: str = Field(..., description="The concept produced by the collision")
    description: str


# ============================================================================
# GREENBERG - FLATNESS
# ============================================================================


class Illusionism(str, Enum):
    RECESSIONAL = "recessional"
    SHALLOW = "shallow"
    FLAT = "flat"


class SurfaceEmphasis(str, Enum):
    TEXTURE = "texture"
    PATTERN = "pattern"
    COLOR_FIELD = "color_field"
    GRID = "grid"
    GESTURE = "gesture"
    MINIMAL = "minimal"


class GreenbergMoment(BaseModel):
    time: str
    flatness_index: int = Field(..., ge=1, le=10, description="1=deep illusion, 10=pure flatness")
    illusionism: Illusionism
    surface_emphasis: SurfaceEmphasis
    medium_reflexivity: bool = Field(..., description="Does it foreground its own medium?")
    description: str


# ============================================================================
# NGAI - AESTHETIC CATEGORIES
# ============================================================================


class NgaiCategory(str, Enum):
    CUTE = "cute"
    ZANY = "zany"
    INTERESTING = "interesting"
    GIMMICKY = "gimmicky"


class NgaiMoment(BaseModel):
    time: str
    category: NgaiCategory
    intensity: int = Field(..., ge=1, le=10, description="Strength of the aesthetic category")
    rationale: str = Field(..., description="Why this category applies")
    affect_register: Optional[str] = Field(None, description="Associated feeling")
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
        ..., description="Concise practical description (1-2 sentences) for cataloging"
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


class ZizekResult(BaseAnalysisResult):
    """Žižek parallax and ideology analysis."""

    timecodes: list[ZizekMoment]


class BarthesResult(BaseAnalysisResult):
    """Barthes punctum/studium and mythology analysis."""

    timecodes: list[BarthesMoment]


class BenjaminResult(BaseAnalysisResult):
    """Benjamin aura and dialectical image analysis."""

    timecodes: list[BenjaminMoment]


class RanciereResult(BaseAnalysisResult):
    """Rancière distribution of the sensible analysis."""

    timecodes: list[RanciereMoment]


class SontagResult(BaseAnalysisResult):
    """Sontag camp sensibility analysis."""

    timecodes: list[SontagMoment]


class HarawayResult(BaseAnalysisResult):
    """Haraway cyborg and situated knowledge analysis."""

    timecodes: list[HarawayMoment]


class MarksResult(BaseAnalysisResult):
    """Marks haptic visuality analysis."""

    timecodes: list[MarksMoment]


class ChionResult(BaseAnalysisResult):
    """Chion audio-vision analysis."""

    timecodes: list[ChionMoment]


class BazinResult(BaseAnalysisResult):
    """Bazin realism and long-take analysis."""

    timecodes: list[BazinMoment]


class EisensteinResult(BaseAnalysisResult):
    """Eisenstein montage analysis."""

    timecodes: list[EisensteinMoment]


class GreenbergResult(BaseAnalysisResult):
    """Greenberg flatness and medium specificity analysis."""

    timecodes: list[GreenbergMoment]


class NgaiResult(BaseAnalysisResult):
    """Ngai aesthetic categories analysis."""

    timecodes: list[NgaiMoment]


class HauntologyResult(BaseAnalysisResult):
    """Fisher/Han/Curtis capitalist realism and hauntology analysis."""

    timecodes: list[HauntologyMoment]


# ============================================================================
# TECHNICAL ANALYSIS
# ============================================================================

# ============================================================================
# SIZZLE - PRODUCTION-FOCUSED ANALYSIS
# ============================================================================


class ShotType(str, Enum):
    """Production shot categories for sizzle reels."""

    HERO = "hero"  # Clean, polished, holds attention - can carry a beat
    ACTION = "action"  # Dynamic movement, sports, activity
    PRODUCT = "product"  # Object/interface showcase, demo footage
    PORTRAIT = "portrait"  # Person-focused, testimonial-ready
    ESTABLISHING = "establishing"  # Scene-setter, wide, context
    MONTAGE = "montage"  # Quick-cut worthy, texture
    TRANSITION = "transition"  # Movement between scenes, motion blur
    DATA = "data"  # Screens, charts, UI, stats


class ToneRegister(str, Enum):
    """Emotional tone for sizzle reel moments."""

    CONFIDENT = "confident"  # Assured, punchy, "we've got this"
    EXCITING = "exciting"  # High energy, thrilling, dynamic
    DRAMATIC = "dramatic"  # Stakes, tension, intensity
    ASPIRATIONAL = "aspirational"  # Premium, desirable, lifestyle
    TRIUMPHANT = "triumphant"  # Victory, celebration, achievement
    TECHNICAL = "technical"  # Professional, data-driven, smart
    WARM = "warm"  # Friendly, approachable, human
    URGENT = "urgent"  # Fast-paced, don't miss out


class SizzlePosition(str, Enum):
    """Where in a sizzle structure this could work."""

    HOOK = "hook"  # Opening punch, first 5 seconds
    ESTABLISH = "establish"  # "What is this?" section
    DEMO = "demo"  # Feature showcase, how it works
    PROOF = "proof"  # Social proof, results, testimonials
    MONTAGE = "montage"  # Fast-cut energy section
    CLIMAX = "climax"  # Emotional peak, payoff
    CTA = "cta"  # Call to action, closer


class SizzleMoment(BaseModel):
    """Production-focused moment analysis for sizzle reel editing."""

    time: str
    shot_type: ShotType = Field(..., description="Production category")
    energy: int = Field(..., ge=1, le=10, description="Visual punch (1=subtle, 10=explosive)")
    tone: ToneRegister = Field(..., description="Emotional register")
    subjects: list[str] = Field(..., description="Key subjects/objects in frame")
    motion: str = Field(
        ..., description="Camera/subject movement (static, pan, track, handheld, etc.)"
    )
    sizzle_position: list[SizzlePosition] = Field(
        ..., description="Where in sizzle structure this fits"
    )
    usable_seconds: str = Field(
        ..., description="How long this moment is usable (e.g., '2-3s', '0.5s', 'full clip')"
    )
    notes: str = Field(..., description="Editor notes - why this works or specific warnings")


class SizzleResult(BaseAnalysisResult):
    """Production-focused sizzle reel analysis."""

    timecodes: list[SizzleMoment]
    overall_energy: int = Field(..., ge=1, le=10, description="Average energy across all moments")
    dominant_tone: ToneRegister = Field(..., description="Most prevalent tone")
    best_for: list[SizzlePosition] = Field(
        ..., description="Recommended sizzle positions for this footage"
    )
    warnings: Optional[list[str]] = Field(None, description="Issues: shaky, bad audio, logos, etc.")


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
