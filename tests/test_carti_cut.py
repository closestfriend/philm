# tests/test_carti_cut.py — seed reproducibility for the carti_cut scheduler and clip pool.
import json
import random
import sys
from pathlib import Path

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
                          "lip_sync": True, "weight": 3.0}
    assert paths_a["take1"] == take and paths_a["c0"] == files[0]


def test_sidecar_records_seed_and_args(tmp_path):
    out = tmp_path / "carti_cut_v03.mp4"
    cc.write_sidecar(out, seed=123, tempo=130.2, args={"music": "t.wav", "density": 1.0},
                     schedule=cc.build_cut_schedule(BEATS, _pool(), seed=123))
    side = json.loads((tmp_path / "carti_cut_v03.json").read_text())
    assert side["seed"] == 123
    assert side["args"]["music"] == "t.wav"
    assert side["cuts"] == len(cc.build_cut_schedule(BEATS, _pool(), seed=123))
