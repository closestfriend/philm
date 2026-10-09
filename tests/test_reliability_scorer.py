# tests/test_reliability_scorer.py — aligner behaviour and the §6 red-team on synthetic runs.
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from reliability import align, score  # noqa: E402
from reliability.align import Bins, Moment  # noqa: E402
from reliability.score import ClipRun  # noqa: E402


# ------------------------------------------------------------------ align

@pytest.mark.parametrize("s,sec", [
    ("00:05", 5.0), ("1:05", 65.0), ("00:01:05", 65.0), ("314:00", 18840.0),
    ("00:05.5", 5.5), ("5s", None), ("", None), (None, None), ("abc", None),
])
def test_parse_time(s, sec):
    assert align.parse_time(s) == sec


def test_n_bins_rule():
    assert align.n_bins(3.0) == 1
    assert align.n_bins(9.9) == 1
    assert align.n_bins(10.0) == 2
    assert align.n_bins(60.0) == 12
    assert align.n_bins(61.0) == 13


def test_step_hold_and_pre_first_fill():
    m = [Moment(7.0, 2, "static", False), Moment(21.0, 8, "upward", True)]
    b = align.to_bins(m, 30.0)
    assert b.n == 6
    assert b.intensity == [2, 2, 2, 2, 2, 8]  # bins start 0,5,10,15,20,25; 21s moment lands in bin 5
    assert b.vector[-1] == "upward" and b.captures[-1] is True
    assert b.flags == set()


def test_flags_are_recorded_not_repaired():
    assert "no_moments" in align.to_bins([], 20.0).flags
    same = [Moment(0.0, 3, "static", False), Moment(0.0, 9, "static", False)]
    assert "all_same_time" in align.to_bins(same, 20.0).flags
    late = [Moment(0.0, 3, "static", False), Moment(99.0, 3, "static", False)]
    assert "time_past_end" in align.to_bins(late, 20.0).flags
    moments, flags = align.moments_from_result({"timecodes": [
        {"time": "xx", "intensity": 1, "vector": "static", "captures": False},
        {"time": "00:01", "intensity": 1, "vector": "synergistic interaction", "captures": False},
    ]}, normalize_vectors=True)
    assert len(moments) == 1 and "unparsable_time" in flags and "unmappable_vector" in flags
    assert moments[0].vector is None


# ------------------------------------------------------------------ synthetic runs

VECS = list(score.VECTOR_CODES)


def synthetic(n_clips=30, seed=0, noise=0.0):
    """A plausible run: per-clip curves with structure, optional noise for a second run."""
    rng = random.Random(seed)
    clips = {f"c{i:02d}": {"duration": rng.choice([8.0, 20.0, 45.0, 90.0])} for i in range(n_clips)}
    run = {}
    for cid, c in clips.items():
        n = align.n_bins(c["duration"])
        base = rng.uniform(2, 8)
        inten = [min(10, max(1, round(base + math.sin(b / 2) * 2 + rng.gauss(0, noise)))) for b in range(n)]
        vec = [VECS[(hash(cid) + b) % 5 + (0 if inten[b] >= base else 5)] for b in range(n)]
        cap = [inten[b] > 6 for b in range(n)]
        run[cid] = ClipRun(cid, Bins([float(v) for v in inten], vec, cap))
    return clips, run


def alphas(runs, clip_ids, clips):
    return {f: score.alpha(score.matrix(runs, clip_ids, clips, f), lvl) for f, lvl in score.FIELD_LEVEL.items()}


def test_identical_copy_scores_one():
    clips, run = synthetic()
    a = alphas([run, run], sorted(clips), clips)
    assert all(abs(v - 1) < 1e-9 for v in a.values())


def test_null_reader_scores_at_or_below_zero():
    clips, run = synthetic()
    null = {cid: ClipRun(cid, Bins([5.0] * cr.bins.n, ["neutral"] * cr.bins.n, [False] * cr.bins.n))
            for cid, cr in run.items()}
    a = alphas([run, null], sorted(clips), clips)
    assert a["intensity"] <= 0.1 and a["vector"] <= 0.1


def test_shuffled_clip_ids_destroy_agreement_on_average():
    clips, run = synthetic(n_clips=40)
    ids = sorted(clips)
    floor = score.permutation_floor(run, ids, clips, "intensity", n_perm=30)
    assert floor["mean"] <= 0.15 and floor["sd"] < 0.25


def test_shuffle_has_no_fixed_points():
    clips, run = synthetic(n_clips=12)
    for seed in range(10):
        sh = score.shuffled_run(run, seed)
        assert all(sh[c].bins is not run[c].bins for c in sh)


def test_noisy_rerun_lands_between_null_and_copy():
    clips, run = synthetic(seed=0)
    _, noisy = synthetic(seed=0, noise=1.0)
    a = alphas([run, noisy], sorted(clips), clips)["intensity"]
    assert 0.3 < a < 1.0


def test_missing_clip_is_missing_not_zero():
    clips, run = synthetic()
    ids = sorted(clips)
    partial = dict(run)
    partial[ids[0]] = ClipRun(ids[0], None)
    mf = score.missing_and_flags({"a": run, "b": partial}, ids)
    assert mf["b"]["missing"] == 1 and mf["a"]["missing"] == 0
    assert abs(alphas([run, partial], ids, clips)["intensity"] - 1) < 1e-9


def test_bootstrap_interval_brackets_point():
    clips, run = synthetic(seed=1)
    _, noisy = synthetic(seed=1, noise=0.8)
    a, lo, hi = score.bootstrap_alpha([run, noisy], sorted(clips), clips, "intensity", n_boot=100)
    assert lo <= a <= hi and hi - lo < 0.5


def test_clip_level_agreement_on_copy_and_noise():
    clips, run = synthetic(seed=2)
    _, noisy = synthetic(seed=2, noise=0.8)
    same = score.pairwise_clip_agreement([run, run], sorted(clips))
    assert abs(same["rho_mean"] - 1) < 1e-9 and same["mad_mean_points"] == 0
    diff = score.pairwise_clip_agreement([run, noisy], sorted(clips))
    assert 0.3 < diff["rho_mean"] < 1.0 and diff["mad_mean_points"] > 0
