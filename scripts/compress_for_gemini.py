#!/usr/bin/env python3
"""
Compress videos for Gemini analysis.

Converts videos to 720p H.264 MP4 with optional audio stripping.
Designed to prepare footage for Philm/vanalyze pipeline.

Usage:
    # Single file
    python compress_for_gemini.py input.MOV -o output/

    # Batch (directory)
    python compress_for_gemini.py /path/to/videos/ -o output/ --recursive

    # Strip audio (recommended for Philm - saves ~25% on upload)
    python compress_for_gemini.py input.MOV -o output/ --no-audio

    # Custom resolution
    python compress_for_gemini.py input.MOV -o output/ --height 480
"""

import argparse
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

VIDEO_EXTENSIONS = {'.mov', '.mp4', '.mpg', '.mpeg', '.avi', '.mkv', '.mts', '.m4v', '.webm'}


def get_video_info(input_path: Path) -> dict:
    """Get video duration and resolution using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-show_entries', 'format=duration:stream=width,height',
        '-of', 'csv=p=0',
        str(input_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        duration = None
        width, height = None, None
        for line in lines:
            parts = line.split(',')
            if len(parts) == 1 and duration is None:
                try:
                    duration = float(parts[0])
                except ValueError:
                    pass
            elif len(parts) >= 2:
                try:
                    width, height = int(parts[0]), int(parts[1])
                except ValueError:
                    pass
        return {'duration': duration, 'width': width, 'height': height}
    except subprocess.CalledProcessError:
        return {'duration': None, 'width': None, 'height': None}


def compress_video(
    input_path: Path,
    output_dir: Path,
    target_height: int = 720,
    strip_audio: bool = False,
    crf: int = 23,
    preset: str = 'medium'
) -> tuple[bool, str]:
    """
    Compress a video file for Gemini upload.

    Returns (success, message)
    """
    output_path = output_dir / f"{input_path.stem}_compressed.mp4"

    if output_path.exists():
        return True, f"Skipped (exists): {output_path.name}"

    # Get source info
    info = get_video_info(input_path)

    # Build ffmpeg command
    cmd = ['ffmpeg', '-y', '-i', str(input_path)]

    # Video filters - scale to target height, maintain aspect ratio
    # Only scale down, never up
    if info['height'] and info['height'] > target_height:
        cmd.extend(['-vf', f'scale=-2:{target_height}'])

    # Video codec settings
    cmd.extend([
        '-c:v', 'libx264',
        '-crf', str(crf),
        '-preset', preset,
        '-pix_fmt', 'yuv420p',  # compatibility
    ])

    # Audio handling
    if strip_audio:
        cmd.extend(['-an'])
    else:
        cmd.extend(['-c:a', 'aac', '-b:a', '128k'])

    # Output
    cmd.append(str(output_path))

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )

        # Get compressed file size
        original_size = input_path.stat().st_size / (1024 * 1024)
        compressed_size = output_path.stat().st_size / (1024 * 1024)
        ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        duration_str = f"{info['duration']:.1f}s" if info['duration'] else "?"
        return True, f"✓ {input_path.name} ({duration_str}) → {compressed_size:.1f}MB ({ratio:.0f}% reduction)"

    except subprocess.CalledProcessError as e:
        return False, f"✗ {input_path.name}: {e.stderr.decode()[:200] if e.stderr else 'Unknown error'}"


def find_videos(path: Path, recursive: bool = False) -> list[Path]:
    """Find all video files in a path."""
    if path.is_file():
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            return [path]
        return []

    if recursive:
        return [f for f in path.rglob('*') if f.suffix.lower() in VIDEO_EXTENSIONS]
    else:
        return [f for f in path.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]


def main():
    parser = argparse.ArgumentParser(
        description='Compress videos for Gemini/Philm analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('input', type=Path, help='Input video file or directory')
    parser.add_argument('-o', '--output', type=Path, required=True, help='Output directory')
    parser.add_argument('--height', type=int, default=720, help='Target height in pixels (default: 720)')
    parser.add_argument('--no-audio', action='store_true', help='Strip audio track')
    parser.add_argument('--recursive', '-r', action='store_true', help='Process directories recursively')
    parser.add_argument('--crf', type=int, default=23, help='Quality (0-51, lower=better, default: 23)')
    parser.add_argument('--preset', default='medium',
                        choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
                        help='Encoding speed/quality tradeoff (default: medium)')
    parser.add_argument('--workers', type=int, default=2, help='Parallel encoding workers (default: 2)')

    args = parser.parse_args()

    # Validate input
    if not args.input.exists():
        print(f"Error: Input path does not exist: {args.input}")
        sys.exit(1)

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Find videos
    videos = find_videos(args.input, args.recursive)

    if not videos:
        print(f"No video files found in: {args.input}")
        sys.exit(1)

    print(f"Found {len(videos)} video(s)")
    print(f"Output: {args.output}")
    print(f"Settings: {args.height}p, CRF {args.crf}, {'no audio' if args.no_audio else 'with audio'}")
    print("-" * 60)

    # Process videos
    success_count = 0

    if len(videos) == 1:
        # Single file - no parallelism needed
        ok, msg = compress_video(
            videos[0], args.output,
            target_height=args.height,
            strip_audio=args.no_audio,
            crf=args.crf,
            preset=args.preset
        )
        print(msg)
        success_count = 1 if ok else 0
    else:
        # Multiple files - use thread pool
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    compress_video,
                    v, args.output,
                    target_height=args.height,
                    strip_audio=args.no_audio,
                    crf=args.crf,
                    preset=args.preset
                ): v for v in videos
            }

            for future in as_completed(futures):
                ok, msg = future.result()
                print(msg)
                if ok:
                    success_count += 1

    print("-" * 60)
    print(f"Completed: {success_count}/{len(videos)} videos")

    if success_count < len(videos):
        sys.exit(1)


if __name__ == '__main__':
    main()
