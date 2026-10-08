# Music-understanding audio LLMs — landscape survey

> **Provenance:** produced by Codex (OpenAI) using paid research-query credits, saved verbatim
> 2026-08-09 at Hunter's request. **Field state as of 2026-07-25.** Not independently verified by
> me — treat benchmark claims, version numbers, and API shapes as needing a check before you build
> on them. Successor to [`2026-05-30-essentia-mir-prototype.md`](./2026-05-30-essentia-mir-prototype.md),
> which is the local prototype (`scripts/essentia_probe.py`) this survey contextualises.

---

State of the field as of July 25, 2026: there are finally several systems worth taking seriously, but only a few are genuinely music-oriented. The most important new release is MOSS-Music, which currently reports the strongest results among downloadable music-language models and has an unofficial but unusually practical MLX port for Apple Silicon. Music Flamingo remains the most established specialized alternative. Gemini 3.6 Flash is the easiest hosted system for full-song experiments.

The catch is substantial: models are much better at generating plausible musical commentary than at reliably perceiving exact pitch relationships, meter, chord function, modulation, or rhythmic transformations. MUSE found that Qwen2.5-Omni and Audio Flamingo 3 were at or near chance on several basic relational tasks, while even Gemini's confident chain-of-thought often described the underlying musical evidence incorrectly. MuChoMusic also found strong language-only shortcuts.

## The practical shortlist

| Rank | System | Best use | Full songs | Tonight access | Mac viability |
|---|---|---|---|---|---|
| 1 | MOSS-Music-8B-Instruct | Broad music QA, structure, instrumentation, lyrics, key/tempo/chords | Demonstrated; hard limit undocumented | Official HF Space | Excellent via community MLX |
| 2 | Gemini 3.6 Flash | Fast full-song analysis, timestamps, comparison, long context | Up to 9.5 hours | AI Studio or API | Hosted |
| 3 | Music Flamingo 2601 | Specialized music captioning and long-track QA | Up to 20 minutes | HF Space or weights | Space recommended |
| 4 | Audio Flamingo Next | Timestamped long-audio QA and dense description | Up to 30 minutes | HF Space or weights | Space recommended |
| 5 | Qwen3-Omni | Strong general audio baseline and tagging | Yes, subject to deployment context | Qwen Chat/demo or weights | Too large locally |
| 6 | MOSS-Music-8B-Thinking | Expansive musical interpretation and reasoning | Demonstrated | Weights, demo, MLX | Good via community MLX |
| 7 | TuneJury | Pairwise aesthetic preference for generated instrumentals | Not really | HF Space | Hosted/lightweight |
| 8 | MuQ-Eval | Technical artifacts and generated-music quality | Ten-second inputs | Local weights/code | Easy enough locally |

## 1. Best models to try immediately

### 1. MOSS-Music-8B-Instruct

My first choice for your experiment tonight.

MOSS-Music was released May 1, 2026 by OpenMOSS, MOSI.AI, and the Shanghai Innovation Institute. It is explicitly trained for:

- Musical captioning and tagging
- Lyrics transcription with timestamps
- Key, tempo, beat, downbeat, and chord reasoning
- Song-structure segmentation
- Instrument and voice recognition
- Full-track question answering
- Emotional and production-style description

It uses a dedicated MOSS audio encoder operating at 12.5 Hz, a modality adapter, and Qwen3-8B, for roughly 9.1 billion parameters. Time markers are inserted into the audio representation so it can associate events with positions in a song.

**Evidence**

In OpenMOSS's own evaluation, the Instruct checkpoint averaged 80.38% across eight music-QA benchmarks, ahead of Gemini 3.1 Pro, Music Flamingo, Audio Flamingo Next, MiMo-Audio, Step-Audio-R1, and Qwen3-Omni. It scored 89.39% on MuChoMusic and 93.59% on GTZAN. However:

- These are author-run results, not yet broadly replicated.
- The release is extremely new.
- MuChoMusic itself is vulnerable to language shortcuts.
- Chord-transcription benchmark results are still promised rather than published.
- The captioning evaluation was preliminary and used GPT-5.4 as judge rather than human listeners.

