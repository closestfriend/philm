"""
Local vision backend using Ollama.

Extracts frames from video and analyzes them with local vision models.
"""

import base64
import subprocess
import tempfile
import requests
from pathlib import Path
from dataclasses import dataclass


@dataclass
class LocalConfig:
    """Configuration for local analysis."""
    model: str = "qwen3-vl:4b"
    ollama_url: str = "http://localhost:11434"
    num_frames: int = 4
    timeout: int = 180


def extract_frames(video_path: Path, num_frames: int = 4, output_dir: Path = None) -> list[Path]:
    """
    Extract evenly-spaced frames from a video.

    Args:
        video_path: Path to video file
        num_frames: Number of frames to extract
        output_dir: Directory for output frames (uses temp if None)

    Returns:
        List of paths to extracted frame images
    """
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="philm_frames_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration
    probe_cmd = [
        'ffprobe', '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',
        str(video_path)
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip())

    # Calculate frame times (evenly spaced, avoiding very start/end)
    margin = duration * 0.05  # 5% margin
    usable_duration = duration - (2 * margin)

    if num_frames == 1:
        times = [duration / 2]
    else:
        step = usable_duration / (num_frames - 1)
        times = [margin + (i * step) for i in range(num_frames)]

    # Extract frames
    frames = []
    for i, t in enumerate(times):
        output_path = output_dir / f"frame_{i:02d}.jpg"
        cmd = [
            'ffmpeg', '-y', '-ss', str(t),
            '-i', str(video_path),
            '-vframes', '1',
            '-q:v', '2',
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True)
        if output_path.exists():
            frames.append(output_path)

    return frames


def analyze_frame(
    frame_path: Path,
    prompt: str,
    config: LocalConfig
) -> str:
    """
    Analyze a single frame using Ollama vision model.

    Args:
        frame_path: Path to image file
        prompt: Analysis prompt
        config: Local configuration

    Returns:
        Model response text
    """
    # Encode image
    with open(frame_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Call Ollama API
    resp = requests.post(
        f"{config.ollama_url}/api/generate",
        json={
            "model": config.model,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False
        },
        timeout=config.timeout
    )

    data = resp.json()
    if "response" in data:
        return data["response"].strip()
    elif "error" in data:
        raise RuntimeError(f"Ollama error: {data['error']}")
    else:
        raise RuntimeError(f"Unexpected response: {data}")


def aggregate_descriptions(descriptions: list[str], config: LocalConfig) -> str:
    """
    Aggregate multiple frame descriptions into a single video description.

    Uses the LLM to synthesize frame descriptions into a coherent summary.
    """
    if len(descriptions) == 1:
        return descriptions[0]

    # Format descriptions with frame numbers
    numbered = "\n".join(f"Frame {i+1}: {d}" for i, d in enumerate(descriptions))

    prompt = f"""Given these descriptions of frames from a video, write a single 1-2 sentence description that captures what the video contains. Be concise and focus on the main content.

{numbered}

Video description:"""

    resp = requests.post(
        f"{config.ollama_url}/api/generate",
        json={
            "model": config.model.replace("-vl", ""),  # Use text model if available
            "prompt": prompt,
            "stream": False
        },
        timeout=config.timeout
    )

    data = resp.json()
    if "response" in data:
        return data["response"].strip()
    else:
        # Fallback: just join descriptions
        return " ".join(descriptions)


def analyze_video_local(
    video_path: Path,
    config: LocalConfig = None,
    progress_callback=None
) -> dict:
    """
    Analyze a video using local Ollama vision model.

    Args:
        video_path: Path to video file
        config: Local configuration (uses defaults if None)
        progress_callback: Optional callback(stage, message) for progress updates

    Returns:
        Dict with video_description and frame_descriptions
    """
    if config is None:
        config = LocalConfig()

    def progress(stage, msg):
        if progress_callback:
            progress_callback(stage, msg)

    # Extract frames
    progress("extract", f"Extracting {config.num_frames} frames...")
    frames = extract_frames(video_path, config.num_frames)

    if not frames:
        raise RuntimeError(f"Failed to extract frames from {video_path}")

    progress("extract", f"Extracted {len(frames)} frames")

    # Analyze each frame
    frame_prompt = "Describe this image in one detailed sentence for video cataloging. Focus on the main subject, setting, and any notable elements."

    descriptions = []
    for i, frame in enumerate(frames):
        progress("analyze", f"Analyzing frame {i+1}/{len(frames)}...")
        desc = analyze_frame(frame, frame_prompt, config)
        descriptions.append(desc)
        progress("analyze", f"Frame {i+1}: {desc[:50]}...")

    # Aggregate into single description
    progress("aggregate", "Aggregating descriptions...")
    video_description = aggregate_descriptions(descriptions, config)

    # Cleanup temp frames
    for frame in frames:
        try:
            frame.unlink()
            frame.parent.rmdir()
        except:
            pass

    return {
        "video_description": video_description,
        "frame_descriptions": descriptions,
        "model": config.model,
        "num_frames": len(frames)
    }


def check_ollama_available(config: LocalConfig = None) -> tuple[bool, str]:
    """
    Check if Ollama is running and the model is available.

    Returns:
        (available, message)
    """
    if config is None:
        config = LocalConfig()

    try:
        resp = requests.get(f"{config.ollama_url}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, f"Ollama not responding (status {resp.status_code})"

        models = resp.json().get("models", [])
        model_names = [m["name"] for m in models]

        # Check for exact match or prefix match
        model_base = config.model.split(":")[0]
        if not any(config.model in name or model_base in name for name in model_names):
            return False, f"Model '{config.model}' not found. Available: {', '.join(model_names[:5])}"

        return True, f"Ollama ready with {config.model}"

    except requests.exceptions.ConnectionError:
        return False, "Ollama not running. Start with: ollama serve"
    except Exception as e:
        return False, f"Error checking Ollama: {e}"


def _chat_json(model: str, prompt: str, image_paths, ollama_url: str,
               schema: dict, timeout: int = 180) -> str:
    """POST a vision chat request to Ollama with JSON-schema-constrained output.

    Returns the raw JSON string from the model's message content.
    """
    import base64 as _b64

    images = [_b64.b64encode(Path(p).read_bytes()).decode("ascii") for p in image_paths]
    resp = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": schema,  # Ollama accepts a JSON schema object for structured output
            "messages": [{"role": "user", "content": prompt, "images": images}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
