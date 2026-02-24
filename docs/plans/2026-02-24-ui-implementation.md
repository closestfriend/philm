# Philm UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `vanalyze ui` subcommand that launches a local FastAPI + HTMX web app for browsing, ingesting, and analyzing video footage.

**Architecture:** FastAPI serves both the API and Jinja2-rendered HTMX templates. The existing `Archive` class in `archive.py` is the sole data layer — no new database. Analysis jobs run as background tasks and stream progress back via SSE.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, python-multipart, HTMX (via CDN), Video.js (via CDN)

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add new dependencies**

In `pyproject.toml`, add to the `dependencies` list:
```toml
"fastapi>=0.115.0",
"uvicorn>=0.32.0",
"jinja2>=3.1.0",
"python-multipart>=0.0.12",
```

**Step 2: Sync**

```bash
uv sync
```
Expected: dependencies install without errors.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add fastapi/uvicorn/jinja2 deps for UI"
```

---

## Task 2: Scaffold the UI Subcommand

**Files:**
- Create: `src/video_analyzer/ui_cli.py`
- Modify: `src/video_analyzer/cli.py`

**Step 1: Create `ui_cli.py`**

```python
"""UI subcommand — launches the Philm web interface."""

import typer
import uvicorn

app = typer.Typer(name="ui", help="Launch the Philm web UI")


@app.callback(invoke_without_command=True)
def launch(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes"),
):
    """Launch the Philm web interface at http://localhost:8000"""
    typer.echo(f"Starting Philm UI at http://{host}:{port}")
    uvicorn.run(
        "video_analyzer.ui:app",
        host=host,
        port=port,
        reload=reload,
    )
```

**Step 2: Register in `cli.py`**

Add after the existing `register_archive_commands` import and call (around line 21):
```python
from .ui_cli import app as ui_app
```

And after `register_archive_commands(app)`:
```python
app.add_typer(ui_app, name="ui")
```

**Step 3: Create a stub `ui.py` so the import resolves**

```python
"""FastAPI application for the Philm web UI."""

from fastapi import FastAPI

app = FastAPI(title="Philm UI")


@app.get("/")
async def index():
    return {"status": "ok"}
```

**Step 4: Verify it launches**

```bash
uv run vanalyze ui
```
Expected: "Starting Philm UI at http://127.0.0.1:8000", server starts, `curl http://localhost:8000/` returns `{"status":"ok"}`.

**Step 5: Commit**

```bash
git add src/video_analyzer/ui_cli.py src/video_analyzer/ui.py src/video_analyzer/cli.py
git commit -m "feat: add vanalyze ui subcommand (stub)"
```

---

## Task 3: Base Template + Static Structure

**Files:**
- Create: `src/video_analyzer/templates/base.html`
- Create: `src/video_analyzer/templates/corpus.html`
- Modify: `src/video_analyzer/ui.py`

