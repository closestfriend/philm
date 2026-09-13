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
