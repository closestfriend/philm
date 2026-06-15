"""
Archive CLI commands for video-analyzer.

Provides commands for managing the video archive database:
- init: Initialize the archive database
- scan: Scan folders for videos
- status: Show archive status
- search: Query the archive
- stats: Show statistics
- process: Process unprocessed videos
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .archive import Archive, DEFAULT_ARCHIVE_PATH, get_video_duration

console = Console()
app = typer.Typer(
    name="archive",
    help="Manage video archive database",
    no_args_is_help=True,
)


@app.command()
def init(
    db_path: Optional[Path] = typer.Option(
        None, "--db", help=f"Database path (default: {DEFAULT_ARCHIVE_PATH})"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Reinitialize if exists"),
):
    """Initialize the archive database."""
    path = db_path or DEFAULT_ARCHIVE_PATH

    if path.exists() and not force:
        console.print(f"[yellow]Archive already exists:[/yellow] {path}")
        console.print("Use --force to reinitialize")
        raise typer.Exit(1)

    if path.exists() and force:
        path.unlink()
        console.print(f"[yellow]Removed existing archive[/yellow]")

    archive = Archive(path)
    archive.init_db()
    archive.close()

    console.print(f"[green]Archive initialized:[/green] {path}")


@app.command()
def scan(
    folder: Path = typer.Argument(..., help="Folder to scan for videos"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Scan subdirectories"),
    exclude: Optional[list[str]] = typer.Option(None, "--exclude", "-e", help="Exclude patterns"),
    db_path: Optional[Path] = typer.Option(None, "--db", help="Database path"),
    extract_duration: bool = typer.Option(False, "--duration", "-d", help="Extract video durations (slower)"),
):
    """Scan a folder for videos and add to archive."""
    if not folder.exists():
        console.print(f"[red]Error:[/red] Folder not found: {folder}")
        raise typer.Exit(1)

    archive = Archive(db_path)
    archive.init_db()

    console.print(f"Scanning: {folder}")
    if exclude:
        console.print(f"Excluding: {', '.join(exclude)}")

    new_count, existing_count = archive.scan_folder(folder, recursive, exclude)

    console.print(f"[green]New videos:[/green] {new_count}")
    console.print(f"[dim]Already in archive:[/dim] {existing_count}")

    if extract_duration and new_count > 0:
        console.print("\nExtracting durations...")
        unprocessed = archive.get_unprocessed(tier=-1, limit=new_count)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=len(unprocessed))
            for video in unprocessed:
                if video.get("duration_sec") is None:
                    duration = get_video_duration(Path(video["path"]))
                    if duration:
                        archive.update_video(video["id"], duration_sec=duration)
                progress.advance(task)

    archive.close()


@app.command()
def status(
    db_path: Optional[Path] = typer.Option(None, "--db", help="Database path"),
):
    """Show archive status."""
    archive = Archive(db_path)

    try:
        archive.connect()
    except Exception as e:
        console.print(f"[red]Error:[/red] Could not open archive: {e}")
        console.print(f"Run 'vanalyze archive init' to create one.")
        raise typer.Exit(1)

    stats = archive.get_stats()
    archive.close()

    # Header
    console.print(Panel(
        f"[bold cyan]VIDEO ARCHIVE[/bold cyan]\n"
        f"Database: {archive.db_path}",
        expand=False
    ))
    console.print()

    # Video counts
    table = Table(title="Videos by Processing Tier")
    table.add_column("Tier", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Count", justify="right", style="green")

    tier_names = {
        0: "Unprocessed",
        1: "Basic (paragraph/gaze/sublime)",
        2: "Full (all modes)",
    }
    for tier, count in sorted(stats["videos_by_tier"].items()):
        table.add_row(str(tier), tier_names.get(tier, "Unknown"), str(count))

    console.print(table)
    console.print()

    # Quick stats
    console.print(f"[bold]Total videos:[/bold] {stats['total_videos']}")
    console.print(f"[bold]Total duration:[/bold] {stats['total_duration_hours']:.1f} hours")
    console.print(f"[bold]Total cost:[/bold] ${stats['total_cost']:.2f}")


@app.command()
def stats(
    db_path: Optional[Path] = typer.Option(None, "--db", help="Database path"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Show stats for specific mode"),
):
    """Show detailed archive statistics."""
    archive = Archive(db_path)

    try:
        archive.connect()
    except Exception:
        console.print("[red]Archive not found.[/red] Run 'vanalyze archive init' first.")
        raise typer.Exit(1)

    stats = archive.get_stats()
    archive.close()

    # Gaze distribution
    if not mode or mode == "gaze":
        if stats["gaze_distribution"]:
            table = Table(title="Gaze Type Distribution")
            table.add_column("Type", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Bar", style="blue")

            total = sum(stats["gaze_distribution"].values())
            for gaze_type, count in sorted(
                stats["gaze_distribution"].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                pct = count / total * 100 if total else 0
                bar = "█" * int(pct / 2)
                table.add_row(gaze_type, str(count), bar)

            console.print(table)
            console.print(f"Fourth wall breaks: {stats['fourth_wall_breaks']}")
            console.print()

    # Sublime distribution
    if not mode or mode == "sublime":
        if stats["sublime_distribution"]:
            table = Table(title="Sublime Type Distribution")
            table.add_column("Type", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Bar", style="magenta")

            total = sum(stats["sublime_distribution"].values())
            for sub_type, count in sorted(
                stats["sublime_distribution"].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                pct = count / total * 100 if total else 0
                bar = "█" * int(pct / 2)
                table.add_row(sub_type, str(count), bar)

            console.print(table)
            recovery = stats["sublime_recovery"]
            total_sub = recovery["with_recovery"] + recovery["no_recovery"]
            if total_sub:
                no_recovery_pct = recovery["no_recovery"] / total_sub * 100
                console.print(f"Recovery: {recovery['with_recovery']} yes / {recovery['no_recovery']} no ({no_recovery_pct:.0f}% no recovery)")
            console.print()


@app.command()
def search(
    query: Optional[str] = typer.Argument(None, help="Text search query"),
    gaze: Optional[str] = typer.Option(None, "--gaze", "-g", help="Gaze type filter"),
    sublime: Optional[str] = typer.Option(None, "--sublime", "-s", help="Sublime type filter"),
    fourth_wall: bool = typer.Option(False, "--fourth-wall", help="Only fourth wall breaks"),
    no_recovery: bool = typer.Option(False, "--no-recovery", help="Only no-recovery sublime"),
    frenetic_min: Optional[int] = typer.Option(None, "--frenetic-min", help="Minimum frenetic level"),
    frenetic_max: Optional[int] = typer.Option(None, "--frenetic-max", help="Maximum frenetic level"),
    min_intensity: Optional[int] = typer.Option(None, "--min-intensity", help="affect peak intensity >= (1-10)"),
    tone: Optional[str] = typer.Option(None, "--tone", help="sizzle dominant tone (e.g. dramatic)"),
    best_for: Optional[str] = typer.Option(None, "--best-for", help="sizzle best_for contains (e.g. hook)"),
    min_energy: Optional[int] = typer.Option(None, "--min-energy", help="sizzle overall_energy >= (1-10)"),
    atmosphere: Optional[str] = typer.Option(None, "--atmosphere", help="affect atmosphere contains (e.g. blazing)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    db_path: Optional[Path] = typer.Option(None, "--db", help="Database path"),
):
    """Search the archive."""
    archive = Archive(db_path)

    try:
        archive.connect()
    except Exception:
        console.print("[red]Archive not found.[/red] Run 'vanalyze archive init' first.")
        raise typer.Exit(1)

    results = []
    facet_filters = any(x is not None for x in (min_intensity, tone, best_for, min_energy, atmosphere))

    # Structured / faceted search (intensity, energy, tone, best_for, atmosphere) — optionally + text
    if facet_filters:
        results = archive.search_facets(
            query=query, min_intensity=min_intensity, tone=tone, best_for=best_for,
            min_energy=min_energy, atmosphere=atmosphere, limit=limit)
        if results:
            table = Table(title=f"Structured search ({len(results)})")
            table.add_column("File", style="cyan", max_width=26)
            table.add_column("i", style="red"); table.add_column("E", style="yellow")
            table.add_column("tone", style="green"); table.add_column("best_for", style="magenta", max_width=22)
            table.add_column("Description", style="white", max_width=44)
            for r in results:
                table.add_row(
                    r["filename"], str(r.get("peak_intensity") or "-"), str(r.get("overall_energy") or "-"),
                    (r.get("dominant_tone") or "-"), (r.get("best_for") or "").strip("[]\"").replace('"', "")[:22],
                    (r.get("description") or "")[:44])
            console.print(table)
        else:
            console.print("[yellow]No clips match those filters.[/yellow]")

    # Text search
    elif query:
        results = archive.search_text(query, limit)
        if results:
            table = Table(title=f"Text Search: '{query}'")
            table.add_column("File", style="cyan", max_width=40)
            table.add_column("Description", style="white", max_width=60)

            for r in results:
                table.add_row(
                    r["filename"],
                    (r["description"] or "")[:60] + "..." if r.get("description") else "[dim]No description[/dim]"
                )
            console.print(table)
        else:
            console.print(f"[yellow]No results for:[/yellow] {query}")

    # Gaze search
    elif gaze or fourth_wall:
        results = archive.search_gaze(
            gaze_type=gaze,
            fourth_wall=fourth_wall if fourth_wall else None,
            limit=limit
        )
        if results:
            table = Table(title=f"Gaze Moments{' (fourth wall)' if fourth_wall else ''}")
            table.add_column("File", style="cyan", max_width=30)
            table.add_column("Time", style="yellow")
            table.add_column("Type", style="green")
            table.add_column("Subject", style="white", max_width=40)

            for r in results:
                table.add_row(
                    r["filename"],
                    r["timecode"],
                    r["gaze_type"],
                    (r["subject_position"] or "")[:40]
                )
            console.print(table)
        else:
            console.print("[yellow]No gaze moments found[/yellow]")

    # Sublime search
    elif sublime or no_recovery:
        results = archive.search_sublime(
            sublime_type=sublime,
            recovery=False if no_recovery else None,
            limit=limit
        )
        if results:
            table = Table(title=f"Sublime Moments{' (no recovery)' if no_recovery else ''}")
            table.add_column("File", style="cyan", max_width=30)
            table.add_column("Time", style="yellow")
            table.add_column("Type", style="magenta")
            table.add_column("Description", style="white", max_width=40)

            for r in results:
                table.add_row(
                    r["filename"],
                    r["timecode"],
                    r["sublime_type"],
                    (r["description"] or "")[:40]
                )
            console.print(table)
        else:
            console.print("[yellow]No sublime moments found[/yellow]")

    # Camera search
    elif frenetic_min is not None or frenetic_max is not None:
        results = archive.search_camera(
            min_frenetic=frenetic_min,
            max_frenetic=frenetic_max,
            limit=limit
        )
        if results:
            table = Table(title="Camera Moments")
            table.add_column("File", style="cyan", max_width=30)
            table.add_column("Time", style="yellow")
            table.add_column("Frenetic", style="red")
            table.add_column("Stability", style="green")
            table.add_column("Description", style="white", max_width=30)

            for r in results:
                table.add_row(
                    r["filename"],
                    r["timecode"],
                    str(r["frenetic"]),
                    r["stability"],
                    (r["description"] or "")[:30]
                )
            console.print(table)
        else:
            console.print("[yellow]No camera moments found[/yellow]")

    else:
        console.print("Specify a search query or filter. Use --help for options.")

    console.print(f"\n[dim]Found {len(results)} results[/dim]")
    archive.close()


@app.command()
def process(
    modes: str = typer.Option(
        "paragraph,gaze,sublime",
        "--modes", "-m",
        help="Comma-separated list of modes to run"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max videos to process"),
    tier: int = typer.Option(1, "--tier", "-t", help="Target processing tier"),
    no_audio: bool = typer.Option(False, "--no-audio", help="Strip audio before upload"),
    db_path: Optional[Path] = typer.Option(None, "--db", help="Database path"),
):
    """Process unprocessed videos in the archive."""
    import os
    from .providers import get_provider
    from .modes import get_mode
    from dotenv import load_dotenv

    load_dotenv()

    archive = Archive(db_path)

    try:
        archive.connect()
    except Exception:
        console.print("[red]Archive not found.[/red] Run 'vanalyze archive init' first.")
        raise typer.Exit(1)

    # Get unprocessed videos
    unprocessed = archive.get_unprocessed(tier=tier - 1, limit=limit)

    if not unprocessed:
        console.print("[green]All videos processed to tier {tier}![/green]")
        archive.close()
        return

    console.print(Panel(
        f"[bold cyan]ARCHIVE PROCESSING[/bold cyan]\n"
        f"Videos: {len(unprocessed)}\n"
        f"Modes: {modes}\n"
        f"Target tier: {tier}",
        expand=False
    ))

    # Resolve provider (env var VANALYZE_PROVIDER or default "gemini")
    try:
        provider = get_provider(os.getenv("VANALYZE_PROVIDER"))
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    mode_list = [m.strip() for m in modes.split(",")]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:

        main_task = progress.add_task(
            f"Processing {len(unprocessed)} videos...",
            total=len(unprocessed)
        )

        for video in unprocessed:
            video_path = Path(video["path"])
            progress.update(main_task, description=f"[cyan]{video_path.name}")

            if not video_path.exists():
                console.print(f"  [yellow]Skipped (not found):[/yellow] {video_path.name}")
                progress.advance(main_task)
                continue

            try:
                # Prepare video via provider
                console.print(f"\n[bold]{video_path.name}[/bold]")
                handle = provider.prepare(video_path, no_audio=no_audio)

                try:
                    # Run each mode
                    for mode_name in mode_list:
                        try:
                            mode = get_mode(mode_name)
                            result = provider.analyze(handle, mode, "")

                            # Store in database
                            archive.store_analysis(
                                video["id"],
                                mode_name,
                                result.model_dump()
                            )
                            console.print(f"  [green]✓[/green] {mode_name}")

                        except Exception as e:
                            console.print(f"  [red]✗[/red] {mode_name}: {e}")

                    # Update tier
                    archive.update_video(video["id"], tier=tier)
                finally:
                    provider.cleanup(handle)

            except Exception as e:
                console.print(f"  [red]Failed:[/red] {e}")

            progress.advance(main_task)

    archive.close()
    console.print("\n[green]Processing complete![/green]")


@app.command("import")
def import_results(
    results_dir: Path = typer.Argument(..., help="Directory with JSON result files"),
    tier: int = typer.Option(1, "--tier", "-t", help="Processing tier to assign"),
    db_path: Optional[Path] = typer.Option(None, "--db", help="Database path"),
):
    """Import existing JSON analysis results into archive."""
    import json

    if not results_dir.exists():
        console.print(f"[red]Error:[/red] Directory not found: {results_dir}")
        raise typer.Exit(1)

    archive = Archive(db_path)
    archive.init_db()

    # Find JSON files
    json_files = list(results_dir.glob("*.json"))
    json_files = [f for f in json_files if not f.name.startswith("_")]  # Skip _batch_results.json

    if not json_files:
        console.print("[yellow]No JSON files found[/yellow]")
        raise typer.Exit(1)

    console.print(f"Found {len(json_files)} result files")

    imported = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Importing...", total=len(json_files))

        for json_file in json_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)

                video_path = Path(data.get("path", ""))

                # Find video in archive by path
                video = archive.get_video_by_path(video_path)

                if not video:
                    # Try adding the video first
                    if video_path.exists():
                        archive.add_video(video_path)
                        video = archive.get_video_by_path(video_path)

                if not video:
                    console.print(f"  [yellow]Skipped:[/yellow] {json_file.name} (video not found)")
                    skipped += 1
                    progress.advance(task)
                    continue

                video_id = video["id"]

                # Import each mode's analysis
                analyses = data.get("analyses", {})
                for mode_name, result in analyses.items():
                    if "error" not in result:
                        archive.store_analysis(video_id, mode_name, result)

                # Update tier
                archive.update_video(video_id, tier=tier)
                imported += 1

            except Exception as e:
                console.print(f"  [red]Error:[/red] {json_file.name}: {e}")
                skipped += 1

            progress.advance(task)

    archive.close()

    console.print(f"\n[green]Imported:[/green] {imported} videos")
    if skipped:
        console.print(f"[yellow]Skipped:[/yellow] {skipped} files")


# Export for main CLI
def register_archive_commands(parent_app: typer.Typer):
    """Register archive commands with parent app."""
    parent_app.add_typer(app, name="archive")
