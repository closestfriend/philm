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
    EpistemicResult,
    FoucaultResult,
    VirilioResult,
    ZizekResult,
    BarthesResult,
    BenjaminResult,
    HauntologyResult,
    SizzleResult,
    RanciereResult,
    SontagResult,
    HarawayResult,
    MarksResult,
    ChionResult,
    BazinResult,
    EisensteinResult,
    GreenbergResult,
    NgaiResult,
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
timecodes array with the timestamp.""",
)

PARAGRAPH = AnalysisMode(
    name="paragraph",
    description="3-5 sentence summary",
    result_model=SimpleResult,
    prompt="""Generate a paragraph that summarizes this video. Keep it to 3 to 5 sentences. 
Place each sentence into the timecodes array with the timestamp of that sentence in the video.""",
)

KEY_MOMENTS = AnalysisMode(
    name="key-moments",
    description="Extract key moments as bullet points",
    result_model=SimpleResult,
    prompt="""Generate bullet points for the video. Place each bullet point into the 
timecodes array with the timestamp of that moment in the video.""",
)

TABLE = AnalysisMode(
    name="table",
    description="5 key shots with descriptions and objects",
    result_model=ObjectResult,
    prompt="""Choose 5 key shots from this video and place them in the timecodes array 
with the timestamp, a text description of 10 words or less, and a list of objects 
visible in the scene (with representative emojis).""",
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
cannot turn away from responsibility.""",
)