The most defensible wording is: MOSS-Music is the current reported open-model leader, but not yet the independently established leader.

**Fastest access**

Use the official OpenMOSS Hugging Face organization page and launch the running MOSS-Music-8B-Instruct Space. It accepts uploaded music and returns textual analysis.

Good opening prompt:

> Analyze this recording using only audible evidence. Map its sections with timestamps; identify instrumentation, approximate tempo, likely key or tonal center, harmonic rhythm, vocal treatment, production style, and emotional trajectory. Separate direct observations from uncertain inference.

**Local Apple Silicon**

A community MLX conversion is the best local Mac option I found:

- 4-bit: roughly 6 GB; intended for 16 GB Macs.
- 6-bit: middle option.
- 8-bit: roughly 10 GB; appropriate for a 24 GB machine.
- Audio encoder remains BF16 while Qwen layers are quantized.

On an M4 Mac with 24 GB unified memory, the converter reports approximately 34 seconds to process a 75-second song and around 23 generated tokens per second. Those are community measurements, not official OpenMOSS benchmarks. The same model through stock PyTorch/MPS reportedly falls back to CPU for several encoder operations and becomes effectively unusable.

The verified download and invocation pattern is:

```bash
pip install "huggingface_hub[hf_xet]"
huggingface-cli download \
  --local-dir MOSS-Music-8B-Thinking-8bit \
  mlx-community/MOSS-Music-8B-Thinking-8bit
```

The checkpoint requires the custom `moss_music_mlx` backend rather than `mlx_lm` or `mlx_vlm`:

```python
from huggingface_hub import snapshot_download
from moss_music_mlx import load_pretrained, generate
from src.processing_moss_music import MossMusicProcessor

path = snapshot_download(
    "mlx-community/MOSS-Music-8B-Thinking-8bit"
)

model = load_pretrained(path)
processor = MossMusicProcessor.from_pretrained(
    path,
    trust_remote_code=True,
    enable_time_marker=True,
)

response = generate(
    model,
    processor,
    "Analyze this track: genre, key, BPM, structure.",
    audio_path="song.mp3",
)

print(response)
```

This is medium-difficulty, because the MLX backend currently lives in a community branch/upstream pull request rather than a polished pip package. The conversion is Apache 2.0 and therefore substantially more permissive than NVIDIA's music models.

**Instruct versus Thinking**

Start with Instruct for objective questions. OpenMOSS's own table shows it outperforming the Thinking version across most QA tasks. Use Thinking for long-form interpretive writing, comparisons, or requests that require synthesis. Extra reasoning does not necessarily produce more accurate listening.

### 2. Gemini 3.6 Flash

The strongest practical hosted option and easiest system for whole-song analysis.

Google's current audio documentation uses `gemini-3.6-flash`, released in July 2026. It accepts WAV, MP3, AIFF, AAC, OGG, and FLAC; supports timestamped questions; and allows up to 9.5 hours of audio in one prompt. Files over 20 MB can be uploaded through the Files API.

**Fastest access**

Upload an obscure or unreleased track in Google AI Studio, then ask timestamp-grounded questions. No local hardware is needed.

Verified API pattern:

```bash
pip install google-genai
export GEMINI_API_KEY="YOUR_KEY"
```

```python
from google import genai

client = genai.Client()

audio = client.files.upload(file="song.mp3")

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input=[
        {
            "type": "text",
            "text": """
Analyze this song chronologically.

Return:
1. Section boundaries with timestamps
2. Instruments entering and exiting
3. Approximate tempo and meter
4. Likely tonal center and harmonic movement
5. Production and vocal-processing observations
6. Emotional trajectory

Separate audible observations from uncertain inference.
"""
        },
        {
            "type": "audio",
            "uri": audio.uri,
            "mime_type": audio.mime_type,
        },
    ],
)

print(interaction.output_text)
```

This exact upload/interaction workflow appears in the current official documentation.

**Why it is not a mastering critic**

Google downsamples audio to 16 Kbps and combines multichannel material into a single channel. That makes Gemini unsuitable for reliable judgments about:

