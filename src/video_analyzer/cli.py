"""
CLI for video-analyzer v2.

Built with typer for elegant command-line interaction.
"""

import sys
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from dotenv import load_dotenv

from . import __version__
from .analyzer import configure_genai, upload_video, analyze_video, analyze_with_custom_prompt
from .technical import get_technical_metrics, format_technical_context
from .modes import get_mode, get_chart_prompt, ALL_MODES, CHART_MODES
from .models import SimpleResult, NumericResult
from .output import format_for_display, format_as_json, save_json, format_technical_summary
from .batch import run_batch, find_videos
from .archive_cli import register_archive_commands
from .local import LocalConfig, analyze_video_local, check_ollama_available


# Load environment variables
load_dotenv()

app = typer.Typer(
    name="vanalyze",
    help="Philosophical video analysis using Gemini 2.5 Flash",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"video-analyzer v{__version__}")
        raise typer.Exit()


@app.command()
def main(
    video: Optional[Path] = typer.Argument(
        None,
        help="Path to video file (or use --folder for batch)",
    ),

    # Analysis modes (can combine multiple)
    captions: bool = typer.Option(False, "--captions", help="A/V captions"),
    paragraph: bool = typer.Option(False, "--paragraph", help="3-5 sentence summary"),
    key_moments: bool = typer.Option(False, "--key-moments", help="Extract key moments"),
    table: bool = typer.Option(False, "--table", help="5 key shots with objects"),
    affect: bool = typer.Option(False, "--affect", help="Massumi affect analysis"),
    camera: bool = typer.Option(False, "--camera", help="Camera kinetics analysis"),
    levinas: bool = typer.Option(False, "--levinas", help="Levinasian ethical analysis"),
    gaze: bool = typer.Option(False, "--gaze", help="Mulvey gaze analysis"),
    sublime: bool = typer.Option(False, "--sublime", help="Sublime classification"),
    rhythm: bool = typer.Option(False, "--rhythm", help="Deleuzian rhythm analysis"),
    baudrillard: bool = typer.Option(False, "--baudrillard", help="Simulacra/hyperreality analysis"),
    epistemic: bool = typer.Option(False, "--epistemic", help="Truth claims/evidence analysis"),
    foucault: bool = typer.Option(False, "--foucault", help="Power/surveillance analysis"),
    virilio: bool = typer.Option(False, "--virilio", help="Speed/accident analysis"),
    zizek: bool = typer.Option(False, "--zizek", help="Parallax/ideology analysis"),
    barthes: bool = typer.Option(False, "--barthes", help="Punctum/studium/mythology analysis"),
    benjamin: bool = typer.Option(False, "--benjamin", help="Aura/dialectical image analysis"),
    hauntology: bool = typer.Option(False, "--hauntology", help="Fisher/Han/Curtis capitalist realism"),
    sizzle: bool = typer.Option(False, "--sizzle", help="Sizzle reel production analysis"),

    # Chart mode
    chart: Optional[str] = typer.Option(
        None,
        "--chart",
        help=f"Generate chart data: {', '.join(CHART_MODES.keys())}"
    ),

    # Custom prompt
    custom: Optional[str] = typer.Option(None, "--custom", help="Custom analysis prompt"),

    # Options
    deep: bool = typer.Option(False, "--deep", help="Include FFmpeg technical analysis"),
    no_audio: bool = typer.Option(False, "--no-audio", help="Strip audio before upload (reduces cost ~25%)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save to file"),

    # Batch processing
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Process all videos in folder"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursive folder processing"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory for batch results"),

    # Local mode (Ollama)
    local: bool = typer.Option(False, "--local", help="Use local Ollama model instead of Gemini"),
    model: str = typer.Option("qwen3-vl:4b", "--model", help="Ollama model for local analysis"),
    frames: int = typer.Option(4, "--frames", help="Number of frames to extract (local mode)"),

    # Version
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        help="Show version"
    ),
):
    """
    Analyze video through various philosophical and aesthetic frameworks.

    Examples:

        vanalyze video.mp4 --affect

        vanalyze video.mp4 --gaze --paragraph --sublime

        vanalyze --folder ./videos --gaze --paragraph --sublime

        vanalyze video.mp4 --custom "find moments of stillness"

        vanalyze video.mp4 --affect --json --output results.json
    """

    # Determine active modes
    mode_flags = {
        "captions": captions,
        "paragraph": paragraph,
        "key-moments": key_moments,
        "table": table,
        "affect": affect,
        "camera": camera,
        "levinas": levinas,
        "gaze": gaze,
        "sublime": sublime,
        "rhythm": rhythm,
        "baudrillard": baudrillard,
        "epistemic": epistemic,
        "foucault": foucault,
        "virilio": virilio,
        "zizek": zizek,
        "barthes": barthes,
        "benjamin": benjamin,
        "hauntology": hauntology,
        "sizzle": sizzle,
    }

    active_modes = [name for name, active in mode_flags.items() if active]

    # =========================================================================
    # BATCH MODE
    # =========================================================================
    if folder:
        folder_path = Path(folder)

        try:
            exists = folder_path.exists()
        except PermissionError:
            console.print(f"[red]Error:[/red] Permission denied: {folder}")
            console.print("[dim]Grant Full Disk Access in System Settings → Privacy & Security[/dim]")
            raise typer.Exit(1)

        if not exists:
            console.print(f"[red]Error:[/red] Folder not found: {folder}")
            raise typer.Exit(1)

        if not folder_path.is_dir():
            console.print(f"[red]Error:[/red] Not a directory: {folder}")
            raise typer.Exit(1)

        if not active_modes:
            console.print("[red]Error:[/red] No analysis modes specified for batch.")
            console.print(f"Available: {', '.join(ALL_MODES.keys())}")
            raise typer.Exit(1)

        # Configure Gemini
        try:
            configure_genai()
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        # Run batch
        run_batch(
            folder=folder_path,
            modes=active_modes,
            recursive=recursive,
            output_dir=output_dir,
            technical=deep,
            no_audio=no_audio,
        )
        return

    # =========================================================================
    # LOCAL MODE (Ollama)
    # =========================================================================
    if local:
        # Validate video path
        if folder:
            # Local batch mode
            folder_path = Path(folder)
            if not folder_path.exists():
                console.print(f"[red]Error:[/red] Folder not found: {folder}")
                raise typer.Exit(1)

            videos = find_videos(folder_path, recursive)
            if not videos:
                console.print(f"[red]Error:[/red] No videos found in {folder}")
                raise typer.Exit(1)
        elif video:
            if not video.exists():
                console.print(f"[red]Error:[/red] Video not found: {video}")
                raise typer.Exit(1)
            videos = [video]
        else:
            console.print("[red]Error:[/red] No video file or --folder specified")
            raise typer.Exit(1)

        # Check Ollama availability
        config = LocalConfig(model=model, num_frames=frames)
        available, msg = check_ollama_available(config)
        if not available:
            console.print(f"[red]Error:[/red] {msg}")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] {msg}")

        # Process videos
        from rich.progress import Progress, SpinnerColumn, TextColumn
        import json

        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for i, vid in enumerate(videos):
                task = progress.add_task(f"[{i+1}/{len(videos)}] {vid.name}", total=None)

                def progress_cb(stage, msg):
                    progress.update(task, description=f"[{i+1}/{len(videos)}] {vid.name}: {msg}")

                try:
                    result = analyze_video_local(vid, config, progress_callback=progress_cb)
                    result["video"] = vid.name
                    result["path"] = str(vid)
                    results.append(result)
                    progress.update(task, description=f"[{i+1}/{len(videos)}] {vid.name}: ✓ Done")
                except Exception as e:
                    console.print(f"[red]Error processing {vid.name}:[/red] {e}")
                    results.append({"video": vid.name, "path": str(vid), "error": str(e)})

                progress.remove_task(task)

        # Output
        if len(videos) == 1 and not folder:
            # Single video output
            result = results[0]
            if output:
                with open(output, 'w') as f:
                    json.dump(result, f, indent=2)
                console.print(f"[green]Saved:[/green] {output}")
            elif json_output:
                print(json.dumps(result, indent=2))
            else:
                console.print(f"\n[bold]{video.name}[/bold]")
                console.print(f"[cyan]Description:[/cyan] {result['video_description']}")
                console.print(f"\n[dim]Frames analyzed: {result['num_frames']} | Model: {result['model']}[/dim]")
        else:
            # Batch output
            out_dir = output_dir or Path("./local_results")
            out_dir.mkdir(parents=True, exist_ok=True)

            for result in results:
                if "error" not in result:
                    out_file = out_dir / f"{Path(result['video']).stem}_local.json"
                    with open(out_file, 'w') as f:
                        json.dump(result, f, indent=2)

            console.print(f"\n[green]✓[/green] Processed {len(results)} videos")
            console.print(f"[dim]Results saved to: {out_dir}[/dim]")

        return

    # =========================================================================
    # SINGLE VIDEO MODE (Gemini)
    # =========================================================================

    # Validate video path
    if not video:
        console.print("[red]Error:[/red] No video file or --folder specified")
        console.print("Use --help for usage information")
        raise typer.Exit(1)

    if not video.exists():
        console.print(f"[red]Error:[/red] Video not found: {video}")
        raise typer.Exit(1)

    # Validate at least one mode
    if len(active_modes) == 0 and not chart and not custom:
        console.print("[red]Error:[/red] No analysis mode specified.")
        console.print(f"Available modes: {', '.join(ALL_MODES.keys())}")
        console.print("Or use --chart or --custom")
        raise typer.Exit(1)

    # Configure Gemini
    try:
        configure_genai()
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Technical analysis (if requested)
    technical_context = ""
    if deep:
        try:
            metrics = get_technical_metrics(video)
            format_technical_summary(metrics)
            technical_context = format_technical_context(metrics)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Technical analysis failed: {e}")
            console.print("Continuing without technical context...")

    # Upload video once
    try:
        video_file = upload_video(video, no_audio=no_audio)
    except Exception as e:
        console.print(f"[red]Error:[/red] Video upload failed: {e}")
        raise typer.Exit(1)

    # =========================================================================
    # MULTI-MODE ANALYSIS (single video, multiple modes)
    # =========================================================================
    if len(active_modes) > 1:
        from .batch import analyze_video_multi_mode
        import json

        console.print(f"\n[bold]Running {len(active_modes)} analyses...[/bold]\n")

        results = analyze_video_multi_mode(video_file, active_modes, technical_context)

        # Output
        combined = {
            "video": video.name,
            "path": str(video),
            "modes": active_modes,
            "analyses": results
        }

        if output:
            with open(output, 'w') as f:
                json.dump(combined, f, indent=2)
            console.print(f"[green]Saved:[/green] {output}")
        elif json_output:
            print(json.dumps(combined, indent=2))
        else:
            # Display each result
            from .modes import get_mode as get_mode_def
            from .models import BaseAnalysisResult

            for mode_name, result_data in results.items():
                if "error" not in result_data:
                    mode_def = get_mode_def(mode_name)
                    result_obj = mode_def.result_model.model_validate(result_data)
                    format_for_display(result_obj, mode_name)
        return

    # =========================================================================
    # SINGLE MODE ANALYSIS
    # =========================================================================
    try:
        if active_modes:
            # Standard mode
            mode_name = active_modes[0]
            mode = get_mode(mode_name)
            result = analyze_video(video_file, mode, technical_context)

        elif chart:
            # Chart mode
            if chart not in CHART_MODES:
                console.print(f"[red]Error:[/red] Unknown chart type: {chart}")
                console.print(f"Available: {', '.join(CHART_MODES.keys())}")
                raise typer.Exit(1)

            chart_prompt = get_chart_prompt(chart)
            result = analyze_with_custom_prompt(
                video_file,
                chart_prompt,
                NumericResult,
                technical_context
            )
            mode_name = f"chart-{chart}"

        else:
            # Custom prompt
            result = analyze_with_custom_prompt(
                video_file,
                custom,
                SimpleResult,
                technical_context
            )
            mode_name = "custom"

    except Exception as e:
        console.print(f"[red]Error:[/red] Analysis failed: {e}")
        raise typer.Exit(1)

    # Output
    if output:
        # Save to file
        save_json(result, str(output))
    elif json_output:
        # Print JSON to stdout
        print(format_as_json(result))
    else:
        # Rich formatted display
        format_for_display(result, mode_name)


# Register archive subcommands
register_archive_commands(app)


if __name__ == "__main__":
    app()
