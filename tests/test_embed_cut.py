# tests/test_embed_cut.py — the exact cut file (JSON sidecar) that lets a proxy cut be rebuilt
# from the originals, and a render that comes out exactly as long as that file says.
import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import embed_cut as ec  # noqa: E402
import embed_local as el  # noqa: E402

DIM = 4


def _index(tmp_path, dates=True):
    """A real two-clip index on disk, in the layout embed_local writes."""
    out = tmp_path / "index"
    (out / "clips").mkdir(parents=True)
    rows = [{"rel": "spain vids/IMG_5625.mp4", "dur": 41.37, "windows": [[0.0, 32.0], [32.0, 41.0]]},
            {"rel": "IMG_9413.mp4", "dur": 7.0, "windows": [[0.0, 7.0]]}]
    for r in rows:
        r["key"] = el.key_for(r["rel"])
        np.save(out / "clips" / f"{r['key']}.npy", np.ones((len(r["windows"]), DIM), dtype=np.float32))
    (out / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    if dates:
        (out / "dates.json").write_text(json.dumps({
            rows[0]["key"]: {"date": "2018-07-05", "orig": "spain vids/IMG_5625.m4v"},
            rows[1]["key"]: {"date": "2019-01-02", "orig": "IMG_9413.MOV"}}))
    return ec.Index(out, dim=DIM)


def _cut(**over):
    cut = {"w": 0, "t0": 0.0, "t1": 0.4, "hold": 0.4, "seek": 1.6, "rel": "IMG_9413.mp4",
           "orig": "IMG_9413.MOV", "win": (0.0, 7.0), "date": "2019-01-02", "step": "n", "sim": 0.688}
    return {**cut, **over}


def _write(tmp_path, monkeypatch, seq):
    monkeypatch.setattr(ec, "OUT_DIR", tmp_path)
    p = ec.sidecar("T_v01", "silent", seq, None, None, ["a note"], "stretch", (360, 640),
                   Path("/proxies"))
    return json.loads(p.read_text())


def test_cast_carries_the_original_path(tmp_path):
    idx = _index(tmp_path)
    seq = ec.cast(idx, [{"w": 1}, {"w": 2}], [(0.0, 0.4), (0.4, 0.8)], random.Random(1))
    assert [s["orig"] for s in seq] == ["spain vids/IMG_5625.m4v", "IMG_9413.MOV"]


def test_cast_without_a_dates_file_has_no_original(tmp_path):
    idx = _index(tmp_path, dates=False)
    seq = ec.cast(idx, [{"w": 0}], [(0.0, 0.4)], random.Random(1))
    assert seq[0]["orig"] is None


def test_sidecar_keeps_the_in_point_unrounded(tmp_path, monkeypatch):
    doc = _write(tmp_path, monkeypatch, [_cut(seek=38.4567891)])
    assert doc["cuts"][0]["seek"] == 38.4567891      # the sheet would print 38.5


def test_sidecar_names_proxy_and_original_for_each_cut(tmp_path, monkeypatch):
    doc = _write(tmp_path, monkeypatch, [_cut()])
    assert doc["proxy_root"] == "/proxies"
    assert (doc["cuts"][0]["rel"], doc["cuts"][0]["orig"]) == ("IMG_9413.mp4", "IMG_9413.MOV")


def test_sidecar_frame_counts_follow_the_24fps_grid(tmp_path, monkeypatch):
    # three 0.4s cuts are 9.6 frames each; on the grid they land as 10, 9, 10 (29 in all), which is
    # what the render encodes. Counting hold x fps per cut would give 10, 10, 10.
    seq = [_cut(t0=0.0, t1=0.4), _cut(t0=0.4, t1=0.8), _cut(t0=0.8, t1=1.2)]
    doc = _write(tmp_path, monkeypatch, seq)
    assert doc["fps"] == 24
    assert [c["frames"] for c in doc["cuts"]] == [10, 9, 10]


def test_sidecar_keeps_recipe_arguments_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["embed_cut.py", "silent", "--prompt", "a mirror"])
    doc = _write(tmp_path, monkeypatch, [_cut()])
    assert doc["recipe"] == ["silent", "--prompt", "a mirror"]


