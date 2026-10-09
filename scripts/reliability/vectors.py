"""Map the archive's free-text `vector` strings onto the AffectVector enum.

Only arm A0 (the existing archive readings) needs this; every new run is constrained to
the enum by the schema. The rule is deliberately simple so it can be stated in the card:
lower-case, split into words, and the FIRST word that has an entry in SYNONYMS wins.
"forward, expanding" -> forward. "slight outward pull" -> outward. Strings with no
mappable word return None and are counted as unmappable, never silently binned.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

SYNONYMS: dict[str, str] = {
    # rising
    "expanding": "expanding", "expansion": "expanding", "expand": "expanding",
    "expands": "expanding", "emerging": "expanding", "opening": "expanding",
    "outward": "outward", "outwards": "outward",
    "forward": "forward", "forwards": "forward", "advancing": "forward",
    "toward": "toward", "towards": "toward", "approaching": "toward",
    "upward": "upward", "upwards": "upward", "rising": "upward", "ascending": "upward",
    "lifting": "upward",
    # falling
    "contracting": "contracting", "contraction": "contracting", "contract": "contracting",
    "contracts": "contracting", "closing": "contracting", "tightening": "contracting",
    "inward": "inward", "inwards": "inward",
    "receding": "receding", "fading": "receding", "withdrawing": "receding",
    "retreating": "receding", "dissipating": "receding",
    "away": "away",
    "downward": "downward", "downwards": "downward", "falling": "downward",
    "descending": "downward", "sinking": "downward", "settling": "downward",
    # flat
    "static": "static", "still": "static", "stable": "static", "steady": "static",
    "holding": "static", "held": "static", "sustaining": "static", "sustained": "static",
    "suspended": "static", "stationary": "static",
    "neutral": "neutral", "none": "neutral", "flat": "neutral",
}

_WORD = re.compile(r"[a-z]+")


def normalize_vector(raw: Optional[str]) -> Optional[str]:
    """Return an AffectVector value, or None when no word in `raw` is in SYNONYMS."""
    if not raw:
        return None
    for word in _WORD.findall(raw.lower()):
        hit = SYNONYMS.get(word)
        if hit:
            return hit
    return None


def coverage(raws: Iterable[Optional[str]]) -> tuple[Counter, Counter]:
    """(mapped value counts, unmappable raw-string counts) for a reporting line."""
    mapped: Counter = Counter()
    unmapped: Counter = Counter()
    for r in raws:
        v = normalize_vector(r)
        if v is None:
            unmapped[(r or "").strip().lower()] += 1
        else:
            mapped[v] += 1
    return mapped, unmapped


if __name__ == "__main__":  # report coverage over the live archive
    import os
    import sqlite3

    db = sqlite3.connect(os.path.expanduser("~/.vanalyze/archive.db"))
    raws = [r[0] for r in db.execute("SELECT vector FROM affect_moments")]
    mapped, unmapped = coverage(raws)
    n = len(raws)
    um = sum(unmapped.values())
    print(f"{n} moments: {n - um} mapped ({(n - um) / n:.1%}), {um} unmappable")
    for k, v in mapped.most_common():
        print(f"  {k:12s} {v}")
    print("top unmappable:")
    for k, v in unmapped.most_common(15):
        print(f"  {v:5d}  {k!r}")