- Stereo width
- Fine spatial placement
- Codec transparency
- Subtle transient degradation
- Mastering differences
- Very small EQ or compression changes
- Phase relationships

It can discuss broad production characteristics, but it is not listening to the original stereo master at mastering resolution.

**Evidence**

The independent MUSE benchmark found Gemini 2.5 Pro dramatically stronger than Audio Flamingo 3 and Qwen2.5-Omni on basic pitch, melody-shape, rhythm, and modulation tasks. It was still substantially behind expert musicians on meter, syncopation, chord-sequence comparison, and other relational skills. Gemini 3.6 Flash has not yet received equivalent independent music testing, so its ranking here reflects access, context length, and the strength of its recent predecessors—not proven 3.6-specific superiority.

### 3. Music Flamingo 2601

The most established dedicated music-language model.

NVIDIA's Music Flamingo is an 8B model comprising:

- AF-Whisper audio encoder
- MLP audio adapter
- Qwen2.5-7B language backbone
- Twenty-minute maximum audio input
- WAV, MP3, and FLAC support

It is designed for music QA, long-context comprehension, musical reasoning, and interactive music-assistant use.

**What it does well**

- Instrumentation and timbre
- Broad genre/style description
- Long-song summaries
- Arrangement development
- Music-specific vocabulary
- Comparisons between passages
- Relatively coherent chronological commentary

**Fastest access**

Use NVIDIA's linked Hugging Face Space. The model card also provides Colab and Kaggle entry points. Local installation begins with:

```bash
pip install --upgrade pip
pip install --upgrade transformers accelerate
```

The basic Transformers loading pattern is:

```python
from transformers import AutoProcessor, AutoModelForSeq2SeqLM

model_id = "nvidia/music-flamingo-2601-hf"

processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForSeq2SeqLM.from_pretrained(
    model_id,
    device_map="auto",
)
```

**Hardware and licensing**

The BF16 checkpoint is approximately 16.5 GB before inference overhead. NVIDIA lists Linux with A100/H100 hardware as supported. A 24 GB CUDA GPU might handle shorter material with careful settings, but 32–48 GB is a more realistic comfortable target for long tracks. That is an estimate based on checkpoint size, not an NVIDIA guarantee.

The license is NVIDIA OneWay Noncommercial. It is suitable for experimentation and research, not a straightforward commercial product foundation.

There are community GGUF conversions, but audio support depends on very recent llama.cpp multimodal implementations. I would not make those your first Mac experiment.

### 4. Audio Flamingo Next

Best open generalist for long, timestamped audio.

Released in April 2026, Audio Flamingo Next is an 8B general audio model covering speech, environmental sound, and music. It supports:

- Up to 30 minutes of audio
- Thirty-second internal windows
- Mono 16 kHz input
- Timestamp-aware Rotary Time Embeddings
- Music captioning
- Lyrics transcription
- Follow-up questions and multi-turn interaction

NVIDIA provides Instruct, Think, and Captioner variants.

Choose:

- **Instruct:** direct questions and formatted answers.
- **Think:** timestamp-grounded reasoning.
- **Captioner:** detailed chronological descriptions.

Verified installation:

```bash
pip install --upgrade pip
pip install --upgrade transformers accelerate
```

The model card provides this music prompt:

> Summarize the track with precision: mention its musical style, BPM, key, arrangement, production choices, and the emotions or story it conveys.

It is a particularly good comparator against MOSS-Music because it uses a more general audio training regime. If both models produce the same timestamp-specific observation on an unreleased recording, that is more interesting than either model producing a polished standalone review.

Like Music Flamingo, AF-Next is noncommercial, BF16, Linux/CUDA-oriented, and roughly 16.5 GB before runtime overhead.

### 5. Qwen3-Omni

Qwen3-Omni is a much broader omni-modal system rather than a music specialist. Its released family includes:

- 30B-A3B Instruct
- 30B-A3B Thinking
- A specialized Captioner
- "Flash" hosted variants

