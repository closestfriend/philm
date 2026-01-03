/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
/* tslint:disable */
// Copyright 2024 Google LLC

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     https://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

export default {
  'A/V captions': {
    emoji: '👀',
    prompt: `For each scene in this video, generate captions that describe the \
    scene along with any spoken text placed in quotation marks. Place each \
    caption into an object sent to set_timecodes with the timecode of the caption \
    in the video.`,
    isList: true,
  },

  Paragraph: {
    emoji: '📝',
    prompt: `Generate a paragraph that summarizes this video. Keep it to 3 to 5 \
sentences. Place each sentence of the summary into an object sent to \
set_timecodes with the timecode of the sentence in the video.`,
  },

  'Key moments': {
    emoji: '🔑',
    prompt: `Generate bullet points for the video. Place each bullet point into an \
object sent to set_timecodes with the timecode of the bullet point in the video.`,
    isList: true,
  },

  Table: {
    emoji: '🤓',
    prompt: `Choose 5 key shots from this video and call set_timecodes_with_objects \
with the timecode, text description of 10 words or less, and a list of objects \
visible in the scene (with representative emojis).`,
  },

  Haiku: {
    emoji: '🌸',
    prompt: `Generate a haiku for the video. Place each line of the haiku into an \
object sent to set_timecodes with the timecode of the line in the video. Make sure \
to follow the syllable count rules (5-7-5).`,
  },

  'Affect Theory': {
    emoji: '⚡',
    prompt: `Analyze the affective intensities across this video using Massumi's affect \
theory framework. For each significant moment, map:
- The raw pre-cognitive intensity (1-10 scale)
- The qualitative atmosphere (the felt sense before cognition captures it)
- The vector of movement (direction the affect is pulling - toward/away, up/down, expanding/contracting)
- Whether this moment "captures" or "qualifies" the affect (does it freeze the intensity \
into recognizable emotion, or does it remain pure potential?)

Focus on transitions, thresholds, and moments where affect escapes capture. Call analyze_affect \
with your findings.`,
  },

  'Camera Kinetics': {
    emoji: '🎥',
    prompt: `Analyze the camera work in this video on a spectrum from controlled/contemplative \
to frenetic/chaotic.

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

Note if the camera shows RESTLESSNESS (micro-adjustments, inability to be still even when "static").
Describe any evidence of OPERATOR PRESENCE (breathing, footsteps, shadow, body movement).

Call analyze_camera with your findings.`,
  },

  'Deleuzian Rhythm': {
    emoji: '🌀',
    prompt: `Analyze this video's rhythm through a Deleuzo-Guattarian lens.

For each shift in tempo or territorial movement:
- Rate the speed of deterritorialization (1-10):
  1 = deeply coded/striated, 10 = smooth space / absolute deterritorialization
- Classify the movement:
  - "territorializing": establishing codes, habits, boundaries
  - "deterritorializing": breaking down, escaping, becoming-other
  - "reterritorializing": recapturing flows into new codes
  - "line_of_flight": pure escape, creation of the new
- Identify the refrain (ritornello): what repetition anchors or releases?

Call analyze_rhythm with your findings.`,
  },

  'Benjamin: Aura/Distraction': {
    emoji: '🕯️',
    prompt: `Analyze aura, shock, and attention under mechanical reproduction (Benjamin).

For each moment:
- Classify mode: aura, trace, shock, distraction, exhibition
- Rate aura_index (1-10) as here-and-now presence vs reproducibility
- Note attention form: concentration, distraction, habit, collective
- Assess politicization: aestheticized_politics vs politicized_art (or ambivalent)

Call analyze_aura_benjamin with your findings.`,
  },

  'Foucault: Visibility/Power': {
    emoji: '🛰️',
    prompt: `Map regimes of visibility and subject formation (Foucault).

For each scene:
- Classify diagram: disciplinary, biopolitical, sovereign, panoptic, capillary, counter_visibility
- Identify visibility: surveillant_view, confessional, normative_measurement, self_surveillance, obscured
- Name apparatus: camera, clinic, platform, metric, archive, etc.
- Describe subjectivation and any resistance/counter-visibility tactics

Call analyze_visibility_power_foucault with your findings.`,
  },

  "Rancière: Distribution": {
    emoji: '🎭',
    prompt: `Track partitions of the sensible and moments of dissensus (Rancière).

For each moment:
- Mark partition: visible/invisible, audible/inaudible, sayable/unsayable, noise, miscount
- Describe policing_act (how roles/places are enforced)
- Flag dissensus if the sensible order is reconfigured
- Note subject_of_politics (who appears/speaks) and reconfiguration

Call analyze_distribution_ranciere with your findings.`,
  },

  'Sontag: Camp': {
    emoji: '💅',
    prompt: `Assess camp sensibility: artifice, stylization, failed seriousness (Sontag).

For each moment:
- Classify camp_mode: naive, deliberate, baroque, androgynous, glam, failed_seriousness
- Rate stylization (1-10) and seriousness (1-10)
- Set irony_temperature (1-10) and add brief notes

Call analyze_camp_sontag with your findings.`,
  },

  'Haraway: Cyborg/Situated': {
    emoji: '🤖',
    prompt: `Track boundary transgressions and situated perspectives (Haraway).

For each scene:
- Boundary_transgression: human/machine, nature/culture, organic/synthetic, species, physical/virtual, none
- Partial_perspective: acknowledged or disavowed
- Note kin_making and control_infrastructure (platforms, protocols, logistics)
- Set technoculture_tone: utopian, critical, ambivalent, apocalyptic

Call analyze_cyborg_haraway with your findings.`,
  },

  'Barthes: Studium/Punctum': {
    emoji: '🎯',
    prompt: `Distinguish studium vs punctum (Barthes).

For each shot:
- Provide studium (cultural reading)
- Mark punctum_present and, if so, punctum_detail and wound_intensity (1-10)
- Temporal_punctum if relevant: future_anterior, anachronic, none

Call analyze_punctum_barthes with your findings.`,
  },

  'Marks: Haptic Visuality': {
    emoji: '🖐️',
    prompt: `Measure haptic vs optical vision (Laura Marks).

For each segment:
- Scopic_mode: optical, haptic, aural_haptic, olfactory_evoked
- Describe texture_language (grain, blur, close detail, tactility)
- Proximity (1-10), indexicality (high/medium/low), synaesthesia flag

Call analyze_haptic_marks with your findings.`,
  },

  'Chion: Audio-Vision': {
    emoji: '🔊',
    prompt: `Classify audio-image relations (Chion). If the input lacks audio, skip segments.

For each moment:
- Sound_relation: empathetic, anempathetic, counterpoint, acousmatic, acousmetre_present, synchresis_peak
- Flag voice_of_god and audio_leads_image where applicable
- Describe perceived_causality and rhetorical force of sound

Call analyze_audiovision_chion with your findings.`,
  },

  // Purely visual (no audio dependency)
  'Bazin: Realism (Visual)': {
    emoji: '🎬',
    prompt: `Assess Bazinian realism with no reliance on audio.

For each shot/sequence:
- Report take_length_sec and staging_mode: plan_sequence, deep_focus, tableau, montage_like
- Depth_focus: high, medium, low; mark ambiguity if action remains interpretively open
- Indexical_trust: high, medium, low; add description

Call analyze_realism_bazin with your findings.`,
  },

  'Eisenstein: Montage (Visual)': {
    emoji: '✂️',
    prompt: `Classify montage purely from visual cutting (no audio assumed).

For each cluster:
- Montage_type: metric, rhythmic, tonal, overtonal, intellectual
- Rate cut_intensity (1-10) and collision_intensity (1-10)
- Provide ideogram and a brief description

Call analyze_montage_eisenstein with your findings.`,
  },

  'Greenberg: Flatness (Visual)': {
    emoji: '🟥',
    prompt: `Evaluate modernist flatness and medium specificity (visual only).

For each frame/shot:
- Flatness_index (1-10), illusionism: recessional, shallow, flat
- Surface_emphasis: texture, pattern, color_field, grid, gesture, minimal
- Mark medium_reflexivity and add description

Call analyze_flatness_greenberg with your findings.`,
  },

  'Ngai: Categories (Visual)': {
    emoji: '🧸',
    prompt: `Apply Ngai’s categories without audio assumptions.

For each moment:
- Category: cute, zany, interesting, gimmicky
- Intensity (1-10) and concise rationale
- Optionally note affect_register

Call analyze_categories_ngai with your findings.`,
  },

  'Virilio: Dromology (Visual)': {
    emoji: '🚀',
    prompt: `Map regimes of speed/vision with no audio reliance (Virilio).

For each sequence:
- Speed_regime: slow, moderate, fast, ultrafast, instantaneous
- Motion_blur: none, subtle, pronounced, strobing; telepresence flag
- Perspective_warp: none, wide_angle_distortion, compression, drone_godview, glitch

Call analyze_dromology_virilio with your findings.`,
  },

  Chart: {
    emoji: '📈',
    prompt: (input) =>
      `Generate chart data for this video based on the following instructions: \
${input}. Call set_timecodes_with_numeric_values once with the list of data values and timecodes.`,
    subModes: {
      Excitement:
        'for each scene, estimate the level of excitement on a scale of 1 to 10',
      Importance:
        'for each scene, estimate the level of overall importance to the video on a scale of 1 to 10',
      'Number of people': 'for each scene, count the number of people visible',
    },
  },

  Custom: {
    emoji: '🔧',
    prompt: (input) =>
      `Call set_timecodes once using the following instructions: ${input}`,
    isList: true,
  },
};
