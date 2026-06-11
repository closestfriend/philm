"""Replicate predictor: Adam Curtis voice clone via Qwen3-TTS.

Mirrors the proven local pipeline in
'/Volumes/2025_exSSD_2tb/adam curtis audio/scripts/generate_voiceover.py':
paragraph-by-paragraph generation, 0.8s default pauses, failed paragraphs
skipped rather than fatal.
"""

import sys

import numpy as np
import soundfile as sf
import torch
from cog import BasePredictor, Input, Path

from narration import split_paragraphs, stitch

WEIGHTS_DIR = "/weights"
REF_AUDIO = "/src/curtis_ref_clean.mp3"
REF_TEXT = (
    "and it was an empire, I mean the Soviet empire was, to an extent, "
    "a growth out of the Russian empire which had been going for a number of years"
)


class Predictor(BasePredictor):
    def setup(self):
        from qwen_tts import Qwen3TTSModel

        self.model = Qwen3TTSModel.from_pretrained(
            WEIGHTS_DIR,
            device_map="cuda",
            torch_dtype=torch.float32,
        )
        self.voice_prompt = self.model.create_voice_clone_prompt(
            ref_audio=REF_AUDIO,
            ref_text=REF_TEXT,
        )

    def predict(
        self,
        text: str = Input(description="Narration text; blank lines separate paragraphs"),
        pause_seconds: float = Input(
            default=0.8, ge=0.0, le=5.0, description="Silence between paragraphs"
        ),
    ) -> Path:
        paragraphs = split_paragraphs(text)
        if not paragraphs:
            raise ValueError("No narration text provided")

        wavs: list[np.ndarray] = []
        sample_rate = None
        for i, para in enumerate(paragraphs):
            try:
                chunks, sr = self.model.generate_voice_clone(
                    text=para,
                    language="English",
                    voice_clone_prompt=self.voice_prompt,
                )
            except Exception as e:
                print(f"paragraph {i + 1}/{len(paragraphs)} failed: {e}", file=sys.stderr)
                continue
            sample_rate = sr
            wavs.append(chunks[0])

        if not wavs:
            raise RuntimeError("All paragraphs failed to generate")

        audio = stitch(wavs, sample_rate, pause_seconds)
        out_path = "/tmp/voiceover.wav"
        sf.write(out_path, audio, sample_rate)
        return Path(out_path)
