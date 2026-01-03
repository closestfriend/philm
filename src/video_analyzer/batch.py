"""
Batch processing for video analysis.

Handles multi-video, multi-mode analysis with efficient single-upload-per-video.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel

from .analyzer import upload_video, analyze_video, VIDEO_MIME_TYPES
from .modes import get_mode, ALL_MODES
from .output import format_for_display, format_as_json


console = Console()


# Supported video extensions
VIDEO_EXTENSIONS = set(VIDEO_MIME_TYPES.keys())


def find_videos(folder: Path, recursive: bool = False) -> list[Path]:
    """Find all video files in a folder."""
    videos = []

    # Check both lowercase and uppercase extensions
    extensions = list(VIDEO_EXTENSIONS) + [ext.upper() for ext in VIDEO_EXTENSIONS]

    if recursive:
        for ext in extensions:
            videos.extend(folder.rglob(f"*{ext}"))
    else:
        for ext in extensions:
            videos.extend(folder.glob(f"*{ext}"))

    # Dedupe and sort by name
    videos = list(set(videos))
    return sorted(videos, key=lambda p: p.name.lower())


def analyze_video_multi_mode(
    video_file: Any,
    modes: list[str],
    technical_context: str = ""
) -> dict[str, Any]:
    """
    Run multiple analysis modes on a single uploaded video.

    Returns dict mapping mode name to result.
    """
    results = {}

    for mode_name in modes:
        try:
            mode = get_mode(mode_name)
            result = analyze_video(video_file, mode, technical_context)
            results[mode_name] = result.model_dump()
        except Exception as e:
            console.print(f"  [red]Error in {mode_name}:[/red] {e}")
            results[mode_name] = {"error": str(e)}

    return results


def run_batch(
    folder: Path,
    modes: list[str],
    recursive: bool = False,
    output_dir: Optional[Path] = None,
    technical: bool = False,
    no_audio: bool = False,
) -> dict[str, Any]:
    """
    Run batch analysis on all videos in a folder.

    Args:
        folder: Directory containing videos
        modes: List of analysis mode names
        recursive: Search subdirectories
        output_dir: Where to save results (default: folder/vanalysis_results)
        technical: Include FFmpeg technical analysis
        no_audio: Strip audio before upload to reduce token cost

    Returns:
        Combined results dict
    """
    from .technical import get_technical_metrics, format_technical_context

    # Find videos
    videos = find_videos(folder, recursive)

    if not videos:
        console.print(f"[yellow]No video files found in {folder}[/yellow]")
        return {}

    console.print(Panel(
        f"[bold cyan]BATCH ANALYSIS[/bold cyan]\n"
        f"Folder: {folder}\n"
        f"Videos: {len(videos)}\n"
        f"Modes: {', '.join(modes)}",
        expand=False
    ))
    console.print()

    # Validate modes
    invalid_modes = [m for m in modes if m not in ALL_MODES]
    if invalid_modes:
        console.print(f"[red]Invalid modes:[/red] {', '.join(invalid_modes)}")
        console.print(f"Available: {', '.join(ALL_MODES.keys())}")
        return {}

    # Setup output directory
    if output_dir is None:
        output_dir = folder / "vanalysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each video
    all_results = {
        "batch_info": {
            "folder": str(folder),
            "modes": modes,
            "video_count": len(videos),
            "timestamp": datetime.now().isoformat(),
        },
        "videos": {}
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:

        main_task = progress.add_task(
            f"[cyan]Processing {len(videos)} videos...",
            total=len(videos)
        )

        for video_path in videos:
            video_name = video_path.name
            progress.update(main_task, description=f"[cyan]{video_name}")

            try:
                # Technical analysis (if requested)
                technical_context = ""
                if technical:
                    try:
                        metrics = get_technical_metrics(video_path)
                        technical_context = format_technical_context(metrics)
                    except Exception as e:
                        console.print(f"  [yellow]Technical analysis skipped:[/yellow] {e}")

                # Upload once
                console.print(f"\n[bold]{video_name}[/bold]")
                video_file = upload_video(video_path, no_audio=no_audio)

                # Run all modes
                video_results = analyze_video_multi_mode(
                    video_file,
                    modes,
                    technical_context
                )

                # Store results
                all_results["videos"][video_name] = {
                    "path": str(video_path),
                    "analyses": video_results
                }

                # Save individual video result
                video_output = output_dir / f"{video_path.stem}.json"
                with open(video_output, 'w') as f:
                    json.dump({
                        "video": video_name,
                        "path": str(video_path),
                        "modes": modes,
                        "analyses": video_results
                    }, f, indent=2)

                console.print(f"  [green]Saved:[/green] {video_output.name}")

            except Exception as e:
                console.print(f"  [red]Failed:[/red] {e}")
                all_results["videos"][video_name] = {"error": str(e)}

            progress.advance(main_task)

    # Save combined results
    combined_output = output_dir / "_batch_results.json"
    with open(combined_output, 'w') as f:
        json.dump(all_results, f, indent=2)

    console.print()
    console.print(Panel(
        f"[green]Batch complete![/green]\n"
        f"Results: {output_dir}\n"
        f"Combined: {combined_output.name}",
        expand=False
    ))

    return all_results
