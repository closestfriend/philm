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

    -- Baudrillard moments (simulacra/hyperreality)
    CREATE TABLE IF NOT EXISTS baudrillard_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        simulacra_order TEXT NOT NULL,
        hyperreality_mode TEXT NOT NULL,
        sign_value TEXT,
        implosion TEXT,
        precession BOOLEAN,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Epistemic moments (truth claims)
    CREATE TABLE IF NOT EXISTS epistemic_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        epistemic_mode TEXT NOT NULL,
        certainty TEXT NOT NULL,
        claim TEXT,
        evidence_type TEXT,
        verifiable BOOLEAN,
        appeals_to TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Foucault moments (power/surveillance)
    CREATE TABLE IF NOT EXISTS foucault_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        power_mode TEXT NOT NULL,
        surveillance TEXT NOT NULL,
        subject_produced TEXT,
        norm_enforced TEXT,
        resistance TEXT,
        apparatus TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Virilio moments (speed/accident)
    CREATE TABLE IF NOT EXISTS virilio_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        speed_regime TEXT NOT NULL,
        dromology TEXT,
        accident TEXT NOT NULL,
        territory_collapse BOOLEAN,
        real_time BOOLEAN,
        war_machine TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Žižek moments (parallax/ideology)
    CREATE TABLE IF NOT EXISTS zizek_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        parallax_type TEXT NOT NULL,
        lacanian_register TEXT NOT NULL,
        ideology_at_work TEXT,
        obscene_supplement TEXT,
        gap_between TEXT,
        real_intrusion TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Barthes moments (punctum/mythology)
    CREATE TABLE IF NOT EXISTS barthes_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        register TEXT NOT NULL,
        punctum_detail TEXT,
        myth_operation TEXT,
        denotation TEXT,
        connotation TEXT,
        grain TEXT,
        death_present BOOLEAN,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Benjamin moments (aura/dialectical image)
    CREATE TABLE IF NOT EXISTS benjamin_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        aura_status TEXT NOT NULL,
        aura_source TEXT,
        dialectical_image TEXT,
        optical_unconscious TEXT,
        cult_vs_exhibition TEXT,
        reproducibility TEXT,
        now_time TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Hauntology moments (Fisher/Han/Curtis)
    CREATE TABLE IF NOT EXISTS hauntology_moments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
        timecode TEXT NOT NULL,
        temporal_pathology TEXT NOT NULL,
        capitalist_realism TEXT,
        smoothness TEXT NOT NULL,
        hypernormal TEXT,
        lost_future TEXT,
        suffering_individualized BOOLEAN,
        achievement_subject BOOLEAN,
        libidinal_capture TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Generic moments table for all other modes (Levinas, rhythm, etc.)
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
    CREATE INDEX IF NOT EXISTS idx_baudrillard_order ON baudrillard_moments(simulacra_order);
    CREATE INDEX IF NOT EXISTS idx_baudrillard_precession ON baudrillard_moments(precession);
    CREATE INDEX IF NOT EXISTS idx_epistemic_mode ON epistemic_moments(epistemic_mode);
    CREATE INDEX IF NOT EXISTS idx_epistemic_verifiable ON epistemic_moments(verifiable);
    CREATE INDEX IF NOT EXISTS idx_foucault_power ON foucault_moments(power_mode);
    CREATE INDEX IF NOT EXISTS idx_foucault_surveillance ON foucault_moments(surveillance);
    CREATE INDEX IF NOT EXISTS idx_virilio_speed ON virilio_moments(speed_regime);
    CREATE INDEX IF NOT EXISTS idx_virilio_accident ON virilio_moments(accident);
    CREATE INDEX IF NOT EXISTS idx_zizek_parallax ON zizek_moments(parallax_type);
    CREATE INDEX IF NOT EXISTS idx_zizek_register ON zizek_moments(lacanian_register);
    CREATE INDEX IF NOT EXISTS idx_barthes_register ON barthes_moments(register);
    CREATE INDEX IF NOT EXISTS idx_barthes_myth ON barthes_moments(myth_operation);
    CREATE INDEX IF NOT EXISTS idx_benjamin_aura ON benjamin_moments(aura_status);
    CREATE INDEX IF NOT EXISTS idx_benjamin_dialectical ON benjamin_moments(dialectical_image);
    CREATE INDEX IF NOT EXISTS idx_hauntology_temporal ON hauntology_moments(temporal_pathology);
    CREATE INDEX IF NOT EXISTS idx_hauntology_realism ON hauntology_moments(capitalist_realism);
    CREATE INDEX IF NOT EXISTS idx_hauntology_smooth ON hauntology_moments(smoothness);
    CREATE INDEX IF NOT EXISTS idx_hauntology_hypernormal ON hauntology_moments(hypernormal);

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

    def get_video(self, video_id: int) -> "VideoRecord | None":
        """Return a single video by id, or None."""
        conn = self.connect()
        row = conn.execute(
            """SELECT id, path, filename, file_hash, file_size, duration_sec,
                      date_recorded, location, camera, description,
                      processed_at, processing_cost, tier
               FROM videos WHERE id=?""",
            (video_id,)
        ).fetchone()
        return VideoRecord(*row) if row else None

    def get_video_dict(self, video_id: int) -> Optional[dict]:
        """Get video by ID as a dict (internal/legacy use)."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_videos(self) -> list[VideoRecord]:
        """Return all videos ordered by id descending."""
        conn = self.connect()
        rows = conn.execute(
            """SELECT id, path, filename, file_hash, file_size, duration_sec,
                      date_recorded, location, camera, description,
                      processed_at, processing_cost, tier
               FROM videos ORDER BY id DESC"""
        ).fetchall()
        return [VideoRecord(*row) for row in rows]

    def search_videos(self, query: str) -> list[VideoRecord]:
        """Search videos by description (LIKE)."""
        conn = self.connect()
        rows = conn.execute(
            """SELECT id, path, filename, file_hash, file_size, duration_sec,
                      date_recorded, location, camera, description,
                      processed_at, processing_cost, tier
               FROM videos WHERE description LIKE ? ORDER BY id DESC""",
            (f"%{query}%",)
        ).fetchall()
        return [VideoRecord(*row) for row in rows]

    def get_completed_modes(self, video_id: int) -> list[str]:
        """Return list of mode names with completed analyses for this video."""
        conn = self.connect()
        # Map mode name -> dedicated table (only tables that exist in SCHEMA)
        mode_tables = {
            "gaze": "gaze_moments",
            "sublime": "sublime_moments",
            "affect": "affect_moments",
            "camera": "camera_moments",
            "baudrillard": "baudrillard_moments",
            "epistemic": "epistemic_moments",
            "foucault": "foucault_moments",
            "virilio": "virilio_moments",
            "zizek": "zizek_moments",
            "barthes": "barthes_moments",
            "benjamin": "benjamin_moments",
            "hauntology": "hauntology_moments",
        }
        completed = []
        for mode, table in mode_tables.items():
            try:
                row = conn.execute(
                    f"SELECT 1 FROM {table} WHERE video_id=? LIMIT 1", (video_id,)
                ).fetchone()
                if row:
                    completed.append(mode)
            except Exception:
                pass
        # Also check generic_moments for any other modes stored there
        try:
            rows = conn.execute(
                "SELECT DISTINCT mode FROM generic_moments WHERE video_id=?",
                (video_id,)
            ).fetchall()
            for row in rows:
                mode_name = row[0]
                if mode_name not in completed:
                    completed.append(mode_name)
        except Exception:
            pass
        return completed

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

    def store_baudrillard_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Baudrillard simulacra/hyperreality analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM baudrillard_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO baudrillard_moments
                (video_id, timecode, simulacra_order, hyperreality_mode, sign_value,
                 implosion, precession, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("order", ""),
                    t.get("hyperreality_mode", ""),
                    t.get("sign_value", ""),
                    t.get("implosion", ""),
                    t.get("precession"),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_epistemic_analysis(self, video_id: int, timecodes: list[dict]):
        """Store epistemic truth claims analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM epistemic_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO epistemic_moments
                (video_id, timecode, epistemic_mode, certainty, claim, evidence_type,
                 verifiable, appeals_to, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("mode", ""),
                    t.get("certainty", ""),
                    t.get("claim", ""),
                    t.get("evidence_type", ""),
                    t.get("verifiable"),
                    t.get("appeals_to", ""),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_foucault_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Foucault power/surveillance analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM foucault_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO foucault_moments
                (video_id, timecode, power_mode, surveillance, subject_produced,
                 norm_enforced, resistance, apparatus, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("power_mode", ""),
                    t.get("surveillance", ""),
                    t.get("subject_produced", ""),
                    t.get("norm_enforced", ""),
                    t.get("resistance", ""),
                    t.get("apparatus", ""),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_virilio_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Virilio speed/accident analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM virilio_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO virilio_moments
                (video_id, timecode, speed_regime, dromology, accident,
                 territory_collapse, real_time, war_machine, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("speed_regime", ""),
                    t.get("dromology", ""),
                    t.get("accident", ""),
                    t.get("territory_collapse"),
                    t.get("real_time"),
                    t.get("war_machine", ""),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_zizek_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Žižek parallax/ideology analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM zizek_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO zizek_moments
                (video_id, timecode, parallax_type, lacanian_register, ideology_at_work,
                 obscene_supplement, gap_between, real_intrusion, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("parallax", ""),
                    t.get("register", ""),
                    t.get("ideology_at_work", ""),
                    t.get("obscene_supplement", ""),
                    t.get("gap_between", ""),
                    t.get("real_intrusion", ""),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_barthes_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Barthes punctum/mythology analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM barthes_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO barthes_moments
                (video_id, timecode, register, punctum_detail, myth_operation,
                 denotation, connotation, grain, death_present, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("register", ""),
                    t.get("punctum_detail", ""),
                    t.get("myth_operation", ""),
                    t.get("denotation", ""),
                    t.get("connotation", ""),
                    t.get("grain", ""),
                    t.get("death_present"),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_benjamin_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Benjamin aura/dialectical image analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM benjamin_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO benjamin_moments
                (video_id, timecode, aura_status, aura_source, dialectical_image,
                 optical_unconscious, cult_vs_exhibition, reproducibility, now_time, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("aura_status", ""),
                    t.get("aura_source", ""),
                    t.get("dialectical_image", ""),
                    t.get("optical_unconscious", ""),
                    t.get("cult_vs_exhibition", ""),
                    t.get("reproducibility", ""),
                    t.get("now_time", ""),
                    t.get("description", ""),
                )
            )
        conn.commit()

    def store_hauntology_analysis(self, video_id: int, timecodes: list[dict]):
        """Store Fisher/Han/Curtis hauntology analysis."""
        conn = self.connect()
        conn.execute("DELETE FROM hauntology_moments WHERE video_id = ?", (video_id,))

        for t in timecodes:
            conn.execute(
                """
                INSERT INTO hauntology_moments
                (video_id, timecode, temporal_pathology, capitalist_realism, smoothness,
                 hypernormal, lost_future, suffering_individualized, achievement_subject,
                 libidinal_capture, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    t.get("time", ""),
                    t.get("temporal_pathology", ""),
                    t.get("capitalist_realism", ""),
                    t.get("smoothness", ""),
                    t.get("hypernormal", ""),
                    t.get("lost_future", ""),
                    t.get("suffering_individualized"),
                    t.get("achievement_subject"),
                    t.get("libidinal_capture", ""),
                    t.get("description", ""),
                )
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
        elif mode == "baudrillard":
            self.store_baudrillard_analysis(video_id, timecodes)
        elif mode == "epistemic":
            self.store_epistemic_analysis(video_id, timecodes)
        elif mode == "foucault":
            self.store_foucault_analysis(video_id, timecodes)
        elif mode == "virilio":
            self.store_virilio_analysis(video_id, timecodes)
        elif mode == "zizek":
            self.store_zizek_analysis(video_id, timecodes)
        elif mode == "barthes":
            self.store_barthes_analysis(video_id, timecodes)
        elif mode == "benjamin":
            self.store_benjamin_analysis(video_id, timecodes)
        elif mode == "hauntology":
            self.store_hauntology_analysis(video_id, timecodes)
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

    def get_all_moments(self, video_id: int) -> list[dict]:
        """
        Return all analyzed moments for a video across all modes,
        as a list of dicts suitable for JSON serialization in the player template.

        Each dict contains:
          - mode (str)
          - timecode (str)
          - start_sec (float)
          - end_sec (float, start_sec + 5.0)
          - summary (str)
        """
        conn = self.connect()
        results: list[dict] = []

        # Dedicated tables: mode name -> (table, summary_column_or_None, fallback_columns)
        # Each table has a `description` column that serves as the human-readable summary,
        # except gaze_moments and affect_moments which lack `description` — we build one
        # from their typed columns instead.
        dedicated: list[tuple[str, str, list[str]]] = [
            # (mode, table, [candidate summary columns in priority order])
            ("gaze",        "gaze_moments",        ["gaze_type", "power_dynamic", "subject_position"]),
            ("sublime",     "sublime_moments",     ["description", "sublime_type", "overwhelm_source"]),
            ("affect",      "affect_moments",      ["atmosphere", "vector"]),
            ("camera",      "camera_moments",      ["description", "intentional_motion", "operator_presence"]),
            ("baudrillard", "baudrillard_moments", ["description", "simulacra_order", "hyperreality_mode"]),
            ("epistemic",   "epistemic_moments",   ["description", "claim", "epistemic_mode"]),
            ("foucault",    "foucault_moments",    ["description", "power_mode", "apparatus"]),
            ("virilio",     "virilio_moments",     ["description", "speed_regime", "accident"]),
            ("zizek",       "zizek_moments",       ["description", "parallax_type", "lacanian_register"]),
            ("barthes",     "barthes_moments",     ["description", "punctum_detail", "denotation"]),
            ("benjamin",    "benjamin_moments",    ["description", "dialectical_image", "aura_status"]),
            ("hauntology",  "hauntology_moments",  ["description", "temporal_pathology", "capitalist_realism"]),
        ]

        for mode, table, candidate_cols in dedicated:
            try:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE video_id = ? ORDER BY id",
                    (video_id,)
                ).fetchall()
                for row in rows:
                    r = dict(row)
                    # Build summary from first non-empty candidate column
                    summary_parts = []
                    for col in candidate_cols:
                        val = r.get(col)
                        if val and str(val).strip():
                            summary_parts.append(str(val).strip())
                    summary = " — ".join(summary_parts) if summary_parts else mode
                    tc = r.get("timecode", "")
                    start = _parse_timecode(tc)
                    results.append({
                        "mode": mode,
                        "timecode": tc,
                        "start_sec": start,
                        "end_sec": start + 5.0,
                        "summary": summary,
                    })
            except Exception:
                pass

        # generic_moments table: data is a JSON blob
        try:
            rows = conn.execute(
                "SELECT mode, timecode, data FROM generic_moments WHERE video_id = ? ORDER BY id",
                (video_id,)
            ).fetchall()
            for row in rows:
                tc = row["timecode"] or ""
                data = {}
                try:
                    data = json.loads(row["data"]) if row["data"] else {}
                except (ValueError, TypeError):
                    pass
                summary = (
                    data.get("description")
                    or data.get("summary")
                    or data.get("content")
                    or str(row["mode"])
                )
                start = _parse_timecode(tc)
                results.append({
                    "mode": row["mode"],
                    "timecode": tc,
                    "start_sec": start,
                    "end_sec": start + 5.0,
                    "summary": str(summary),
                })
        except Exception:
            pass

        # Sort by start_sec so the sidebar list is chronological
        results.sort(key=lambda m: m["start_sec"])
        return results


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def _parse_timecode(tc: str) -> float:
    """Convert timecode string like '1:15' or '0:30-1:00' to seconds."""
    # Handle ranges like "0:30-1:00" by taking the start
    tc = tc.split("-")[0].strip()
    parts = tc.split(":")
    try:
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        else:
            return float(tc)
    except (ValueError, IndexError):
        return 0.0


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
