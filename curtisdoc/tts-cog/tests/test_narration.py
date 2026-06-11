import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from narration import split_paragraphs, stitch


def test_split_paragraphs_basic():
    text = "This is a zoo.\n\nIt is a place where we go to look at things."
    assert split_paragraphs(text) == [
        "This is a zoo.",
        "It is a place where we go to look at things.",
    ]


def test_split_paragraphs_ignores_extra_blank_lines_and_whitespace():
    text = "\n\n  First.  \n\n\n\nSecond.\n\n"
    assert split_paragraphs(text) == ["First.", "Second."]


def test_split_paragraphs_empty_input():
    assert split_paragraphs("") == []
    assert split_paragraphs("\n\n  \n\n") == []


def test_stitch_inserts_pause_between_clips():
    sr = 10
    a = np.ones(5, dtype=np.float32)
    b = np.ones(3, dtype=np.float32)
    out = stitch([a, b], sample_rate=sr, pause_seconds=1.0)
    assert len(out) == 5 + 10 + 3
    assert (out[5:15] == 0).all()


def test_stitch_single_clip_has_no_pause():
    sr = 10
    a = np.ones(4, dtype=np.float32)
    out = stitch([a], sample_rate=sr, pause_seconds=1.0)
    assert len(out) == 4