**Step 1: Create `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Philm{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@2.0.3"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0a0a0a;
      color: #e0e0e0;
      font-family: 'Courier New', monospace;
      font-size: 14px;
    }
    nav {
      padding: 16px 24px;
      border-bottom: 1px solid #222;
      display: flex;
      align-items: center;
      gap: 24px;
    }
    nav a { color: #e0e0e0; text-decoration: none; }
    nav .logo { font-size: 18px; font-weight: bold; letter-spacing: 2px; }
    main { padding: 24px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }
    .card {
      background: #111;
      border: 1px solid #222;
      border-radius: 4px;
      overflow: hidden;
      cursor: pointer;
      transition: border-color 0.15s;
    }
    .card:hover { border-color: #444; }
    .card-thumb {
      width: 100%;
      aspect-ratio: 16/9;
      background: #1a1a1a;
      object-fit: cover;
    }
    .card-thumb-placeholder {
      width: 100%;
      aspect-ratio: 16/9;
      background: #1a1a1a;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #333;
      font-size: 11px;
    }
    .card-body { padding: 12px; }
    .card-filename { font-size: 11px; color: #666; margin-bottom: 6px; }
    .card-desc { font-size: 12px; color: #bbb; line-height: 1.5; margin-bottom: 10px; }
    .coverage {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }
    .pill {
      font-size: 9px;
      padding: 2px 6px;
      border-radius: 2px;
      border: 1px solid #333;
      color: #555;
      cursor: pointer;
      transition: all 0.1s;
    }
    .pill.done { border-color: #4a9; color: #4a9; }
    .pill.running { border-color: #a84; color: #a84; animation: pulse 1s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    .search-bar {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    input[type=text], input[type=search] {
      background: #111;
      border: 1px solid #333;
      color: #e0e0e0;
      padding: 8px 12px;
      font-family: monospace;
      font-size: 13px;
      border-radius: 2px;
      outline: none;
    }
    input:focus { border-color: #555; }
    button {
      background: #1a1a1a;
      border: 1px solid #333;
      color: #e0e0e0;
      padding: 8px 16px;
      font-family: monospace;
      font-size: 13px;
      cursor: pointer;
      border-radius: 2px;
    }
    button:hover { border-color: #555; }
    .drop-zone {
      border: 1px dashed #333;
      border-radius: 4px;
      padding: 24px;
      text-align: center;
      color: #444;
      margin-top: 16px;
      transition: border-color 0.15s, color 0.15s;
    }
    .drop-zone.drag-over { border-color: #4a9; color: #4a9; }
  </style>
</head>
<body>
  <nav>
    <a href="/" class="logo">PHILM</a>
    <a href="/">corpus</a>
  </nav>
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
```

**Step 2: Create `templates/corpus.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="search-bar">
  <input
    type="search"
    name="q"
    placeholder="search descriptions..."
    value="{{ q }}"
    hx-get="/corpus"
    hx-trigger="input changed delay:300ms"
    hx-target="#card-grid"
    hx-swap="innerHTML"
  >
</div>

<div class="drop-zone"
  id="drop-zone"
  ondragover="event.preventDefault(); this.classList.add('drag-over')"
  ondragleave="this.classList.remove('drag-over')"
  ondrop="handleDrop(event)">
  drop videos here — or <input type="text" id="folder-input" placeholder="enter folder path"> <button onclick="scanFolder()">scan</button>
</div>

<div class="grid" id="card-grid">
  {% include "partials/cards.html" %}
</div>

<script>
async function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  const files = [...e.dataTransfer.files];
  for (const file of files) {
    const fd = new FormData();
    fd.append('file', file);
    await fetch('/api/ingest/file', { method: 'POST', body: fd });
  }
  htmx.trigger('#card-grid', 'refresh');
}

async function scanFolder() {
  const path = document.getElementById('folder-input').value;
  if (!path) return;
  await fetch('/api/ingest/folder', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ path })
  });
  htmx.trigger('#card-grid', 'refresh');
}
</script>
{% endblock %}
```

**Step 3: Create `templates/partials/cards.html`**

```html
{% for video in videos %}
  {% include "partials/card.html" %}
{% else %}
<p style="color:#444; grid-column:1/-1">no clips in archive yet — drop some videos above.</p>
{% endfor %}
```

**Step 4: Create `templates/partials/card.html`**

```html
<div class="card" onclick="window.location='/video/{{ video.id }}'">
  {% if video.thumbnail %}
    <img class="card-thumb" src="/thumbnails/{{ video.id }}.jpg" alt="">
  {% else %}
    <div class="card-thumb-placeholder">no thumbnail</div>
  {% endif %}
  <div class="card-body">
    <div class="card-filename">{{ video.filename }}</div>
    <div class="card-desc">{{ video.description or '—' }}</div>
    <div class="coverage">
      {% for mode, done in video.coverage.items() %}
        <span class="pill {{ 'done' if done else '' }}"
          {% if not done %}
            hx-post="/api/analyze/{{ video.id }}/{{ mode }}"
            hx-swap="none"
            onclick="event.stopPropagation()"
          {% endif %}
        >{{ mode }}</span>
      {% endfor %}
    </div>
  </div>
</div>
```

**Step 5: Wire up Jinja2 in `ui.py`**

