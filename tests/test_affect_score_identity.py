# tests/test_affect_score_identity.py — clips are identified by their unique id (uid), not by
# filename stem: the same IMG_1234 name recurs in different folders, so a stem is not an identity.
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import affect_score as AS  # noqa: E402


def _clip(uid, folder):
    """A real Clip whose proxy shares the filename IMG_1234 with its namesake in another folder."""
    return AS.Clip(vid=uid, proxy=Path("/proxies") / folder / "IMG_1234.mp4",
                   times=[0.0, 1.0, 2.0, 3.0], intens=[5, 5, 5, 5],
                   dom_vector="neutral", dom_atmo="calm")


def _seq(*clips):
    return [{"clip": c, "seek": 0.0, "hold": 1.5, "target": 5.0, "achieved": 5.0, "tslope": 0,
             "vector": "neutral", "atmo": "calm", "section": "verse"} for c in clips]


def _ledger(tmp_path, monkeypatch, rows):
    monkeypatch.setattr(AS, "OUT", tmp_path)
    monkeypatch.setattr(AS, "USAGE_MANIFEST", tmp_path / "usage_manifest.jsonl")
    monkeypatch.setattr(AS, "SCRATCH", tmp_path / "scratch")
    (tmp_path / "usage_manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_load_usage_counts_keys_by_uid_with_stem_fallback(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [
        {"label": "T", "clip": "IMG_1234", "uid": "uidA"},
        {"label": "T", "clip": "IMG_1234", "uid": "uidA"},
        {"label": "T", "clip": "IMG_1234", "uid": "uidA"},
        {"label": "OLD", "clip": "MVI_9945", "backfill": True},   # older row: no uid
    ])
    assert AS.load_usage_counts() == Counter({"uidA": 3, "MVI_9945": 1})


def test_rarity_penalizes_only_the_clip_that_was_used(tmp_path, monkeypatch):
    a, b = _clip("uidA", "folder1"), _clip("uidB", "folder2")
    assert a.proxy.stem == b.proxy.stem == "IMG_1234"
    _ledger(tmp_path, monkeypatch, [{"label": "T", "clip": "IMG_1234", "uid": "uidA"}] * 3)
    usage = AS.load_usage_counts()
    # identical fit; A has 3 prior uses -> penalty 0.4 * 1.0 * sqrt(3) = 0.69 lands on A only.
    # A is listed first, so a stem-keyed lookup (which sees no penalty on either) would pick A.
    cost, clip, *_ = AS.pick_clip([a, b], set(), 5.0, 0, "", random.Random(0), jitter=0.0,
                                  usage=usage, rarity_w=0.4)
    assert clip.vid == "uidB"
    assert cost == 0.25                     # only the 0.25 atmosphere change; B carries no rarity penalty
    # and the namesake's history does not leak the other way
    usage = Counter({"uidB": 3})
    _, clip, *_ = AS.pick_clip([a, b], set(), 5.0, 0, "", random.Random(0), jitter=0.0,
                               usage=usage, rarity_w=0.4)
    assert clip.vid == "uidA"


def test_rarity_still_counts_legacy_rows_that_only_have_a_filename(tmp_path, monkeypatch):
    # the real ledger has 1,783 rows that predate uids and carry only the filename. They must still
    # count against the clip with that filename, or --rarity forgets that part of the history.
    old = AS.Clip(vid="uidOld", proxy=Path("/proxies/shoot/MVI_9945.mp4"), times=[0.0, 1.0, 2.0, 3.0],
                  intens=[5, 5, 5, 5], dom_vector="neutral", dom_atmo="calm")
    fresh = _clip("uidFresh", "folder1")
    _ledger(tmp_path, monkeypatch, [{"label": "OLD", "clip": "MVI_9945", "backfill": True}] * 4)
    usage = AS.load_usage_counts()
    # identical fit and `old` is listed first, so with its history ignored it would be picked.
    cost, clip, *_ = AS.pick_clip([old, fresh], set(), 5.0, 0, "", random.Random(0), jitter=0.0,
                                  usage=usage, rarity_w=0.4)
    assert clip.vid == "uidFresh"
    assert cost == 0.25                     # `old` would cost 0.25 + 0.4 * sqrt(4) = 1.05


def _run_main(monkeypatch, argv, clips, seq):
    """Run the real main() with the catalogue and composers faked; return the usage Counter
    snapshot each compose call saw, so the in-run accumulation is observable."""
    seen = []

    def fake_compose(*args, **kw):
        seen.append(dict(kw["usage"]))
        return list(seq)

    def fake_compose_audio(path, clips_, **kw):
        seen.append(dict(kw["usage"]))
        return list(seq), []

    monkeypatch.setattr(AS, "load_clips", lambda **kw: clips)
    monkeypatch.setattr(AS, "compose", fake_compose)
    monkeypatch.setattr(AS, "compose_audio", fake_compose_audio)
    monkeypatch.setattr(sys, "argv", ["affect_score.py"] + argv)
    assert AS.main() == 0
    return seen


def test_main_accumulates_usage_by_uid_score_path(tmp_path, monkeypatch):
    a, b = _clip("uidA", "folder1"), _clip("uidB", "folder2")
    _ledger(tmp_path, monkeypatch, [])
    seen = _run_main(monkeypatch, ["--score", "all", "--rarity", "--dry"], [a, b], _seq(a))
    # each compose call sees exactly what the earlier ones placed: uidA, not the shared stem
    assert seen[0] == {} and seen[1] == {"uidA": 1} and seen[2] == {"uidA": 2}


def test_main_accumulates_usage_by_uid_audio_path(tmp_path, monkeypatch):
    a, b = _clip("uidA", "folder1"), _clip("uidB", "folder2")
    _ledger(tmp_path, monkeypatch, [])
    seen = _run_main(monkeypatch, ["--audio", "song.wav", "--variations", "2", "--rarity", "--dry"],
                     [a, b], _seq(a, b))
    assert seen == [{}, {"uidA": 1, "uidB": 1}]


def test_sheet_has_uid_column_after_clip(tmp_path, monkeypatch):
    a, b = _clip("uidA", "folder1"), _clip("uidB", "folder2")
    _ledger(tmp_path, monkeypatch, [])
    AS.render("swell", _seq(a, b), dry=True)
    sheet = next(tmp_path.glob("*_cut.md")).read_text().splitlines()
    head = next(i for i, ln in enumerate(sheet) if ln.startswith("| # | section |"))
    assert sheet[head] == ("| # | section | clip | uid | seek | hold | tgt | got | slope | vector "
                           "| atmosphere |")
    assert sheet[head + 1] == ("|--:|---------|------|-----|-----:|-----:|:---:|:---:|:-----:|--------"
                               "|------------|")
    assert sheet[head + 2] == ("| 1 | verse | `IMG_1234` | `uidA` | 0.0s | 1.5s | 5.0 | 5.0 | → | "
                               "neutral | calm |")
    assert sheet[head + 3] == ("| 2 | verse | `IMG_1234` | `uidB` | 0.0s | 1.5s | 5.0 | 5.0 | → | "
                               "neutral | calm |")
