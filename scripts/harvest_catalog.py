#!/usr/bin/env python3
"""
Harvest video descriptions from vanalyze results into a catalog.

Usage:
    python scripts/harvest_catalog.py ./footage/compressed/vanalysis_results -o catalog.csv
"""

import argparse
import csv
import json
import subprocess
from pathlib import Path


def get_duration(video_path: Path) -> str:
    """Get video duration as MM:SS string."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', str(video_path)],
            capture_output=True, text=True, check=True
        )
        seconds = float(result.stdout.strip())
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    except Exception:
        return "?"


def generate_title(description: str, max_words: int = 6) -> str:
    """Generate a short title from the first few words of description."""
    words = description.split()[:max_words]
    title = ' '.join(words)
    # Remove trailing punctuation
    title = title.rstrip('.,;:')
    # Capitalize first letter
    if title:
        title = title[0].upper() + title[1:]
    return title


def harvest_catalog(results_dir: Path, video_dir: Path = None) -> list[dict]:
    """
    Read all JSON results and extract catalog data.

    Returns list of dicts with: filename, title, duration, description
    """
    catalog = []

    for json_file in sorted(results_dir.glob("*.json")):
        if json_file.name.startswith("_"):
            continue  # Skip _batch_results.json

        try:
            with open(json_file) as f:
                data = json.load(f)

            # Get video description from paragraph analysis
            description = ""
            if "analyses" in data and "paragraph" in data["analyses"]:
                description = data["analyses"]["paragraph"].get("video_description", "")
            elif "video_description" in data:
                description = data["video_description"]

            # Original filename (strip _compressed suffix)
            compressed_name = json_file.stem  # MVI_0001_compressed
            original_name = compressed_name.replace("_compressed", "") + ".MOV"

            # Get duration from video file
            duration = "?"
            if video_dir:
                video_path = video_dir / json_file.stem.replace(".json", "")
                video_path = video_dir / (json_file.stem + ".mp4")
                if video_path.exists():
                    duration = get_duration(video_path)

            catalog.append({
                "filename": original_name,
                "title": generate_title(description),
                "duration": duration,
                "description": description,
            })

        except Exception as e:
            print(f"Warning: Failed to process {json_file.name}: {e}")

    return catalog


def main():
    parser = argparse.ArgumentParser(description="Harvest video catalog from vanalyze results")
    parser.add_argument("results_dir", type=Path, help="Directory containing JSON results")
    parser.add_argument("-o", "--output", type=Path, default=Path("catalog.csv"), help="Output CSV file")
    parser.add_argument("--video-dir", type=Path, help="Directory containing video files (for duration lookup)")

    args = parser.parse_args()

    if not args.results_dir.exists():
        print(f"Error: Results directory not found: {args.results_dir}")
        return 1

    # Default video dir to parent of results dir
    video_dir = args.video_dir or args.results_dir.parent

    print(f"Harvesting from: {args.results_dir}")
    catalog = harvest_catalog(args.results_dir, video_dir)

    if not catalog:
        print("No results found")
        return 1

    # Write CSV
    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "title", "duration", "description"])
        writer.writeheader()
        writer.writerows(catalog)

    print(f"Wrote {len(catalog)} entries to {args.output}")

    # Preview first few
    print("\nPreview:")
    print("-" * 80)
    for entry in catalog[:5]:
        print(f"{entry['filename']} ({entry['duration']})")
        print(f"  Title: {entry['title']}")
        print(f"  {entry['description'][:80]}...")
        print()


if __name__ == "__main__":
    main()
