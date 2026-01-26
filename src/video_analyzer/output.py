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
    BaudrillardMoment,
    EpistemicMoment,
    FoucaultMoment,
    VirilioMoment,
    ZizekMoment,
    BarthesMoment,
    BenjaminMoment,
    HauntologyMoment,
    SizzleMoment,
    SizzleResult,
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

    # Sizzle summary (if SizzleResult)
    if isinstance(result, SizzleResult):
        best_for = ", ".join([p.value for p in result.best_for])
        console.print(f"[bold]SUMMARY[/bold]")
        console.print(f"  Overall energy: [yellow]{result.overall_energy}/10[/yellow]")
        console.print(f"  Dominant tone: [cyan]{result.dominant_tone.value}[/cyan]")
        console.print(f"  Best for: [green]{best_for}[/green]")
        if result.warnings:
            console.print(f"  [red]Warnings: {', '.join(result.warnings)}[/red]")
        console.print()
        console.print("[bold]MOMENTS[/bold]")
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

        elif isinstance(item, BaudrillardMoment):
            # Baudrillard analysis
            precession_marker = " [red]⟲ PRECESSION[/red]" if item.precession else ""
            console.print(f"{time_str} [{item.order.value}] | {item.hyperreality_mode.value}{precession_marker}")
            console.print(f"         sign: {item.sign_value}")
            if item.implosion:
                console.print(f"         [dim]implosion: {item.implosion}[/dim]")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, EpistemicMoment):
            # Epistemic analysis
            verifiable = "[green]✓[/green]" if item.verifiable else "[red]✗[/red]"
            console.print(f"{time_str} [{item.mode.value}] | certainty: {item.certainty.value} {verifiable}")
            console.print(f"         claim: {item.claim}")
            if item.evidence_type:
                console.print(f"         evidence: {item.evidence_type}")
            if item.appeals_to:
                console.print(f"         appeals to: {item.appeals_to}")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, FoucaultMoment):
            # Foucault analysis
            console.print(f"{time_str} [{item.power_mode.value}] | surveillance: {item.surveillance.value}")
            console.print(f"         subject produced: {item.subject_produced}")
            if item.norm_enforced:
                console.print(f"         norm: {item.norm_enforced}")
            if item.resistance:
                console.print(f"         [green]resistance: {item.resistance}[/green]")
            console.print(f"         apparatus: {item.apparatus}")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, VirilioMoment):
            # Virilio analysis
            collapse = " [red]↯ COLLAPSE[/red]" if item.territory_collapse else ""
            real_time = " [cyan]⚡RT[/cyan]" if item.real_time else ""
            console.print(f"{time_str} [{item.speed_regime.value}] | accident: {item.accident.value}{collapse}{real_time}")
            console.print(f"         dromology: {item.dromology}")
            if item.war_machine:
                console.print(f"         [red]war machine: {item.war_machine}[/red]")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, ZizekMoment):
            # Zizek analysis
            console.print(f"{time_str} [{item.parallax.value}] | register: {item.register.value}")
            console.print(f"         ideology: {item.ideology_at_work}")
            console.print(f"         gap between: {item.gap_between}")
            if item.obscene_supplement:
                console.print(f"         [dim]obscene supplement: {item.obscene_supplement}[/dim]")
            if item.real_intrusion:
                console.print(f"         [red]Real intrusion: {item.real_intrusion}[/red]")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, BarthesMoment):
            # Barthes analysis
            death = " [dim]† DEATH PRESENT[/dim]" if item.death_present else ""
            console.print(f"{time_str} [{item.register.value}]{death}")
            if item.punctum_detail:
                console.print(f"         [bold]punctum: {item.punctum_detail}[/bold]")
            console.print(f"         denotation: {item.denotation}")
            console.print(f"         connotation: {item.connotation}")
            if item.myth_operation:
                console.print(f"         myth: {item.myth_operation.value}")
            if item.grain:
                console.print(f"         grain: {item.grain}")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, BenjaminMoment):
            # Benjamin analysis
            console.print(f"{time_str} [{item.aura_status.value}] | {item.cult_vs_exhibition}")
            if item.aura_source:
                console.print(f"         aura source: {item.aura_source}")
            if item.dialectical_image:
                console.print(f"         dialectical image: {item.dialectical_image.value}")
            if item.optical_unconscious:
                console.print(f"         optical unconscious: {item.optical_unconscious}")
            console.print(f"         reproducibility: {item.reproducibility}")
            if item.now_time:
                console.print(f"         [bold]Jetztzeit: {item.now_time}[/bold]")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, HauntologyMoment):
            # Hauntology analysis (Fisher/Han/Curtis)
            individual = " [red]↓ INDIVIDUALIZED[/red]" if item.suffering_individualized else ""
            achievement = " [yellow]⚙ ACHIEVEMENT-SUBJECT[/yellow]" if item.achievement_subject else ""
            console.print(f"{time_str} [{item.temporal_pathology.value}] | {item.smoothness.value}{individual}{achievement}")
            if item.capitalist_realism:
                console.print(f"         [dim]capitalist realism: {item.capitalist_realism.value}[/dim]")
            if item.hypernormal:
                console.print(f"         hypernormal: {item.hypernormal.value}")
            if item.lost_future:
                console.print(f"         lost future: {item.lost_future}")
            if item.libidinal_capture:
                console.print(f"         libidinal capture: {item.libidinal_capture}")
            console.print(f"         {item.description}")
            console.print()

        elif isinstance(item, SizzleMoment):
            # Sizzle reel production analysis
            energy_color = "red" if item.energy >= 8 else "yellow" if item.energy >= 5 else "dim"
            positions = ", ".join([p.value for p in item.sizzle_position])
            shot_type_upper = item.shot_type.value.upper()
            console.print(f"{time_str} [magenta]{shot_type_upper}[/magenta] | [{energy_color}]energy: {item.energy}/10[/{energy_color}] | {item.tone.value}")
            console.print(f"         subjects: {', '.join(item.subjects)}")
            console.print(f"         motion: {item.motion} | usable: {item.usable_seconds}")
            console.print(f"         [cyan]fits: {positions}[/cyan]")
            console.print(f"         [dim]{item.notes}[/dim]")
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