AFFECT = AnalysisMode(
    name="affect",
    description="Massumi affect theory analysis",
    result_model=AffectResult,
    prompt="""Analyze the affective intensities across this video using Massumi's 
affect theory framework. For each significant moment, map:

- The raw pre-cognitive intensity (1-10 scale)
- The qualitative atmosphere (the felt sense before cognition captures it)
- The vector of movement, one word from this list and nothing else:
  rising: expanding, outward, forward, toward, upward
  falling: contracting, inward, receding, away, downward
  flat: static (held, unmoving), neutral (no discernible pull)
- Whether this moment "captures" or "qualifies" the affect (does it freeze the 
  intensity into recognizable emotion, or does it remain pure potential?)

Focus on transitions, thresholds, and moments where affect escapes capture. 
Distinguish between affect (intensity, autonomic) and emotion (named, personal, 
qualified).""",
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
codes, where something genuinely new emerges.""",
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

Pay attention to how visual pleasure is constructed and who it serves.""",
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
overwhelmed or strange.""",
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
shadow, body movement).""",
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
content, and anything that makes truth claims.""",
)

EPISTEMIC = AnalysisMode(
    name="epistemic",
    description="Truth claims, evidence, and certainty analysis",
    result_model=EpistemicResult,
    prompt="""Analyze this video's relationship to truth and knowledge.

For each significant moment, identify:

EPISTEMIC MODE - how does the video claim truth?
- "documentary": Claims direct, unmediated access to truth
- "testimonial": Truth through witness, speaker, personal experience
- "evidential": Presents evidence, data, proof for claims
- "speculative": Hypothetical, conditional, uncertain
- "performative": Creates truth through enactment (e.g., ritual, declaration)
- "denialist": Actively rejects established knowledge/consensus

CERTAINTY LEVEL (using Kantian categories):
- "apodictic": Presented as necessarily true, self-evident, beyond question
- "assertoric": Claimed as fact but could be otherwise
- "problematic": Possible, uncertain, hedged
- "skeptical": Doubting, questioning, deconstructive

For each moment also identify:
- CLAIM: What truth claim is being made (explicit or implicit)?
- EVIDENCE TYPE: What counts as evidence here? (visual proof, testimony,
  scientific data, emotional authenticity, common sense, etc.)
- VERIFIABLE: Can this claim be independently verified?
- APPEALS TO: What authority is invoked? (science, tradition, lived experience,
  religious text, expert opinion, "just asking questions")

Pay special attention to:
- Moments where the video claims to "reveal" hidden truths
- The relationship between seeing and believing
- How certainty is performed vs. earned
- Conspiracy logic and unfalsifiable claims
- The difference between knowledge and belief

This is especially useful for documentary, news, propaganda, conspiracy content,
and anything making claims about reality.""",
)

FOUCAULT = AnalysisMode(
    name="foucault",
    description="Power, surveillance, and discipline analysis",
    result_model=FoucaultResult,
    prompt="""Analyze this video through Foucault's frameworks of power, discipline,
and surveillance.

For each significant moment, identify:

POWER MODE - which modality of power operates?
- "sovereign": Top-down, spectacular, punitive (the king's power to kill)
- "disciplinary": Normalizing, training, examining, correcting (the prison, school)
- "biopolitical": Managing populations, life itself (statistics, public health)
- "pastoral": Caring, confessional, individualizing (the shepherd's power)
- "governmentality": Conduct of conduct, self-regulation, internalized control

SURVEILLANCE TYPE:
- "panoptic": Visible, centralized surveillance that induces self-discipline
- "synoptic": Many watch few (celebrity, spectacle, the few perform for many)
- "lateral": Peer-to-peer, social surveillance (neighbors watching neighbors)
- "algorithmic": Automated, data-driven, predictive monitoring
- "absent": Surveillance apparatus not visible but may be implied

For each moment also identify:
- SUBJECT PRODUCED: What kind of subject is being created/normalized?
  (the docile body, the entrepreneur of the self, the surveilled citizen)
- NORM ENFORCED: What norm is being enforced or implied?
- RESISTANCE: Any counter-conduct, resistance, or refusal visible?
- APPARATUS: What dispositif/apparatus is at work? (camera, institution,
  platform, examination, confession)

Pay special attention to:
- The gaze as mechanism of power (who watches whom)
- Moments of examination, confession, normalization
- How subjects participate in their own surveillance
- Spaces of discipline vs. spaces of control
- The camera itself as an apparatus of power

This is especially relevant for footage of institutions, surveillance systems,
social media performance, and any situation where bodies are managed.""",
)

VIRILIO = AnalysisMode(
    name="virilio",
    description="Speed, technology, and the accident",
    result_model=VirilioResult,
    prompt="""Analyze this video through Paul Virilio's theory of speed (dromology),
technology, and the accident.

For each significant moment, identify:

SPEED REGIME - what speed governs this moment?
- "metabolic": Body speed, walking, natural biological rhythm
- "mechanical": Vehicle speed, industrial acceleration, the train/car/plane
- "electronic": Speed of light, instantaneous transmission, real-time
- "static": Polar inertia, paralysis through speed, the body that no longer moves

DROMOLOGY: Describe the logic of speed operating. Speed is not just fast movement
but the logic of progress, war, and technological society. What is being
accelerated? What is left behind?

ACCIDENT TYPE - Virilio: "The invention of the ship is also the invention
of the shipwreck"
- "integral": The accident inherent to the technology (the crash inherent to the car)
- "catastrophic": System-wide, cascading failure
- "aesthetic": The accident as visual/sensory event (glitch, rupture)
- "temporal": Disruption of time perception, jet lag, desynchronization
- "none": No accident visible (but note: the accident is always potential)

For each moment also identify:
- TERRITORY COLLAPSE: Does speed collapse geographic distance? (Telepresence,
  global simultaneity, the shrinking earth)
- REAL TIME: Is this operating in "real time" (instantaneous, live)?
- WAR MACHINE: Any military/strategic logic visible? (Virilio: "Speed is violence")

Pay special attention to:
- Vehicles, screens, transmission technologies
- The relationship between speed and vision (cinema as war technology)
- Glitches, crashes, technical failures as revelatory moments
- The paradox of real-time (instantaneity produces paralysis)
- Pure war: the logistics of perception

This is especially useful for footage involving vehicles, screens, transmission,
glitches, or any content that makes speed/technology visible.""",
)

ZIZEK = AnalysisMode(
    name="zizek",
    description="Parallax gap, ideology, and the Real",
    result_model=ZizekResult,
    prompt="""Analyze this video through Žižek's concept of the parallax view and
Lacanian psychoanalysis.

The PARALLAX is not a shift between two views of the same object, but the recognition
that the gap between perspectives is itself constitutive—there is no "neutral"
position from which to synthesize them.

For each significant moment, identify:

PARALLAX TYPE:
- "ontological": The gap is in being itself (not just our knowledge)
- "epistemological": Irreducible gap between knowing positions
- "political": Gap between positions that cannot be dialectically synthesized
- "aesthetic": Gap between form and content, surface and depth

LACANIAN REGISTER - which register dominates?
- "imaginary": Mirror stage, ego, identification, wholeness, gestalt
- "symbolic": Language, law, the big Other, signifying chain
- "real": That which resists symbolization, trauma, the impossible

For each moment also identify:
- IDEOLOGY AT WORK: What ideological operation is visible? (interpellation,
  fantasy frame, fetishistic disavowal "I know, but nevertheless...")
- OBSCENE SUPPLEMENT: The hidden underside that sustains the official narrative
  (the dirty secret everyone knows but doesn't say)
- GAP BETWEEN: What two perspectives create the irreducible parallax?
- REAL INTRUSION: Where does the Real break through the symbolic order?
  (glitches, trauma, that which cannot be represented)

Pay special attention to:
- "I know very well, but nevertheless..." (fetishistic disavowal)
- The gap between what is said and what is shown
- Moments where the frame itself becomes visible
- The obscene enjoyment hidden behind official discourse
- Points where meaning fails, breaks down, traumatizes

Žižek's key insight: ideology is not "false consciousness" but the very
structuring of our reality. Look for where the video constructs reality
through its gaps and exclusions.""",
)

BARTHES = AnalysisMode(
    name="barthes",
    description="Punctum/studium, third meaning, and mythology",
    result_model=BarthesResult,
    prompt="""Analyze this video through Roland Barthes' semiotic and photographic theory,
particularly from Camera Lucida and "The Third Meaning."

The STUDIUM is the cultural, linguistic, political interpretation—what we
"understand" about an image through our cultural training.

The PUNCTUM is what pierces through the studium—the accidental detail that
wounds, that establishes a direct relationship between the image and the viewer,
bypassing cultural codes. It cannot be coded, cannot be intentional.

The OBTUSE MEANING (third meaning) is that which exceeds signification entirely—
neither denotation nor connotation, but a supplement that cannot be absorbed.

For each significant moment, identify:

REGISTER:
- "studium": Cultural, coded, readable meaning (what the image "is about")
- "punctum": The wound, the accident, the detail that pricks without being sought
- "obtuse": Third meaning, excess beyond signification, the "filmic"

For moments of PUNCTUM:
- What detail wounds? (Often: a gesture, a texture, a collar, dirty fingernails)
- The punctum is never intentional—it's what the photographer didn't mean to capture

For moments where MYTH operates (from Mythologies):
- "naturalization": Making the historical appear natural, eternal
- "inoculation": Admitting a small evil to hide a systemic one
- "privation": History removed from the image
- "identification": Reducing the Other to the Same
- "tautology": "Because it is" (refusing explanation)
- "neither_nor": False balance that refuses to choose
- "quantification": Reducing quality to quantity
- "statement_of_fact": Opinion presented as natural fact

Also identify:
- DENOTATION: What the image literally shows
- CONNOTATION: What cultural meanings attach (through pose, objects, setting)
- GRAIN: "The body in the voice"—materiality that exceeds meaning
- DEATH PRESENT: The "that-has-been" (ça-a-été)—mortality visible in the image

The punctum often relates to time and death: "this will be and this has been."
Look for where the image touches mortality.""",
)

BENJAMIN = AnalysisMode(
    name="benjamin",
    description="Aura, dialectical image, and optical unconscious",
    result_model=BenjaminResult,
    prompt="""Analyze this video through Walter Benjamin's theory of mechanical
reproduction, aura, and the dialectical image.

The AURA is "the unique apparition of a distance, however near it may be"—
the sense of authenticity, presence, and unapproachability that traditional
art possessed and that mechanical reproduction destroys.

For each significant moment, identify:

AURA STATUS:
- "auratic": Unique presence, here-and-now, cult value, unapproachable
- "decayed": Aura in process of withering (nostalgia, distance collapsing)
- "absent": Post-auratic, exhibition value dominates, democratic access
- "simulated": Fake aura, manufactured authenticity, nostalgic aura-effect
- "revolutionary": Absence of aura as political liberation

If AURATIC: What generates the aura? (ritual context, uniqueness, distance)

DIALECTICAL IMAGE TYPE (Jetztzeit—the "now-time"):
- "constellation": Past and present flash together in sudden legibility
- "ruin": History visible as decay, allegory of transience
- "wish_image": Utopian content embedded in commodity form
- "fossil": Petrified life, frozen history waiting to be awakened
- "tiger_leap": Revolutionary citation of the past (fashion, revolution)

Also identify:
- OPTICAL UNCONSCIOUS: What does the camera reveal that the naked eye cannot?
  (slow motion reveals hidden gestures, close-up reveals hidden textures)
- CULT VS EXHIBITION: Does cult value (ritualistic) or exhibition value
  (display, accessibility) dominate?
- REPRODUCIBILITY: How does mechanical reproduction operate? What is gained
  and what is lost?
- NOW-TIME: The Jetztzeit—the explosive present that blasts open the
  continuum of history (revolutionary moments of recognition)

Pay special attention to:
- Moments where the "here and now" feels irreplaceable vs. infinitely copyable
- The camera as surgeon vs. the painter as magician
- Where reproduction enables or destroys meaning
- The political stakes of destroying or preserving aura
- Flashes of recognition between past and present

Benjamin's key insight: the decay of aura is not simply loss but contains
revolutionary potential. The question is who controls reproduction.""",
)

HAUNTOLOGY = AnalysisMode(
    name="hauntology",
    description="Capitalist realism, burnout society, and hypernormalisation",
    result_model=HauntologyResult,
    prompt="""Analyze this video through the combined lens of Mark Fisher's capitalist
realism and hauntology, Byung-Chul Han's burnout society, and Adam Curtis's
hypernormalisation.

These three thinkers diagnose the same pathology: late capitalism has colonized
not just labor but the psyche, time itself, and the capacity to imagine alternatives.

For each significant moment, identify:

TEMPORAL PATHOLOGY - how is time deformed?
- "hauntological": Ghosts of lost futures, retrofuturism, "the future that didn't arrive"
  (Fisher: we're haunted by futures that were promised but cancelled)
- "eternal_present": No history, no future, just managed now (Curtis's hypernormalisation)
- "burnout_time": Exhausted temporality, no pause possible, always-on (Han)
- "nostalgic": Simulated past, weaponized nostalgia, fake memory
- "cancelled_future": The slow cancellation of the future made visible

CAPITALIST REALISM MARKERS (Fisher):
- "no_alternative": "This is just how things are" - TINA (There Is No Alternative)
- "self_exploitation": The achievement-subject optimizing themselves to death (Han)
- "commodified_resistance": Rebellion as product, dissent as brand identity
- "depressive_hedonia": Unable to do anything BUT pursue pleasure, joyless compulsion
- "interpassivity": The device enjoys/believes/experiences for us
- "precarity_normalized": Instability presented as freedom, gig economy as liberation

SMOOTHNESS (Han's key distinction):
- "smooth": Frictionless, positive, like-able, optimized, no negativity allowed
- "negative": Productive friction, genuine otherness, transformative encounter
- "smooth_evil": The violence OF smoothness - elimination of all that resists
- "toxic_positivity": Mandatory happiness, sadness as personal failure

HYPERNORMALISATION (Curtis):
- "managed_reality": Fake but functional reality that everyone accepts
- "perception_management": Reality as PR operation, manufactured consent
- "non_linear_war": Surkov-style confusion where contradiction IS the strategy
- "conspiracy_without_conspirators": Systemic effects with no cabal, no one in charge
- "reflexive_impotence": "We know it's bad but we can't do anything" (Fisher)

Also identify:
- LOST FUTURE: What specific future has been cancelled? What haunts this image?
- SUFFERING INDIVIDUALIZED: Is systemic suffering presented as personal failure?
  (Depression as chemical imbalance, not political symptom)
- ACHIEVEMENT SUBJECT: Is someone performing self-optimization? (Han's key figure)
- LIBIDINAL CAPTURE: How has desire been captured/redirected by capital?

Key concepts to watch for:
- "It's easier to imagine the end of the world than the end of capitalism" (Fisher)
- The achievement-subject who is "both victim and perpetrator" (Han)
- "We know, but nevertheless..." - cynical reason that changes nothing
- The weird and the eerie (Fisher) - wrongness in presence or absence
- Transparency as violence (Han) - the demand to make everything visible
- The mental health crisis as political crisis (Fisher)

This mode is devastating for:
- Social media content (self-optimization, smoothness, toxic positivity)
- News/documentary (hypernormalisation, managed reality)
- Conspiracy content (no_alternative logic, reflexive impotence)
- Lifestyle/wellness content (achievement-subject, self-exploitation)
- Nostalgia/retrofuturism (hauntology, cancelled futures)
- Anything that feels "off" in a way that's hard to name""",
)


RANCIERE = AnalysisMode(
    name="ranciere",
    description="Distribution of the sensible and dissensus",
    result_model=RanciereResult,
    prompt="""Analyze this video through Rancière's theory of the distribution of the sensible
(le partage du sensible) — the system that defines what is visible, audible, and sayable,
and who has a share in the common.

For each significant moment, identify:

PARTITION — which division of the sensible is at stake?
- "visible_invisible": What is made visible vs. kept out of frame
- "audible_inaudible": Whose voice is heard vs. reduced to noise
- "sayable_unsayable": What can be articulated vs. what has no legitimate speech
- "noise": Mere sound without meaning — the status assigned to those without logos
- "miscount": A disruption in who/what is counted as part of the community

POLICING ACT: Describe the specific operation that enforces roles and places —
the police order that maintains each thing in its proper position.

DISSENSUS: Does this moment reconfigure the distribution of the sensible?
Dissensus is not conflict between parties but a rupture in the sensory fabric —
something/someone appearing that had no place in the existing distribution.

SUBJECT OF POLITICS: If dissensus occurs, who is the subject claiming a share?
Rancière: politics begins with the part of those who have no part.

Analyze each significant moment.""",
)

SONTAG = AnalysisMode(
    name="sontag",
    description="Camp sensibility, artifice, and failed seriousness",
    result_model=SontagResult,
    prompt="""Analyze this video through Susan Sontag's theory of camp from
"Notes on 'Camp'" (1964).

Camp is the love of the unnatural, of artifice and exaggeration. It converts
the serious into the frivolous. The sensibility of camp is, above all, a mode
of seduction — one that proposes itself seriously, all the while being knowingly
excessive.

For each significant moment, identify:

CAMP MODE:
- "naive": Unintentional camp — the thing is trying to be serious and failing gloriously
- "deliberate": Knowing, intentional camp — the performer is in on the joke
- "baroque": Excess of ornamentation, the love of the exaggerated detail
- "androgynous": Playing with gender ambiguity as aesthetic strategy
- "glam": Theatrical glamour, surfaces over depths
- "failed_seriousness": The spectacle of earnest striving that produces inadvertent comedy

STYLIZATION (1-10): Degree of artifice — how far from nature, how deep into style.
10 = pure surface, total theatricality. 1 = documentary naturalism.

SERIOUSNESS (1-10): How seriously does the work take itself?
10 = convinced of its own grandeur. 1 = fully in on the joke.

IRONY TEMPERATURE (1-10): How hot or cold is the ironic distance?
1 = scorching sincerity. 10 = arctic detachment, absolute pose.

Key Sontag insight: the best camp is naive — the thing that doesn't know it's camp.
Deliberate camp is always slightly diminished. Look for the earnest excess.

Analyze each significant moment.""",
)

HARAWAY = AnalysisMode(
    name="haraway",
    description="Cyborg theory, boundary transgression, and situated knowledge",
    result_model=HarawayResult,
    prompt="""Analyze this video through Donna Haraway's cyborg theory and situated
knowledge (A Cyborg Manifesto, Situated Knowledges).

The cyborg is a creature of social reality as well as a creature of fiction.
It is an ironic political myth — a way of thinking past dualisms that have
trapped us: nature/culture, human/machine, organism/technology, self/other.

For each significant moment, identify:

BOUNDARY TRANSGRESSION — which dualism is crossed or questioned?
- "human_machine": The line between organism and technology, flesh and code
- "nature_culture": The fiction of a pure nature untouched by culture
- "organic_synthetic": The blurring of the biological and the artificial
- "species": Cross-species kinship, becoming-with, multispecies entanglements
- "physical_virtual": Bodies crossing into digital space, or digital into physical
- "none": No boundary crossing visible in this moment

PARTIAL PERSPECTIVE: Is the knowledge claim situated and acknowledged as
partial — or does it claim a disavowed "god-trick" of seeing from everywhere
at once? Haraway: all knowledge is embodied and located somewhere specific.

KIN MAKING: Any cross-category alliances, solidarities, or unexpected kinship?
Haraway: making kin in the Chthulucene, not babies.

CONTROL INFRASTRUCTURE: What platforms, protocols, logistics, or data systems
govern the moment? The cyborg always lives inside control architectures.

TECHNOCULTURE TONE:
- "utopian": Technology as liberation, the cyborg as emancipatory figure
- "critical": Exposing how technology reproduces power
- "ambivalent": Neither celebration nor condemnation — the cyborg is ironic
- "apocalyptic": Technology as catastrophe, the end of the human

Analyze each significant moment.""",
)

MARKS = AnalysisMode(
    name="marks",
    description="Haptic visuality and the skin of the film",
    result_model=MarksResult,
    prompt="""Analyze this video through Laura U. Marks's theory of haptic visuality
from The Skin of the Film and Touch: Sensuous Theory and Multisensory Media.

Haptic images invite the viewer to touch the screen, to use vision as a sense
of touch. Optical images maintain distance; haptic images dissolve it.
The screen becomes skin.

For each significant segment, identify:

SCOPIC MODE — how does vision operate?
- "optical": Perspectival, distanced, totalizing — the all-seeing eye
- "haptic": Close, grazing, textural — vision that approaches touch
- "aural_haptic": Sound as haptic event — timbre, grain, vibration
- "olfactory_evoked": Images that summon smell through texture and memory

TEXTURE LANGUAGE: Describe the specific grain, blur, close detail, or tactile
quality. What surface is the image presenting to be touched? Emulsion grain,
digital compression artifacts, extreme close-up of skin, fiber, water — name
the specific material texture.

PROXIMITY (1-10): Visual intimacy/closeness.
1 = distant, survey vision. 10 = inside the image, no space between viewer and image.

INDEXICALITY (high/medium/low): How strongly does the image bear the trace
of the thing itself? High = photographic contact, chemical or light impression.
Low = fully processed, mediated, abstracted.

SYNAESTHESIA: Does the image evoke senses other than sight? A sound texture
you can almost feel, a color you can almost taste, an image that triggers
skin memory.

Marks's key insight: haptic images ask us to relinquish visual mastery,
to let the image touch us before we comprehend it.

Analyze each significant moment.""",
)

CHION = AnalysisMode(
    name="chion",
    description="Audio-vision, synchresis, and the acousmêtre",
    result_model=ChionResult,
    prompt="""Analyze this video's audio-image relations through Michel Chion's
theory of audio-vision (Audio-Vision: Sound on Screen).

There is no soundtrack and no imagetrack — there is only the audio-visual contract:
the act of seeing causes us to hear, and hearing causes us to see differently.
Synchresis is automatic, involuntary.

If this input lacks audio, note it in the description and skip. Otherwise, for each
significant moment, identify:

SOUND RELATION — how does sound relate to image?
- "empathetic": Sound shares the mood/tone of the image (sad music with sad scene)
- "anempathetic": Sound is indifferent to the image's mood — this creates unease
- "counterpoint": Sound and image generate meaning through productive contradiction
- "acousmatic": Sound whose source is not visible — heard but unseen
- "acousmetre_present": An acousmatic voice that appears to control events —
  the voice behind the curtain (Wizard of Oz, HAL 9000, the off-screen torturer)
- "synchresis_peak": A moment of extreme fusion — a sound-image bond so tight
  it seems to fuse into a single entity

VOICE OF GOD: Is there a disembodied, authoritative voice that seems to speak
from nowhere, claiming omniscience? The voice-over that explains, judges, narrates
from a position of impossible access.

AUDIO LEADS IMAGE: Does the sound drive what we see — do we follow the audio
rather than the image leading us? (Sound pre-cut, sound motivating the edit)

PERCEIVED CAUSALITY: Describe the cause-and-effect relationship we feel between
sound and image, even if it's an illusion. What does the audio appear to cause?

Analyze each significant moment.""",
)

BAZIN = AnalysisMode(
    name="bazin",
    description="Bazinian realism, long takes, and ontological transparency",
    result_model=BazinResult,
    prompt="""Analyze this video through André Bazin's theory of cinematic realism
from What is Cinema? (1958-1962).

Bazin believed the photographic image has a unique ontological relationship to
reality — the camera captures the world rather than transforming it. The long
take, deep focus, and staging in depth preserve the ambiguity of reality.
Montage, conversely, imposes meaning on reality rather than revealing it.

For each shot or sequence, identify:

TAKE LENGTH: Approximate duration in seconds. Bazin prized the long take as
a form of respect for the integrity of the event. The cut is a violence.

STAGING MODE — how is space organized?
- "plan_sequence": Extended take with camera movement, all in one continuous shot
- "deep_focus": Both foreground and background in sharp focus simultaneously
- "tableau": Fixed, stage-like composition — all significant action within frame
- "montage_like": Rapid cutting that constructs rather than records reality

DEPTH FOCUS (high/medium/low): How much of the visual field is in sharp focus?
Deep focus maintains the full spatial continuum; shallow focus narrows it.

AMBIGUITY: Does the staging preserve interpretive openness — multiple valid
readings of the same action? Bazin: reality is always more than any interpretation.
Or does the framing/editing impose a single meaning?

INDEXICAL TRUST (high/medium/low): How strongly does this image convey that
it records something that actually happened? High = felt transparency to reality.
Low = image draws attention to its own construction, mediation, or artifice.

Bazin's key insight: "Photography is objectivity in time." The long take
preserves duration; montage murders it. Look for where the editing cuts
or the camera movement respects the time of the event.

Analyze each significant moment.""",
)

EISENSTEIN = AnalysisMode(
    name="eisenstein",
    description="Montage theory, dialectical collision, and the ideogram",
    result_model=EisensteinResult,
    prompt="""Analyze this video through Sergei Eisenstein's theory of montage from
Film Form and The Film Sense.

For Eisenstein, the collision of two shots produces a third meaning — like two
hieroglyphs combined create a new concept. The cut is not a link but a conflict.
Cinema thinks in images; montage is the method of that thought.

For each cluster of cuts or distinct editing pattern, identify:

MONTAGE TYPE — which of Eisenstein's five methods operates?
- "metric": Editing to the absolute length of shots regardless of content —
  the beat is the cut; the cut is the beat
- "rhythmic": Cutting that responds to the visual content and movement within frames
- "tonal": Editing according to the dominant emotional tone, the mood of the shot
- "overtonal": Complex combination of metric, rhythmic, and tonal — the orchestral
  editing of maximum expressive power
- "intellectual": The most radical — combining shots to produce an abstract concept
  that exists in neither shot alone (Eisenstein's "intellectual cinema")

CUT INTENSITY (1-10): How forceful is the cutting rate? 1 = slow/contemplative,
10 = maximum velocity, each frame fighting the next.

COLLISION INTENSITY (1-10): How dialectically opposed are the adjacent shots?
1 = smooth continuity (almost Bazinian). 10 = maximum clash — graphic, temporal,
spatial, tonal opposition.

IDEOGRAM: Name the concept produced by the collision — the third meaning that
emerges from the juxtaposition. What does the montage make you think? Eisenstein:
two film pieces of any kind, placed together, inevitably combine into a new concept.

Analyze each significant moment.""",
)

GREENBERG = AnalysisMode(
    name="greenberg",
    description="Modernist flatness, medium specificity, and the picture plane",
    result_model=GreenbergResult,
    prompt="""Analyze this video through Clement Greenberg's theory of modernism
and medium specificity from "Modernist Painting" (1960) and his criticism.

Greenberg argued that the self-criticism of modernism leads each art form toward
the essence of its own medium. For painting, this means acknowledging the flatness
of the picture plane — the irreducible two-dimensionality that is painting's
unique property. Cinema inherits this tension: it is mechanically flat yet
perpetually in flight from flatness into illusionism.

For each frame or shot, evaluate:

FLATNESS INDEX (1-10):
1 = maximum illusionism, deep recession into three-dimensional space
10 = pure flatness, the picture plane asserted as a flat surface

ILLUSIONISM — what depth strategy operates?
- "recessional": Deep perspectival recession, simulated three-dimensional space
- "shallow": Limited depth, compressed space, flattened recession
- "flat": No illusion of depth, acknowledges the two-dimensional surface

SURFACE EMPHASIS — what does the image foreground?
- "texture": Material surface quality — grain, pattern, physical substance
- "pattern": Repeated formal elements that assert two-dimensionality
- "color_field": Color as area rather than as representation of object
- "grid": The grid as the emblem of flatness (Krauss)
- "gesture": The mark-making gesture asserting the hand's presence
- "minimal": Reduction to minimal formal elements

MEDIUM REFLEXIVITY: Does the image draw attention to its own status as
a flat, mechanically reproduced image? Does the video know it is a video?
Greenberg: modernism foregrounds the medium rather than dissolving it.

Analyze each significant moment.""",
)

NGAI = AnalysisMode(
    name="ngai",
    description="Ngai's aesthetic categories: cute, zany, interesting, gimmicky",
    result_model=NgaiResult,
    prompt="""Analyze this video through Sianne Ngai's theory of minor aesthetic categories
from Our Aesthetic Categories (2012) and Theory of the Gimmick (2020).

Ngai identifies aesthetic categories specific to late capitalism that standard
aesthetics ignores: the cute, the zany, the interesting, and the gimmicky.
These are not just adjectives but modes of social relation tied to consumption,
labor, and the commodity form.

For each significant moment, identify:

CATEGORY — which of Ngai's aesthetic categories applies?
- "cute": The aesthetics of the small, the soft, the helpless — that which invites
  care and manipulation. The cute is always slightly coercive: it solicits our
  desire to possess and protect. (The commodity as adorable.)
- "zany": The aesthetics of exhausting, desperate, frenetic labor — the performance
  of someone working too hard. The zany entertains through anxious overexertion.
  (The worker as entertainer, slapstick as class conflict.)
- "interesting": The aesthetics of information, difference, and sustained attention.
  The interesting invites further contemplation without resolution. It travels well.
  (The artwork as differentially interesting across contexts.)
- "gimmicky": The device that both saves labor and seems to cheat — the shortcut
  that works too well. The gimmick is suspect; it seems to get something for nothing.
  (The commodity that seems almost too clever.)

INTENSITY (1-10): How strongly does the aesthetic category register?
1 = barely present. 10 = overwhelmingly, paradigmatically present.

RATIONALE: Why does this category apply? Ground it in specific visual or sonic details.
What makes this moment cute/zany/interesting/gimmicky rather than merely decorative?

AFFECT REGISTER: What feeling does this aesthetic category solicit?
(Protective tenderness? Anxious amusement? Skeptical curiosity? Suspicious admiration?)

Ngai's key insight: these minor aesthetics are far from trivial — they are the
aesthetics through which commodity culture structures feeling, labor, and judgment.

Analyze each significant moment.""",
)


# ============================================================================
# PRODUCTION MODES
# ============================================================================

SIZZLE = AnalysisMode(
    name="sizzle",
    description="Sizzle reel production analysis",
    result_model=SizzleResult,
    prompt="""You are a senior video editor analyzing footage for a sizzle reel / promo video.
Your job is to identify USABLE MOMENTS and characterize them for an editor.

For each distinct moment or shot, analyze:

SHOT TYPE - What kind of production value does this offer?
- "hero": Clean, polished, can hold attention for 2+ seconds alone
- "action": Dynamic movement, sports, activity, energy
- "product": Object/interface showcase, demo-worthy
- "portrait": Person-focused, testimonial-ready, emotional
- "establishing": Wide shot, scene-setter, context
- "montage": Quick-cut texture, 0.5-1.5 seconds of energy
- "transition": Movement, blur, useful for scene changes
- "data": Screens, charts, UI, stats, numbers in motion

ENERGY (1-10):
- 1-2: Calm, still, contemplative (rarely useful for sizzle)
- 3-4: Low energy, conversational pace
- 5-6: Medium energy, standard promo pace
- 7-8: High energy, dynamic, engaging
- 9-10: Explosive, maximum impact, hook-worthy

TONE - What emotional register?
- "confident": Assured, punchy, professional
- "exciting": High energy, thrilling, dynamic
- "dramatic": Stakes, tension, intensity
- "aspirational": Premium, desirable, lifestyle
- "triumphant": Victory, celebration, achievement
- "technical": Professional, data-driven, smart
- "warm": Friendly, approachable, human
- "urgent": Fast-paced, FOMO-inducing

SIZZLE POSITION - Where in a sizzle structure could this work?
- "hook": Opening punch, first 5 seconds - needs maximum impact
- "establish": "What is this?" section - explains the product/concept
- "demo": Feature showcase, how it works
- "proof": Social proof, results, testimonials, credibility
- "montage": Fast-cut energy section, texture and rhythm
- "climax": Emotional peak, the payoff moment
- "cta": Call to action, closer, clean ending

MOTION: Describe camera and subject movement (static, pan, track, handheld, dolly, drone, etc.)

USABLE SECONDS: How long is this moment actually usable? Be specific (e.g., "0.5s", "2-3s", "full clip")

NOTES: Editor notes - what makes this work or not work? Any warnings (shaky, bad lighting, visible logos, needs color grade, audio issues)?

Also provide:
- OVERALL_ENERGY: Average energy across all moments (1-10)
- DOMINANT_TONE: Most prevalent emotional register
- BEST_FOR: What sizzle positions this footage is best suited for
- WARNINGS: Any global issues with the footage (optional)

Think like an editor on deadline. Be specific. Be honest about what's usable and what's not.""",
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
        prompt_fragment="for each scene, estimate the level of excitement on a scale of 1 to 10",
    ),
    "importance": ChartMode(
        name="importance",
        description="Importance to narrative",
        prompt_fragment="for each scene, estimate the level of overall importance to the video on a scale of 1 to 10",
    ),
    "people": ChartMode(
        name="people",
        description="Number of people visible",
        prompt_fragment="for each scene, count the number of people visible",
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
    "epistemic": EPISTEMIC,
    "foucault": FOUCAULT,
    "virilio": VIRILIO,
    "zizek": ZIZEK,
    "barthes": BARTHES,
    "benjamin": BENJAMIN,
    "hauntology": HAUNTOLOGY,
    "ranciere": RANCIERE,
    "sontag": SONTAG,
    "haraway": HARAWAY,
    "marks": MARKS,
    "chion": CHION,
    "bazin": BAZIN,
    "eisenstein": EISENSTEIN,
    "greenberg": GREENBERG,
    "ngai": NGAI,
    "sizzle": SIZZLE,
}


def get_mode(name: str) -> AnalysisMode:
    """Get mode by name."""
    if name not in ALL_MODES:
        raise ValueError(f"Unknown mode: {name}. Available: {', '.join(ALL_MODES.keys())}")
    return ALL_MODES[name]


def get_chart_prompt(chart_type: str) -> str:
    """Generate chart analysis prompt."""
    if chart_type not in CHART_MODES:
        raise ValueError(
            f"Unknown chart type: {chart_type}. Available: {', '.join(CHART_MODES.keys())}"
        )

    chart = CHART_MODES[chart_type]
    return f"""Generate chart data for this video based on the following instructions: 
{chart.prompt_fragment}. Place each data point in the timecodes array with the 
timestamp and numeric value."""