The official results include 52.0–52.1 on its RUL-MuChoMusic evaluation, approximately 93% GTZAN accuracy, and improvements over Qwen2.5-Omni on mood, instrumentation, genre, and tag prediction.

**Verdict**

Useful as a strong generalist control, particularly through hosted access. Not attractive as a local model on your machine:

- The complete checkpoint is around 30B total parameters.
- Official examples include four-GPU deployments.
- Its speech and omni-modal machinery adds substantial weight that is irrelevant to pure music analysis.

Its high GTZAN score demonstrates genre recognition, not necessarily harmonic or compositional understanding.

### 6. MOSS-Music-8B-Thinking

This uses the same architecture and Apache 2.0 licensing as MOSS-Music-Instruct, but is trained to produce explicit musical reasoning. It is the variant currently available in the community MLX conversion.

Its prose will often be richer, but OpenMOSS's own results show lower objective QA performance than Instruct: 74.26 versus 80.38 average. That fits the broader MUSE finding that verbal chain-of-thought can make an audio model sound more convincing without improving—and sometimes while worsening—its perception.

Use it for:

- "Explain the arrangement's emotional logic."
- "Compare these two versions and build an argument."
- "Identify recurring motifs and explain their functions."
- "Discuss why the final chorus feels larger."
- "Separate technical evidence from aesthetic interpretation."

Do not automatically trust it more on exact BPM, pitch, chord, or meter questions.

## 2. Best open-source projects

### Current generation

| Project | Size / architecture | Access and hardware | Assessment |
|---|---|---|---|
| MOSS-Music-8B Instruct/Thinking | ~9.1B; MOSS encoder + Qwen3-8B | Apache 2.0; CUDA reference code; community MLX 4/6/8-bit | Best current specialized open release, but young and lightly replicated. |
| Music Flamingo 2601 | 8B; AF-Whisper + Qwen2.5-7B | HF Transformers; 20 minutes; A100/H100 officially supported | Mature specialist; noncommercial. |
| Audio Flamingo Next | 8B; AF-Whisper + Qwen2.5 family | 30 minutes; Space/Colab/weights | Best open long-context generalist; noncommercial. |
| MOSS-Audio 4B/8B | ~4.6B/~8.6B; dedicated encoder + Qwen3 | Apache 2.0; CUDA repo | Broader precursor to MOSS-Music; useful for sound/music/speech comparisons. |
| MiMo-Audio-7B-Instruct | Listed as 8B; custom 1.2B tokenizer + audio LM | MIT; Linux, Python 3.12, CUDA 12+, FlashAttention | Strong general audio model; music evidence less compelling than MOSS/Music Flamingo. |
| Step-Audio-R1 | Qwen2 audio encoder + Qwen2.5-32B | Apache 2.0; four L40S/H100-class GPUs; custom vLLM | Serious audio-reasoning research, but wholly impractical locally. |
| Qwen3-Omni | 30B-A3B MoE | Multi-GPU or hosted | Strong general baseline; too large for tonight's local experiment. |
| Qwen2.5-Omni 3B/7B | Omni-modal thinker/talker | Official 7B GPTQ/AWQ; CUDA | Usable general baseline, but independent music-perception results are mixed. |

**Qwen2.5-Omni as a smaller baseline**

The 3B and 7B models have documented music results for tempo, MusicCaps, and MMAU-music. Official 7B GPTQ/AWQ checkpoints reduce memory by more than 50%; the published usage remains CUDA-specific. The INT4 model consumed about 11.6 GB for a 15-second video test, rising substantially with longer context. Audio-only use may be cheaper, but the project does not provide equivalent memory tables for music files.

### Older but historically relevant

**Qwen2-Audio** — Still useful as a baseline because it outperformed the original music-specialized models in MuChoMusic's 2024 evaluation. Its advantage probably reflects broad audio training rather than deep music representation. It is no longer a frontier choice.

**SALMONN** — Combines Whisper, BEATs, and Vicuna. It demonstrated audio captioning and music-related instruction following, but installation is comparatively brittle and its architecture is now several generations old.

