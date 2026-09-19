# tests/test_carti_cut.py — seed reproducibility for the carti_cut scheduler and clip pool.
import json
import random
import shutil
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import carti_cut as cc  # noqa: E402

BEATS = [i * 0.46 for i in range(120)]  # ~55s at 130 BPM


def _pool(n=6, lipsync=False):
    pool = [{"clip_id": f"clip{i}", "offset": float(i), "name": f"clip{i}.mov",
             "lip_sync": False, "weight": 1.0} for i in range(n)]
    if lipsync:
        pool.append({"clip_id": "take1", "offset": 0.0, "name": "take1.mov",
                     "lip_sync": True, "weight": 3.0})
    return pool


def test_schedule_same_seed_same_plan():
    a = cc.build_cut_schedule(BEATS, _pool(), seed=42)
    b = cc.build_cut_schedule(BEATS, _pool(), seed=42)
    assert a == b


def test_schedule_same_seed_same_plan_weighted():
    a = cc.build_cut_schedule(BEATS, _pool(lipsync=True), seed=7)
    b = cc.build_cut_schedule(BEATS, _pool(lipsync=True), seed=7)
    assert a == b
    assert any(e["lip_sync"] for e in a)


def test_schedule_different_seed_different_plan():
    a = cc.build_cut_schedule(BEATS, _pool(), seed=1)
    b = cc.build_cut_schedule(BEATS, _pool(), seed=2)
    assert a != b


def test_clip_pool_offsets_follow_seed(tmp_path):
    files = [tmp_path / f"c{i}.mov" for i in range(4)]
    take = tmp_path / "take1.mov"
    fake_probe = lambda p: 40.0  # noqa: E731 — avoid ffprobe on nonexistent files

    pool_a, paths_a = cc.build_clip_pool(files, [take], 3.0, random.Random(99), probe=fake_probe)
    pool_b, paths_b = cc.build_clip_pool(files, [take], 3.0, random.Random(99), probe=fake_probe)
    pool_c, _ = cc.build_clip_pool(files, [take], 3.0, random.Random(100), probe=fake_probe)

    assert pool_a == pool_b
    assert [c["offset"] for c in pool_a[:4]] != [c["offset"] for c in pool_c[:4]]
    assert all(0 <= c["offset"] <= 30.0 for c in pool_a[:4])  # within 75% of duration
    assert pool_a[-1] == {"clip_id": "take1", "offset": 0.0, "name": "take1.mov",
                          "lip_sync": True, "weight": 3.0, "song_start": 0.0, "song_end": 40.0}
    assert paths_a["take1"] == take and paths_a["c0"] == files[0]


def test_sidecar_records_seed_and_args(tmp_path):
    out = tmp_path / "carti_cut_v03.mp4"
    cc.write_sidecar(out, seed=123, tempo=130.2, args={"music": "t.wav", "density": 1.0},
                     schedule=cc.build_cut_schedule(BEATS, _pool(), seed=123))
    side = json.loads((tmp_path / "carti_cut_v03.json").read_text())
    assert side["seed"] == 123
    assert side["args"]["music"] == "t.wav"
    assert side["cuts"] == len(cc.build_cut_schedule(BEATS, _pool(), seed=123))


# ─── lip-sync song alignment + eligibility window ─────────────────────────────

def _take(clip_id, song_start, song_end, weight=3.0):
    return {"clip_id": clip_id, "offset": 0.0, "name": f"{clip_id}.mov", "lip_sync": True,
            "weight": weight, "song_start": song_start, "song_end": song_end}


def test_lipsync_only_placed_inside_its_window():
    pool = _pool(3) + [_take("late", 18.0, 60.0)]
    sched = cc.build_cut_schedule(BEATS, pool, seed=5)
    ls = [e for e in sched if e["lip_sync"]]
    assert ls, "weight 3 vs 3 B-roll clips should place the take somewhere"
    for e in ls:
        assert e["beat_time"] >= 18.0
        assert e["beat_time"] + e["duration"] <= 60.0
        assert e["start_offset"] == e["beat_time"] - 18.0


def test_lipsync_stutter_cannot_run_past_window():
    pool = _pool(3) + [_take("short", 0.0, 10.0, weight=50.0)]
    sched = cc.build_cut_schedule(BEATS, pool, seed=11)
    assert all(e["beat_time"] + e["duration"] <= 10.0 for e in sched if e["lip_sync"])
    assert any(e["lip_sync"] for e in sched)
    assert any(not e["lip_sync"] for e in sched if e["beat_time"] > 10.0)


def test_all_takes_ineligible_falls_back_to_broll():
    pool = _pool(2) + [_take("never", 500.0, 600.0, weight=99.0)]
    sched = cc.build_cut_schedule(BEATS, pool, seed=3)
    assert sched and not any(e["lip_sync"] for e in sched)


