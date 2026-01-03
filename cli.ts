#!/usr/bin/env npx ts-node
/**
 * Video Analyzer CLI
 * Semantic video analysis powered by Gemini 2.5 Flash
 */

import { GoogleGenAI, Type } from '@google/genai';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

// Video file extensions we support
const VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mov', '.avi', '.mpg', '.mpeg', '.mkv', '.m4v'];

// Find all video files in a directory
function findVideoFiles(dirPath: string, recursive: boolean, excludePatterns: string[] = []): string[] {
  const absolutePath = path.resolve(dirPath);
  const files: string[] = [];

  function shouldExclude(dirName: string): boolean {
    return excludePatterns.some(pattern =>
      dirName.toLowerCase().includes(pattern.toLowerCase())
    );
  }

  function scan(dir: string) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory() && recursive) {
        if (!shouldExclude(entry.name)) {
          scan(fullPath);
        } else {
          console.error(`  Skipping excluded folder: ${entry.name}`);
        }
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name).toLowerCase();
        if (VIDEO_EXTENSIONS.includes(ext)) {
          files.push(fullPath);
        }
      }
    }
  }

  scan(absolutePath);
  return files.sort();
}

// Technical analysis types
interface TechnicalMetrics {
  duration: number;
  sceneChanges: number;
  changeDensity: number;  // changes per second
  avgSceneScore: number;
  maxSceneScore: number;
  framerate: number;
  chaosIndex: number;     // normalized 1-10 scale
}

// Load API key from .env.local
const envPath = path.join(import.meta.dirname, '.env.local');
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, 'utf-8');
  const match = envContent.match(/GEMINI_API_KEY=(.+)/);
  if (match) process.env.GEMINI_API_KEY = match[1].trim();
}

