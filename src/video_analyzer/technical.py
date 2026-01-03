"""
Technical video analysis using FFmpeg.

Provides frame-level chaos metrics to inform perceptual analysis.
"""

import subprocess
import json
import re
from pathlib import Path
from .models import TechnicalMetrics


def get_technical_metrics(video_path: Path) -> TechnicalMetrics:
    """
    Run FFmpeg analysis to extract technical video metrics.
    
    Provides:
    - Duration and framerate
    - Scene change detection  
    - Frame-to-frame difference scores
    - Chaos index (1-10 scale)
    """
    
    # Get duration and framerate using ffprobe
    probe_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration:stream=r_frame_rate",
        "-of", "json",
        str(video_path)
    ]
    
    try:
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(probe_result.stdout)
        
        duration = float(probe_data["format"]["duration"])
        
        # Parse framerate (comes as "30000/1001" format)
        framerate_str = probe_data.get("streams", [{}])[0].get("r_frame_rate", "30/1")
        num, den = map(int, framerate_str.split("/"))
        framerate = num / (den or 1)
        
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ValueError) as e:
        raise RuntimeError(f"Failed to probe video: {e}")
    
    # Run scene detection - get frame scene scores
    scene_cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", "select='gte(scene,0)',metadata=print:file=-",
        "-an",
        "-f", "null",
        "-"
    ]
    
    scene_scores = []
    try:
        # Run scene detection, capture up to 500 frames
        result = subprocess.run(
            scene_cmd,
            capture_output=True,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=60
        )
        
        # Parse scene scores from output
        for line in result.stdout.split('\n')[:500]:
            if 'lavfi.scene_score' in line:
                match = re.search(r'lavfi\.scene_score=([0-9.]+)', line)
                if match:
                    score = float(match.group(1))
                    if score > 0:
                        scene_scores.append(score)
                        
    except subprocess.TimeoutExpired:
        # Fallback to simpler count-based detection
        pass
    except Exception as e:
        print(f"Warning: Scene detection failed, using fallback: {e}")
    
    # Fallback if scene detection failed
    if not scene_scores:
        try:
            fallback_cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", "select='gt(scene,0.1)',showinfo",
                "-an",
                "-f", "null",
                "-"
            ]
            result = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=60)
            count = len([l for l in result.stderr.split('\n') if 'pts_time' in l])
            scene_scores = [0.15] * count if count > 0 else [0.0]
        except:
            scene_scores = [0.0]
    
    # Calculate metrics
    scene_changes = len([s for s in scene_scores if s > 0.1])
    change_density = scene_changes / duration if duration > 0 else 0
    avg_scene_score = sum(scene_scores) / len(scene_scores) if scene_scores else 0
    max_scene_score = max(scene_scores) if scene_scores else 0
    
    # Calculate chaos index (1-10 scale)
    # Factors: change density, average scene score, max scene score
    density_factor = min(change_density * 2, 5)  # 0-5 points, caps at 2.5 changes/sec
    avg_factor = avg_scene_score * 20  # 0-2 points typical
    max_factor = max_scene_score * 3  # 0-3 points
    chaos_index = max(1, min(10, density_factor + avg_factor + max_factor))
    
    return TechnicalMetrics(
        duration=duration,
        framerate=framerate,
        scene_changes=scene_changes,
        change_density=change_density,
        avg_scene_score=avg_scene_score,
        max_scene_score=max_scene_score,
        chaos_index=chaos_index
    )


def format_technical_context(metrics: TechnicalMetrics) -> str:
    """
    Format technical metrics into a context string for the LLM.
    
    This gives the model frame-level data to inform its perceptual analysis.
    """
    
    chaos_interpretation = (
        "significant" if metrics.chaos_index >= 5 else "low"
    )
    
    density_note = ""
    if metrics.chaos_index >= 5 and metrics.change_density > 0.5:
        density_note = ("High change density suggests rapid movement or cuts that may appear "
                       "smoother than actual chaos. Account for masked instability.")
    elif metrics.chaos_index < 4:
        density_note = "Low technical chaos suggests genuinely stable footage."
    else:
        density_note = ("Moderate instability detected - look for subtle signs of handheld "
                       "operation or scene dynamism.")
    
    return f"""
TECHNICAL PRE-ANALYSIS (FFmpeg):
- Duration: {metrics.duration:.1f} seconds
- Framerate: {metrics.framerate:.1f} fps
- Scene changes detected: {metrics.scene_changes}
- Change density: {metrics.change_density:.2f} changes/second
- Average frame difference: {metrics.avg_scene_score:.3f}
- Max frame difference: {metrics.max_scene_score:.3f}
- Technical chaos index: {metrics.chaos_index:.1f}/10

IMPORTANT: The technical analysis shows {chaos_interpretation} frame-to-frame instability.
{density_note}

Use this technical data to inform your perceptual analysis. If the technical chaos index 
is high but the video appears calm, note this as "masked chaos" - the smoothness may be 
deceiving.

---

"""
