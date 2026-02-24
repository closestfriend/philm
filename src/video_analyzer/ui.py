"""FastAPI application for the Philm web UI."""

import shutil
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .archive import Archive, DEFAULT_ARCHIVE_PATH
from .modes import ALL_MODES
from .thumbnails import extract_thumbnail

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


@app.get("/thumbnails/{video_id}.jpg")
async def serve_thumbnail(video_id: int):
    thumb = Path.home() / ".vanalyze" / "thumbnails" / f"{video_id}.jpg"
    if not thumb.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(thumb))


class FolderRequest(BaseModel):
    path: str


@app.post("/api/ingest/file")
async def ingest_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Accept an uploaded video file, register in archive, extract thumbnail."""
    dest = Path.home() / ".vanalyze" / "uploads" / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    background_tasks.add_task(_register_video, str(dest))
    return {"status": "queued", "path": str(dest)}


@app.post("/api/ingest/folder")
async def ingest_folder(req: FolderRequest, background_tasks: BackgroundTasks):
    """Scan a folder and register all found videos."""
    folder = Path(req.path)
    if not folder.exists():
        raise HTTPException(status_code=400, detail="Folder not found")
    background_tasks.add_task(_scan_folder, str(folder))
    return {"status": "scanning", "path": str(folder)}


def _register_video(path: str):
    archive = get_archive()
    video_id = archive.add_video(Path(path))
    extract_thumbnail(path, video_id)
    archive.close()


def _scan_folder(folder: str):
    archive = get_archive()
    archive.scan_folder(Path(folder), recursive=True)
    # Extract thumbnails for all videos (they skip if already exists)
    for video in archive.list_videos():
        extract_thumbnail(video.path, video.id)
    archive.close()
