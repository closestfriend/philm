# tests/test_reliability.py — affect vector enum, the A0 normaliser, and the sampler's pure parts.
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from reliability import sample, vectors  # noqa: E402
from video_analyzer.models import AffectMoment, AffectResult, AffectVector  # noqa: E402
from video_analyzer.providers.schema import pydantic_to_strict_schema  # noqa: E402


def test_vector_enum_is_closed_and_balanced():
    vals = [v.value for v in AffectVector]
    assert len(vals) == 12 and len(set(vals)) == 12
    rising = {"expanding", "outward", "forward", "toward", "upward"}
    falling = {"contracting", "inward", "receding", "away", "downward"}
    assert rising | falling | {"static", "neutral"} == set(vals)


def test_affect_moment_rejects_free_text_vector():
    ok = AffectMoment(time="00:03", intensity=7, atmosphere="x", vector="upward", captures=False)
    assert ok.vector is AffectVector.UPWARD
    with pytest.raises(ValidationError):
        AffectMoment(time="00:03", intensity=7, atmosphere="x", vector="forward, expanding", captures=False)


def test_strict_schema_carries_the_enum():
    sc = pydantic_to_strict_schema(AffectResult)
    assert sc["$defs"]["AffectVector"]["enum"] == [v.value for v in AffectVector]


@pytest.mark.parametrize("raw,expected", [
    ("expanding", "expanding"),
    ("Upward", "upward"),
    ("forward, expanding", "forward"),
    ("slight outward pull", "outward"),
    ("inward pull", "inward"),
    ("contracting, then neutral", "contracting"),
    ("none", "neutral"),
    ("steady", "static"),
    ("holding", "static"),
    ("approaching", "toward"),
    ("fading", "receding"),
    ("synergistic interaction", None),
    ("", None),
    (None, None),
])
def test_normalize_vector(raw, expected):
    assert vectors.normalize_vector(raw) == expected


def test_normalizer_only_emits_enum_values():
    for word, target in vectors.SYNONYMS.items():
        assert target in {v.value for v in AffectVector}, word


def test_camera_and_year_parsing():
    assert sample.camera_of("MVI_0251.MOV") == "canon"
    assert sample.camera_of("M2U00528.MPG") == "sony"
    assert sample.camera_of("P1060509.MOV") == "lumix"
    assert sample.camera_of("IMG_7421.mp4") == "iphone"
    assert sample.camera_of("S7300012.MP4") == "other"
    assert sample.year_of("x/2021 - 2022 t6i/MVI_2010.MOV") == 2021
    assert sample.year_of("x/june 9 video/MVI_0251.MOV") is None
    assert sample.year_of("x/IMG_20260101.mp4") is None  # part of a longer digit run


def test_allocate_is_proportional_with_floor_and_cap():
    alloc = sample.allocate({"a": 300, "b": 100, "c": 2, "d": 0}, 40)
    assert sum(alloc.values()) == 40
    assert alloc["c"] >= 1 and alloc["c"] <= 2
    assert "d" not in alloc
    assert alloc["a"] > alloc["b"]
    assert sample.allocate({"a": 5, "b": 3}, 40) == {"a": 5, "b": 3}
    many = {f"c{i}": 10 + i for i in range(15)}  # 15 cells, floor of one each must not overshoot
    assert sum(sample.allocate(many, 40).values()) == 40


def test_tercile_labels():
    cuts = (4.71, 5.7)
    assert sample.tercile_of(2.0, cuts) == "calm"
    assert sample.tercile_of(5.0, cuts) == "mid"
    assert sample.tercile_of(8.0, cuts) == "intense"
