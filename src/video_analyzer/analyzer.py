"""
Core video analysis using Google Gemini 2.5 Flash.

Handles video upload, structured output generation, and result parsing.
Uses the new google.genai SDK.
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Any, Type, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel

from .models import BaseAnalysisResult
from .modes import AnalysisMode


# Video MIME type mapping
VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    ".mkv": "video/x-matroska",
}

# Global client instance
_client: Optional[genai.Client] = None


def configure_genai(api_key: Optional[str] = None):
    """Configure Gemini API client with key from env or parameter."""
    global _client
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY not found. Set it in .env or pass explicitly."
        )
    _client = genai.Client(api_key=key)


def get_client() -> genai.Client:
    """Get the configured client instance."""
    if _client is None:
        raise RuntimeError("Gemini client not configured. Call configure_genai() first.")
    return _client


def strip_audio(video_path: Path) -> Path:
    """
    Strip audio from video using ffmpeg.

    Returns path to temporary file without audio.
    """
    # Create temp file with same extension
    suffix = video_path.suffix.lower()
    if suffix in ('.mpg', '.mpeg'):
        # Re-encode to mp4 for better compatibility
        suffix = '.mp4'

    temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(temp_fd)
    temp_path = Path(temp_path)

    print(f"  Stripping audio...", file=sys.stderr, flush=True)

    try:
        result = subprocess.run([
            'ffmpeg', '-y', '-i', str(video_path),
            '-an',  # No audio
            '-c:v', 'copy' if suffix == video_path.suffix.lower() else 'libx264',
            '-preset', 'ultrafast',
            str(temp_path)
        ], capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        return temp_path

    except Exception as e:
        # Clean up on failure
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to strip audio: {e}")


def upload_video(video_path: Path, display_name: Optional[str] = None, no_audio: bool = False) -> Any:
    """
    Upload video to Gemini and wait for processing.

    Args:
        video_path: Path to video file
        display_name: Optional display name for the file
        no_audio: If True, strip audio before upload to reduce token cost

    Returns the file object once it's ready for analysis.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    client = get_client()
    temp_file = None

    try:
        # Strip audio if requested
        if no_audio:
            temp_file = strip_audio(video_path)
            upload_path = temp_file
            mime_type = "video/mp4"  # Always mp4 after strip
        else:
            upload_path = video_path
            ext = video_path.suffix.lower()
            mime_type = VIDEO_MIME_TYPES.get(ext, "video/mp4")

        # Upload
        print(f"Uploading video: {video_path.name}...", file=sys.stderr, flush=True)
        uploaded_file = client.files.upload(
            file=str(upload_path),
            config=types.UploadFileConfig(
                display_name=display_name or video_path.name,
                mime_type=mime_type
            )
        )

        # Wait for processing
        print("Processing video...", file=sys.stderr, flush=True)
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            print(f"  Status: {uploaded_file.state.name}", file=sys.stderr, flush=True)

        if uploaded_file.state.name == "FAILED":
            raise RuntimeError(f"Video processing failed: {uploaded_file.state.name}")

        print("Video ready!", file=sys.stderr, flush=True)
        return uploaded_file

    finally:
        # Clean up temp file
        if temp_file and temp_file.exists():
            temp_file.unlink()


def analyze_video(
    video_file: Any,
    mode: AnalysisMode,
    prompt_prefix: str = ""
) -> BaseAnalysisResult:
    """
    Analyze video using a specific mode.

    Args:
        video_file: Uploaded Gemini file object
        mode: AnalysisMode defining the theoretical framework
        prompt_prefix: Optional context to prepend (e.g., technical metrics)

    Returns:
        Pydantic model instance with structured results
    """
    client = get_client()

    # Construct full prompt
    full_prompt = prompt_prefix + mode.prompt

    # Generate response with structured output
    print(f"Analyzing with mode: {mode.name}...", file=sys.stderr, flush=True)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[full_prompt, video_file],
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a sophisticated video analysis system. When given a video and "
                "analytical framework, provide structured insights following the schema precisely. "
                "Be theoretically rigorous but practically clear."
            ),
            response_mime_type="application/json",
            response_schema=mode.result_model,
            temperature=0.5,
        )
    )

    # Parse JSON response into Pydantic model
    try:
        result = mode.result_model.model_validate_json(response.text)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to parse response: {e}\n\nRaw response: {response.text}")


def analyze_with_custom_prompt(
    video_file: Any,
    custom_prompt: str,
    result_model: Type[BaseAnalysisResult],
    prompt_prefix: str = ""
) -> BaseAnalysisResult:
    """
    Analyze video with a custom user prompt.

    Uses SimpleResult model by default for flexible text responses.
    """
    client = get_client()

    full_prompt = f"""{prompt_prefix}
Call the analysis function with the following instructions:
{custom_prompt}

Place each relevant moment into the timecodes array with the timestamp and description.
"""

    print("Analyzing with custom prompt...", file=sys.stderr, flush=True)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[full_prompt, video_file],
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a video analysis system. Analyze the video according to the "
                "user's instructions and return structured timecode data."
            ),
            response_mime_type="application/json",
            response_schema=result_model,
            temperature=0.5,
        )
    )

    try:
        result = result_model.model_validate_json(response.text)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to parse response: {e}\n\nRaw response: {response.text}")