Replace the stub `ui.py`:
```python
"""FastAPI application for the Philm web UI."""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .archive import Archive, DEFAULT_ARCHIVE_PATH
from .modes import ALL_MODES

app = FastAPI(title="Philm UI")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

MODES = list(ALL_MODES.keys())


def get_archive() -> Archive:
    archive = Archive(DEFAULT_ARCHIVE_PATH)
    archive.init_db()
    return archive


def build_video_context(video, archive: Archive) -> dict:
    """Attach thumbnail path and coverage dict to a video record."""
    thumb = Path.home() / ".vanalyze" / "thumbnails" / f"{video.id}.jpg"
    done_modes = set(archive.get_completed_modes(video.id))
    return {
        **video.__dict__,
        "thumbnail": thumb.exists(),
        "coverage": {m: m in done_modes for m in MODES},
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, q: str = ""):
    archive = get_archive()
    videos_raw = archive.search_videos(q) if q else archive.list_videos()
    videos = [build_video_context(v, archive) for v in videos_raw]
    archive.close()
    return templates.TemplateResponse("corpus.html", {
        "request": request, "videos": videos, "q": q
    })


@app.get("/corpus", response_class=HTMLResponse)
async def corpus_partial(request: Request, q: str = ""):
    """HTMX partial — returns just the cards."""
    archive = get_archive()
    videos_raw = archive.search_videos(q) if q else archive.list_videos()
    videos = [build_video_context(v, archive) for v in videos_raw]
    archive.close()
    return templates.TemplateResponse("partials/cards.html", {
        "request": request, "videos": videos
    })
```

**Step 6: Verify it renders**

```bash
uv run vanalyze ui
```
Open `http://localhost:8000` — should see the dark corpus page with search bar and drop zone. If archive is empty, shows "no clips yet" message.

**Step 7: Commit**

```bash
git add src/video_analyzer/ui.py src/video_analyzer/templates/
git commit -m "feat: corpus browser with card grid and HTMX search"
```

---

## Task 4: Archive Methods Needed by UI

**Files:**
- Modify: `src/video_analyzer/archive.py`

The UI needs three methods that likely don't exist yet. Check first — add only what's missing.

**Step 1: Add `list_videos` if missing**

```python
def list_videos(self) -> list[VideoRecord]:
    """Return all videos ordered by date added descending."""
    rows = self.conn.execute(
        "SELECT * FROM videos ORDER BY id DESC"
    ).fetchall()
    return [VideoRecord(*row) for row in rows]
```

**Step 2: Add `search_videos` if missing**

```python
def search_videos(self, query: str) -> list[VideoRecord]:
    """Full-text search over video descriptions."""
    rows = self.conn.execute(
        "SELECT * FROM videos WHERE description LIKE ? ORDER BY id DESC",
        (f"%{query}%",)
    ).fetchall()
    return [VideoRecord(*row) for row in rows]
```

**Step 3: Add `get_completed_modes` if missing**

```python
def get_completed_modes(self, video_id: int) -> list[str]:
    """Return list of mode names that have been analyzed for this video."""
    # Check each mode-specific table for rows with this video_id
    completed = []
    mode_tables = {
        "affect": "affect_moments",
        "gaze": "gaze_moments",
        # ... add all mode→table mappings
    }
    for mode, table in mode_tables.items():
        try:
            row = self.conn.execute(
                f"SELECT 1 FROM {table} WHERE video_id=? LIMIT 1", (video_id,)
            ).fetchone()
            if row:
                completed.append(mode)
        except Exception:
            pass
    return completed
```

Note: Check `archive.py` for existing table names — use those. Do not invent table names.

**Step 4: Commit**

```bash
git add src/video_analyzer/archive.py
git commit -m "feat: add list_videos, search_videos, get_completed_modes to Archive"
```

---

## Task 5: Thumbnail Extraction on Ingest

**Files:**
- Create: `src/video_analyzer/thumbnails.py`
- Modify: `src/video_analyzer/ui.py`

**Step 1: Create `thumbnails.py`**

