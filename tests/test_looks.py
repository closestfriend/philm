# tests/test_looks.py — look definitions, hit gating, filter composition, look context.
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import looks  # noqa: E402


@dataclass
class Sec:
    start: float
    end: float
    label: str


def test_opium_grade_is_monochrome_and_ends_with_vignette():
    g = looks.LOOKS["opium"].grade
    assert g.startswith("hue=s=0,")
    assert "curves=" in g and "noise=" in g and g.endswith("vignette=angle=PI/4.5")
    assert looks.LOOKS["opium"].flash == "invert"


def test_choose_hit_never_fires_without_a_kick():
    rng = random.Random(0)
    assert looks.choose_hit(looks.OPIUM, None, rng) is None


def test_choose_hit_by_density():
    always = random.Random(1)
    always.random = lambda: 0.0  # every prob roll passes
    assert looks.choose_hit(looks.OPIUM, 0.95, always).name == "rgbsplit"
    assert looks.choose_hit(looks.OPIUM, 0.75, always).name == "shake"
    assert looks.choose_hit(looks.OPIUM, 0.3, always) is None


def test_compose_vf_order_fps_then_extras():
    vf = looks.compose_vf("scale=1920:1080", "rgbashift=rh=-8:bh=8", None, "hue=s=0")
    assert vf == "scale=1920:1080,fps=30,rgbashift=rh=-8:bh=8,hue=s=0"


def test_freeze_vf_holds_half_the_cut():
    assert looks.freeze_vf(0.4) == "freezeframes=first=0:last=6:replace=0"


def test_look_context_kick_window_and_sections():
    secs = [Sec(0, 10, "breakdown"), Sec(10, 30, "drop"), Sec(30, 40, "outro")]
    ctx = looks.LookContext(looks.OPIUM, beat_times=[], kick_onsets=[1.00, 5.02],
                            kick_density=lambda t: 0.8, sections=secs)
    assert ctx.kick_at(1.03) == 0.8          # 30 ms away → kick
    assert ctx.kick_at(5.10) is None         # 80 ms away → no kick
    assert ctx.kick_at(20.0) is None
    assert ctx.label_at(3.0) == "breakdown" and ctx.label_at(10.0) == "drop"
    assert ctx.label_at(99.0) == "outro"     # past the end → last section


def test_passage_lookup_defaults():
    p = looks.OPIUM.passage("breakdown")
    assert p.hold_every == 2 and p.shrink_zoom_scale == 0.0 and "lagfun" in p.vf
    assert looks.OPIUM.passage("drop").grid_beats == 4
    assert looks.OPIUM.passage(None) == looks.Passage()
