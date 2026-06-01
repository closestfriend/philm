#!/usr/bin/env python3
"""
Auto-generate sizzle reel from script specification and sizzle analysis.
Maps script scenes to best-scoring clips, extracts, and assembles final video.
"""

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SceneClip:
    """Clip to extract for a scene"""
    scene_num: int
    scene_name: str
    video: str
    timecode: str
    duration: float
    description: str


# Scene-to-clip mapping based on sizzle analysis
SCENE_CLIPS = [
    SceneClip(1, "HOOK", "MD_Home_Screen", "00:15-00:18", 3, "Rising Stars profiles"),
    SceneClip(1, "HOOK", "MD_Acquire_Player", "00:07-00:09", 2, "Player Value graph"),

    SceneClip(2, "MARKETPLACE", "MD_Marketplace", "00:11", 2.5, "Player Marketplace"),
    SceneClip(2, "MARKETPLACE", "MD_Acquire_Player", "00:17-00:18", 1, "Acquire button"),
    SceneClip(2, "MARKETPLACE", "MD_Leaderboard", "00:03-00:07", 2, "Portfolio"),

    SceneClip(3, "TENNIS_MIND", "MD_Marketplace", "00:04", 1.5, "Daily Draw content"),
    SceneClip(3, "TENNIS_MIND", "MD_Home_Screen", "00:12-00:15", 2.5, "Daily Draw section"),
    SceneClip(3, "TENNIS_MIND", "MD_Home_Screen", "00:15-00:18", 2, "Rising Stars"),

    SceneClip(4, "RESEARCH", "MD_Player_Details", "00:00-00:02", 2, "Player profile"),
    SceneClip(4, "RESEARCH", "MD_Player_Details", "00:16-00:18", 1.5, "Value/Rank graphs"),
    SceneClip(4, "RESEARCH", "MD_Player_Details", "00:04-00:06", 2, "Stats Over Time"),

    SceneClip(6, "SCORE_POINTS", "MD_Tournaments_2", "00:00-00:02", 2, "Tournament info"),
    SceneClip(6, "SCORE_POINTS", "MD_Tournaments_2", "00:09-00:10", 0.5, "Expand animation"),
    SceneClip(6, "SCORE_POINTS", "MD_Tournaments_2", "00:10-00:15", 2.5, "Match results"),

    SceneClip(7, "REWARDS", "MD_Leaderboard", "00:00-00:01", 1.5, "Leaderboard"),
    SceneClip(7, "REWARDS", "MD_Home_Screen", "00:18-00:23", 3, "Pro Shop"),

    SceneClip(8, "BUILD", "MD_Marketplace", "00:03", 0.5, "Quick transition"),
    SceneClip(8, "BUILD", "MD_Player_Details", "00:16-00:17", 0.5, "Tab switch"),
    SceneClip(8, "BUILD", "MD_Tournaments_2", "00:09-00:10", 0.5, "Expand"),
    SceneClip(8, "BUILD", "MD_Leaderboard", "00:01-00:02", 0.5, "Pagination"),
]


def parse_timecode(tc_str: str) -> tuple:
    """Parse '00:15-00:18' or '00:04' to (start_seconds, duration_seconds)"""
    if "-" in tc_str:
        start_str, end_str = tc_str.split("-")
    else:
        start_str = tc_str
        end_str = None

    def to_seconds(t):
        # Handle both MM:SS and HH:MM:SS formats
        parts = t.split(":")
        if len(parts) == 2:
            # MM:SS format
            return int(parts[0]) * 60 + int(parts[1])
        else:
            # HH:MM:SS format
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    start = to_seconds(start_str)
    if end_str:
        end = to_seconds(end_str)
        duration = end - start
    else:
        duration = 1.0  # default 1s if single timecode

    return start, duration


def extract_clip(video_path: Path, start: float, duration: float, output_path: Path,
                width: int = 1920, height: int = 1080):
    """Extract clip from video using ffmpeg"""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-t", str(duration),
        "-i", str(video_path),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-y", str(output_path)
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    results_dir = Path("/Users/hnsk/Downloads/MD_ScreenRecordings_v0.0.5a/vanalysis_results")
    videos_dir = Path("/Users/hnsk/Downloads/MD_ScreenRecordings_v0.0.5a")
    output_dir = Path("/Users/hnsk/Downloads/MD_ScreenRecordings_v0.0.5a/sizzle_reel")
    clips_dir = output_dir / "clips"

    # Setup
    output_dir.mkdir(exist_ok=True)
    clips_dir.mkdir(exist_ok=True)

    print("╭────────────────────────────────────────────────────╮")
    print("│ AUTO-EXTRACTING SIZZLE REEL CLIPS                 │")
    print("╰────────────────────────────────────────────────────╯\n")

    # Extract clips
    print("Extracting clips from videos...\n")
    concat_list = []

    for clip in SCENE_CLIPS:
        video_path = videos_dir / f"{clip.video}.mov"
        start, duration = parse_timecode(clip.timecode)

        # Cap to requested duration
        duration = min(duration, clip.duration)

        clip_name = f"{clip.scene_num:02d}_{clip.scene_name}_{len([c for c in SCENE_CLIPS if c.scene_num == clip.scene_num and SCENE_CLIPS.index(c) <= SCENE_CLIPS.index(clip)])}.mp4"
        output_path = clips_dir / clip_name

        print(f"  Scene {clip.scene_num} - {clip.description}")
        print(f"    Video: {clip.video}")
        print(f"    Time: {clip.timecode} → {duration:.1f}s")
        print(f"    Output: {clip_name}")

        try:
            extract_clip(video_path, start, duration, output_path)
            concat_list.append(f"file '{output_path.absolute()}'")
            print(f"    ✓ Extracted\n")
        except Exception as e:
            print(f"    ✗ Error: {e}\n")

    # Create concat file
    concat_file = output_dir / "concat_list.txt"
    with open(concat_file, "w") as f:
        for line in concat_list:
            f.write(line + "\n")

    # Concatenate final video
    print("\nAssembling final sizzle reel...")
    final_output = output_dir / "sizzle_reel_final.mp4"

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-y", str(final_output)
    ]

    subprocess.run(cmd, check=True)

    # Summary
    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(final_output)
    ]
    duration = subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip()

    size_cmd = ["du", "-h", str(final_output)]
    size = subprocess.run(size_cmd, capture_output=True, text=True).stdout.split()[0]

    print("\n╭────────────────────────────────────────────────────╮")
    print("│ SIZZLE REEL ASSEMBLED!                            │")
    print("╰────────────────────────────────────────────────────╯\n")
    print(f"Output: {final_output}")
    print(f"Duration: {float(duration):.1f} seconds")
    print(f"Size: {size}")
    print(f"Clips dir: {clips_dir}")


if __name__ == "__main__":
    main()