def test_dry_run_writes_the_sidecar_beside_the_sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "OUT_DIR", tmp_path / "cuts")
    idx = _index(tmp_path)
    a = argparse.Namespace(label="T", fit="stretch", canvas=[360, 640], dry=True)
    seq = ec.cast(idx, [{"w": 2}], [(0.0, 0.4)], random.Random(1))
    ec.finish(a, "silent", idx, seq, None, None, [])
    assert (tmp_path / "cuts" / "T_v01_cut.md").exists()
    doc = json.loads((tmp_path / "cuts" / "T_v01_cut.json").read_text())
    assert (doc["name"], doc["fit"], doc["canvas"]) == ("T_v01", "stretch", [360, 640])
    assert doc["cuts"][0]["orig"] == "IMG_9413.MOV"


def _frame_count(video: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                        "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip())


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_render_holds_a_clip_that_ends_just_short_of_its_cut(tmp_path, monkeypatch):
    # a 26-frame 30fps clip (0.87s) has to fill a 1.00s cut, 24 frames on the grid. ffmpeg gets 22
    # frames out of it; the rough must still be 24, or every later cut lands ahead of the music.
    monkeypatch.setattr(ec, "OUT_DIR", tmp_path / "cuts")
    monkeypatch.setattr(ec, "SCRATCH", tmp_path / "scratch")
    (tmp_path / "cuts").mkdir()
    idx = _index(tmp_path)
    idx.root = tmp_path / "proxies"
    idx.root.mkdir()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=202x360:rate=30",
                    "-frames:v", "26", "-pix_fmt", "yuv420p", str(idx.root / "IMG_9413.mp4")], check=True)
    rough = ec.render("T_v01", idx, [_cut(w=2, t0=0.0, t1=1.0, hold=1.0, seek=0.0)], None,
                      "stretch", (360, 640))
    assert _frame_count(rough) == 24


# ----------------------------------------------------------------------------- axis mode
import affect_score as AS  # noqa: E402


def _axis(tmp_path, monkeypatch, z, invert=False, extra=(), argv=("axis",)):
    """Run run_axis() on the tiny index with fixed per-window scores and a stubbed engine.
    Windows are: clip 0 -> w0, w1; clip 1 -> w2. Returns (index, namespace, what the engine saw)."""
    idx = _index(tmp_path)
    seen = {}

    def fake_main():
        seen["argv"] = list(sys.argv)
        seen["recipe"] = AS.RECIPE
        return 0

    real_index = ec.Index
    monkeypatch.setattr(ec, "Index", lambda out: real_index(out, dim=DIM))
    monkeypatch.setattr(ec, "axis_scores", lambda i, name: np.array(z, dtype=float))
    monkeypatch.setattr(ec, "OUT_DIR", tmp_path / "cuts")
    monkeypatch.setattr(ec, "SCRATCH", tmp_path / "scratch")
    monkeypatch.setattr(sys, "argv", ["embed_cut.py", *argv])
    for g in ("CATALOG", "OUT", "USAGE_MANIFEST", "SCRATCH", "SEG_VF"):
        monkeypatch.setattr(AS, g, getattr(AS, g))      # so teardown restores what run_axis rewrites
    monkeypatch.setattr(AS, "RECIPE", None, raising=False)
    monkeypatch.setattr(AS, "main", fake_main)
    a = argparse.Namespace(index=str(tmp_path / "index"), axis="dwelling", invert=invert,
                           track="t.mp3", dry=True, fit="stretch", canvas=[360, 640], extra=list(extra))
    ec.run_axis(a)
    return idx, a, seen


