#!/usr/bin/env python3
"""
drift_cut.py — Contemplative decay montage. Dean Blunt end of the spectrum.

Long holds. Off-beat cuts. Restraint over spectacle.
The piece starts clean and gradually loses fidelity — color drains,
compression artifacts accumulate, the image becomes a memory of itself.

Thin CLI over drift_core (the engine). See drift_core.build_composition.
"""

import argparse
import sys

import drift_core


def main():
    parser = argparse.ArgumentParser(description="Drift Cut — contemplative decay montage")
    parser.add_argument('--videos', required=True,
        help="Directory of clips, or comma-separated file paths")
    parser.add_argument('--audio', required=True,
        help="Audio file to score the composition")
    parser.add_argument('--output-dir', default='drift_cuts',
        help="Output directory (default: drift_cuts/)")
    parser.add_argument('--decay-intensity', type=float, default=0.7,
        help="How extreme the decay gets (0.0=none, 1.0=full). Default: 0.7")
    parser.add_argument('--min-hold', type=float, default=8.0,
        help="Minimum clip hold in seconds. Default: 8.0")
    parser.add_argument('--max-hold', type=float, default=20.0,
        help="Maximum clip hold in seconds. Default: 20.0")
    parser.add_argument('--split-chance', type=float, default=0.15,
        help="Probability of split-screen segment. Default: 0.15")
    parser.add_argument('--pip-chance', type=float, default=0.10,
        help="Probability of picture-in-picture segment. Default: 0.10")
    parser.add_argument('--seed', type=int, default=None,
        help="Random seed for reproducibility")
    args = parser.parse_args()

    print("\n╭────────────────────────────────────────────╮")
    print("│  DRIFT CUT — contemplative decay montage  │")
    print("╰────────────────────────────────────────────╯\n")

    def progress(current, total):
        print(f"  [{current}/{total}] rendering…", end="\r", flush=True)

    try:
        output_path = drift_core.build_composition(
            videos=args.videos,
            audio=args.audio,
            output_dir=args.output_dir,
            decay_intensity=args.decay_intensity,
            min_hold=args.min_hold,
            max_hold=args.max_hold,
            split_chance=args.split_chance,
            pip_chance=args.pip_chance,
            seed=args.seed,
            progress_callback=progress,
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"\n\n╭────────────────────────────────────────────╮")
    print(f"│  DONE!                                     │")
    print(f"╰────────────────────────────────────────────╯")
    print(f"Output: {output_path}\n")


if __name__ == '__main__':
    main()
