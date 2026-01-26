#!/usr/bin/env python3
"""
Match analyzed footage to storyboard scenes.

Takes sizzle analysis results and a storyboard definition, produces a shot list
with match scores for each scene.

Usage:
    # Match footage to storyboard
    python scripts/match_storyboard.py storyboard.json -r ./sizzle_results/ -o shotlist.json

    # From catalog of pre-analyzed footage
    python scripts/match_storyboard.py storyboard.json -r ./sizzle_results/ --top 3

    # Output as markdown
    python scripts/match_storyboard.py storyboard.json -r ./sizzle_results/ --format md
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# =============================================================================
# STORYBOARD MODEL
# =============================================================================

@dataclass
class StoryboardScene:
    """A scene in a storyboard with requirements."""
    id: str
    name: str
    duration: str  # e.g., "0:00-0:06"
    description: str

    # Requirements (all optional - missing = don't care)
    min_energy: Optional[int] = None  # minimum energy (1-10)
    max_energy: Optional[int] = None  # maximum energy
    tones: Optional[list[str]] = None  # acceptable tones
    shot_types: Optional[list[str]] = None  # acceptable shot types
    positions: Optional[list[str]] = None  # sizzle positions (hook, demo, etc.)
    keywords: Optional[list[str]] = None  # keywords to match in subjects/notes


@dataclass
class Storyboard:
    """Full storyboard definition."""
    title: str
    scenes: list[StoryboardScene]

    @classmethod
    def from_dict(cls, data: dict) -> "Storyboard":
        """Parse storyboard from dict."""
        scenes = []
        for s in data.get("scenes", []):
            scenes.append(StoryboardScene(
                id=s.get("id", f"scene_{len(scenes)+1}"),
                name=s.get("name", "Unnamed"),
                duration=s.get("duration", ""),
                description=s.get("description", ""),
                min_energy=s.get("min_energy"),
                max_energy=s.get("max_energy"),
                tones=s.get("tones"),
                shot_types=s.get("shot_types"),
                positions=s.get("positions"),
                keywords=s.get("keywords"),
            ))
        return cls(title=data.get("title", "Untitled"), scenes=scenes)

    @classmethod
    def from_json(cls, path: Path) -> "Storyboard":
        """Load storyboard from JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))


# =============================================================================
# SIZZLE RESULT LOADING
# =============================================================================

@dataclass
class SizzleMoment:
    """A moment from sizzle analysis."""
    video: str
    video_path: str
    time: str
    shot_type: str
    energy: int
    tone: str
    subjects: list[str]
    motion: str
    positions: list[str]  # sizzle_position values
    usable_seconds: str
    notes: str


@dataclass
class SizzleFootage:
    """Analyzed footage with all its moments."""
    video: str
    path: str
    description: str
    overall_energy: int
    dominant_tone: str
    best_for: list[str]
    warnings: list[str]
    moments: list[SizzleMoment]


def load_sizzle_results(results_dir: Path) -> list[SizzleFootage]:
    """Load all sizzle analysis results from a directory."""
    footage = []

    for json_file in sorted(results_dir.glob("*.json")):
        if json_file.name.startswith("_"):
            continue

        try:
            with open(json_file) as f:
                data = json.load(f)

            # Handle both single-mode and multi-mode results
            sizzle_data = None
            if "analyses" in data and "sizzle" in data["analyses"]:
                sizzle_data = data["analyses"]["sizzle"]
                video_name = data.get("video", json_file.stem)
                video_path = data.get("path", str(json_file))
            elif "timecodes" in data and "overall_energy" in data:
                sizzle_data = data
                video_name = json_file.stem
                video_path = str(json_file)
            else:
                continue  # Not a sizzle result

            moments = []
            for tc in sizzle_data.get("timecodes", []):
                moments.append(SizzleMoment(
                    video=video_name,
                    video_path=video_path,
                    time=tc.get("time", ""),
                    shot_type=tc.get("shot_type", ""),
                    energy=tc.get("energy", 5),
                    tone=tc.get("tone", ""),
                    subjects=tc.get("subjects", []),
                    motion=tc.get("motion", ""),
                    positions=tc.get("sizzle_position", []),
                    usable_seconds=tc.get("usable_seconds", ""),
                    notes=tc.get("notes", ""),
                ))

            footage.append(SizzleFootage(
                video=video_name,
                path=video_path,
                description=sizzle_data.get("video_description", ""),
                overall_energy=sizzle_data.get("overall_energy", 5),
                dominant_tone=sizzle_data.get("dominant_tone", ""),
                best_for=sizzle_data.get("best_for", []),
                warnings=sizzle_data.get("warnings", []),
                moments=moments,
            ))

        except Exception as e:
            print(f"Warning: Failed to load {json_file.name}: {e}")

    return footage