def test_pool_lipsync_window_and_no_double_casting(tmp_path):
    take = tmp_path / "MVI_0397.mov"
    files = [tmp_path / "b1.mov", take, tmp_path / "b2.mov"]  # take also sits in the B-roll folder
    probe = lambda p: 100.0  # noqa: E731
    pool, paths = cc.build_clip_pool(files, [take], 3.0, random.Random(1), probe=probe,
                                     lipsync_offsets=[18.72])
    ids = [c["clip_id"] for c in pool]
    assert ids.count("MVI_0397") == 1
    entry = pool[-1]
    assert entry["lip_sync"] and entry["song_start"] == 18.72 and entry["song_end"] == 118.72
    assert [c["clip_id"] for c in pool if not c["lip_sync"]] == ["b1", "b2"]


def test_pool_negative_offset_means_camera_rolled_first(tmp_path):
    take = tmp_path / "t.mov"
    pool, _ = cc.build_clip_pool([], [take], 3.0, random.Random(1), probe=lambda p: 130.0,
                                 lipsync_offsets=[-9.41])
    assert pool[0]["song_start"] == -9.41 and pool[0]["song_end"] == 130.0 - 9.41


def test_resolve_manual_offsets_count_mismatch(tmp_path):
    with pytest.raises(SystemExit):
        cc.resolve_lipsync_offsets([tmp_path / "a.mov", tmp_path / "b.mov"], tmp_path / "s.wav",
                                   manual=[1.0], cache_dir=tmp_path)


def test_resolve_manual_offsets_skips_detection(tmp_path):
    out = cc.resolve_lipsync_offsets([tmp_path / "a.mov"], tmp_path / "s.wav",
                                     manual=[5.5], cache_dir=tmp_path)
    assert out == [{"offset": 5.5, "score": None, "source": "manual"}]


