"""Step model-chosen affect moments onto a fixed time grid (design §2).

Two runs of the same clip never pick the same timecodes, so nothing is compared moment
to moment. Each run is turned into one value per 5-second bin by step-hold: a bin takes
the most recent moment at or before its start; bins before the first moment take the
first moment's value. Clips shorter than 10 s get a single bin.

Anything odd about a run is recorded in `Bins.flags` and left for the scorer to report,
never silently repaired. The flags the red-team (design §6) relies on:
  no_moments        the run returned an empty list
  all_same_time     every moment has the same timecode (e.g. all at 00:00)
  time_past_end     a moment lies more than one bin past the clip's duration
  unparsable_time   a timecode could not be read; that moment is dropped
  unmappable_vector a vector string had no enum value (A0 only); that bin is missing
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from .vectors import normalize_vector

BIN_SECONDS = 5.0
SINGLE_BIN_BELOW = 10.0

_TIME = re.compile(r"^\s*(\d+):(\d{1,2}(?:\.\d+)?)(?::(\d{1,2}(?:\.\d+)?))?\s*$")


def parse_time(s: Optional[str]) -> Optional[float]:
    """'MM:SS', 'M:SS', 'HH:MM:SS', 'MMM:SS' and fractional seconds. None if unreadable."""
    if not s:
        return None
    m = _TIME.match(s)
    if not m:
        return None
    a, b, c = m.groups()
    if c is None:
        return int(a) * 60 + float(b)
    return int(a) * 3600 + float(b) * 60 + float(c)


@dataclass
class Moment:
    t: float
    intensity: Optional[int]
    vector: Optional[str]
    captures: Optional[bool]


@dataclass
class Bins:
    intensity: list[Optional[float]]
    vector: list[Optional[str]]
    captures: list[Optional[bool]]
    flags: set[str] = field(default_factory=set)

    @property
    def n(self) -> int:
        return len(self.intensity)


def n_bins(duration: float) -> int:
    if duration < SINGLE_BIN_BELOW:
        return 1
    return max(1, math.ceil(duration / BIN_SECONDS))


def moments_from_result(result: dict, *, normalize_vectors: bool = False) -> tuple[list[Moment], set[str]]:
    """Read an AffectResult dict. `normalize_vectors` is for A0 rows whose vectors are
    free text; new runs carry enum values and are taken as-is."""
    flags: set[str] = set()
    out: list[Moment] = []
    for tc in result.get("timecodes") or []:
        t = parse_time(tc.get("time"))
        if t is None:
            flags.add("unparsable_time")
            continue
        vec = tc.get("vector")
        if normalize_vectors:
            vec = normalize_vector(vec)
            if vec is None:
                flags.add("unmappable_vector")
        out.append(Moment(t=t, intensity=tc.get("intensity"), vector=vec, captures=tc.get("captures")))
    out.sort(key=lambda m: m.t)
    return out, flags


def to_bins(moments: list[Moment], duration: float, flags: Optional[set[str]] = None) -> Bins:
    n = n_bins(duration)
    f = set(flags or ())
    if not moments:
        f.add("no_moments")
        return Bins([None] * n, [None] * n, [None] * n, f)
    if len({m.t for m in moments}) == 1 and len(moments) > 1:
        f.add("all_same_time")
    if any(m.t > duration + BIN_SECONDS for m in moments):
        f.add("time_past_end")

    intensity: list[Optional[float]] = []
    vector: list[Optional[str]] = []
    captures: list[Optional[bool]] = []
    idx = 0
    current = moments[0]
    for b in range(n):
        start = b * BIN_SECONDS
        while idx < len(moments) and moments[idx].t <= start:
            current = moments[idx]
            idx += 1
        intensity.append(float(current.intensity) if current.intensity is not None else None)
        vector.append(current.vector)
        captures.append(current.captures)
    return Bins(intensity, vector, captures, f)
