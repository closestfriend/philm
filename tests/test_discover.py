"""Search results must stay tied to playable proxy windows and originals."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from video_analyzer.discover import EmbeddingIndex
from video_analyzer import ui


def make_index(tmp_path: Path) -> tuple[Path, Path, Path]:
    index_dir = tmp_path / "index"
    (index_dir / "clips").mkdir(parents=True)
    proxy_root = tmp_path / "proxies"
    source_root = tmp_path / "sources"
    (proxy_root / "shoot").mkdir(parents=True)
    (source_root / "shoot").mkdir(parents=True)
    (proxy_root / "shoot" / "take.mp4").write_bytes(b"proxy")
    (source_root / "shoot" / "take.mov").write_bytes(b"original")
    (proxy_root / "shoot" / "other.mp4").write_bytes(b"proxy")
    rows = [
        {"key": "take", "rel": "shoot/take.mp4", "dur": 18,
         "windows": [[0, 8], [8, 18]]},
        {"key": "other", "rel": "shoot/other.mp4", "dur": 8,
         "windows": [[0, 8]]},
    ]
    (index_dir / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (index_dir / "dates.json").write_text(json.dumps({
        "take": {"orig": "shoot/take.mov", "date": "2020-01-02"}
    }))
    np.save(index_dir / "clips" / "take.npy", np.array([[1, 0], [0, 1]], dtype=np.float16))
    np.save(index_dir / "clips" / "other.npy", np.array([[0.8, 0.6]], dtype=np.float16))
    return index_dir, proxy_root, source_root


def test_search_returns_timecoded_moments_with_original_path(tmp_path):
    index_dir, proxy_root, source_root = make_index(tmp_path)
    index = EmbeddingIndex(index_dir, proxy_root, source_root)

    hits = index.search(np.array([0, 1], dtype=np.float32), limit=3)

    assert [(hit.key, hit.start_sec, hit.end_sec) for hit in hits] == [
        ("take", 8.0, 18.0), ("other", 0.0, 8.0), ("take", 0.0, 8.0)
    ]
    assert hits[0].original_path == source_root / "shoot" / "take.mov"
    assert hits[0].proxy_path == proxy_root / "shoot" / "take.mp4"
    assert hits[0].capture_date == "2020-01-02"


def test_lookup_rejects_unknown_or_unsafe_manifest_paths(tmp_path):
    index_dir, proxy_root, source_root = make_index(tmp_path)
    index = EmbeddingIndex(index_dir, proxy_root, source_root)
    assert index.proxy_for("missing") is None

    manifest = index_dir / "manifest.jsonl"
    manifest.write_text(manifest.read_text() + json.dumps({
        "key": "escape", "rel": "../escape.mp4", "dur": 1, "windows": [[0, 1]]
    }) + "\n")
    np.save(index_dir / "clips" / "escape.npy", np.array([[1, 0]], dtype=np.float16))
    with pytest.raises(ValueError, match="outside"):
        EmbeddingIndex(index_dir, proxy_root, source_root)


def test_discover_page_and_media_resolve_indexed_sources(tmp_path, monkeypatch):
    index_dir, proxy_root, source_root = make_index(tmp_path)
    index = EmbeddingIndex(index_dir, proxy_root, source_root)
    monkeypatch.setattr(ui, "get_discover_index", lambda: index)
    monkeypatch.setattr(ui, "encode_query", lambda query: np.array([0, 1]))
    client = TestClient(ui.app)

    page = client.get("/discover", params={"q": "dark crossing"})
    assert page.status_code == 200
    assert "shoot/take.mov" in page.text
    assert "00:00:08–00:00:18" in page.text
    assert "/discover/media/take" in page.text
    assert client.get("/discover/media/take").content == b"proxy"
    assert client.get("/discover/media/missing").status_code == 404
    assert client.get("/discover/thumb/missing/0.jpg").status_code == 404
