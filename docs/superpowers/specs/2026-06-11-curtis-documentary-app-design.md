# Curtis Documentary App — Design

**Date:** 2026-06-11
**Status:** Draft for review

## What it is

A web app for friends: upload random footage of your life, get back a short
Adam Curtis-style documentary about yourself — your own clips, lightly
trimmed, with a voice-cloned Curtis narration generated from a hauntological
reading of the footage.

This is a hosted version of the pipeline already proven locally
(`documentary/` + `/Volumes/2025_exSSD_2tb/adam curtis audio/scripts/`):
philm analysis → script generation → Qwen3-TTS Curtis voice clone → FFmpeg
assembly.

## Scope (v1)

- **In:** upload clips → hauntology analysis → Curtis-style narration script
  → voice-cloned voiceover → clips played roughly in order, trimmed to match
  narration length, voiceover on top → downloadable MP4.
- **Out:** auto-edit EDL matched to narration beats (the "option 1" full
  Curtis experience), music bed, user accounts, archive integration. All can
  come later.

## Architecture

```
Browser (secret URL)
  │  direct client upload (signed token, no size problem, no key exposure)
  ▼
Vercel Blob  ◄────────────┐
  │                       │ final MP4 written back
  ▼                       │
Fly.io worker (Python/FastAPI, one small VM + queue)
  │  GEMINI_API_KEY + REPLICATE_API_TOKEN live ONLY here
  ├──► Gemini Files API: upload clips, run hauntology mode (philm schema)
  ├──► Gemini text call: hauntology JSON → Curtis narration script
  ├──► Replicate: private Cog model wrapping Qwen3-TTS + Curtis ref voice
  └──► FFmpeg (on the worker): trim/normalize clips, mux voiceover
```

- **Frontend:** Next.js on Vercel. Upload form, job progress, result player.
  The app lives at an unguessable path (e.g. `/d/<random-32-char>`); no
  accounts, no password.
- **Vercel Blob:** client-direct uploads via signed tokens minted by a Vercel
  function. Holds both input clips and the final MP4. Objects expire after 7
  days.
- **Fly.io worker:** single Python service running the whole pipeline.
  Imports philm (`video_analyzer`) as a dependency for modes/schemas and
  reuses the compress-for-Gemini logic. Simple job model: POST /jobs returns
  an id, frontend polls GET /jobs/:id for step-by-step status.
- **Replicate model:** private Cog package of `Qwen3-TTS-12Hz-0.6B-Base` with
  `curtis_ref_clean.mp3` + its reference transcript baked in (same as
  `curtis_voice.py`). Input: narration text. Output: WAV. Pay per second of
  GPU; cold start ~60–90s is acceptable ("generating your documentary…").

## Pipeline (per job)

1. **Intake.** Validate: max 10 clips, max 500MB / 15 minutes total. Download
   from Blob to worker disk.
2. **Analyze.** Compress if needed, upload each clip to Gemini Files API, run
   the **hauntology** mode (Fisher/Han/Curtis — `lost_future`,
   `hypernormal`, `suffering_individualized`, `temporal_pathology` map
   directly onto Curtis narration tropes). One mode in v1; multi-mode later.
3. **Script.** Gemini text call: hauntology timecodes JSON + a Curtis style
   prompt modeled on the postmodern-zoo narration (short declarative
   sentences, "But this was a fantasy", statistics stated flatly). Target
   ~2–4 minutes of narration. Output: plain paragraphs.
4. **Voiceover.** Send narration to the Replicate model. Paragraph-by-
   paragraph generation with 0.8s pauses, concatenated — same approach as
   `generate_voiceover.py`. A failed paragraph is skipped, not fatal.
5. **Assemble.** FFmpeg on the worker, same normalization as
   `build_documentary.sh` (1080p, 25fps, CRF 18): clips in upload order,
   each trimmed proportionally so total video duration ≈ voiceover duration,
   concatenated, voiceover muxed over (original audio ducked to ~-20dB under
   narration).
6. **Deliver.** Upload MP4 to Blob, return download/stream URL. Delete Gemini
   files immediately; Blob objects expire on their own.

## Error handling

- Job status exposes the current step and a human-readable message; failures
  mark the job failed with the step that died.
- Per-clip analysis failure → skip the clip, continue (job fails only if
  *all* clips fail).
- Replicate/Gemini calls get 2 retries with backoff.
- Worker restarts mid-job → job marked stale and failed after a timeout;
  jobs are not resumed in v1 (friends can just re-run).

## Cost & abuse controls

- **Gemini:** dedicated GCP project with a hard monthly spend cap (~$25) set
  in AI Studio, plus budget alerts at 50/80/95%. (Hard project-level caps
  exist as of March 2026.)
- **Replicate:** native monthly spend limit in account settings.
- **Per-job limits:** clip count / size / duration caps above.
- **Access:** unguessable URL only. Worst case if the URL leaks: services
  pause at the caps; no surprise bill.

## Testing

- Unit: trim-math (clip durations → per-clip trim points), script-prompt
  assembly, job state machine.
- Integration (gated, like the existing philm smoke tests): one small sample
  clip through the full pipeline against real APIs.
- Manual: golden path with 2–3 phone clips before sharing the URL.

## Decisions log

- **Hauntology over Baudrillard** as the v1 analysis mode — schema is
  literally built on Curtis.
- **Fly.io over Vercel functions** for the pipeline — no body-size/timeout
  limits, Python-native, philm drops in.
- **Replicate over HF Endpoints/RunPod** for TTS — per-second billing fits
  bursty friend traffic; Cog packaging is acceptable one-time work. RunPod
  is the cheaper fallback if Replicate costs annoy.
- **No Vertex** — Developer API + dedicated capped GCP project is enough.
- **Secret URL, no auth** — spend caps bound the blast radius.