const client = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// Run FFmpeg technical analysis
async function getTechnicalMetrics(filePath: string): Promise<TechnicalMetrics> {
  const absolutePath = path.resolve(filePath);

  console.error('Running technical analysis...');

  // Get duration and framerate
  const probeCmd = `ffprobe -v quiet -show_entries format=duration:stream=r_frame_rate -of json "${absolutePath}"`;
  const probeResult = JSON.parse(execSync(probeCmd).toString());
  const duration = parseFloat(probeResult.format.duration);
  const framerateStr = probeResult.streams?.[0]?.r_frame_rate || '30/1';
  const [num, den] = framerateStr.split('/').map(Number);
  const framerate = num / (den || 1);

  // Run scene detection - get all frame scene scores
  console.error('  Detecting scene changes...');
  const sceneCmd = `ffmpeg -i "${absolutePath}" -vf "select='gte(scene,0)',metadata=print:file=-" -an -f null - 2>/dev/null | grep lavfi.scene_score | head -500`;

  let sceneScores: number[] = [];
  try {
    const sceneOutput = execSync(sceneCmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
    sceneScores = sceneOutput
      .split('\n')
      .filter(line => line.includes('lavfi.scene_score'))
      .map(line => {
        const match = line.match(/lavfi\.scene_score=([0-9.]+)/);
        return match ? parseFloat(match[1]) : 0;
      })
      .filter(score => score > 0);
  } catch (e) {
    // Fallback: simpler scene detection
    const fallbackCmd = `ffmpeg -i "${absolutePath}" -vf "select='gt(scene,0.1)',showinfo" -an -f null - 2>&1 | grep "pts_time" | wc -l`;
    try {
      const count = parseInt(execSync(fallbackCmd).toString().trim()) || 0;
      sceneScores = Array(count).fill(0.15);
    } catch {
      sceneScores = [];
    }
  }

  // Calculate metrics
  const sceneChanges = sceneScores.filter(s => s > 0.1).length;  // threshold for "significant" change
  const changeDensity = sceneChanges / duration;
  const avgSceneScore = sceneScores.length > 0
    ? sceneScores.reduce((a, b) => a + b, 0) / sceneScores.length
    : 0;
  const maxSceneScore = sceneScores.length > 0
    ? Math.max(...sceneScores)
    : 0;

  // Calculate chaos index (1-10 scale)
  // Factors: change density, average scene score, max scene score
  const densityFactor = Math.min(changeDensity * 2, 5);  // 0-5 points, caps at 2.5 changes/sec
  const avgFactor = avgSceneScore * 20;                   // 0-2 points typical
  const maxFactor = maxSceneScore * 3;                    // 0-3 points
  const chaosIndex = Math.min(Math.max(densityFactor + avgFactor + maxFactor, 1), 10);

  console.error(`  Duration: ${duration.toFixed(1)}s, Framerate: ${framerate.toFixed(1)}fps`);
  console.error(`  Scene changes: ${sceneChanges}, Density: ${changeDensity.toFixed(2)}/sec`);
  console.error(`  Chaos index: ${chaosIndex.toFixed(1)}/10`);

  return {
    duration,
    sceneChanges,
    changeDensity,
    avgSceneScore,
    maxSceneScore,
    framerate,
    chaosIndex,
  };
}

const MODES = {
  captions: {
    name: 'A/V captions',
    fn: 'set_timecodes',
    prompt: `For each scene in this video, generate captions that describe the scene along with any spoken text placed in quotation marks. Place each caption into an object sent to set_timecodes with the timecode of the caption in the video.`,
  },
  paragraph: {
    name: 'Paragraph',
    fn: 'set_timecodes',
    prompt: `Generate a paragraph that summarizes this video. Keep it to 3 to 5 sentences. Place each sentence of the summary into an object sent to set_timecodes with the timecode of the sentence in the video.`,
  },
  'key-moments': {
    name: 'Key moments',
    fn: 'set_timecodes',
    prompt: `Generate bullet points for the video. Place each bullet point into an object sent to set_timecodes with the timecode of the bullet point in the video.`,
  },
  table: {
    name: 'Table',
    fn: 'set_timecodes_with_objects',
    prompt: `Choose 5 key shots from this video and call set_timecodes_with_objects with the timecode, text description of 10 words or less, and a list of objects visible in the scene (with representative emojis).`,
  },
  haiku: {
    name: 'Haiku',
    fn: 'set_timecodes',
    prompt: `Generate a haiku for the video. Place each line of the haiku into an object sent to set_timecodes with the timecode of the line in the video. Make sure to follow the syllable count rules (5-7-5).`,
  },
  affect: {
    name: 'Affect Analysis (Massumi)',
    fn: 'analyze_affect',
    prompt: `Analyze the affective intensities across this video using Massumi's affect theory framework. For each significant moment, map:
- The raw pre-cognitive intensity (1-10 scale)
- The qualitative atmosphere (the felt sense before cognition captures it)
- The vector of movement (direction the affect is pulling - toward/away, up/down, expanding/contracting)
- Whether this moment "captures" or "qualifies" the affect (does it freeze the intensity into recognizable emotion, or does it remain pure potential?)

Focus on transitions, thresholds, and moments where affect escapes capture. Call analyze_affect with your findings.`,
  },
  camera: {
    name: 'Camera Analysis (Frenetic/Kinetic)',
    fn: 'analyze_camera',
    prompt: `Analyze the camera work in this video on a spectrum from controlled/contemplative to frenetic/chaotic.

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
  rhythm: {
    name: 'Deleuzian Rhythm/Tempo Analysis',
    fn: 'analyze_rhythm',
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
  benjamin: {
    name: 'Benjamin: Aura/Distraction',
    fn: 'analyze_aura_benjamin',
    prompt: `Analyze aura, shock, and attention under mechanical reproduction (Benjamin).

For each moment:
- Classify mode: aura, trace, shock, distraction, exhibition
- Rate aura_index (1-10) as here-and-now presence vs reproducibility
- Note attention form: concentration, distraction, habit, collective
- Assess politicization: aestheticized_politics vs politicized_art (or ambivalent)

Call analyze_aura_benjamin with your findings.`,
  },
  foucault: {
    name: 'Foucault: Visibility/Power',
    fn: 'analyze_visibility_power_foucault',
    prompt: `Map regimes of visibility and subject formation (Foucault).

For each scene:
- Classify diagram: disciplinary, biopolitical, sovereign, panoptic, capillary, counter_visibility
- Identify visibility: surveillant_view, confessional, normative_measurement, self_surveillance, obscured
- Name apparatus: camera, clinic, platform, metric, archive, etc.
- Describe subjectivation and any resistance/counter-visibility tactics

Call analyze_visibility_power_foucault with your findings.`,
  },
  rancier: {
    name: 'Rancière: Distribution',
    fn: 'analyze_distribution_ranciere',
    prompt: `Track partitions of the sensible and moments of dissensus (Rancière).

For each moment:
- Mark partition: visible/invisible, audible/inaudible, sayable/unsayable, noise, miscount
- Describe policing_act (how roles/places are enforced)
- Flag dissensus if the sensible order is reconfigured
- Note subject_of_politics (who appears/speaks) and reconfiguration

Call analyze_distribution_ranciere with your findings.`,
  },
  sontag: {
    name: 'Sontag: Camp',
    fn: 'analyze_camp_sontag',
    prompt: `Assess camp sensibility: artifice, stylization, failed seriousness (Sontag).

For each moment:
- Classify camp_mode: naive, deliberate, baroque, androgynous, glam, failed_seriousness
- Rate stylization (1-10) and seriousness (1-10)
- Set irony_temperature (1-10) and add brief notes

Call analyze_camp_sontag with your findings.`,
  },
  haraway: {
    name: 'Haraway: Cyborg/Situated',
    fn: 'analyze_cyborg_haraway',
    prompt: `Track boundary transgressions and situated perspectives (Haraway).

For each scene:
- Boundary_transgression: human/machine, nature/culture, organic/synthetic, species, physical/virtual, none
- Partial_perspective: acknowledged or disavowed
- Note kin_making and control_infrastructure (platforms, protocols, logistics)
- Set technoculture_tone: utopian, critical, ambivalent, apocalyptic

Call analyze_cyborg_haraway with your findings.`,
  },
  barthes: {
    name: 'Barthes: Studium/Punctum',
    fn: 'analyze_punctum_barthes',
    prompt: `Distinguish studium vs punctum (Barthes).

For each shot:
- Provide studium (cultural reading)
- Mark punctum_present and, if so, punctum_detail and wound_intensity (1-10)
- Temporal_punctum if relevant: future_anterior, anachronic, none

Call analyze_punctum_barthes with your findings.`,
  },
  marks: {
    name: 'Marks: Haptic Visuality',
    fn: 'analyze_haptic_marks',
    prompt: `Measure haptic vs optical vision (Laura Marks).

For each segment:
- Scopic_mode: optical, haptic, aural_haptic, olfactory_evoked
- Describe texture_language (grain, blur, close detail, tactility)
- Proximity (1-10), indexicality (high/medium/low), synaesthesia flag

Call analyze_haptic_marks with your findings.`,
  },
  chion: {
    name: 'Chion: Audio-Vision',
    fn: 'analyze_audiovision_chion',
    prompt: `Classify audio-image relations (Chion). If the input lacks audio, skip segments.

For each moment:
- Sound_relation: empathetic, anempathetic, counterpoint, acousmatic, acousmetre_present, synchresis_peak
- Flag voice_of_god and audio_leads_image where applicable
- Describe perceived_causality and rhetorical force of sound

Call analyze_audiovision_chion with your findings.`,
  },
  bazin: {
    name: 'Bazin: Realism (Visual)',
    fn: 'analyze_realism_bazin',
    prompt: `Assess Bazinian realism with no reliance on audio.

For each shot/sequence:
- Report take_length_sec and staging_mode: plan_sequence, deep_focus, tableau, montage_like
- Depth_focus: high, medium, low; mark ambiguity if action remains interpretively open
- Indexical_trust: high, medium, low; add description

Call analyze_realism_bazin with your findings.`,
  },
  eisenstein: {
    name: 'Eisenstein: Montage (Visual)',
    fn: 'analyze_montage_eisenstein',
    prompt: `Classify montage purely from visual cutting (no audio assumed).

For each cluster:
- Montage_type: metric, rhythmic, tonal, overtonal, intellectual
- Rate cut_intensity (1-10) and collision_intensity (1-10)
- Provide ideogram and a brief description

Call analyze_montage_eisenstein with your findings.`,
  },
  greenberg: {
    name: 'Greenberg: Flatness (Visual)',
    fn: 'analyze_flatness_greenberg',
    prompt: `Evaluate modernist flatness and medium specificity (visual only).

For each frame/shot:
- Flatness_index (1-10), illusionism: recessional, shallow, flat
- Surface_emphasis: texture, pattern, color_field, grid, gesture, minimal
- Mark medium_reflexivity and add description

Call analyze_flatness_greenberg with your findings.`,
  },
  ngai: {
    name: 'Ngai: Categories (Visual)',
    fn: 'analyze_categories_ngai',
    prompt: `Apply Ngai’s categories without audio assumptions.

For each moment:
- Category: cute, zany, interesting, gimmicky
- Intensity (1-10) and concise rationale
- Optionally note affect_register

Call analyze_categories_ngai with your findings.`,
  },
  virilio: {
    name: 'Virilio: Dromology (Visual)',
    fn: 'analyze_dromology_virilio',
    prompt: `Map regimes of speed/vision with no audio reliance (Virilio).

For each sequence:
- Speed_regime: slow, moderate, fast, ultrafast, instantaneous
- Motion_blur: none, subtle, pronounced, strobing; telepresence flag
- Perspective_warp: none, wide_angle_distortion, compression, drone_godview, glitch

Call analyze_dromology_virilio with your findings.`,
  },
};

const CHART_TYPES = {
  excitement: 'for each scene, estimate the level of excitement on a scale of 1 to 10',
  importance: 'for each scene, estimate the level of overall importance to the video on a scale of 1 to 10',
  people: 'for each scene, count the number of people visible',
};

const FUNCTIONS = [
  {
    name: 'set_timecodes',
    description: 'Set the timecodes for the video with associated text',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              text: { type: Type.STRING },
            },
            required: ['time', 'text'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'set_timecodes_with_objects',
    description: 'Set the timecodes for the video with associated text and object list',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              text: { type: Type.STRING },
              objects: { type: Type.ARRAY, items: { type: Type.STRING } },
            },
            required: ['time', 'text', 'objects'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'set_timecodes_with_numeric_values',
    description: 'Set the timecodes for the video with associated numeric values',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              value: { type: Type.NUMBER },
            },
            required: ['time', 'value'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_affect',
    description: 'Map affective intensities across the video using Massumi affect theory',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              intensity: { type: Type.NUMBER },      // 1-10 raw affective charge
              atmosphere: { type: Type.STRING },     // qualitative description
              vector: { type: Type.STRING },         // direction of movement
              captures: { type: Type.BOOLEAN },      // does it capture/qualify the affect?
            },
            required: ['time', 'intensity', 'atmosphere', 'vector', 'captures'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_camera',
    description: 'Analyze camera behavior on spectrum from Tarkovsky stillness to Safdie/DG chaos',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              stability: { type: Type.STRING },        // tripod, gimbal, steadicam, handheld_*, drone, uncertain
              frenetic: { type: Type.NUMBER },         // 1-10: Tarkovsky → Safdie/DG
              intentional_motion: { type: Type.STRING }, // static, pan, tilt, track, push, pull, crane, whip, searching, reactive
              proximity: { type: Type.NUMBER },        // 1-10: distant → claustrophobic
              restlessness: { type: Type.BOOLEAN },    // camera wants to move even when "still"
              operator_presence: { type: Type.STRING }, // evidence of human behind camera
              description: { type: Type.STRING },
            },
            required: ['time', 'stability', 'frenetic', 'intentional_motion', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_rhythm',
    description: 'Map territorialization dynamics and rhythmic flows using Deleuze-Guattari framework',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              tempo: { type: Type.NUMBER },            // 1-10 speed of deterritorialization
              movement: { type: Type.STRING },         // territorializing, deterritorializing, reterritorializing, line_of_flight
              refrain: { type: Type.STRING },          // what rhythmic motif anchors/releases?
              description: { type: Type.STRING },
            },
            required: ['time', 'tempo', 'movement', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_aura_benjamin',
    description: 'Track aura, shock, and modes of attention under mechanical reproduction (Benjamin)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              mode: { type: Type.STRING },
              aura_index: { type: Type.NUMBER },
              attention_form: { type: Type.STRING },
              politicization: { type: Type.STRING },
              description: { type: Type.STRING },
            },
            required: ['time', 'mode', 'aura_index', 'attention_form', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_visibility_power_foucault',
    description: 'Map regimes of visibility and subject formation under power (Foucault)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              diagram: { type: Type.STRING },
              visibility: { type: Type.STRING },
              apparatus: { type: Type.STRING },
              subjectivation: { type: Type.STRING },
              resistance: { type: Type.BOOLEAN },
              description: { type: Type.STRING },
            },
            required: ['time', 'diagram', 'visibility', 'apparatus', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_distribution_ranciere',
    description: 'Track partitions of the sensible and moments of dissensus (Rancière)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              partition: { type: Type.STRING },
              policing_act: { type: Type.STRING },
              dissensus: { type: Type.BOOLEAN },
              subject_of_politics: { type: Type.STRING },
              reconfiguration: { type: Type.STRING },
            },
            required: ['time', 'partition', 'dissensus'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_camp_sontag',
    description: 'Assess camp sensibility: artifice, stylization, and failed seriousness (Sontag)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              camp_mode: { type: Type.STRING },
              stylization: { type: Type.NUMBER },
              seriousness: { type: Type.NUMBER },
              irony_temperature: { type: Type.NUMBER },
              notes: { type: Type.STRING },
            },
            required: ['time', 'camp_mode', 'stylization', 'seriousness'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_cyborg_haraway',
    description: 'Track boundary transgressions and situated perspectives (Haraway)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              boundary_transgression: { type: Type.STRING },
              partial_perspective: { type: Type.STRING },
              kin_making: { type: Type.BOOLEAN },
              control_infrastructure: { type: Type.STRING },
              technoculture_tone: { type: Type.STRING },
              description: { type: Type.STRING },
            },
            required: ['time', 'boundary_transgression', 'partial_perspective', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_punctum_barthes',
    description: 'Distinguish studium (cultural field) from punctum (wounding detail) (Barthes)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              studium: { type: Type.STRING },
              punctum_present: { type: Type.BOOLEAN },
              punctum_detail: { type: Type.STRING },
              wound_intensity: { type: Type.NUMBER },
              temporal_punctum: { type: Type.STRING },
            },
            required: ['time', 'studium', 'punctum_present'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_haptic_marks',
    description: 'Measure haptic vs optical vision and texture-driven sense (Laura Marks)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              scopic_mode: { type: Type.STRING },
              texture_language: { type: Type.STRING },
              proximity: { type: Type.NUMBER },
              indexicality: { type: Type.STRING },
              synaesthesia: { type: Type.BOOLEAN },
              description: { type: Type.STRING },
            },
            required: ['time', 'scopic_mode', 'texture_language', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_audiovision_chion',
    description: 'Classify audio-image relations: synchresis, acousmêtre, counterpoint (Chion)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              sound_relation: { type: Type.STRING },
              voice_of_god: { type: Type.BOOLEAN },
              audio_leads_image: { type: Type.BOOLEAN },
              perceived_causality: { type: Type.STRING },
              description: { type: Type.STRING },
            },
            required: ['time', 'sound_relation', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  // Visual-only, no audio dependency
  {
    name: 'analyze_realism_bazin',
    description: 'Assess Bazinian realism: long take, depth, ambiguity (no audio dependency)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              take_length_sec: { type: Type.NUMBER },
              depth_focus: { type: Type.STRING },
              staging_mode: { type: Type.STRING },
              ambiguity: { type: Type.BOOLEAN },
              indexical_trust: { type: Type.STRING },
              description: { type: Type.STRING },
            },
            required: ['time', 'staging_mode', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_montage_eisenstein',
    description: 'Classify montage type and collision intensity (no audio dependency)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              montage_type: { type: Type.STRING },
              cut_intensity: { type: Type.NUMBER },
              collision_intensity: { type: Type.NUMBER },
              ideogram: { type: Type.STRING },
              description: { type: Type.STRING },
            },
            required: ['time', 'montage_type', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_flatness_greenberg',
    description: 'Evaluate modernist flatness and medium specificity (no audio dependency)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              flatness_index: { type: Type.NUMBER },
              surface_emphasis: { type: Type.STRING },
              illusionism: { type: Type.STRING },
              medium_reflexivity: { type: Type.BOOLEAN },
              description: { type: Type.STRING },
            },
            required: ['time', 'flatness_index', 'illusionism', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_categories_ngai',
    description: 'Apply Ngai’s aesthetic categories (cute, zany, interesting, gimmicky) visually',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              category: { type: Type.STRING },
              intensity: { type: Type.NUMBER },
              rationale: { type: Type.STRING },
              affect_register: { type: Type.STRING },
            },
            required: ['time', 'category', 'intensity', 'rationale'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
  {
    name: 'analyze_dromology_virilio',
    description: 'Map regimes of speed and vision (dromology), no audio dependency',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: { type: Type.STRING, description: 'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging' },
        timecodes: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              time: { type: Type.STRING },
              speed_regime: { type: Type.STRING },
              motion_blur: { type: Type.STRING },
              acceleration_event: { type: Type.BOOLEAN },
              telepresence: { type: Type.BOOLEAN },
              perspective_warp: { type: Type.STRING },
              description: { type: Type.STRING },
            },
            required: ['time', 'speed_regime', 'description'],
          },
        },
      },
      required: ['video_description', 'timecodes'],
    },
  },
];

function printHelp() {
  console.log(`
Video Analyzer CLI - Semantic video analysis with Gemini 2.5 Flash

Usage: npx ts-node cli.ts <video-file> [options]
       npx ts-node cli.ts --folder <path> [options]

Options:
  --captions      Generate A/V captions for each scene
  --paragraph     Generate a 3-5 sentence summary
  --key-moments   Extract key moments as bullet points
  --table         5 key shots with descriptions and objects
  --haiku         Generate a haiku about the video
  --affect        Massumi affect theory analysis (intensity, atmosphere, vector)
  --camera        Camera kinetics: Tarkovsky (1) to Safdie/DG (10) frenetic scale
  --rhythm        Deleuzian rhythm/tempo analysis (territorialization dynamics)
  --benjamin      Benjamin: aura, shock, attention, politicization
  --foucault      Foucault: visibility regimes, apparatus, subjectivation
  --ranciere      Rancière: distribution of the sensible, dissensus
  --sontag        Sontag: camp modes, stylization, failed seriousness
  --haraway       Haraway: cyborg/situated knowledge, boundaries, kin-making
  --barthes       Barthes: studium/punctum, wounding detail
  --marks         Laura Marks: haptic vs optical visuality
  --chion         Chion: audio-vision (skips if no audio)
  --bazin         Bazin: realism (visual-only; long take, depth, ambiguity)
  --eisenstein    Eisenstein: montage types (visual-only)
  --greenberg     Greenberg: flatness and medium specificity (visual-only)
  --ngai          Ngai: cute, zany, interesting, gimmicky (visual-only)
  --virilio       Virilio: dromology, speed and vision (visual-only)
  --chart <type>  Generate numeric chart data
                  Types: excitement, importance, people
  --custom "..."  Custom analysis prompt
  --deep          Enable technical pre-analysis (FFmpeg scene detection)
                  Injects frame-level chaos metrics into the prompt
  --json          Output raw JSON (default: formatted)
  --output <file> Save results to file (single file mode only)
  -h, --help      Show this help

Batch Processing:
  --folder <path> Process all videos in a directory
  --recursive     Include subdirectories when using --folder
  --exclude <str> Skip folders containing this string (can use multiple)
  --parallel <n>  Process n videos concurrently (default: 1, max: 5)
                  Output: {video}_analysis.json per file

Examples:
  npx ts-node cli.ts video.mp4 --captions
  npx ts-node cli.ts video.mp4 --chart excitement
  npx ts-node cli.ts video.mp4 --custom "find all moments with laughter"
  npx ts-node cli.ts video.mp4 --deep --custom "analyze camera work"

  # Batch processing
  npx ts-node cli.ts --folder /Volumes/drive/videos --captions
  npx ts-node cli.ts --folder ./clips --recursive --key-moments --deep
`);
}

async function uploadVideo(filePath: string) {
  const absolutePath = path.resolve(filePath);
  if (!fs.existsSync(absolutePath)) {
    throw new Error(`File not found: ${absolutePath}`);
  }

  const fileBuffer = fs.readFileSync(absolutePath);
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes: Record<string, string> = {
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.mov': 'video/quicktime',
    '.avi': 'video/x-msvideo',
    '.mpg': 'video/mpeg',
    '.mpeg': 'video/mpeg',
    '.mkv': 'video/x-matroska',
  };
  const mimeType = mimeTypes[ext] || 'video/mp4';

  console.error('Uploading video...');
  const blob = new Blob([fileBuffer], { type: mimeType });
  const uploadedFile = await client.files.upload({
    file: blob,
    config: { displayName: path.basename(filePath) },
  });

  console.error('Processing...');
  let file = await client.files.get({ name: uploadedFile.name });
  while (file.state === 'PROCESSING') {
    await new Promise(r => setTimeout(r, 2000));
    file = await client.files.get({ name: uploadedFile.name });
    console.error(`  Status: ${file.state}`);
  }

  if (file.state === 'FAILED') {
    throw new Error('Video processing failed');
  }

  console.error('Ready!');
  return file;
}

async function analyze(file: any, prompt: string, fnName: string) {
  const functionDeclarations = FUNCTIONS.filter(f => f.name === fnName);

  const response = await client.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: [
      {
        role: 'user',
        parts: [
          { text: prompt },
          { fileData: { mimeType: file.mimeType, fileUri: file.uri } },
        ],
      },
    ],
    config: {
      systemInstruction: 'When given a video and a query, call the relevant function only once with the appropriate timecodes and text for the video',
      temperature: 0.5,
      tools: [{ functionDeclarations }],
    },
  });

  const candidate = response.candidates?.[0];
  const parts = candidate?.content?.parts || [];

  // Search all parts for a functionCall (Gemini sometimes returns text + functionCall)
  for (const part of parts) {
    if (part && 'functionCall' in part) {
      return part.functionCall.args;
    }
  }

  return { error: 'No structured response', raw: candidate?.content };
}

function formatOutput(data: any, mode: string, jsonOutput: boolean) {
  if (jsonOutput) {
    return JSON.stringify(data, null, 2);
  }

  if (!data.timecodes) {
    return JSON.stringify(data, null, 2);
  }

  let output = `\n${mode}\n${'='.repeat(mode.length)}\n\n`;

  // Show video description first if present
  if (data.video_description) {
    output += `DESCRIPTION: ${data.video_description}\n\n---\n\n`;
  }

  for (const item of data.timecodes) {
    const time = item.time || '??:??';
    if ('frenetic' in item && 'stability' in item) {
      // Camera analysis format
      const restless = item.restlessness ? ' [RESTLESS]' : '';
      output += `[${time}] ${item.stability} | frenetic: ${item.frenetic}/10 | proximity: ${item.proximity || '?'}/10${restless}\n`;
      output += `        motion: ${item.intentional_motion}\n`;
      output += `        ${item.description}\n`;
      if (item.operator_presence) {
        output += `        operator: ${item.operator_presence}\n`;
      }
      output += '\n';
    } else if ('intensity' in item) {
      // Affect analysis format
      const captured = item.captures ? 'CAPTURED' : 'escapes';
      output += `[${time}] intensity: ${item.intensity}/10 | ${captured}\n`;
      output += `        atmosphere: ${item.atmosphere}\n`;
      output += `        vector: ${item.vector}\n\n`;
    } else if ('value' in item) {
      output += `[${time}] ${item.value}\n`;
    } else if ('objects' in item) {
      output += `[${time}] ${item.text}\n        Objects: ${item.objects.join(', ')}\n`;
    } else {
      output += `[${time}] ${item.text}\n`;
    }
  }

  return output;
}

// Parse mode from args (extracted for reuse)
function parseMode(args: string[]): { mode: string; prompt: string; fnName: string } | null {
  if (args.includes('--captions')) {
    return { mode: 'A/V Captions', prompt: MODES.captions.prompt, fnName: MODES.captions.fn };
  } else if (args.includes('--paragraph')) {
    return { mode: 'Paragraph', prompt: MODES.paragraph.prompt, fnName: MODES.paragraph.fn };
  } else if (args.includes('--key-moments')) {
    return { mode: 'Key Moments', prompt: MODES['key-moments'].prompt, fnName: MODES['key-moments'].fn };
  } else if (args.includes('--table')) {
    return { mode: 'Table', prompt: MODES.table.prompt, fnName: MODES.table.fn };
  } else if (args.includes('--haiku')) {
    return { mode: 'Haiku', prompt: MODES.haiku.prompt, fnName: MODES.haiku.fn };
  } else if (args.includes('--affect')) {
    return { mode: 'Affect Analysis (Massumi)', prompt: MODES.affect.prompt, fnName: MODES.affect.fn };
  } else if (args.includes('--camera')) {
    return { mode: 'Camera Analysis (Frenetic/Kinetic)', prompt: MODES.camera.prompt, fnName: MODES.camera.fn };
  } else if (args.includes('--rhythm')) {
    return { mode: 'Deleuzian Rhythm/Tempo Analysis', prompt: MODES.rhythm.prompt, fnName: MODES.rhythm.fn };
  } else if (args.includes('--benjamin')) {
    return { mode: MODES.benjamin.name, prompt: MODES.benjamin.prompt, fnName: MODES.benjamin.fn };
  } else if (args.includes('--foucault')) {
    return { mode: MODES.foucault.name, prompt: MODES.foucault.prompt, fnName: MODES.foucault.fn };
  } else if (args.includes('--ranciere')) {
    return { mode: MODES.rancier.name, prompt: MODES.rancier.prompt, fnName: MODES.rancier.fn };
  } else if (args.includes('--sontag')) {
    return { mode: MODES.sontag.name, prompt: MODES.sontag.prompt, fnName: MODES.sontag.fn };
  } else if (args.includes('--haraway')) {
    return { mode: MODES.haraway.name, prompt: MODES.haraway.prompt, fnName: MODES.haraway.fn };
  } else if (args.includes('--barthes')) {
    return { mode: MODES.barthes.name, prompt: MODES.barthes.prompt, fnName: MODES.barthes.fn };
  } else if (args.includes('--marks')) {
    return { mode: MODES.marks.name, prompt: MODES.marks.prompt, fnName: MODES.marks.fn };
  } else if (args.includes('--chion')) {
    return { mode: MODES.chion.name, prompt: MODES.chion.prompt, fnName: MODES.chion.fn };
  } else if (args.includes('--bazin')) {
    return { mode: MODES.bazin.name, prompt: MODES.bazin.prompt, fnName: MODES.bazin.fn };
  } else if (args.includes('--eisenstein')) {
    return { mode: MODES.eisenstein.name, prompt: MODES.eisenstein.prompt, fnName: MODES.eisenstein.fn };
  } else if (args.includes('--greenberg')) {
    return { mode: MODES.greenberg.name, prompt: MODES.greenberg.prompt, fnName: MODES.greenberg.fn };
  } else if (args.includes('--ngai')) {
    return { mode: MODES.ngai.name, prompt: MODES.ngai.prompt, fnName: MODES.ngai.fn };
  } else if (args.includes('--virilio')) {
    return { mode: MODES.virilio.name, prompt: MODES.virilio.prompt, fnName: MODES.virilio.fn };
  } else if (args.includes('--chart')) {
    const chartIndex = args.indexOf('--chart');
    const chartType = args[chartIndex + 1] as keyof typeof CHART_TYPES;
    if (!chartType || !CHART_TYPES[chartType]) {
      return null;
    }
    return {
      mode: `Chart (${chartType})`,
      prompt: `Generate chart data for this video based on the following instructions: ${CHART_TYPES[chartType]}. Call set_timecodes_with_numeric_values once with the list of data values and timecodes.`,
      fnName: 'set_timecodes_with_numeric_values',
    };
  } else if (args.includes('--custom')) {
    const customIndex = args.indexOf('--custom');
    const customPrompt = args[customIndex + 1];
    if (!customPrompt) {
      return null;
    }
    return {
      mode: 'Custom',
      prompt: `Call set_timecodes once using the following instructions: ${customPrompt}`,
      fnName: 'set_timecodes',
    };
  }
  return null;
}

// Process a single video file
async function processSingleVideo(
  videoFile: string,
  mode: string,
  prompt: string,
  fnName: string,
  deepMode: boolean,
  jsonOutput: boolean
): Promise<{ result: any; mode: string }> {
  let technicalContext = '';
  let modeLabel = mode;

  if (deepMode) {
    const metrics = await getTechnicalMetrics(videoFile);

    technicalContext = `
TECHNICAL PRE-ANALYSIS (FFmpeg):
- Duration: ${metrics.duration.toFixed(1)} seconds
- Framerate: ${metrics.framerate.toFixed(1)} fps
- Scene changes detected: ${metrics.sceneChanges}
- Change density: ${metrics.changeDensity.toFixed(2)} changes/second
- Average frame difference: ${metrics.avgSceneScore.toFixed(3)}
- Max frame difference: ${metrics.maxSceneScore.toFixed(3)}
- Technical chaos index: ${metrics.chaosIndex.toFixed(1)}/10

IMPORTANT: The technical analysis shows ${metrics.chaosIndex >= 5 ? 'significant' : 'low'} frame-to-frame instability.
${metrics.chaosIndex >= 5 && metrics.changeDensity > 0.5
  ? 'High change density suggests rapid movement or cuts that may appear smoother than actual chaos. Account for masked instability.'
  : metrics.chaosIndex < 4
    ? 'Low technical chaos suggests genuinely stable footage.'
    : 'Moderate instability detected - look for subtle signs of handheld operation or scene dynamism.'}

Use this technical data to inform your perceptual analysis. If the technical chaos index is high but the video appears calm, note this as "masked chaos" - the smoothness may be deceiving.

---

`;
    modeLabel = `${mode} (deep)`;
  }

  const file = await uploadVideo(videoFile);
  console.error(`Analyzing: ${modeLabel}...`);

  const fullPrompt = technicalContext + prompt;
  const result = await analyze(file, fullPrompt, fnName);

  return { result, mode: modeLabel };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('-h') || args.includes('--help') || args.length === 0) {
    printHelp();
    process.exit(0);
  }

  const jsonOutput = args.includes('--json');
  const deepMode = args.includes('--deep');
  const recursive = args.includes('--recursive');
  const folderIndex = args.indexOf('--folder');
  const folderPath = folderIndex >= 0 ? args[folderIndex + 1] : null;
  const outputIndex = args.indexOf('--output');
  const outputFile = outputIndex >= 0 ? args[outputIndex + 1] : null;

  // Parse --exclude patterns (can have multiple)
  const excludePatterns: string[] = [];
  let idx = 0;
  while ((idx = args.indexOf('--exclude', idx)) !== -1) {
    if (args[idx + 1] && !args[idx + 1].startsWith('-')) {
      excludePatterns.push(args[idx + 1]);
    }
    idx++;
  }

  // Parse --parallel count
  const parallelIndex = args.indexOf('--parallel');
  const parallelCount = parallelIndex >= 0
    ? Math.min(Math.max(parseInt(args[parallelIndex + 1]) || 1, 1), 5)
    : 1;

  // Parse mode
  const modeConfig = parseMode(args);
  if (!modeConfig) {
    if (args.includes('--chart')) {
      console.error('Error: --chart requires type: excitement, importance, or people');
    } else if (args.includes('--custom')) {
      console.error('Error: --custom requires a prompt string');
    } else {
      console.error('Error: No analysis mode specified. Use --help to see options.');
    }
    process.exit(1);
  }

  const { mode, prompt, fnName } = modeConfig;

  // Batch folder mode
  if (folderPath) {
    if (!fs.existsSync(folderPath)) {
      console.error(`Error: Folder not found: ${folderPath}`);
      process.exit(1);
    }

    const videoFiles = findVideoFiles(folderPath, recursive, excludePatterns);
    if (videoFiles.length === 0) {
      console.error(`No video files found in: ${folderPath}`);
      process.exit(1);
    }

    const excludeInfo = excludePatterns.length > 0 ? ` (excluding: ${excludePatterns.join(', ')})` : '';
    const parallelInfo = parallelCount > 1 ? ` [${parallelCount} parallel]` : '';
    console.error(`\nFound ${videoFiles.length} video(s) in ${folderPath}${recursive ? ' (recursive)' : ''}${excludeInfo}${parallelInfo}`);
    console.error(`Mode: ${mode}${deepMode ? ' (deep)' : ''}\n`);

    const errors: { file: string; error: string }[] = [];
    let successCount = 0;
    let completedCount = 0;

    // Process a single video and track results
    async function processOne(videoFile: string, index: number): Promise<void> {
      const fileName = path.basename(videoFile);
      const progress = `[${index + 1}/${videoFiles.length}]`;

      console.error(`${progress} Starting: ${fileName}`);

      try {
        const { result, mode: modeLabel } = await processSingleVideo(
          videoFile,
          mode,
          prompt,
          fnName,
          deepMode,
          jsonOutput
        );

        const output = formatOutput(result, modeLabel, true); // Always JSON for batch
        const ext = path.extname(videoFile);
        const outputPath = videoFile.replace(ext, '_analysis.json');

        fs.writeFileSync(outputPath, output);
        completedCount++;
        console.error(`${progress} ✓ Saved: ${path.basename(outputPath)} (${completedCount}/${videoFiles.length} done)`);
        successCount++;
      } catch (err: any) {
        completedCount++;
        console.error(`${progress} ✗ FAILED: ${fileName} - ${err.message}`);
        errors.push({ file: fileName, error: err.message });
      }
    }

    // Process in parallel batches
    if (parallelCount > 1) {
      // Parallel mode: process N at a time
      for (let i = 0; i < videoFiles.length; i += parallelCount) {
        const batch = videoFiles.slice(i, i + parallelCount);
        const promises = batch.map((file, batchIdx) => processOne(file, i + batchIdx));
        await Promise.all(promises);
      }
    } else {
      // Sequential mode (original behavior)
      for (let i = 0; i < videoFiles.length; i++) {
        await processOne(videoFiles[i], i);
      }
    }

    // Summary
    console.error('\n' + '─'.repeat(50));
    console.error(`Completed: ${successCount}/${videoFiles.length} videos`);
    if (errors.length > 0) {
      console.error(`\nFailed (${errors.length}):`);
      for (const { file, error } of errors) {
        console.error(`  • ${file}: ${error}`);
      }
    }
    process.exit(errors.length > 0 ? 1 : 0);
  }

  // Single file mode
  const videoFile = args.find(a => !a.startsWith('-'));
  if (!videoFile) {
    console.error('Error: No video file specified');
    process.exit(1);
  }

  try {
    const { result, mode: modeLabel } = await processSingleVideo(
      videoFile,
      mode,
      prompt,
      fnName,
      deepMode,
      jsonOutput
    );

    const output = formatOutput(result, modeLabel, jsonOutput);

    if (outputFile) {
      fs.writeFileSync(outputFile, output);
      console.error(`Results saved to: ${outputFile}`);
    } else {
      console.log(output);
    }
  } catch (err: any) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

main();
