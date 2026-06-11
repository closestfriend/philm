"""Pure text/audio helpers for the Curtis TTS predictor.

Kept free of torch/qwen imports so they can be unit-tested without a GPU.
"""

import numpy as np


def split_paragraphs(text: str) -> list[str]:
    """Split narration into paragraphs on blank lines; drop empties."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def stitch(wavs: list[np.ndarray], sample_rate: int, pause_seconds: float) -> np.ndarray:
    """Concatenate audio chunks with silence between them (not after the last)."""
    pause = np.zeros(int(sample_rate * pause_seconds), dtype=np.float32)
    parts: list[np.ndarray] = []
    for i, wav in enumerate(wavs):
        parts.append(np.asarray(wav, dtype=np.float32))
        if i < len(wavs) - 1:
            parts.append(pause)
    return np.concatenate(parts)