@pytest.mark.skipif(shutil.which("uvx") is None, reason="uvx not on PATH")
def test_detect_song_offset_on_synthetic_take(tmp_path):
    """take = song from second 4.0 onward, quieter, with room noise. Expect offset ≈ 4.0."""
    sr = 22050
    rng = np.random.default_rng(0)
    song = rng.standard_normal(sr * 30).astype(np.float32)
    song = np.convolve(song, np.ones(8) / 8, mode="same")  # tame it a little
    take = 0.3 * song[int(4.0 * sr):] + 0.05 * rng.standard_normal(sr * 26).astype(np.float32)
    for name, sig in (("song.wav", song), ("take.wav", take)):
        pcm = (sig / np.abs(sig).max() * 32000).astype(np.int16)
        with wave.open(str(tmp_path / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
    offset, score = cc.detect_song_offset(tmp_path / "take.wav", tmp_path / "song.wav", tmp_path)
    assert abs(offset - 4.0) < 0.05
    assert score > 10

    # cache round-trip: second call must not shell out again
    res = cc.resolve_lipsync_offsets([tmp_path / "take.wav"], tmp_path / "song.wav",
                                     manual=None, cache_dir=tmp_path / "cache")
    assert res[0]["source"] == "detected" and abs(res[0]["offset"] - 4.0) < 0.05
    res2 = cc.resolve_lipsync_offsets([tmp_path / "take.wav"], tmp_path / "song.wav",
                                      manual=None, cache_dir=tmp_path / "cache")
    assert res2[0]["source"] == "cache" and res2[0]["offset"] == res[0]["offset"]


# ─── performance-only pools (no B-roll) ───────────────────────────────────────

def test_lipsync_only_pool_holds_last_shot_when_nothing_covers_a_beat():
    # song runs to ~55s; takes cover 0-40 and 5-48; beats 48-55 have no take
    pool = [_take("a", 0.0, 40.0), _take("b", 5.0, 48.0)]
    sched = cc.build_cut_schedule(BEATS, pool, seed=8)
    assert all(e["lip_sync"] for e in sched)
    assert all(e["beat_time"] + e["duration"] <= (40.0 if e["clip_id"] == "a" else 48.0)
               or e["held"] for e in sched)
    # the timeline is still continuous: last entry extends to the end of the beat grid
    last = sched[-1]
    assert last["held"] and last["frame"] + last["frames"] == round(BEATS[-1] * 30) + 15
    assert last["beat_time"] + last["duration"] - last["held_from"] > 7.0  # covers 48→55.2


def test_lipsync_only_pool_uncovered_start_clamps_earliest_take():
    pool = [_take("late", 3.0, 60.0), _take("later", 10.0, 60.0)]
    sched = cc.build_cut_schedule(BEATS, pool, seed=8)
    first = sched[0]
    assert first["clip_id"] == "late" and first["start_offset"] == 0.0 and first["clamped"]


# ─── output versioning ─────────────────────────────────────────────────────────

def test_reserve_output_claims_next_version_immediately(tmp_path):
    (tmp_path / "carti_cut_v01.mp4").touch()
    a = cc.reserve_output(tmp_path)
    assert a.name == "carti_cut_v02.mp4"
    # a second, concurrent run must NOT get the same number even though a's mp4 doesn't exist yet
    b = cc.reserve_output(tmp_path)
    assert b.name == "carti_cut_v03.mp4"
    stub = json.loads(a.with_suffix(".json").read_text())
    assert stub["status"] == "rendering"


# ─── look-driven scheduling ────────────────────────────────────────────────────

from dataclasses import dataclass as _dc  # noqa: E402

import looks as lk  # noqa: E402


@_dc
class _Sec:
    start: float
    end: float
    label: str


def _ctx(sections, onsets=(), density=0.95):
    return lk.LookContext(lk.OPIUM, beat_times=BEATS, kick_onsets=list(onsets),
                          kick_density=lambda t: density, sections=sections)


def test_look_breakdown_holds_every_other_beat_and_disables_geometry():
    pool = [_take("a", 0.0, 60.0), _take("b", 0.0, 60.0)]
    ctx = _ctx([_Sec(0, 20, "breakdown"), _Sec(20, 60, "drop")])
    sched = cc.build_cut_schedule(BEATS, pool, seed=4, look_ctx=ctx)
    bd = [e for e in sched if e["beat_time"] < 20]
    n_beats_bd = sum(1 for b in BEATS if b < 20)
    assert abs(len(bd) - n_beats_bd / 2) <= 1
    assert all(e["section"] == "breakdown" and e["passage_vf"] == "lagfun=decay=0.92" for e in bd)
    assert all(e["effect"] == "normal" for e in bd)
    assert any(e["passage_hold"] for e in bd)
    # timeline stays continuous through the holds
    for prev, nxt in zip(sched, sched[1:]):
        assert prev["frame"] + prev["frames"] == nxt["frame"]


def test_look_drop_opens_with_grid_when_two_takes_cover():
    pool = [_take("a", 0.0, 60.0), _take("b", 0.0, 60.0)]
    ctx = _ctx([_Sec(0, 20, "breakdown"), _Sec(20, 60, "drop")])
    sched = cc.build_cut_schedule(BEATS, pool, seed=4, look_ctx=ctx)
    drop = [e for e in sched if e["beat_time"] >= 20]
    assert [e["grid"] for e in drop[:5]] == [True, True, True, True, False]
    assert all(e["hit"] is None and e["effect"] == "normal" for e in drop[:4])


def test_look_no_grid_when_only_one_take_covers():
    pool = [_take("a", 0.0, 60.0), _take("b", 40.0, 60.0)]
    ctx = _ctx([_Sec(0, 20, "breakdown"), _Sec(20, 60, "drop")])
    sched = cc.build_cut_schedule(BEATS, pool, seed=4, look_ctx=ctx)
    assert not any(e["grid"] for e in sched)


def test_look_hits_only_on_kick_beats():
    pool = [_take("a", 0.0, 60.0), _take("b", 0.0, 60.0)]
    onsets = [BEATS[10] + 0.01, BEATS[11] - 0.02, BEATS[30] + 0.03]
    ctx = _ctx([_Sec(0, 60, "drop")], onsets=onsets, density=0.95)
    sched = cc.build_cut_schedule(BEATS, pool, seed=1, look_ctx=ctx)
    hits = [e for e in sched if e["hit"]]
    assert hits, "density 0.95 on kick beats should fire rgbsplit at least once"
    for e in hits:
        assert min(abs(o - e["beat_time"]) for o in onsets) <= lk.KICK_WINDOW
        assert e["hit_vf"].startswith("rgbashift") or e["hit_vf"].startswith("crop=")


def test_no_look_schedule_unchanged():
    pool = _pool(4)
    assert cc.build_cut_schedule(BEATS, pool, seed=9) == cc.build_cut_schedule(BEATS, pool, seed=9,
                                                                               look_ctx=None)


def test_schedule_is_frame_exact_and_gapless():
    sched = cc.build_cut_schedule(BEATS, _pool(3), seed=2)
    assert sched[0]["frame"] == round(BEATS[0] * 30)
    for prev, nxt in zip(sched, sched[1:]):
        assert prev["frame"] + prev["frames"] == nxt["frame"]
        assert abs(prev["duration"] - prev["frames"] / 30) < 1e-9
    # lip-sync seeks use the placed time, not the raw beat time
    ls = cc.build_cut_schedule(BEATS, [_take("a", 0.0, 99.0)], seed=2)
    assert all(abs(e["start_offset"] - e["time"]) < 1e-9 for e in ls)


def test_last_cut_runs_to_end_of_song():
    pool = [_take("a", 0.0, 99.0)]
    sched = cc.build_cut_schedule(BEATS, pool, seed=2, end_time=60.0)
    last = sched[-1]
    assert last["frame"] + last["frames"] == round(60.0 * 30)
    # without end_time the legacy half-second tail still applies
    legacy = cc.build_cut_schedule(BEATS, pool, seed=2)
    assert legacy[-1]["frame"] + legacy[-1]["frames"] == round(BEATS[-1] * 30) + 15
