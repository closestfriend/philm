"""
SQLite Archive Layer for Video Analyzer.

Unified database for storing video analyses across both TS and Python CLIs.
Enables search, querying, project management, and documentary generation.
"""

import os
import sqlite3
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field

# Default archive location
DEFAULT_ARCHIVE_PATH = Path.home() / ".vanalyze" / "archive.db"

# Video extensions to scan
VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".mov", ".avi", ".mpg", ".mpeg", ".mkv", ".m4v",
    ".MP4", ".WEBM", ".MOV", ".AVI", ".MPG", ".MPEG", ".MKV", ".M4V",
}


@dataclass
class VideoRecord:
    """A video in the archive."""
    id: int
    path: str
    filename: str
    file_hash: Optional[str]
    file_size: int
    duration_sec: Optional[float]
    date_recorded: Optional[str]
    location: Optional[str]
    camera: Optional[str]
    description: Optional[str]
    processed_at: Optional[str]
    processing_cost: Optional[float]
    tier: int  # 0=unprocessed, 1=basic (paragraph/gaze/sublime), 2=full


@dataclass
class AnalysisMoment:
    """A single analyzed moment from any mode."""
    video_id: int
    mode: str
    timecode: str
    data: dict  # Full JSON data for this moment


class Archive:
    """SQLite-backed video archive."""

    SCHEMA = """
    -- Core video table
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE NOT NULL,
        filename TEXT NOT NULL,
        file_hash TEXT,
        file_size INTEGER,
        duration_sec REAL,

        -- Extracted/inferred metadata
        date_recorded DATE,
        location TEXT,
        camera TEXT,

        -- Processing state
        processed_at TIMESTAMP,
        processing_cost REAL,
        tier INTEGER DEFAULT 0,

        -- Denormalized for fast search
        description TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Gaze moments (Mulvey)
    CREATE TABLE IF NOT EXISTS gaze_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        gaze_type TEXT NOT NULL,
        subject_position TEXT,
        power_dynamic TEXT,
        breaks_fourth_wall BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Sublime moments (Kant/Burke)
    CREATE TABLE IF NOT EXISTS sublime_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        sublime_type TEXT NOT NULL,
        description TEXT,
        overwhelm_source TEXT,
        recovery BOOLEAN,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Affect moments (Massumi)
    CREATE TABLE IF NOT EXISTS affect_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        intensity INTEGER,
        atmosphere TEXT,
        vector TEXT,
        captures BOOLEAN,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Camera moments (kinetic analysis)
    CREATE TABLE IF NOT EXISTS camera_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        stability TEXT,
        frenetic INTEGER,
        intentional_motion TEXT,
        proximity INTEGER,
        restlessness BOOLEAN,
        operator_presence TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Generic moments table for all other modes (Benjamin, Foucault, etc.)
    -- Uses JSON blob for flexibility
    CREATE TABLE IF NOT EXISTS generic_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        mode TEXT NOT NULL,
        timecode TEXT NOT NULL,
        data JSON NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Documentary projects
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Project clips (saved queries or manual selections)
    CREATE TABLE IF NOT EXISTS project_clips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode_start TEXT,
        timecode_end TEXT,
        sequence_order INTEGER,
        notes TEXT,
        source_query TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Processing log for cost tracking and resumption
    CREATE TABLE IF NOT EXISTS processing_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        mode TEXT NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        success BOOLEAN,
        error_message TEXT,
        tokens_used INTEGER,
        cost REAL
    );

    -- Indexes for fast querying
    CREATE INDEX IF NOT EXISTS idx_videos_path ON videos(path);
    CREATE INDEX IF NOT EXISTS idx_videos_tier ON videos(tier);
    CREATE INDEX IF NOT EXISTS idx_videos_date ON videos(date_recorded);
    CREATE INDEX IF NOT EXISTS idx_gaze_type ON gaze_moments(gaze_type);
    CREATE INDEX IF NOT EXISTS idx_gaze_fourth_wall ON gaze_moments(breaks_fourth_wall);
    CREATE INDEX IF NOT EXISTS idx_sublime_type ON sublime_moments(sublime_type);
    CREATE INDEX IF NOT EXISTS idx_sublime_recovery ON sublime_moments(recovery);
    CREATE INDEX IF NOT EXISTS idx_affect_intensity ON affect_moments(intensity);
    CREATE INDEX IF NOT EXISTS idx_camera_frenetic ON camera_moments(frenetic);
    CREATE INDEX IF NOT EXISTS idx_generic_mode ON generic_moments(mode);

    -- Full-text search on descriptions
    CREATE VIRTUAL TABLE IF NOT EXISTS video_fts USING fts5(
        path,
        filename,
        description,
        content='videos',
        content_rowid='id'
    );

    -- Triggers to keep FTS in sync
    CREATE TRIGGER IF NOT EXISTS videos_ai AFTER INSERT ON videos BEGIN
        INSERT INTO video_fts(rowid, path, filename, description)
        VALUES (new.id, new.path, new.filename, new.description);
    END;

    CREATE TRIGGER IF NOT EXISTS videos_ad AFTER DELETE ON videos BEGIN
        INSERT INTO video_fts(video_fts, rowid, path, filename, description)
        VALUES ('delete', old.id, old.path, old.filename, old.description);
    END;

    CREATE TRIGGER IF NOT EXISTS videos_au AFTER UPDATE ON videos BEGIN
        INSERT INTO video_fts(video_fts, rowid, path, filename, description)
        VALUES ('delete', old.id, old.path, old.filename, old.description);
        INSERT INTO video_fts(rowid, path, filename, description)
        VALUES (new.id, new.path, new.filename, new.description);
    END;
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_ARCHIVE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_db(self):
        """Initialize database schema."""
        conn = self.connect()
        conn.executescript(self.SCHEMA)
        conn.commit()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =========================================================================
    # VIDEO MANAGEMENT
    # =========================================================================

    def add_video(
        self,
        path: Path,
        file_size: Optional[int] = None,
        duration_sec: Optional[float] = None,
        file_hash: Optional[str] = None,
    ) -> int:
        """Add a video to the archive. Returns video ID."""
        conn = self.connect()
        path_str = str(path.resolve())

        if file_size is None:
            file_size = path.stat().st_size if path.exists() else 0

        try:
            cursor = conn.execute(
                """
                INSERT INTO videos (path, filename, file_size, duration_sec, file_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (path_str, path.name, file_size, duration_sec, file_hash)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Already exists, get existing ID
            row = conn.execute(
                "SELECT id FROM videos WHERE path = ?", (path_str,)
            ).fetchone()
            return row["id"]

    def get_video(self, video_id: int) -> Optional[dict]:
        """Get video by ID."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_video_by_path(self, path: Path) -> Optional[dict]:
        """Get video by path."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM videos WHERE path = ?", (str(path.resolve()),)
        ).fetchone()
        return dict(row) if row else None

    def update_video(self, video_id: int, **kwargs):
        """Update video metadata."""
        conn = self.connect()
        allowed = {
            "description", "duration_sec", "date_recorded", "location",
            "camera", "tier", "processed_at", "processing_cost"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [video_id]

        conn.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", values)
        conn.commit()

    def scan_folder(
        self,
        folder: Path,
        recursive: bool = True,
        exclude_patterns: Optional[list[str]] = None
    ) -> tuple[int, int]:
        """
        Scan folder for videos and add to archive.

        Returns (new_count, existing_count).
        """
        exclude_patterns = exclude_patterns or []
        new_count = 0
        existing_count = 0

        def should_exclude(path: Path) -> bool:
            return any(p.lower() in str(path).lower() for p in exclude_patterns)

        if recursive:
            files = folder.rglob("*")
        else:
            files = folder.glob("*")

        for file_path in files:
            if not file_path.is_file():
                continue
            if file_path.suffix not in VIDEO_EXTENSIONS:
                continue
            if should_exclude(file_path):
                continue

            existing = self.get_video_by_path(file_path)
            if existing:
                existing_count += 1
            else:
                self.add_video(file_path)
                new_count += 1

        return new_count, existing_count

    def get_unprocessed(self, tier: int = 0, limit: int = 100) -> list[dict]:
        """Get videos that haven't been processed to the specified tier."""
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT * FROM videos
            WHERE tier < ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (tier + 1, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # ANALYSIS STORAGE
    # =========================================================================

    def store_gaze_analysis(self, video_id: int, timecodes: list[dict]):
        """Store gaze analysis results."""
        conn = self.connect()
        # Clear existing
        conn.execute("DELETE FROM gaze_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO gaze_moments
                (video_id, timecode, gaze_type, subject_position, power_dynamic, breaks_fourth_wall)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("gaze_type", ""),
                    t.get("subject_position", ""),
                    t.get("power_dynamic", ""),
                    t.get("breaks_fourth_wall", False),
                )
            )
        conn.commit()

    def store_sublime_analysis(self, video_id: int, timecodes: list[dict]):
        """Store sublime analysis results."""
        conn = self.connect()
        conn.execute("DELETE FROM sublime_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO sublime_moments
                (video_id, timecode, sublime_type, description, overwhelm_source, recovery)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("sublime_type", ""),
                    t.get("description", ""),
                    t.get("overwhelm_source", ""),
                    t.get("recovery"),
                )
            )
        conn.commit()

    def store_affect_analysis(self, video_id: int, timecodes: list[dict]):
        """Store affect analysis results."""
        conn = self.connect()
        conn.execute("DELETE FROM affect_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO affect_moments
                (video_id, timecode, intensity, atmosphere, vector, captures)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("intensity"),
                    t.get("atmosphere", ""),
                    t.get("vector", ""),
                    t.get("captures"),
                )
            )
        conn.commit()

    def store_camera_analysis(self, video_id: int, timecodes: list[dict]):
        """Store camera analysis results."""
        conn = self.connect()
        conn.execute("DELETE FROM camera_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO camera_moments
                (video_id, timecode, stability, frenetic, intentional_motion,
                 proximity, restlessness, operator_presence, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("stability", ""),
                    t.get("frenetic"),
                    t.get("intentional_motion", ""),
                    t.get("proximity"),
                    t.get("restlessness"),
                    t.get("operator_presence", ""),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_generic_analysis(self, video_id: int, mode: str, timecodes: list[dict]):
        """Store analysis for any mode as JSON."""
        conn = self.connect()
        conn.execute(
            "DELETE FROM generic_moments WHERE video_id = ? AND mode = ?",
            (video_id, mode)
        )

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO generic_moments (video_id, mode, timecode, data)
                VALUES (?, ?, ?, ?)
                """,
                (video_id, mode, t.get("time", ""), json.dumps(t))
            )
        conn.commit()

    def store_analysis(self, video_id: int, mode: str, result: dict):
        """
        Store analysis result, routing to appropriate table.
        Updates video description and tier.
        """
        timecodes = result.get("timecodes", [])
        description = result.get("video_description", "")

        # Update video description if present
        if description:
            self.update_video(video_id, description=description)

        # Route to specific table or generic
        if mode == "gaze":
            self.store_gaze_analysis(video_id, timecodes)
        elif mode == "sublime":
            self.store_sublime_analysis(video_id, timecodes)
        elif mode == "affect":
            self.store_affect_analysis(video_id, timecodes)
        elif mode == "camera":
            self.store_camera_analysis(video_id, timecodes)
        else:
            self.store_generic_analysis(video_id, mode, timecodes)

    # =========================================================================
    # SEARCH & QUERY
    # =========================================================================

    def search_text(self, query: str, limit: int = 50) -> list[dict]:
        """Full-text search on video descriptions and filenames."""
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT v.* FROM videos v
            JOIN video_fts fts ON v.id = fts.rowid
            WHERE video_fts MATCH ?
            LIMIT ?
            """,
            (query, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def search_gaze(
        self,
        gaze_type: Optional[str] = None,
        fourth_wall: Optional[bool] = None,
        limit: int = 50
    ) -> list[dict]:
        """Search gaze moments."""
        conn = self.connect()
        conditions = []
        params = []

        if gaze_type:
            conditions.append("g.gaze_type = ?")
            params.append(gaze_type)
        if fourth_wall is not None:
            conditions.append("g.breaks_fourth_wall = ?")
            params.append(fourth_wall)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT g.*, v.path, v.filename, v.description as video_description
            FROM gaze_moments g
            JOIN videos v ON g.video_id = v.id
            WHERE {where}
            ORDER BY g.id DESC
            LIMIT ?
            """,
            params
        ).fetchall()
        return [dict(r) for r in rows]

    def search_sublime(
        self,
        sublime_type: Optional[str] = None,
        recovery: Optional[bool] = None,
        limit: int = 50
    ) -> list[dict]:
        """Search sublime moments."""
        conn = self.connect()
        conditions = []
        params = []

        if sublime_type:
            conditions.append("s.sublime_type = ?")
            params.append(sublime_type)
        if recovery is not None:
            conditions.append("s.recovery = ?")
            params.append(recovery)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT s.*, v.path, v.filename, v.description as video_description
            FROM sublime_moments s
            JOIN videos v ON s.video_id = v.id
            WHERE {where}
            ORDER BY s.id DESC
            LIMIT ?
            """,
            params
        ).fetchall()
        return [dict(r) for r in rows]

    def search_camera(
        self,
        min_frenetic: Optional[int] = None,
        max_frenetic: Optional[int] = None,
        stability: Optional[str] = None,
        limit: int = 50
    ) -> list[dict]:
        """Search camera moments by frenetic level or stability."""
        conn = self.connect()
        conditions = []
        params = []

        if min_frenetic is not None:
            conditions.append("c.frenetic >= ?")
            params.append(min_frenetic)
        if max_frenetic is not None:
            conditions.append("c.frenetic <= ?")
            params.append(max_frenetic)
        if stability:
            conditions.append("c.stability = ?")
            params.append(stability)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT c.*, v.path, v.filename
            FROM camera_moments c
            JOIN videos v ON c.video_id = v.id
            WHERE {where}
            ORDER BY c.frenetic DESC
            LIMIT ?
            """,
            params
        ).fetchall()
        return [dict(r) for r in rows]

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict:
        """Get archive statistics."""
        conn = self.connect()

        stats = {}

        # Video counts by tier
        rows = conn.execute(
            "SELECT tier, COUNT(*) as count FROM videos GROUP BY tier"
        ).fetchall()
        stats["videos_by_tier"] = {r["tier"]: r["count"] for r in rows}
        stats["total_videos"] = sum(stats["videos_by_tier"].values())

        # Gaze type distribution
        rows = conn.execute(
            "SELECT gaze_type, COUNT(*) as count FROM gaze_moments GROUP BY gaze_type"
        ).fetchall()
        stats["gaze_distribution"] = {r["gaze_type"]: r["count"] for r in rows}

        # Sublime type distribution
        rows = conn.execute(
            "SELECT sublime_type, COUNT(*) as count FROM sublime_moments GROUP BY sublime_type"
        ).fetchall()
        stats["sublime_distribution"] = {r["sublime_type"]: r["count"] for r in rows}

        # Recovery stats
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN recovery = 1 THEN 1 ELSE 0 END) as with_recovery,
                SUM(CASE WHEN recovery = 0 THEN 1 ELSE 0 END) as no_recovery
            FROM sublime_moments
            """
        ).fetchone()
        stats["sublime_recovery"] = {
            "with_recovery": row["with_recovery"] or 0,
            "no_recovery": row["no_recovery"] or 0
        }

        # Fourth wall breaks
        row = conn.execute(
            "SELECT COUNT(*) as count FROM gaze_moments WHERE breaks_fourth_wall = 1"
        ).fetchone()
        stats["fourth_wall_breaks"] = row["count"]

        # Total processing cost
        row = conn.execute(
            "SELECT SUM(processing_cost) as total FROM videos WHERE processing_cost IS NOT NULL"
        ).fetchone()
        stats["total_cost"] = row["total"] or 0.0

        # Total duration
        row = conn.execute(
            "SELECT SUM(duration_sec) as total FROM videos WHERE duration_sec IS NOT NULL"
        ).fetchone()
        stats["total_duration_sec"] = row["total"] or 0.0
        stats["total_duration_hours"] = stats["total_duration_sec"] / 3600

        return stats

    # =========================================================================
    # PROJECTS
    # =========================================================================

    def create_project(self, name: str, description: str = "") -> int:
        """Create a documentary project."""
        conn = self.connect()
        cursor = conn.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        return cursor.lastrowid

    def add_clip_to_project(
        self,
        project_id: int,
        video_id: int,
        timecode_start: str = "",
        timecode_end: str = "",
        notes: str = "",
        source_query: str = ""
    ):
        """Add a clip to a project."""
        conn = self.connect()

        # Get next sequence order
        row = conn.execute(
            "SELECT MAX(sequence_order) as max_order FROM project_clips WHERE project_id = ?",
            (project_id,)
        ).fetchone()
        next_order = (row["max_order"] or 0) + 1

        conn.execute(
            """
            INSERT INTO project_clips
            (project_id, video_id, timecode_start, timecode_end, sequence_order, notes, source_query)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, video_id, timecode_start, timecode_end, next_order, notes, source_query)
        )
        conn.commit()

    def get_project_clips(self, project_id: int) -> list[dict]:
        """Get all clips for a project in order."""
        conn = self.connect()
        rows = conn.execute(
            """
            SELECT pc.*, v.path, v.filename, v.description
            FROM project_clips pc
            JOIN videos v ON pc.video_id = v.id
            WHERE pc.project_id = ?
            ORDER BY pc.sequence_order
            """,
            (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def get_file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Calculate MD5 hash of file for dedup detection."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


def get_video_duration(path: Path) -> Optional[float]:
    """Get video duration using ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        return None
