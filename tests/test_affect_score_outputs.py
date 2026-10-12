# tests/test_affect_score_outputs.py — output safety of affect_score: never overwrite a render, record
# the effective settings, honour a RECIPE override, and report per-section (not per-label) cut stats.
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import affect_score as AS  # noqa: E402


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(AS, "OUT", tmp_path)
    monkeypatch.setattr(AS, "USAGE_MANIFEST", tmp_path / "usage_manifest.jsonl")
    monkeypatch.setattr(AS, "SCRATCH", tmp_path / "scratch")
    monkeypatch.setattr(AS, "RECIPE", None, raising=False)
    return tmp_path


def _cut(t0, hold, section="drop"):
    clip = SimpleNamespace(proxy=Path("clipA.mp4"), vid="u", tone="t", dom_atmo="a")
    return {"clip": clip, "seek": 0.0, "hold": hold, "t0": t0, "t1": t0 + hold, "target": 5.0,
            "achieved": 5.0, "tslope": 0, "vector": "v", "atmo": "calm", "section": section}


# ---------------------------------------------------------------- unique names
def test_free_name_is_kept(out):
    assert AS.unique_name("MIRROR_V01") == "MIRROR_V01"


@pytest.mark.parametrize("existing", ["{n}_cut.md", "{n}_rough.mp4", "{n}_picture.mp4"])
def test_any_one_of_three_files_forces_r2(out, existing, capsys):
    (out / existing.format(n="MIRROR_V01")).write_text("x")
    assert AS.unique_name("MIRROR_V01") == "MIRROR_V01_r2"
    assert "MIRROR_V01_r2" in capsys.readouterr().out


def test_r2_taken_goes_to_r3(out):
    (out / "MIRROR_V01_cut.md").write_text("x")
    (out / "MIRROR_V01_r2_rough.mp4").write_text("x")
    assert AS.unique_name("MIRROR_V01") == "MIRROR_V01_r3"


def test_lowercase_label_is_uppercased_but_suffix_stays_lowercase(out):
    (out / "SWELL_cut.md").write_text("x")
    assert AS.unique_name("swell") == "SWELL_r2"


def test_render_writes_r2_sheet_with_lowercase_suffix(out):
    AS.render("MIRROR_r2", [_cut(0.0, 4.0)], dry=True)
    assert [p.name for p in out.iterdir()] == ["MIRROR_r2_cut.md"]   # listing: exists() is case-blind on APFS


def _run_main(monkeypatch, argv, seq):
    monkeypatch.setattr(AS, "load_clips", lambda **kw: [])
    monkeypatch.setattr(AS, "compose", lambda *a, **kw: seq)
    monkeypatch.setattr(sys, "argv", ["affect_score.py"] + argv)
    return AS.main()


def test_score_path_second_dry_run_does_not_overwrite(out, monkeypatch):
    seq = [_cut(0.0, 4.0)]
    _run_main(monkeypatch, ["--score", "swell", "--dry"], seq)
    first = (out / "SWELL_cut.md").read_text()
    _run_main(monkeypatch, ["--score", "swell", "--dry", "--diversity", "0.9"], seq)
    assert (out / "SWELL_cut.md").read_text() == first
    assert "diversity=0.9" in (out / "SWELL_r2_cut.md").read_text()
    _run_main(monkeypatch, ["--score", "swell", "--dry"], seq)
    assert (out / "SWELL_r3_cut.md").exists()


def test_ledger_label_is_final_unique_name_on_score_path(out, monkeypatch):
    seen = {}
    monkeypatch.setattr(AS, "append_usage", lambda label, seq: seen.setdefault("labels", []).append(label))

    def fake_render(name, seq, dry, audio=None, sections=None, settings=None):
        seen.setdefault("rendered", []).append(name)
        (AS.OUT / f"{name}_rough.mp4").write_text("x")

    monkeypatch.setattr(AS, "render", fake_render)
    seq = [_cut(0.0, 4.0)]
    _run_main(monkeypatch, ["--score", "swell", "--label", "cast"], seq)
    _run_main(monkeypatch, ["--score", "swell", "--label", "cast"], seq)
    assert seen["labels"] == ["SWELL_CAST", "SWELL_CAST_r2"]
    assert seen["rendered"] == seen["labels"]


