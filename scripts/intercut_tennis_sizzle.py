#!/usr/bin/env python3
"""
Intercut tennis footage with UI sizzle reel based on scene structure and energy levels.
"""

import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class IntercutSegment:
    """A segment in the final intercut reel"""
    scene_num: int
    content_type: str  # "ui" or "tennis"
    source_file: str
    timecode: str  # for tennis extracts
    duration: float
    description: str


# Tennis moments to extract
TENNIS_EXTRACTS = [
    ("tennis_hook", "/Volumes/wer/WERK/Feb_03__1600_56s_202602031656_z7pz5.mp4", "0:00", 2.5, "Hero shot - hand/racket"),
    ("tennis_highlights_1", "/Volumes/wer/WERK/Feb_03__1600_56s_202602031656_z7pz5.mp4", "0:24", 2.5, "Trading interface"),
    ("tennis_highlights_2", "/Volumes/wer/WERK/Feb_03__1600_56s_202602031656_z7pz5.mp4", "0:32", 3.5, "Celebration victory"),
    ("tennis_stadium", "/Volumes/wer/WERK/Feb_03__1600_56s_202602031656_z7pz5.mp4", "0:48", 4, "Grand stadium shot"),
]

# Final intercut structure - scenes with their clips in order
INTERCUT_STRUCTURE = [
    ("scene1_tennis", "tennis", "tennis_hook", 2.5, "Hook: Ball impact intro"),
    ("01_HOOK_1", "ui", None, 3.0, "Hook: Rising Stars"),
    ("01_HOOK_2", "ui", None, 2.0, "Hook: Player Value graph"),

    ("02_MARKETPLACE_1", "ui", None, 1.0, "Marketplace reveal"),
    ("02_MARKETPLACE_2", "ui", None, 1.0, "Acquire button"),
    ("02_MARKETPLACE_3", "ui", None, 2.0, "Portfolio"),

    ("03_TENNIS_MIND_1", "ui", None, 1.0, "Daily Draw"),
    ("03_TENNIS_MIND_2", "ui", None, 2.5, "Daily Draw section"),
    ("03_TENNIS_MIND_3", "ui", None, 2.0, "Rising Stars"),

    ("04_RESEARCH_1", "ui", None, 2.0, "Player profile"),
    ("04_RESEARCH_2", "ui", None, 1.5, "Value/Rank graphs"),
    ("04_RESEARCH_3", "ui", None, 2.0, "Stats Over Time"),

    ("scene5_tennis_1", "tennis", "tennis_highlights_1", 2.5, "Highlights: Trading interface"),
    ("scene5_tennis_2", "tennis", "tennis_highlights_2", 3.5, "Highlights: Victory celebration"),

    ("06_SCORE_POINTS_1", "ui", None, 2.0, "Tournament info"),
    ("06_SCORE_POINTS_2", "ui", None, 0.5, "Expand animation"),
    ("06_SCORE_POINTS_3", "ui", None, 2.5, "Match results"),

    ("07_REWARDS_1", "ui", None, 1.5, "Leaderboard"),
    ("07_REWARDS_2", "ui", None, 3.0, "Pro Shop"),

    ("08_BUILD_1", "ui", None, 0.5, "Quick transition"),
    ("08_BUILD_2", "ui", None, 0.5, "Tab switch"),
    ("08_BUILD_3", "ui", None, 0.5, "Expand"),
    ("08_BUILD_4", "ui", None, 0.5, "Pagination"),
    ("scene8_tennis", "tennis", "tennis_stadium", 3.0, "Build: Grand stadium"),
]


def parse_timecode(tc_str: str) -> tuple:
    """Parse timecode to seconds"""
    parts = tc_str.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def extract_tennis_clip(video_path: str, timecode: str, duration: float, output_path: Path):
    """Extract clip from tennis video"""
    start = parse_timecode(timecode)

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-t", str(duration),
        "-i", video_path,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-y", str(output_path)
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ui_clips_dir = Path("/Users/hnsk/Downloads/MD_ScreenRecordings_v0.0.5a/sizzle_reel/clips")
    output_dir = Path("/Users/hnsk/Downloads/MD_ScreenRecordings_v0.0.5a/final_sizzle")
    intercut_clips_dir = output_dir / "intercut_clips"

    output_dir.mkdir(exist_ok=True)
    intercut_clips_dir.mkdir(exist_ok=True)

    print("╭────────────────────────────────────────────────────╮")
    print("│ INTERCUTTING TENNIS WITH UI SIZZLE REEL          │")
    print("╰────────────────────────────────────────────────────╯\n")

    # Step 1: Extract tennis clips
    print("Extracting tennis moments...\n")
    tennis_clips = {}

    for clip_id, video_path, timecode, duration, desc in TENNIS_EXTRACTS:
        output_path = intercut_clips_dir / f"tennis_{clip_id}.mp4"
        print(f"  {clip_id}: {desc} ({duration:.1f}s)")
        extract_tennis_clip(video_path, timecode, duration, output_path)
        tennis_clips[clip_id] = output_path
        print(f"    ✓ Extracted to {output_path.name}\n")

    # Step 2: Build concat list with interleaved clips
    print("Building intercut sequence...\n")
    concat_file = output_dir / "intercut_list.txt"
    concat_lines = []
    total_duration = 0

    with open(concat_file, "w") as f:
        for clip_id, content_type, tennis_id, duration, desc in INTERCUT_STRUCTURE:
            if content_type == "ui":
                clip_path = ui_clips_dir / f"{clip_id}.mp4"
            else:  # tennis
                clip_path = tennis_clips[tennis_id]

            print(f"  {clip_id} ({duration:.1f}s) - {desc}")
            f.write(f"file '{clip_path.absolute()}'\n")
            total_duration += duration

    print(f"\n✓ Total duration: {total_duration:.1f}s\n")

    # Step 3: Concatenate final video
    print("Assembling final intercut reel...\n")
    final_output = output_dir / "sizzle_reel_with_tennis.mp4"

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
    print("│ FINAL SIZZLE REEL COMPLETE!                       │")
    print("╰────────────────────────────────────────────────────╯\n")
    print(f"Output: {final_output}")
    print(f"Duration: {float(duration):.1f} seconds")
    print(f"Size: {size}")


if __name__ == "__main__":
    main()
