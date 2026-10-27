"""Read an EmbeddingGemma index as timecoded, playable search results."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MEDIA_ROOT = Path("/Volumes/2025_exSSD_2tb/Photography + Video")
# The merged index covers every proxy; its `rel` paths start with the set name.
DEFAULT_INDEX = MEDIA_ROOT / "_embeddings" / "_all"
DEFAULT_PROXIES = MEDIA_ROOT / "_proxies"
DEFAULT_SOURCES = MEDIA_ROOT
QUERY_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "embed_local.py"


def encode_query(query: str) -> np.ndarray:
    """Use the embedding script's cached heavyweight environment for text only."""
    result = subprocess.run(
        ["uv", "run", "--offline", "--script", str(QUERY_SCRIPT), "query-vector", query],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "HF_HUB_OFFLINE": "1"},
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-800:] or "query encoder failed")
    return np.asarray(json.loads(result.stdout), dtype=np.float32)


@dataclass(frozen=True)
class Moment:
    key: str
    rel: str
    filename: str
    start_sec: float
    end_sec: float
    score: float
    proxy_path: Path
    original_path: Path | None
    capture_date: str | None
    window_index: int


def _inside(root: Path, relative: str, *, follow_symlinks: bool = True) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"indexed path outside media root: {relative}")
    path = root / relative_path
    if not follow_symlinks:
        return path
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"indexed path outside media root: {relative}") from exc
    return path


class EmbeddingIndex:
    def __init__(self, index_dir: Path, proxy_root: Path, source_root: Path):
        self.index_dir = Path(index_dir)
        self.proxy_root = Path(proxy_root)
        self.source_root = Path(source_root)
        dates_file = self.index_dir / "dates.json"
        dates = json.loads(dates_file.read_text()) if dates_file.exists() else {}
        self.proxies: dict[str, Path] = {}
        moments: list[Moment] = []
        vectors: list[np.ndarray] = []
        manifest = self.index_dir / "manifest.jsonl"
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key, rel = row["key"], row["rel"]
            proxy = _inside(self.proxy_root, rel)
            self.proxies[key] = proxy
            metadata = dates.get(key, {})
            original_rel = metadata.get("orig")
            # Some originals are symlinks to an archival drive. Preserve their catalog path.
            original = _inside(self.source_root, original_rel, follow_symlinks=False) if original_rel else None
            clip_vectors = np.load(self.index_dir / "clips" / f"{key}.npy").astype(np.float32)
            if clip_vectors.ndim != 2 or clip_vectors.shape[0] != len(row["windows"]):
                raise ValueError(f"vector/window count mismatch: {rel}")
            for wi, ((start, end), vector) in enumerate(zip(row["windows"], clip_vectors)):
                norm = np.linalg.norm(vector)
                if not np.isfinite(norm) or norm == 0:
                    raise ValueError(f"invalid embedding: {rel} window {wi}")
                vectors.append(vector / norm)
                moments.append(Moment(
                    key=key, rel=rel, filename=Path(rel).name,
                    start_sec=float(start), end_sec=float(end), score=0.0,
                    proxy_path=proxy, original_path=original,
                    capture_date=metadata.get("date"), window_index=wi,
                ))
        self.moments = moments
        self.vectors = np.stack(vectors) if vectors else np.empty((0, 768), dtype=np.float32)

    def proxy_for(self, key: str) -> Path | None:
        return self.proxies.get(key)

    def moment_for(self, key: str, window_index: int) -> Moment | None:
        return next((m for m in self.moments if m.key == key and m.window_index == window_index), None)

    def search(self, query_vector: np.ndarray, limit: int = 24) -> list[Moment]:
        if not self.moments:
            return []
        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        if query.shape[0] != self.vectors.shape[1]:
            raise ValueError("query dimension does not match index")
        norm = np.linalg.norm(query)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError("invalid query vector")
        scores = self.vectors @ (query / norm)
        order = np.argsort(-scores, kind="stable")[:max(0, limit)]
        return [Moment(**{**self.moments[i].__dict__, "score": float(scores[i])}) for i in order]