# =============================================================================
# MATCHING ENGINE
# =============================================================================

@dataclass
class Match:
    """A potential match between footage and a scene."""
    scene_id: str
    scene_name: str
    video: str
    video_path: str
    timecode: str
    score: float  # 0-100
    reasons: list[str]
    warnings: list[str]
    moment: SizzleMoment


def score_moment_for_scene(moment: SizzleMoment, scene: StoryboardScene) -> tuple[float, list[str], list[str]]:
    """
    Score how well a moment matches a scene's requirements.

    Returns (score 0-100, reasons, warnings)
    """
    score = 50.0  # Base score
    reasons = []
    warnings = []

    # Energy matching
    if scene.min_energy is not None:
        if moment.energy >= scene.min_energy:
            bonus = min((moment.energy - scene.min_energy) * 5, 15)
            score += bonus
            reasons.append(f"energy {moment.energy} >= min {scene.min_energy}")
        else:
            penalty = (scene.min_energy - moment.energy) * 10
            score -= penalty
            warnings.append(f"energy {moment.energy} < required {scene.min_energy}")

    if scene.max_energy is not None:
        if moment.energy <= scene.max_energy:
            reasons.append(f"energy {moment.energy} within limit")
        else:
            penalty = (moment.energy - scene.max_energy) * 10
            score -= penalty
            warnings.append(f"energy {moment.energy} > max {scene.max_energy}")

    # Tone matching
    if scene.tones:
        if moment.tone in scene.tones:
            score += 15
            reasons.append(f"tone '{moment.tone}' matches")
        else:
            score -= 10
            warnings.append(f"tone '{moment.tone}' not in {scene.tones}")

    # Shot type matching
    if scene.shot_types:
        if moment.shot_type in scene.shot_types:
            score += 15
            reasons.append(f"shot type '{moment.shot_type}' matches")
        else:
            score -= 10
            warnings.append(f"shot type '{moment.shot_type}' not in {scene.shot_types}")

    # Position matching (most important for sizzle structure)
    if scene.positions:
        matching_positions = [p for p in moment.positions if p in scene.positions]
        if matching_positions:
            score += 20
            reasons.append(f"positions {matching_positions} match")
        else:
            score -= 15
            warnings.append(f"positions {moment.positions} don't match {scene.positions}")

    # Keyword matching in subjects and notes
    if scene.keywords:
        text_to_search = " ".join(moment.subjects + [moment.notes]).lower()
        matched_keywords = [kw for kw in scene.keywords if kw.lower() in text_to_search]
        if matched_keywords:
            score += len(matched_keywords) * 10
            reasons.append(f"keywords found: {matched_keywords}")

    # Clamp score
    score = max(0, min(100, score))

    return score, reasons, warnings


def match_footage_to_storyboard(
    footage: list[SizzleFootage],
    storyboard: Storyboard,
    min_score: float = 40.0
) -> dict[str, list[Match]]:
    """
    Match all footage moments to storyboard scenes.

    Returns dict mapping scene_id -> list of matches (sorted by score desc)
    """
    matches: dict[str, list[Match]] = {scene.id: [] for scene in storyboard.scenes}

    for clip in footage:
        for moment in clip.moments:
            for scene in storyboard.scenes:
                score, reasons, warnings = score_moment_for_scene(moment, scene)

                # Add footage-level warnings
                if clip.warnings:
                    warnings.extend([f"[footage] {w}" for w in clip.warnings])

                if score >= min_score:
                    matches[scene.id].append(Match(
                        scene_id=scene.id,
                        scene_name=scene.name,
                        video=moment.video,
                        video_path=moment.video_path,
                        timecode=moment.time,
                        score=score,
                        reasons=reasons,
                        warnings=warnings,
                        moment=moment,
                    ))

    # Sort each scene's matches by score
    for scene_id in matches:
        matches[scene_id].sort(key=lambda m: m.score, reverse=True)

    return matches


# =============================================================================
# OUTPUT FORMATTERS
# =============================================================================

def format_as_json(matches: dict[str, list[Match]], storyboard: Storyboard, top_n: int = 5) -> str:
    """Format matches as JSON."""
    output = {
        "storyboard": storyboard.title,
        "scenes": {}
    }

    for scene in storyboard.scenes:
        scene_matches = matches.get(scene.id, [])[:top_n]
        output["scenes"][scene.id] = {
            "name": scene.name,
            "duration": scene.duration,
            "description": scene.description,
            "matches": [
                {
                    "video": m.video,
                    "timecode": m.timecode,
                    "score": round(m.score, 1),
                    "shot_type": m.moment.shot_type,
                    "energy": m.moment.energy,
                    "tone": m.moment.tone,
                    "usable": m.moment.usable_seconds,
                    "reasons": m.reasons,
                    "warnings": m.warnings,
                }
                for m in scene_matches
            ]
        }

    return json.dumps(output, indent=2)


