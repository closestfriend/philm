"""FastAPI application for the Philm web UI."""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
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


@app.get("/thumbnails/{video_id}.jpg")
async def serve_thumbnail(video_id: int):
    thumb = Path.home() / ".vanalyze" / "thumbnails" / f"{video_id}.jpg"
    if not thumb.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(thumb))
