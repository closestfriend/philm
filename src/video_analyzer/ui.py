"""FastAPI application for the Philm web UI."""

from fastapi import FastAPI

app = FastAPI(title="Philm UI")


@app.get("/")
async def index():
    return {"status": "ok"}