def test_audio_path_unique_name_seed_and_ledger(out, monkeypatch):
    seen = {}
    monkeypatch.setattr(AS, "append_usage", lambda label, seq: seen.setdefault("labels", []).append(label))
    monkeypatch.setattr(AS, "compose_audio", lambda *a, **kw: ([_cut(0.0, 4.0)], []))
    monkeypatch.setattr(AS, "load_clips", lambda **kw: [])

    def fake_render(name, seq, dry, audio=None, sections=None, settings=None):
        seen.setdefault("rendered", []).append(name)
        (AS.OUT / f"{name}_picture.mp4").write_text("x")

    monkeypatch.setattr(AS, "render", fake_render)
    argv = ["--audio", "/x/my track.wav", "--seed", "1", "--label", "cast"]
    for _ in range(2):
        monkeypatch.setattr(sys, "argv", ["affect_score.py"] + argv)
        AS.main()
    # V01 is seed 1, not version 1; the rerun is r2 of the same seed.
    assert seen["labels"] == ["MY_TRACK_CAST_V01", "MY_TRACK_CAST_V01_r2"]
    assert seen["rendered"] == seen["labels"]


# ---------------------------------------------------------------- settings line
def test_settings_line_under_recipe(out, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["affect_score.py", "--audio", "t.wav"])
    AS.render("S", [_cut(0.0, 4.0)], dry=True,
              settings={"fit_tol": 0.6, "rarity_w": 0.0, "topk": 8, "seed": 3, "target_map": "quantile"})
    lines = (out / "S_cut.md").read_text().split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("**Recipe:**"))
    assert lines[i + 1] == "**Settings:** `fit_tol=0.6 rarity_w=0.0 topk=8 seed=3 target_map=quantile`"


def test_settings_line_omitted_when_not_supplied(out):
    AS.render("S", [_cut(0.0, 4.0)], dry=True)
    assert "**Settings:**" not in (out / "S_cut.md").read_text()


def test_main_records_effective_settings(out, monkeypatch):
    monkeypatch.setattr(AS, "FIT_TOL", 0.6)   # main() rebinds this global; let monkeypatch restore it
    _run_main(monkeypatch, ["--score", "swell", "--dry", "--rarity", "--select", "topk", "--topk", "5",
                            "--fit-tol", "0.25", "--diversity", "0.9"], [_cut(0.0, 4.0)])
    text = (out / "SWELL_cut.md").read_text()
    line = next(l for l in text.split("\n") if l.startswith("**Settings:**"))
    for pair in ("fit_tol=0.25", "rarity_w=0.4", "content_w=0.0", "topk=5", "diversity=0.9"):
        assert pair in line


# ---------------------------------------------------------------- RECIPE override
def test_recipe_override_replaces_argv(out, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["affect_score.py", "--wrong"])
    monkeypatch.setattr(AS, "RECIPE", ["embed_cut.py", "axis", "--label", "my label"])
    AS.render("S", [_cut(0.0, 4.0)], dry=True)
    text = (out / "S_cut.md").read_text()
    assert "**Recipe:** `embed_cut.py axis --label 'my label'`" in text
    assert "--wrong" not in text


def test_recipe_none_keeps_argv(out, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["affect_score.py", "--audio", "a b.wav"])
    AS.render("S", [_cut(0.0, 4.0)], dry=True)
    assert "**Recipe:** `--audio 'a b.wav'`" in (out / "S_cut.md").read_text()


# ---------------------------------------------------------------- section table
SECTIONS = [AS.Section(0.0, 10.0, "build"), AS.Section(10.0, 26.0, "drop"), AS.Section(26.0, 40.0, "drop")]
SEQ = ([_cut(0.0, 5.0, "build"), _cut(5.0, 5.0, "build")]
       + [_cut(10.0 + 4 * k, 4.0, "drop") for k in range(4)]
       + [_cut(26.0, 7.0, "drop"), _cut(33.0, 7.0, "drop")])


def _rows(text):
    return [l for l in text.split("\n") if l.startswith("| ") and "**" in l]


def test_section_rows_count_only_their_own_span(out):
    AS.render("S", SEQ, dry=True, sections=SECTIONS)
    assert _rows((out / "S_cut.md").read_text()) == [
        "| 0.0s | 10.0s | **build** | 10.0s | 2 | 5.00s | 12.0 |",
        "| 10.0s | 26.0s | **drop** | 16.0s | 4 | 4.00s | 15.0 |",
        "| 26.0s | 40.0s | **drop** | 14.0s | 2 | 7.00s | 8.6 |",
    ]


def test_section_rows_fall_back_to_cumulative_holds_without_t0(out):
    seq = []
    for s in SEQ:
        s = dict(s)
        del s["t0"], s["t1"]
        seq.append(s)
    AS.render("S", seq, dry=True, sections=SECTIONS)
    assert _rows((out / "S_cut.md").read_text())[1] == "| 10.0s | 26.0s | **drop** | 16.0s | 4 | 4.00s | 15.0 |"
