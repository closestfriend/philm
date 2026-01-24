"""
YOLO + Philm Hybrid Annotation Pipeline.

EXPERIMENTAL - Standalone tool, not part of core Philm.

Overlays object detection with theoretical vocabulary from Philm analysis.
Replaces standard YOLO labels ("person", "car") with theoretical terms
("achievement-subject", "speed prosthesis") based on selected mode.

Requirements (install separately):
    pip install opencv-python ultralytics supervision

Usage:
    python -m video_analyzer.annotate video.mp4 --mode hauntology
    python -m video_analyzer.annotate video.mp4 --analysis analysis.json --mode baudrillard
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import json
import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv


# ============================================================================
# CRITICAL THEORY VOCABULARY MAPPINGS
# ============================================================================

THEORY_MAPPINGS = {
    "hauntology": {
        "person": "achievement-subject",
        "bicycle": "analog ghost",
        "car": "capsule of atomization",
        "motorcycle": "libidinal accelerant",
        "bus": "collective remnant",
        "train": "fordist specter",
        "truck": "logistics of exhaustion",
        "boat": "escape fantasy",
        "airplane": "cancelled future",
        "traffic light": "managed circulation",
        "fire hydrant": "municipal ghost",
        "stop sign": "interpassive command",
        "parking meter": "monetized stillness",
        "bench": "defensive architecture",
        "bird": "escaped domesticate",
        "cat": "interpassive companion",
        "dog": "loyalty simulacrum",
        "horse": "agrarian phantom",
        "backpack": "mobile office",
        "umbrella": "personal climate control",
        "handbag": "identity container",
        "tie": "corporate noose",
        "suitcase": "precarity luggage",
        "bottle": "self-medication unit",
        "wine glass": "sophistication prop",
        "cup": "caffeine delivery system",
        "chair": "posture apparatus",
        "couch": "exhaustion receptacle",
        "potted plant": "nature substitute",
        "bed": "insufficient recovery zone",
        "dining table": "abandoned ritual site",
        "tv": "reality bypass device",
        "laptop": "portable panopticon",
        "mouse": "click labor tool",
        "remote": "channel surfing wand",
        "keyboard": "productivity interface",
        "cell phone": "burnout leash",
        "microwave": "time compression box",
        "refrigerator": "preservation anxiety",
        "book": "attention span ghost",
        "clock": "temporal discipline",
        "teddy bear": "childhood residue",
    },

    "virilio": {
        "person": "metabolic body",
        "bicycle": "metabolic vehicle",
        "car": "speed prosthesis",
        "motorcycle": "exposed accelerant",
        "bus": "mass transport vector",
        "train": "rail trajectory",
        "truck": "logistics vector",
        "boat": "territorial bypass",
        "airplane": "absolute speed machine",
        "traffic light": "circulation regulator",
        "stop sign": "velocity interruptor",
        "bench": "designated pause zone",
        "bird": "aerial vector",
        "cat": "ambush predator",
        "dog": "pursuit vector",
        "backpack": "mobile supply cache",
        "umbrella": "personal shelter",
        "suitcase": "deployment kit",
        "bottle": "hydration unit",
        "cup": "stimulant vessel",
        "knife": "cutting edge",
        "chair": "seated station",
        "couch": "recovery platform",
        "bed": "recovery station",
        "tv": "perception management screen",
        "laptop": "command terminal",
        "mouse": "targeting device",
        "remote": "remote control",
        "keyboard": "command input",
        "cell phone": "real-time communicator",
        "microwave": "rapid heating unit",
        "clock": "temporal coordinate",
    },

    "baudrillard": {
        "person": "sign-body",
        "bicycle": "retro-sign",
        "car": "sign-value vehicle",
        "motorcycle": "rebel simulacrum",
        "bus": "mass transit sign",
        "train": "industrial simulacrum",
        "truck": "logistics sign",
        "boat": "escape simulacrum",
        "airplane": "global village prop",
        "traffic light": "circulation code",
        "stop sign": "command simulacrum",
        "bench": "public space sign",
        "bird": "freedom sign",
        "cat": "independence simulacrum",
        "dog": "loyalty sign",
        "backpack": "adventure sign",
        "handbag": "status container",
        "tie": "professionalism sign",
        "suitcase": "mobility sign",
        "bottle": "hydration sign",
        "wine glass": "sophistication sign",
        "cup": "ritual sign",
        "chair": "comfort sign",
        "couch": "relaxation sign",
        "potted plant": "nature sign",
        "bed": "rest simulacrum",
        "tv": "reality machine",
        "laptop": "world interface",
        "mouse": "navigation sign",
        "remote": "control simulacrum",
        "keyboard": "expression interface",
        "cell phone": "connection sign",
        "book": "knowledge sign",
        "clock": "time sign",
        "teddy bear": "childhood sign",
        "skateboard": "rebel commodity",
    },

    "foucault": {
        "person": "docile body",
        "bicycle": "permitted locomotion",
        "car": "mobile enclosure",
        "motorcycle": "licensed risk",
        "bus": "mass transit apparatus",
        "train": "rail discipline",
        "truck": "commercial circulation",
        "airplane": "aviation subject",
        "traffic light": "circulation apparatus",
        "stop sign": "prohibition sign",
        "parking meter": "temporal surveillance",
        "bench": "positioned rest",
        "bird": "unregistered life",
        "cat": "domestic companion unit",
        "dog": "licensed animal",
        "backpack": "student apparatus",
        "handbag": "searchable container",
        "tie": "professional uniform",
        "suitcase": "customs object",
        "bottle": "labeled container",
        "wine glass": "age-verified",
        "knife": "regulated blade",
        "chair": "posture apparatus",
        "couch": "domestic containment",
        "bed": "sleep apparatus",
        "tv": "broadcast receiver",
        "laptop": "surveillance interface",
        "mouse": "click as record",
        "keyboard": "keystroke logging",
        "cell phone": "tracking device",
        "book": "curriculum object",
        "clock": "temporal apparatus",
    },

    "epistemic": {
        "person": "witness",
        "car": "evidence",
        "truck": "evidence",
        "cell phone": "recording device",
        "laptop": "documentation tool",
        "tv": "broadcast source",
        "book": "knowledge claim",
        "bottle": "forensic object",
    },

    "gaze": {
        "person": "looked-at body",
        "tv": "scopophilic object",
        "cell phone": "returned gaze device",
        "laptop": "screen-gaze",
        "camera": "gaze apparatus",
    },

    "affect": {
        "person": "affective body",
        "car": "movement vector",
        "cell phone": "intensity device",
    },
}


# ============================================================================
# TIMECODE PARSING
# ============================================================================

@dataclass
class FrameRange:
    """A range of frames with associated analysis data."""
    start_frame: int
    end_frame: int
    moment: dict


class TimecodeIndex:
    """Index Philm analysis timecodes for frame-based lookup."""

    def __init__(self, fps: float):
        self.fps = fps
        self.ranges: list[FrameRange] = []

    @staticmethod
    def _tc_to_seconds(tc: str) -> float:
        """Convert timecode string to seconds."""
        tc = tc.strip()
        parts = tc.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(parts[0])

    def add_moment(self, timecode: str, moment: dict):
        """Add a moment with its timecode to the index."""
        if "-" in timecode and not timecode.startswith("-"):
            start_tc, end_tc = timecode.split("-", 1)
            start_sec = self._tc_to_seconds(start_tc)
            end_sec = self._tc_to_seconds(end_tc)
        else:
            start_sec = end_sec = self._tc_to_seconds(timecode)

        start_frame = int(start_sec * self.fps)
        end_frame = int(end_sec * self.fps)

        self.ranges.append(FrameRange(start_frame, end_frame, moment))

    def get_moment(self, frame_num: int) -> Optional[dict]:
        """Get the analysis moment for a given frame number."""
        for r in self.ranges:
            if r.start_frame <= frame_num <= r.end_frame:
                return r.moment
        return self._get_closest(frame_num)

    def _get_closest(self, frame_num: int) -> Optional[dict]:
        """Get the closest moment by frame distance."""
        if not self.ranges:
            return None

        closest = min(self.ranges, key=lambda r: min(
            abs(r.start_frame - frame_num),
            abs(r.end_frame - frame_num)
        ))
        return closest.moment


# ============================================================================
# VOCABULARY MAPPER
# ============================================================================

class VocabularyMapper:
    """Maps YOLO classes to theoretical vocabulary."""

    def __init__(self, mode: str):
        self.mode = mode
        self.mappings = THEORY_MAPPINGS.get(mode, {})

    def get_label(self, class_name: str, moment: Optional[dict] = None) -> str:
        """Get theoretical label for detected object class."""
        class_name_lower = class_name.lower()
        return self.mappings.get(class_name_lower, class_name_lower)


# ============================================================================
# ANNOTATION STYLE
# ============================================================================

@dataclass
class AnnotationStyle:
    """Visual style for annotations."""
    box_thickness: int = 1
    text_scale: float = 0.4
    text_thickness: int = 1
    trace_length: int = 30


# ============================================================================
# MAIN PIPELINE
# ============================================================================

class PhilmAnnotator:
    """
    Hybrid YOLO + Philm annotation pipeline.

    Processes video frame-by-frame, running YOLO detection and
    replacing labels with theoretical vocabulary from Philm analysis.
    """

    def __init__(
        self,
        video_path: Path,
        analysis: dict,
        mode: str = "baudrillard",
        yolo_model: str = "yolov8n.pt",
        confidence: float = 0.3,
        style: Optional[AnnotationStyle] = None,
    ):
        self.video_path = Path(video_path)
        self.analysis = analysis
        self.mode = mode
        self.confidence = confidence
        self.style = style or AnnotationStyle()

        # Initialize YOLO
        self.model = YOLO(yolo_model)

        # Initialize tracker
        self.tracker = sv.ByteTrack()

        # Get video properties
        cap = cv2.VideoCapture(str(video_path))
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        # Build timecode index
        self.timecode_index = self._build_index()

        # Get vocabulary mapper
        self.mapper = VocabularyMapper(mode)

        # Create annotators
        self.box_annotator = sv.BoxAnnotator(
            thickness=self.style.box_thickness,
            color=sv.Color.WHITE,
        )

        self.label_annotator = sv.LabelAnnotator(
            text_scale=self.style.text_scale,
            text_thickness=self.style.text_thickness,
            text_color=sv.Color.WHITE,
            color=sv.Color.BLACK,
            text_position=sv.Position.TOP_LEFT,
        )

        self.trace_annotator = sv.TraceAnnotator(
            thickness=1,
            trace_length=self.style.trace_length,
            color=sv.Color.WHITE,
        )

    def _build_index(self) -> TimecodeIndex:
        """Build timecode index from analysis."""
        index = TimecodeIndex(self.fps)

        # Get timecodes from the specified mode's analysis
        mode_analysis = self.analysis.get("analyses", {}).get(self.mode, {})
        timecodes = mode_analysis.get("timecodes", [])

        for moment in timecodes:
            tc = moment.get("time", "")
            if tc:
                index.add_moment(tc, moment)

        return index

    def process_frame(self, frame: np.ndarray, frame_num: int) -> np.ndarray:
        """Process a single frame with detection and annotation."""

        # Run YOLO detection
        results = self.model(frame, conf=self.confidence, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)

        # Track objects
        detections = self.tracker.update_with_detections(detections)

        # Get current moment from analysis
        moment = self.timecode_index.get_moment(frame_num)

        # Generate theoretical labels
        labels = []
        for class_id in detections.class_id:
            class_name = self.model.names[class_id]
            theoretical_label = self.mapper.get_label(class_name, moment)
            labels.append(theoretical_label)

        # Annotate frame
        annotated = frame.copy()
        annotated = self.trace_annotator.annotate(annotated, detections)
        annotated = self.box_annotator.annotate(annotated, detections)
        annotated = self.label_annotator.annotate(
            annotated, detections, labels=labels
        )

        return annotated

    def run(self, output_path: Path, progress_callback: Optional[callable] = None):
        """Run the full annotation pipeline."""

        cap = cv2.VideoCapture(str(self.video_path))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(output_path),
            fourcc,
            self.fps,
            (self.width, self.height)
        )

        frame_num = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                annotated = self.process_frame(frame, frame_num)
                out.write(annotated)

                frame_num += 1

                if progress_callback:
                    progress_callback(frame_num, self.total_frames)

        finally:
            cap.release()
            out.release()

        return output_path


# ============================================================================
# PUBLIC API
# ============================================================================

def annotate_video(
    video_path: Path,
    analysis_path: Optional[Path] = None,
    analysis_dict: Optional[dict] = None,
    mode: str = "baudrillard",
    output_path: Optional[Path] = None,
    yolo_model: str = "yolov8n.pt",
    confidence: float = 0.3,
) -> Path:
    """
    Annotate video with theoretical labels.

    Args:
        video_path: Path to video file
        analysis_path: Path to Philm JSON analysis
        analysis_dict: Pre-loaded analysis dict
        mode: Philm mode to use for vocabulary
        output_path: Output video path
        yolo_model: YOLO model to use
        confidence: Detection confidence threshold

    Returns:
        Path to annotated video
    """
    video_path = Path(video_path)

    # Load analysis
    if analysis_dict:
        analysis = analysis_dict
    elif analysis_path:
        with open(analysis_path) as f:
            analysis = json.load(f)
    else:
        # Empty analysis - just use default mappings
        analysis = {"analyses": {mode: {"timecodes": []}}}

    # Determine output path
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_{mode}_annotated.mp4"

    output_path = Path(output_path)

    # Run annotation
    annotator = PhilmAnnotator(
        video_path=video_path,
        analysis=analysis,
        mode=mode,
        yolo_model=yolo_model,
        confidence=confidence,
    )

    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.console import Console

    console = Console()
    console.print(f"\n[bold]Annotating:[/bold] {video_path.name}")
    console.print(f"[bold]Mode:[/bold] {mode}")
    console.print(f"[bold]Output:[/bold] {output_path}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing frames...", total=annotator.total_frames)

        def callback(current, total):
            progress.update(task, completed=current)

        annotator.run(output_path, progress_callback=callback)

    console.print(f"\n[green]Complete:[/green] {output_path}")
    return output_path


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YOLO + Philm Annotation")
    parser.add_argument("video", type=Path, help="Video file path")
    parser.add_argument("--analysis", "-a", type=Path,
                        help="Philm JSON analysis file")
    parser.add_argument("--mode", "-m", default="hauntology",
                        choices=list(THEORY_MAPPINGS.keys()),
                        help="Analysis mode for vocabulary")
    parser.add_argument("--output", "-o", type=Path,
                        help="Output video path")
    parser.add_argument("--model", default="yolov8n.pt",
                        help="YOLO model")
    parser.add_argument("--confidence", "-c", type=float, default=0.3,
                        help="Detection confidence")

    args = parser.parse_args()

    annotate_video(
        video_path=args.video,
        analysis_path=args.analysis,
        mode=args.mode,
        output_path=args.output,
        yolo_model=args.model,
        confidence=args.confidence,
    )