**MusiLingo** — A MERT-v1-300M encoder connected to Vicuna-7B through a learned projection. It is genuinely music-specific and historically important, but: uses older Vicuna infrastructure; has noncommercial licensing; requires custom code/checkpoints; is outclassed by MOSS-Music and Music Flamingo.

**MU-LLaMA** — Another MERT-to-LLaMA music QA and captioning system. Public code and checkpoints exist, but reproducing the complete stack requires multiple large assets and old dependencies. It is better treated as a research artifact than a tonight-ready tool.

**Audio Flamingo 3** — Important in the lineage and still downloadable, but superseded by Audio Flamingo Next and Music Flamingo. The independent MUSE results are particularly harsh: it operated at or near chance on most relational music tasks despite sounding fluent.

## 3. Best proprietary or API-based systems

### Gemini 3.6 Flash

Best hosted option overall.

Advantages:

- Longest documented audio context
- Direct file upload
- Timestamp prompting
- No GPU setup
- Handles obscure or private recordings
- Easy structured JSON output
- Useful for repeated A/B tests

Disadvantages:

- Proprietary
- No access to embeddings or internal confidence
- Current music evidence mostly inherited from earlier Gemini models
- Mono, highly downsampled audio path
- Not appropriate for critical mix/mastering decisions

### Gemini Pro-class models

Where a current Pro-class audio model is available in AI Studio, test it alongside Flash. MUSE found Gemini 2.5 Pro far stronger than Flash on some relational tasks, including melody shape and modulation, though not universally.

### OpenAI audio-capable systems

OpenAI's current documented developer audio stack remains centered on transcription, speech generation, and realtime conversational audio. There is not a dedicated, stable music-analysis API with published music-specific evaluation comparable to MOSS-Music or Music Flamingo.

Qwen's reported music table includes a "GPT-4o-Audio" result, demonstrating some measurable music capability, but that does not translate into a clearly documented, reproducible music-analysis endpoint. I would not use OpenAI as the primary experimental system for this project until the audio-file workflow and music evidence are clearer.

### Qwen hosted access

Qwen3-Omni through Qwen's hosted interfaces is worth using as a free or inexpensive control. It is especially relevant for genre and tagging, mood/theme identification, general audio description, and caption generation.

It is less compelling for music-theoretic analysis than its genre scores initially suggest.

## 4. Interesting experimental projects

**Step-Audio-R1 and R1.1** — The most interesting work on audio-grounded reasoning rather than merely adding textual chain-of-thought. Step-Audio-R1 attempts to train reasoning traces that remain connected to acoustic representations. Its architecture uses a frozen Qwen2 audio encoder and a Qwen2.5-32B decoder.

The repository is active and has released weights, Docker deployment, custom vLLM code, and newer R1.1/R1.5 work. But the reference deployment uses four substantial NVIDIA GPUs, making it a research-server model, not a consumer model.

**MiMo-Audio** — Xiaomi's general-purpose open audio model was pretrained on a claimed 100-million-plus hours and supports few-shot audio tasks. It is MIT-licensed and comes with evaluation code, a local Gradio app, and complete weights. The downside is a CUDA 12/FlashAttention setup and no convincing case that its general benchmark performance produces deeper musical interpretation.

**MOSS-Audio** — The direct parent of MOSS-Music. Its 4B checkpoint is worth testing as an ablation: ask MOSS-Audio and MOSS-Music the same questions; measure how much music-specific continual pretraining actually changes answers; use unreleased tracks to prevent metadata leakage.

**Eureka-Audio** — A compact approximately 1.7B general audio model released in early 2026. Interesting because a smaller model is easier to deploy and potentially easier to specialize, but it is not primarily a music model.

**U-SAM** — A research architecture using separate speech, general-audio, and music encoders with mixture-of-experts projection. Architecturally sensible: music does not have to compete with speech for one universal representation. Public code exists, but the availability and usability of complete pretrained checkpoints is less clear.

**Unified Audio Schema** — Tencent work connecting a general audio tokenizer/encoder to Qwen2.5-7B. It covers music but remains a general audio project.

**SLAM-LLM music-captioning recipes** — More useful as a construction framework than as a finished model. It contains recipes for attaching audio encoders to LLMs, including music captioning. Expect pinned dependencies and research-grade documentation.