```python
"""Thumbnail extraction via ffmpeg."""

import subprocess
from pathlib import Path

THUMB_DIR = Path.home() / ".vanalyze" / "thumbnails"


def extract_thumbnail(video_path: str | Path, video_id: int) -> Path | None:
    """Extract a single frame from 10% into the video as a JPEG."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out_path = THUMB_DIR / f"{video_id}.jpg"
    if out_path.exists():
        return out_path
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", "00:00:03",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "3",
            str(out_path),
        ], capture_output=True, timeout=30)
        return out_path if out_path.exists() else None
    except Exception:
        return None
```

**Step 2: Add thumbnail serving endpoint to `ui.py`**

```python
from fastapi.responses import FileResponse

@app.get("/thumbnails/{video_id}.jpg")
async def serve_thumbnail(video_id: int):
    thumb = Path.home() / ".vanalyze" / "thumbnails" / f"{video_id}.jpg"
    if not thumb.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(thumb))
```

**Step 3: Commit**

```bash
git add src/video_analyzer/thumbnails.py src/video_analyzer/ui.py
git commit -m "feat: thumbnail extraction and serving"
```

---

## Task 6: Ingest Endpoints

**Files:**
- Modify: `src/video_analyzer/ui.py`

**Step 1: Add file upload endpoint**

```python
import shutil, tempfile
from fastapi import UploadFile, File, BackgroundTasks

@app.post("/api/ingest/file")
async def ingest_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Accept an uploaded video file, register in archive, extract thumbnail."""
    dest = Path.home() / ".vanalyze" / "uploads" / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    background_tasks.add_task(_register_video, str(dest))
    return {"status": "queued", "path": str(dest)}
```

**Step 2: Add folder scan endpoint**

```python
from pydantic import BaseModel

class FolderRequest(BaseModel):
    path: str

@app.post("/api/ingest/folder")
async def ingest_folder(req: FolderRequest, background_tasks: BackgroundTasks):
    """Scan a folder and register all found videos."""
    folder = Path(req.path)
    if not folder.exists():
        raise HTTPException(status_code=400, detail="Folder not found")
    background_tasks.add_task(_scan_folder, str(folder))
    return {"status": "scanning", "path": str(folder)}
```

**Step 3: Add shared `_register_video` and `_scan_folder` helpers**

```python
from .archive import Archive, DEFAULT_ARCHIVE_PATH, VIDEO_EXTENSIONS
from .thumbnails import extract_thumbnail

def _register_video(path: str):
    archive = get_archive()
    video_id = archive.add_video(path)  # use existing method or adapt
    archive.close()
    if video_id:
        extract_thumbnail(path, video_id)

def _scan_folder(folder: str):
    archive = get_archive()
    new, _ = archive.scan_folder(Path(folder), recursive=True)
    # Extract thumbnails for newly added videos
    for video in archive.list_videos():
        extract_thumbnail(video.path, video.id)
    archive.close()
```

Note: Check `archive.py` for the correct method to add a single video — use it, don't invent one.

**Step 4: Verify**

```bash
uv run vanalyze ui
```
Drop a video onto the page. Refresh — card should appear with thumbnail (if ffmpeg is available).

**Step 5: Commit**

```bash
git add src/video_analyzer/ui.py
git commit -m "feat: file drop and folder scan ingest endpoints"
```

---

## Task 7: Analysis Triggering + SSE Progress

**Files:**
- Modify: `src/video_analyzer/ui.py`

**Step 1: Add analysis trigger endpoint**

```python
import asyncio
from fastapi.responses import StreamingResponse

# In-memory job tracker (sufficient for local single-user tool)
_running_jobs: set[str] = set()

@app.post("/api/analyze/{video_id}/{mode}")
async def trigger_analysis(video_id: int, mode: str, background_tasks: BackgroundTasks):
    job_key = f"{video_id}:{mode}"
    if job_key in _running_jobs:
        return {"status": "already_running"}
    _running_jobs.add(job_key)
    background_tasks.add_task(_run_analysis, video_id, mode, job_key)
    return {"status": "started"}
```

**Step 2: Add `_run_analysis` background task**

