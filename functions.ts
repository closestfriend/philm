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
import {FunctionDeclaration, Type} from '@google/genai';

const functions: FunctionDeclaration[] = [
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
              time: {
                type: Type.STRING,
              },
              text: {
                type: Type.STRING,
              },
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
    description:
      'Set the timecodes for the video with associated text and object list',
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
              time: {
                type: Type.STRING,
              },
              text: {
                type: Type.STRING,
              },
              objects: {
                type: Type.ARRAY,
                items: {
                  type: Type.STRING,
                },
              },
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
    description:
      'Set the timecodes for the video with associated numeric values',
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
              time: {
                type: Type.STRING,
              },
              value: {
                type: Type.NUMBER,
              },
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
              time: {
                type: Type.STRING,
              },
              intensity: {
                type: Type.NUMBER,
              },
              atmosphere: {
                type: Type.STRING,
              },
              vector: {
                type: Type.STRING,
              },
              captures: {
                type: Type.BOOLEAN,
              },
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
              time: {
                type: Type.STRING,
              },
              stability: {
                type: Type.STRING,
              },
              frenetic: {
                type: Type.NUMBER,
              },
              intentional_motion: {
                type: Type.STRING,
              },
              proximity: {
                type: Type.NUMBER,
              },
              restlessness: {
                type: Type.BOOLEAN,
              },
              operator_presence: {
                type: Type.STRING,
              },
              description: {
                type: Type.STRING,
              },
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
              time: {
                type: Type.STRING,
              },
              tempo: {
                type: Type.NUMBER,
              },
              movement: {
                type: Type.STRING,
              },
              refrain: {
                type: Type.STRING,
              },
              description: {
                type: Type.STRING,
              },
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
    description:
      'Track aura, shock, and modes of attention under mechanical reproduction (Benjamin)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Map regimes of visibility and subject formation under power (Foucault)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Track partitions of the sensible and moments of dissensus (Rancière)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Assess camp sensibility: artifice, stylization, and failed seriousness (Sontag)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Track boundary transgressions and situated perspectives (Haraway)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Distinguish studium (cultural field) from punctum (wounding detail) (Barthes)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Measure haptic vs optical vision and texture-driven sense (Laura Marks)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
    description:
      'Classify audio-image relations: synchresis, acousmêtre, counterpoint (Chion)',
    parameters: {
      type: Type.OBJECT,
      properties: {
        video_description: {
          type: Type.STRING,
          description:
            'A concise, practical description of the video content (1-2 sentences) suitable for titling and cataloging',
        },
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
  // Purely visual (no-audio) aesthetic schemas
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
              depth_focus: { type: Type.STRING }, // high, medium, low
              staging_mode: { type: Type.STRING }, // plan_sequence, deep_focus, tableau, montage_like
              ambiguity: { type: Type.BOOLEAN },
              indexical_trust: { type: Type.STRING }, // high, medium, low
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
              montage_type: { type: Type.STRING }, // metric, rhythmic, tonal, overtonal, intellectual
              cut_intensity: { type: Type.NUMBER }, // 1-10
              collision_intensity: { type: Type.NUMBER }, // 1-10
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
              flatness_index: { type: Type.NUMBER }, // 1-10
              surface_emphasis: { type: Type.STRING }, // texture, pattern, color_field, grid, gesture, minimal
              illusionism: { type: Type.STRING }, // recessional, shallow, flat
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
              category: { type: Type.STRING }, // cute, zany, interesting, gimmicky
              intensity: { type: Type.NUMBER }, // 1-10
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
              speed_regime: { type: Type.STRING }, // slow, moderate, fast, ultrafast, instantaneous
              motion_blur: { type: Type.STRING }, // none, subtle, pronounced, strobing
              acceleration_event: { type: Type.BOOLEAN },
              telepresence: { type: Type.BOOLEAN },
              perspective_warp: { type: Type.STRING }, // none, wide_angle_distortion, compression, drone_godview, glitch
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

export default (fnMap) =>
  functions.map((fn) => ({
    ...fn,
    callback: fnMap[fn.name],
  }));