def format_as_markdown(matches: dict[str, list[Match]], storyboard: Storyboard, top_n: int = 5) -> str:
    """Format matches as markdown shot list."""
    lines = [
        f"# Shot List: {storyboard.title}",
        "",
        f"Generated from {sum(len(m) for m in matches.values())} potential matches.",
        ""
    ]

    for scene in storyboard.scenes:
        scene_matches = matches.get(scene.id, [])[:top_n]

        lines.append(f"## {scene.id}: {scene.name}")
        lines.append(f"**Duration:** {scene.duration}")
        lines.append(f"**Description:** {scene.description}")
        lines.append("")

        if not scene_matches:
            lines.append("*No suitable footage found.*")
            lines.append("")
            continue

        lines.append("| Rank | Video | Timecode | Score | Type | Energy | Tone | Notes |")
        lines.append("|------|-------|----------|-------|------|--------|------|-------|")

        for i, m in enumerate(scene_matches, 1):
            notes = "; ".join(m.reasons[:2])
            if m.warnings:
                notes += f" ⚠️ {m.warnings[0]}"
            lines.append(
                f"| {i} | {m.video} | {m.timecode} | {m.score:.0f} | "
                f"{m.moment.shot_type} | {m.moment.energy}/10 | {m.moment.tone} | {notes[:50]} |"
            )

        lines.append("")

    return "\n".join(lines)


def format_as_text(matches: dict[str, list[Match]], storyboard: Storyboard, top_n: int = 3) -> str:
    """Format matches as plain text for terminal."""
    lines = [
        f"SHOT LIST: {storyboard.title}",
        "=" * 60,
        ""
    ]

    for scene in storyboard.scenes:
        scene_matches = matches.get(scene.id, [])[:top_n]

        lines.append(f"[{scene.id}] {scene.name} ({scene.duration})")
        lines.append(f"    {scene.description[:70]}...")

        if not scene_matches:
            lines.append("    → No suitable footage found")
        else:
            for i, m in enumerate(scene_matches, 1):
                warn = " ⚠️" if m.warnings else ""
                lines.append(
                    f"    {i}. {m.video} @ {m.timecode} "
                    f"[{m.score:.0f}] {m.moment.shot_type}/{m.moment.energy}/10/{m.moment.tone}{warn}"
                )

        lines.append("")

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Match analyzed footage to storyboard scenes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("storyboard", type=Path, help="Storyboard JSON file")
    parser.add_argument("-r", "--results", type=Path, required=True,
                        help="Directory containing sizzle analysis results")
    parser.add_argument("-o", "--output", type=Path, help="Output file (default: stdout)")
    parser.add_argument("--format", choices=["json", "md", "text"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--top", type=int, default=3, help="Top N matches per scene (default: 3)")
    parser.add_argument("--min-score", type=float, default=40.0,
                        help="Minimum match score to include (default: 40)")

    args = parser.parse_args()

    # Validate inputs
    if not args.storyboard.exists():
        print(f"Error: Storyboard not found: {args.storyboard}")
        return 1

    if not args.results.exists():
        print(f"Error: Results directory not found: {args.results}")
        return 1

    # Load data
    print(f"Loading storyboard: {args.storyboard}")
    storyboard = Storyboard.from_json(args.storyboard)
    print(f"  → {len(storyboard.scenes)} scenes")

    print(f"Loading sizzle results: {args.results}")
    footage = load_sizzle_results(args.results)
    total_moments = sum(len(f.moments) for f in footage)
    print(f"  → {len(footage)} clips, {total_moments} moments")

    # Match
    print(f"Matching (min_score={args.min_score})...")
    matches = match_footage_to_storyboard(footage, storyboard, min_score=args.min_score)
    total_matches = sum(len(m) for m in matches.values())
    print(f"  → {total_matches} potential matches")

    # Format output
    if args.format == "json":
        output = format_as_json(matches, storyboard, top_n=args.top)
    elif args.format == "md":
        output = format_as_markdown(matches, storyboard, top_n=args.top)
    else:
        output = format_as_text(matches, storyboard, top_n=args.top)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Wrote: {args.output}")
    else:
        print()
        print(output)


if __name__ == "__main__":
    main()