```python
from .analyzer import configure_genai, upload_video, analyze_video
from .modes import get_mode
import os

def _run_analysis(video_id: int, mode: str, job_key: str):
    try:
        archive = get_archive()
        video = archive.get_video(video_id)  # adapt to existing method
        archive.close()
        if not video:
            return
        configure_genai(os.getenv("GEMINI_API_KEY"))
        video_file = upload_video(video.path)
        analysis_mode = get_mode(mode)
        result = analyze_video(video_file, analysis_mode)
        archive = get_archive()
        archive.store_result(video_id, mode, result)  # adapt to existing method
        archive.close()
    finally:
        _running_jobs.discard(job_key)
```

Note: Check `archive.py` for the correct method to store an analysis result — use the existing one.

**Step 3: Add job status endpoint (for pill animation)**

```python
@app.get("/api/analyze/status/{video_id}/{mode}")
async def job_status(video_id: int, mode: str):
    job_key = f"{video_id}:{mode}"
    return {"running": job_key in _running_jobs}
```

**Step 4: Update card pill to poll status while running**

In `templates/partials/card.html`, update the pill trigger:
```html
<span class="pill {{ 'done' if done else 'running' if running else '' }}"
  {% if not done and not running %}
    hx-post="/api/analyze/{{ video.id }}/{{ mode }}"
    hx-swap="none"
    onclick="event.stopPropagation()"
  {% endif %}
  {% if running %}
    hx-get="/api/analyze/status/{{ video.id }}/{{ mode }}"
    hx-trigger="every 2s"
    hx-swap="none"
  {% endif %}
>{{ mode }}</span>
```

**Step 5: Commit**

```bash
git add src/video_analyzer/ui.py src/video_analyzer/templates/
git commit -m "feat: analysis triggering from UI with background jobs"
```

---

## Task 8: Clip Detail Page + Video Player

**Files:**
- Create: `src/video_analyzer/templates/player.html`
- Modify: `src/video_analyzer/ui.py`

**Step 1: Add video file serving endpoint**

```python
@app.get("/video-file/{video_id}")
async def serve_video(video_id: int):
    archive = get_archive()
    video = archive.get_video(video_id)
    archive.close()
    if not video or not Path(video.path).exists():
        raise HTTPException(status_code=404)
    return FileResponse(video.path, media_type="video/mp4")
```

**Step 2: Add clip detail route**

```python
@app.get("/video/{video_id}", response_class=HTMLResponse)
async def clip_detail(request: Request, video_id: int):
    archive = get_archive()
    video = archive.get_video(video_id)
    moments = archive.get_all_moments(video_id)  # adapt to existing method
    archive.close()
    if not video:
        raise HTTPException(status_code=404)
    ctx = build_video_context(video, archive)
    return templates.TemplateResponse("player.html", {
        "request": request,
        "video": ctx,
        "moments": moments,  # list of {mode, timecode, data}
    })
```

**Step 3: Create `templates/player.html`**

```html
{% extends "base.html" %}
{% block title %}{{ video.filename }} — Philm{% endblock %}
{% block content %}
<div style="display:flex; gap:24px; align-items:flex-start;">
  <div style="flex:1; min-width:0;">
    <div style="position:relative;">
      <video id="player" controls style="width:100%; border:1px solid #222;" src="/video-file/{{ video.id }}"></video>
      <div id="overlay" style="position:absolute; bottom:48px; left:0; right:0; padding:12px; pointer-events:none; display:none;">
        <div id="overlay-content" style="background:rgba(0,0,0,0.8); padding:12px; border-left:2px solid #4a9; font-size:12px; line-height:1.6;"></div>
      </div>
    </div>
    <div style="margin-top:8px; display:flex; gap:12px; align-items:center;">
      <button onclick="toggleOverlay()">toggle overlay</button>
      <span style="color:#444; font-size:11px;">{{ video.filename }}</span>
    </div>
    <div style="margin-top:8px; font-size:12px; color:#888;">{{ video.description }}</div>
  </div>

  <div style="width:300px; flex-shrink:0;">
    <div style="color:#555; font-size:11px; margin-bottom:12px;">MOMENTS</div>
    {% for moment in moments %}
    <div class="moment-row" data-timecode="{{ moment.start_sec }}"
      style="padding:8px 0; border-bottom:1px solid #1a1a1a; cursor:pointer;"
      onclick="seekTo({{ moment.start_sec }})">
      <div style="font-size:10px; color:#555;">{{ moment.mode }} · {{ moment.timecode }}</div>
      <div style="font-size:12px; color:#bbb; margin-top:2px;">{{ moment.summary }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<script>
const player = document.getElementById('player');
const overlay = document.getElementById('overlay');
const overlayContent = document.getElementById('overlay-content');
let overlayEnabled = false;

const moments = {{ moments | tojson }};

function toggleOverlay() {
  overlayEnabled = !overlayEnabled;
  overlay.style.display = overlayEnabled ? 'block' : 'none';
}

function seekTo(sec) {
  player.currentTime = sec;
  player.play();
}

player.addEventListener('timeupdate', () => {
  if (!overlayEnabled) return;
  const t = player.currentTime;
  const active = moments.filter(m => t >= m.start_sec && t <= m.end_sec);
  if (active.length) {
    overlayContent.innerHTML = active.map(m =>
      `<div style="margin-bottom:6px;"><span style="color:#4a9;">${m.mode}</span> · ${m.timecode}<br>${m.summary}</div>`
    ).join('');
    overlay.style.display = 'block';
  } else if (overlayEnabled) {
    overlayContent.innerHTML = '';
  }
});
</script>
{% endblock %}
```

