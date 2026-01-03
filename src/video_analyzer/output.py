"""
Output formatting for analysis results.

Supports both human-readable and JSON output.
"""

import json
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    BaseAnalysisResult,
    AffectMoment,
    CameraMoment,
    LevinasianMoment,
    GazeMoment,
    SublimeMoment,
    RhythmMoment,
)


console = Console()


def format_as_json(result: BaseAnalysisResult, indent: int = 2) -> str:
    """Format result as JSON string."""
    return result.model_dump_json(indent=indent)


def format_for_display(result: BaseAnalysisResult, mode_name: str) -> None:
    """
    Format and print result in human-readable form using rich.
    
    Adapts formatting based on the type of analysis.
    """
    
    # Header
    console.print()
    console.print(Panel(
        f"[bold cyan]{mode_name.upper()}[/bold cyan]\n"
        f"[dim]{result.video_description}[/dim]",
        expand=False
    ))
    console.print()
    
    # Timecodes - format based on type
    for item in result.timecodes:
        time_str = f"[yellow]{item.time}[/yellow]"
        
        if isinstance(item, AffectMoment):
            # Affect analysis
            captured = "[green]CAPTURED[/green]" if item.captures else "[blue]escapes[/blue]"
            console.print(f"{time_str} intensity: [bold]{item.intensity}/10[/bold] | {captured}")
            console.print(f"         atmosphere: {item.atmosphere}")
            console.print(f"         vector: {item.vector}")
            console.print()
            
        elif isinstance(item, CameraMoment):
            # Camera analysis
            restless = " [red][RESTLESS][/red]" if item.restlessness else ""
            console.print(f"{time_str} {item.stability} | frenetic: [bold]{item.frenetic}/10[/bold] | "
                        f"proximity: {item.proximity or '?'}/10{restless}")
            console.print(f"         motion: {item.intentional_motion}")
            console.print(f"         {item.description}")
            if item.operator_presence:
                console.print(f"         operator: [dim]{item.operator_presence}[/dim]")
            console.print()
            
        elif isinstance(item, LevinasianMoment):
            # Levinas analysis
            mode_color = {
                "revelation": "green",
                "concealment": "red", 
                "trace": "blue"
            }.get(item.mode.value, "white")
            console.print(f"{time_str} intensity: [bold]{item.intensity}/10[/bold] | "
                        f"[{mode_color}]{item.mode.value}[/{mode_color}]")
            console.print(f"         {item.encounter}")
            console.print()
            
        elif isinstance(item, GazeMoment):
            # Gaze analysis
            fourth_wall = " [red]↔ 4TH WALL[/red]" if item.breaks_fourth_wall else ""
            console.print(f"{time_str} [{item.gaze_type.value}]{fourth_wall}")
            console.print(f"         subject: {item.subject_position}")
            console.print(f"         power: {item.power_dynamic}")
            console.print()
            
        elif isinstance(item, SublimeMoment):
            # Sublime analysis
            recovery = " [green]→ recovery[/green]" if item.recovery else ""
            console.print(f"{time_str} [{item.sublime_type.value}]{recovery}")
            console.print(f"         source: {item.overwhelm_source}")
            console.print(f"         {item.description}")
            console.print()
            
        elif isinstance(item, RhythmMoment):
            # Rhythm analysis
            console.print(f"{time_str} tempo: [bold]{item.tempo}/10[/bold] | {item.movement.value}")
            if item.refrain:
                console.print(f"         refrain: {item.refrain}")
            console.print(f"         {item.description}")
            console.print()
            
        elif hasattr(item, 'objects'):
            # Table format with objects
            console.print(f"{time_str} {item.text}")
            console.print(f"         Objects: {', '.join(item.objects)}")
            console.print()
            
        elif hasattr(item, 'value'):
            # Numeric chart data
            console.print(f"{time_str} [bold]{item.value}[/bold]")
            
        else:
            # Simple timecode
            console.print(f"{time_str} {item.text}")
            console.print()


def save_json(result: BaseAnalysisResult, output_path: str) -> None:
    """Save result to JSON file."""
    with open(output_path, 'w') as f:
        f.write(format_as_json(result))
    console.print(f"[green]✓[/green] Saved to: {output_path}")


def format_technical_summary(metrics: Any) -> None:
    """Display technical metrics summary."""
    table = Table(title="Technical Metrics (FFmpeg)", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Duration", f"{metrics.duration:.1f}s")
    table.add_row("Framerate", f"{metrics.framerate:.1f} fps")
    table.add_row("Scene changes", str(metrics.scene_changes))
    table.add_row("Change density", f"{metrics.change_density:.2f}/sec")
    table.add_row("Chaos index", f"{metrics.chaos_index:.1f}/10")
    
    console.print()
    console.print(table)
    console.print()