**MusicAgent** — An older but still conceptually relevant agent system that orchestrates specialist music tools instead of pretending one neural network can do every MIR task. That basic architecture is arguably more valid now than it was when the project appeared.

## 5. Useful music encoders and analytical components

The custom-system path is stronger than trying to force one audio LLM to infer everything.

| Component | What it provides | Best role |
|---|---|---|
| MuQ / MuQ-MuLan | Strong music embeddings; audio-text similarity; broad MIR transfer | Main semantic music representation |
| MERT 95M/330M | Frame-level music representations trained directly on music | Timbre, harmony, emotion, tagging, custom heads |
| LAION CLAP Music | Shared text/music embedding space | Prompt-based retrieval, similarity, influence search |
| USAD | Lightweight unified speech/sound/music encoder | Small-device experimentation |
| SongFormer | Full-song structural segmentation | Verse/chorus/bridge boundaries |
| Essentia | Tempo, key, loudness, mood, tags, spectral and rhythmic descriptors | Deterministic technical analysis |
| Basic Pitch | Polyphonic audio-to-MIDI transcription | Note/pitch and melodic evidence |
| Demucs / demucs-mlx | Stem separation | Isolate vocals, drums, bass, accompaniment |
| Music2Emo | Time-varying emotion representation | Emotional-trajectory models |
| MARBLE | Benchmarking suite for music-audio representations | Selecting or comparing encoders |
| MuLan-style encoders | Audio/text correspondence | Semantic tagging and retrieval |
| Music2Vec | Older self-supervised music representation | Lightweight baseline |

### Best encoder choices

**MuQ** — Probably the best current starting encoder for a custom system. It is strong across general MIR tasks, and the MuQ-MuLan variant gives you direct audio-text similarity. It is also the foundation of MuQ-Eval.

Use it for: similarity between sections or songs; genre/mood/style representations; retrieval; training a preference head; detecting repeated or contrasting passages; conditioning an LLM with numerical features.

**MERT** — Still the most established music-specific foundation representation. It appears underneath MusiLingo, MU-LLaMA, TuneJury, emotion-recognition work, and many smaller experiments.

Its limitations are mainly licensing and context architecture: common implementations process relatively short windows, so full songs need segmentation and pooling.

**Essentia** — This should be in any serious evaluation stack. It provides objective estimates that can catch hallucinated claims from an LLM. For example:

- LLM says 145 BPM.
- Essentia and a second tempo tracker say approximately 72.5 BPM.
- The disagreement exposes double-time ambiguity.
- LLM must then explain both interpretations rather than silently inventing certainty.

**SongFormer** — Use for section boundaries and form. General audio LLMs frequently produce plausible but fabricated timestamp maps. A dedicated segmentation system gives the language model evidence rather than asking it to discover the structure unaided.

**Demucs-MLX** — Especially relevant to your M4. Separate the recording into stems, analyze each stem, then provide summaries and measurements to the LLM. This makes instrumentation, vocal technique, drum patterns, and arrangement entries substantially easier to identify.

## 6. Qualitative-judgment systems

There is no credible universal "is this music good?" model. Existing systems predict narrower targets.

**SongEval** — the most substantial dataset explicitly aimed at song aesthetics. It contains full songs rated by professional annotators on dimensions including coherence, memorability, vocal breathing and phrasing, structural clarity, and musicality.

The broader release describes 2,399 songs, more than 140 hours of audio, English and Chinese material, nine genres, and 16 professional raters. The associated Hugging Face dataset currently exposes a smaller packaged subset.

- What it measures: expert ratings under a specific rubric.
- What it does not establish: an objective or culturally universal definition of quality.

**TuneJury** — One of the most immediately testable aesthetic systems. It combines frozen CLAP-Music and MERT embeddings with a very small learned preference head trained on roughly 17,500 human A/B comparisons.

It is designed primarily for generated instrumental music and returns a scalar preference score. A running Hugging Face Space is available.

Useful experiment:

1. Upload two generations from the same prompt.
2. Record TuneJury's ranking.
3. Ask MOSS-Music to compare them without seeing TuneJury's result.
4. Compare both with your own preference.
5. Repeat after altering loudness normalization.

Watch for a likely confound: preference models can learn production polish, brightness, loudness, or familiar genre traits rather than composition quality.

**MuQ-Eval** — uses a frozen MuQ encoder plus lightweight prediction heads. It targets generated-music evaluation dimensions such as musical impression, technical artifacts, and text alignment.

The model card reports strong correlation with human mean-opinion scores, including high system-level rank correlation. However, controlled tests found that it was much more sensitive to signal degradation than to distortions of musical structure. Input is capped at roughly ten seconds.

Translation: it may be a good "does this sound technically damaged or generation-like?" model, but a weak "is this composition coherent?" model.

**MusicEval** — A dataset of thousands of clips from dozens of text-to-music systems, scored by expert raters for overall quality and prompt alignment. It is more appropriate for evaluating generators than finished human music.

**CMI-RewardBench and CMI reward models** — These target compositional music instructions, musicality, and text alignment. They are relevant when evaluating whether a generated piece follows a compositional brief. They are not proven critics of arbitrary songs.

**HEAR** — Experimental hierarchical aesthetic representations combining structure-sensitive models with SongEval-style ratings. Conceptually promising because whole-song aesthetics depend on relationships between sections rather than short pooled embeddings.

**APEX** — Attempts to predict engagement/popularity alongside aesthetic dimensions from a large generated-song corpus.

This is exactly where interpretation must remain disciplined:

- Popularity prediction is not quality prediction.
- Skip-rate prediction is not memorability in an artistic sense.
- Prompt alignment is not musicality.
- Technical artifact detection is not production taste.
- Average listener preference is not expert judgment.
- Expert judgment is not universal judgment.

### Benchmarks and what they actually prove

**MuChoMusic** — 1,187 human-validated multiple-choice questions attached to 644 tracks. The original evaluation found that the best tested model answered fewer than half correctly and that general audio models outperformed the music-specialized models of that generation. Perturbed-audio tests revealed overreliance on language.

Later work showed that text-only systems can also score surprisingly well, making very high newer scores less conclusive than they appear.

**MUSE** — The most revealing benchmark for basic perception and relational reasoning: pitch-shift detection, rhythm matching, out-of-key oddballs, melodic contour, chord quality, key modulation, chord-sequence matching, syncopation, meter.

Gemini 2.5 Pro was strong on several beginner tasks. Qwen2.5-Omni and Audio Flamingo 3 often approached chance. Expert musicians remained far ahead on most advanced tasks. Chain-of-thought frequently reduced performance and often produced persuasive but factually incorrect musical explanations.

**BASS** — Released in 2026, BASS covers musical structure and semantic reasoning using nearly 2,000 songs and roughly 138 hours of music. It reports that contemporary audio LMs remain much better at lyrics-related tasks than at structural segmentation and musicological reasoning.

**HumMusQA** — A smaller human-written benchmark intended to reduce synthetic-question artifacts. It also includes unimodal controls designed to reveal when models answer without meaningfully using the recording.

**CMI-Bench** — Focuses on music instruction following and MIR-derived tasks. Useful for evaluating whether a model understands concrete musical directions, but less directly concerned with open-ended criticism.

**MMAU and AIR-Bench music subsets** — Useful broad controls, but music is only one portion of these general audio suites. Strong aggregate audio results can conceal poor harmonic or rhythmic perception.

## 7. Recommended starting stack

**Single easiest model to try** — MOSS-Music-8B-Instruct official Hugging Face Space. It is specialized, accepts real recordings, and requires no setup. Use an unreleased song so the answer cannot be reconstructed from metadata or web knowledge.

**Strongest open model** — MOSS-Music-8B-Instruct, with the qualification that its leading benchmark results are self-reported and not yet thoroughly replicated. Runner-up: Music Flamingo 2601, which is more established but noncommercial and less convenient on Apple Silicon.

**Strongest hosted model** — Gemini 3.6 Flash, especially for complete songs, multiple recordings, structured outputs, and timestamp questions.