def _rows(idx, a):
    cat = Path(a.index) / "axis_catalog" / (a.axis + ("_inv" if a.invert else ""))
    out = []
    for r in idx.rows:
        tcs = json.loads((cat / f"{r['key']}.json").read_text())["analyses"]["affect"]["timecodes"]
        out.append([(t["atmosphere"], t["intensity"]) for t in tcs])
    return out


def test_axis_labels_and_ranks_follow_the_score(tmp_path, monkeypatch):
    # z = [1, -1, 0] -> quantile ranks [1, 0, 0.5] -> intensity floor(1+9r) = [10, 1, 5]
    idx, a, _ = _axis(tmp_path, monkeypatch, [1.0, -1.0, 0.0])
    assert _rows(idx, a) == [[("dwelling high", 10)] * 2 + [("dwelling low", 1)] * 2,
                             [("dwelling mid", 5)] * 2]


def test_inverted_axis_keeps_the_true_label_but_flips_the_rank(tmp_path, monkeypatch):
    # the airport window (z = -1) is still "dwelling low"; only its intensity becomes 10
    idx, a, _ = _axis(tmp_path, monkeypatch, [1.0, -1.0, 0.0], invert=True)
    assert _rows(idx, a) == [[("dwelling high", 1)] * 2 + [("dwelling low", 10)] * 2,
                             [("dwelling mid", 5)] * 2]


def test_axis_hands_the_engine_the_real_recipe(tmp_path, monkeypatch):
    argv = ("axis", "--track", "t.mp3", "--axis", "dwelling", "--invert", "--", "--variations", "2")
    _, _, seen = _axis(tmp_path, monkeypatch, [1.0, -1.0, 0.0], invert=True, argv=argv,
                       extra=["--variations", "2"])
    assert seen["recipe"] == ["embed_cut.py", *argv]
    assert seen["argv"][0] == "affect_score.py"          # argv itself is still rewritten for the engine


@pytest.mark.parametrize("extra", [["--pool-tone", "dramatic"], ["--pool-tone=dramatic"],
                                   ["--pool-best-for", "hook"], ["--pool-best", "hook"]])
def test_axis_refuses_pool_flags_that_empty_the_pool(tmp_path, monkeypatch, extra):
    flag = "--pool-tone" if "tone" in extra[0] else "--pool-best-for"
    with pytest.raises(SystemExit) as e:
        _axis(tmp_path, monkeypatch, [1.0, -1.0, 0.0], extra=extra)
    assert flag in str(e.value) and "empty" in str(e.value)


def test_axis_refuses_before_scoring_anything(tmp_path, monkeypatch):
    def boom(*_):
        raise AssertionError("scored before refusing")
    monkeypatch.setattr(ec, "axis_scores", boom)
    _index(tmp_path)
    monkeypatch.setattr(ec, "Index", lambda out: pytest.fail("loaded the index before refusing"))
    a = argparse.Namespace(index=str(tmp_path / "index"), axis="dwelling", invert=False,
                           track="t.mp3", dry=True, fit="stretch", canvas=[360, 640],
                           extra=["--pool-tone", "dramatic"])
    with pytest.raises(SystemExit):
        ec.run_axis(a)


def test_axis_warns_about_a_flag_that_does_nothing_and_carries_on(tmp_path, monkeypatch, capsys):
    _, _, seen = _axis(tmp_path, monkeypatch, [1.0, -1.0, 0.0],
                       extra=["--pool-tone-or-best-for", "--variations", "2"])
    err = capsys.readouterr().err
    assert "--pool-tone-or-best-for" in err and "ignored" in err
    assert seen["argv"][-3:] == ["--pool-tone-or-best-for", "--variations", "2"]   # still passed on


def test_axis_is_quiet_about_pool_flags_that_work(tmp_path, monkeypatch, capsys):
    # intensity, energy and root all read fields the synthetic catalogue does fill
    _axis(tmp_path, monkeypatch, [1.0, -1.0, 0.0],
          extra=["--pool-min-intensity", "5", "--pool-min-energy", "5", "--pool-root", "/x"])
    assert "ignored" not in capsys.readouterr().err