**Step 4: Add `get_all_moments` to archive if missing**

```python
def get_all_moments(self, video_id: int) -> list[dict]:
    """Return all analyzed moments for a video across all modes."""
    # Query each mode table and unify into list of dicts with
    # {mode, timecode, start_sec, end_sec, summary, data}
    # Adapt based on existing table structure in archive.py
```

Note: Read archive.py tables carefully to understand what columns exist. Parse timecodes (e.g. "1:15") into `start_sec` floats for the JS overlay.

**Step 5: Verify**

Navigate to a clip that has been analyzed. Video should play. Toggle overlay — analysis text should appear over video at the right timecodes.

**Step 6: Commit**

```bash
git add src/video_analyzer/templates/player.html src/video_analyzer/ui.py
git commit -m "feat: clip detail page with video player and timecode overlay"
```

---

## Task 9: Wire Up Full-Text Search in Archive

**Files:**
- Modify: `src/video_analyzer/archive.py`

The current `search_videos` uses LIKE. For real FTS, add SQLite FTS5.

**Step 1: Update `init_db` to create FTS table**

```python
# Add to SCHEMA string in Archive class:
"""
CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts
USING fts5(description, content=videos, content_rowid=id);

CREATE TRIGGER IF NOT EXISTS videos_ai AFTER INSERT ON videos BEGIN
  INSERT INTO videos_fts(rowid, description) VALUES (new.id, new.description);
END;

CREATE TRIGGER IF NOT EXISTS videos_au AFTER UPDATE ON videos BEGIN
  INSERT INTO videos_fts(videos_fts, rowid, description) VALUES('delete', old.id, old.description);
  INSERT INTO videos_fts(rowid, description) VALUES (new.id, new.description);
END;
"""
```

**Step 2: Update `search_videos` to use FTS**

```python
def search_videos(self, query: str) -> list[VideoRecord]:
    rows = self.conn.execute("""
        SELECT v.* FROM videos v
        JOIN videos_fts f ON v.id = f.rowid
        WHERE videos_fts MATCH ?
        ORDER BY rank
    """, (query,)).fetchall()
    return [VideoRecord(*row) for row in rows]
```

**Step 3: Commit**

```bash
git add src/video_analyzer/archive.py
git commit -m "feat: SQLite FTS5 for corpus description search"
```

---

## Task 10: Polish + README Note

**Step 1: Add `vanalyze ui` to README**

In `README.md`, add a new section after the Archive section:

```markdown
## Web UI

```bash
vanalyze ui
```

Launches a local web interface at `http://localhost:8000` for browsing and analyzing your corpus.

- Card grid with description-first navigation
- Framework coverage per clip — click a hollow pill to trigger analysis
- Drag-and-drop video intake, or point at a folder
- Timecode-synced analysis overlay on the video player
```

**Step 2: Commit and push**

```bash
git add README.md
git commit -m "docs: add web UI section to README"
git push
```