**Best option for full-song analysis**

- Hosted: Gemini 3.6 Flash.
- Open with a documented limit: Audio Flamingo Next, up to 30 minutes.
- Music-specialized: MOSS-Music, which demonstrates full-song coverage but does not document a hard maximum in the public README.
- Music-specialized with explicit limit: Music Flamingo, up to 20 minutes.

**Best option for production or mix analysis** — No single audio LLM. Use Demucs-MLX for stems; Essentia for loudness, spectral balance, dynamics, tempo, and key-related features; MOSS-Music for semantic and arrangement commentary; MuQ-Eval for generation artifacts or broad technical quality; a text LLM to reconcile the evidence.

Do not use Gemini's mono 16 Kbps representation to judge stereo width or mastering subtleties.

**Best foundation for a custom system** — MuQ + Essentia + SongFormer + Demucs + MOSS-Music or a text LLM.

A credible architecture would look like:

```
Full recording
      │
      ├── Demucs-MLX ── vocals / drums / bass / accompaniment
      │
      ├── Essentia ─── tempo / key / loudness / spectral / dynamics
      │
      ├── SongFormer ── section boundaries and repetitions
      │
      ├── MuQ/MERT ─── semantic and temporal embeddings
      │
      └── Lyrics ASR
              │
              ▼
       Structured evidence
              │
              ▼
     MOSS-Music or text LLM
              │
              ▼
 Observations + confidence + interpretation
```

This is more likely to produce trustworthy analysis than relying on an audio LLM's internal representations alone.

### A decisive test to run tonight

Use one obscure or unreleased song and create four versions:

1. Original
2. Metadata-stripped original with a meaningless filename
3. Counterfactual edit with one section replaced, removed, or transposed
4. Unrelated recording presented with the original question

Run each through MOSS-Music, Gemini, Music Flamingo, and Audio Flamingo Next.

Ask exactly the same questions:

- At 00:42–01:05, identify every audible entrance, exit, or major textural change. Do not infer from genre conventions.
- Provide a chronological section map. For every boundary, state the audible event that justifies it.
- Estimate tempo, meter, and tonal center. Give an alternative interpretation and explain the ambiguity.
- Describe the emotional trajectory without using lyrics or assumed artist identity.
- Which production observations are directly audible, and which are speculative?
- Compare A and B. Name only differences you can localize to timestamps.

Then score:

- Timestamp correctness
- Event identification
- Stability across renamed files
- Sensitivity to the counterfactual edit
- Whether answers change when unrelated audio is substituted
- Agreement with Essentia/Basic Pitch/SongFormer
- Calibration: does the model admit uncertainty?
- Unsupported detail count
- Narrative quality separately from perceptual accuracy

That experiment will tell you more than another benchmark leaderboard. A system that notices the inserted section, revises its structure map, and localizes the change is listening. A system that produces essentially the same essay for both files is doing genre-conditioned creative writing.

## 8. Source directory

**Primary models and demos**

- MOSS-Music repository, architecture, evaluation, setup and model links
- OpenMOSS Hugging Face organization and running MOSS-Music Space
- MOSS-Music Thinking model and demo discussion
- MOSS-Music MLX 8-bit checkpoint and backend instructions
- Music Flamingo 2601 model card, code, Colab and demo links
- Audio Flamingo Next model card, variants, code and Spaces
- MOSS-Audio checkpoints
- MiMo-Audio weights, repository and installation
- Step-Audio-R1/R1.1 repository, weights, Docker and vLLM setup
- Qwen3-Omni repository, checkpoints, demos and music results
- Qwen2.5-Omni repository and music benchmarks
- Qwen2.5-Omni official GPTQ/AWQ deployment instructions
- Gemini audio documentation and API examples

**Evaluation and qualitative judgment**

- TuneJury model card and demo access
- MuQ-Eval model card and inference details
- SongEval project and dataset description
- MuChoMusic benchmark, data and code
- MUSE benchmark, paper and code links
- CMI-Bench paper
- BASS benchmark
- HumMusQA paper page
