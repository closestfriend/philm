#!/usr/bin/env python3
"""
looks.py — named visual looks for carti_cut: a grade that never changes, hits that fire on
kicks, and passages that run across song sections.

A Look is DATA (filter strings + thresholds), not code paths, so adding a look means adding a
dict entry. The triggers (kick density, section labels) come from affect_score's detectors;
carti_cut wires them in and asks this module what to do at each beat.

Filter-chain order for every segment: geometry effect → fps → hit → passage → grade.
"""

from dataclasses import dataclass, field

TARGET_FPS = 30
KICK_WINDOW = 0.04  # a beat "has a kick" if a kick onset lands within ±40 ms of it


@dataclass(frozen=True)
class Hit:
    """A one-cut effect fired by a kick. Candidates are tried in list order; the first whose
    min_density the kick clears and whose prob roll passes wins."""
    name: str
    vf: str
    min_density: float
    prob: float = 1.0


@dataclass(frozen=True)
class Passage:
    """Per-section editing grammar."""
    vf: str | None = None          # filter applied to every segment in the section
    hold_every: int = 1            # 2 = cut on every other beat (hold the shot between)
    shrink_zoom_scale: float = 1.0 # multiplier on the shrink/zoom roll
    grid_beats: int = 0            # open the section with N beats of the multi-take sync grid


@dataclass(frozen=True)
class Look:
    name: str
    grade: str
    flash: str = "white"           # "white" | "invert"
    hits: tuple[Hit, ...] = ()
    passages: dict[str, Passage] = field(default_factory=dict)

    def passage(self, label: str | None) -> Passage:
        return self.passages.get(label or "", Passage())


def freeze_vf(duration: float, hold_fraction: float = 0.5) -> str:
    """Hold the first frame for part of the cut, then release."""
    k = max(1, int(round(TARGET_FPS * duration * hold_fraction)))
    return f"freezeframes=first=0:last={k}:replace=0"


OPIUM = Look(
    name="opium",
    # crushed monochrome: desaturate, hard S with blacks sunk and whites lifted, coarse grain,
    # a little edge bite, corners darkened. Grain is a stand-in until a shot plate exists.
    grade=(
        "hue=s=0,"
        "curves=m='0/0 0.18/0.04 0.5/0.5 0.82/0.97 1/1',"
        "unsharp=5:5:0.8,"
        "noise=alls=22:allf=t+u,"
        "vignette=angle=PI/4.5"
    ),
    flash="invert",
    hits=(
        Hit("rgbsplit", "rgbashift=rh=-8:bh=8", min_density=0.9, prob=0.8),
        Hit("shake", "crop=w=iw-32:h=ih-32:x=16+14*sin(n*1.7):y=16+10*cos(n*2.3),scale=1920:1080",
            min_density=0.7, prob=0.6),
    ),
    passages={
        "breakdown": Passage(vf="lagfun=decay=0.92", hold_every=2, shrink_zoom_scale=0.0),
        "build":     Passage(shrink_zoom_scale=0.5),
        "drop":      Passage(shrink_zoom_scale=1.0, grid_beats=4),
        "outro":     Passage(vf="lagfun=decay=0.95", hold_every=2, shrink_zoom_scale=0.0),
    },
)

LOOKS: dict[str, Look] = {"opium": OPIUM}


def choose_hit(look: Look, kick_density: float | None, rng) -> Hit | None:
    """Pick the hit for a beat, or None. No kick on the beat → no hit, ever."""
    if kick_density is None:
        return None
    for hit in look.hits:
        if kick_density >= hit.min_density and rng.random() < hit.prob:
            return hit
    return None


def compose_vf(base: str, *extras: str | None) -> str:
    """Join filter fragments in canonical order: base geometry, fps normalisation, then the
    extras (hit, passage, grade) in the order given. Empty/None fragments are skipped."""
    parts = [base, f"fps={TARGET_FPS}"] + [e for e in extras if e]
    return ",".join(parts)


class LookContext:
    """What the scheduler needs to know about the song to apply a look: which beats carry a
    kick and how hard, and which section each beat is in. Built once per render."""

    def __init__(self, look: Look, beat_times: list[float], kick_onsets: list[float],
                 kick_density, sections):
        import bisect
        self.look = look
        self.sections = sections
        self._onsets = sorted(kick_onsets)
        self._density = kick_density
        self._bisect = bisect

    def kick_at(self, t: float) -> float | None:
        """Kick density at beat t, or None if no kick onset lands within KICK_WINDOW of it."""
        i = self._bisect.bisect_left(self._onsets, t)
        near = [self._onsets[j] for j in (i - 1, i) if 0 <= j < len(self._onsets)]
        if not near or min(abs(o - t) for o in near) > KICK_WINDOW:
            return None
        return float(self._density(t))

    def section_at(self, t: float):
        for s in self.sections:
            if s.start <= t < s.end:
                return s
        return self.sections[-1] if self.sections else None

    def label_at(self, t: float) -> str | None:
        s = self.section_at(t)
        return s.label if s else None
