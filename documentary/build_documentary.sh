#!/bin/bash
# =============================================================================
# THE GAZE AND THE MACHINE - Documentary Assembly Script
# =============================================================================
# Generated from video analysis data
# Uses FFmpeg to extract clips and concatenate into final edit
# =============================================================================

set -e

# Configuration
SOURCE_DIR="/Volumes/Vault_Σ/photography_shot_by_me/photography_and_archaeology(web)/recordings_various_cameras/zoo-spring-2025-misc"
OUTPUT_DIR="/Users/wer/video-analyzer-v2/documentary/output"
CLIPS_DIR="$OUTPUT_DIR/clips"
FINAL_OUTPUT="$OUTPUT_DIR/the_gaze_and_the_machine.mp4"

# Video settings (normalize all clips)
WIDTH=1920
HEIGHT=1080
FPS=25
CRF=18  # Quality (lower = better, 18-23 is good)

# Create directories
mkdir -p "$CLIPS_DIR"
mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "THE GAZE AND THE MACHINE - Assembly"
echo "=============================================="
echo ""

# Function to extract clip
# Usage: extract_clip <source_file> <start_time> <duration> <output_name>
extract_clip() {
    local src="$SOURCE_DIR/$1"
    local start="$2"
    local duration="$3"
    local out="$CLIPS_DIR/$4.mp4"

    if [ -f "$out" ]; then
        echo "  [skip] $4 (exists)"
        return
    fi

    echo "  [clip] $4"
    ffmpeg -hide_banner -loglevel error \
        -ss "$start" -t "$duration" -i "$src" \
        -vf "scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=$FPS" \
        -c:v libx264 -preset fast -crf $CRF \
        -c:a aac -b:a 128k \
        -y "$out"
}

# =============================================================================
# ACT 1: THE LOOK (~2 minutes)
# =============================================================================
echo ""
echo "=== ACT 1: THE LOOK ==="
echo ""

# Sequence 1A: Voyeuristic Gaze
echo "Sequence 1A: Voyeuristic Gaze"
extract_clip "M2U00248.MPG" "00:00:00" "5"  "01_flamingos_open"
extract_clip "M2U00248.MPG" "00:00:05" "10" "02_flamingos_scan"
extract_clip "M2U00245.MPG" "00:00:00" "8"  "03_swan_resting"
extract_clip "M2U00247.MPG" "00:00:00" "9"  "04_swan_swimming"
extract_clip "M2U00256.MPG" "00:00:05" "6"  "05_anaconda_coiled"

# Sequence 1B: Fetishistic Fragment
echo "Sequence 1B: Fetishistic Fragment"
extract_clip "M2U00248.MPG" "00:00:20" "8"  "06_flamingo_closeup"
extract_clip "M2U00256.MPG" "00:00:16" "6"  "07_anaconda_scales"
extract_clip "M2U00249.MPG" "00:00:00" "4"  "08_flamingo_abstract"

# Sequence 1C: Returned Gaze
echo "Sequence 1C: Returned Gaze"
extract_clip "M2U00252.MPG" "00:01:05" "5"  "09_snake_eyes"
extract_clip "M2U00261.MPG" "00:00:46" "4"  "10_rattlesnake_gaze"
extract_clip "M2U00243.MPG" "00:00:14" "5"  "11_camera_handoff"

# Sequence 1D: Human Gazes
echo "Sequence 1D: Human Gazes"
extract_clip "M2U00243.MPG" "00:00:23" "8"  "12_friends_posing"
extract_clip "M2U00243.MPG" "00:00:51" "3"  "13_love_videos_meta"

# =============================================================================
# ACT 2: THE MACHINE (~2-3 minutes)
# =============================================================================
echo ""
echo "=== ACT 2: THE MACHINE ==="
echo ""

# Sequence 2A: Car as Capsule
echo "Sequence 2A: Car as Capsule"
extract_clip "M2U00224.MPG" "00:00:01" "8"  "14_night_driving_blur"
extract_clip "M2U00224.MPG" "00:00:21" "6"  "15_ambient_light_touch"
extract_clip "M2U00226.MPG" "00:00:00" "5"  "16_infotainment_multicam"
extract_clip "M2U00226.MPG" "00:00:15" "10" "17_parking_garage"

# Sequence 2B: The Glitch
echo "Sequence 2B: The Glitch"
extract_clip "M2U00226.MPG" "00:00:30" "4"  "18_screen_glitch_critical"
extract_clip "M2U00243.MPG" "00:00:00" "4"  "19_asphalt_abstract"
extract_clip "M2U00243.MPG" "00:00:14" "4"  "20_camera_smear"
extract_clip "M2U00244.MPG" "00:00:15" "3"  "21_swan_static_break"
extract_clip "M2U00245.MPG" "00:00:52" "4"  "22_swan_corrupted"

# Sequence 2C: Lyotard Moment
echo "Sequence 2C: Lyotard Moment"
extract_clip "M2U00227.MPG" "00:00:26" "9"  "23_lyotard_book_show"
extract_clip "M2U00227.MPG" "00:00:35" "10" "24_lyotard_point"

# Sequence 2D: Screens Within Screens
echo "Sequence 2D: Screens Within Screens"
extract_clip "M2U00227.MPG" "00:03:40" "8"  "25_touchscreen_ambient"
extract_clip "M2U00227.MPG" "00:05:05" "5"  "26_blue_saturation"
extract_clip "M2U00263.MPG" "00:00:44" "5"  "27_surveillance_meta"
extract_clip "M2U00227.MPG" "00:05:40" "10" "28_side_cameras"

# =============================================================================
# ACT 3: THE REFUSAL (~1-2 minutes)
# =============================================================================
echo ""
echo "=== ACT 3: THE REFUSAL ==="
echo ""

# Sequence 3A: Woman Refuses
echo "Sequence 3A: Woman Refuses"
extract_clip "M2U00276.MPG" "00:00:00" "5"  "29_woman_walking"
extract_clip "M2U00276.MPG" "00:00:18" "4"  "30_woman_acknowledges"
extract_clip "M2U00276.MPG" "00:00:22" "4"  "31_woman_averts"
extract_clip "M2U00276.MPG" "00:00:30" "3"  "32_woman_covers_face"
extract_clip "M2U00276.MPG" "00:00:39" "6"  "33_woman_sustained_refusal"
extract_clip "M2U00276.MPG" "00:00:10" "3"  "34_woman_eye_fragmented"

# Sequence 3B: Ski Mask
echo "Sequence 3B: Ski Mask"
extract_clip "M2U00227.MPG" "00:03:05" "5"  "35_ski_mask_donned"
extract_clip "M2U00227.MPG" "00:03:10" "6"  "36_masked_glance"
extract_clip "M2U00227.MPG" "00:05:20" "5"  "37_masked_driver"

# Sequence 3C: Dynamic Sublime
echo "Sequence 3C: Dynamic Sublime"
extract_clip "M2U00256.MPG" "00:00:50" "8"  "38_anaconda_power"
extract_clip "M2U00252.MPG" "00:01:05" "5"  "39_snake_unblinking"
extract_clip "M2U00253.MPG" "00:00:00" "6"  "40_emerald_boa"
extract_clip "M2U00263.MPG" "00:00:19" "5"  "41_viper_fangs"

# Sequence 3D: Final Non-Recovery
echo "Sequence 3D: Final Non-Recovery"
extract_clip "M2U00279.MPG" "00:00:17" "4"  "42_man_looks_away"
extract_clip "M2U00268.MPG" "00:00:17" "3"  "43_woman_brief_connection"
extract_clip "M2U00268.MPG" "00:00:18" "4"  "44_woman_withdraws"
extract_clip "M2U00268.MPG" "00:00:21" "4"  "45_pan_to_void"
extract_clip "M2U00227.MPG" "00:06:00" "6"  "46_mundane_ending_alt"

# =============================================================================
# CREATE CONCAT LIST
# =============================================================================
echo ""
echo "=== Creating concat list ==="

CONCAT_FILE="$OUTPUT_DIR/concat_list.txt"
> "$CONCAT_FILE"

for i in $(seq -w 01 46); do
    clip=$(ls "$CLIPS_DIR"/${i}_*.mp4 2>/dev/null | head -1)
    if [ -f "$clip" ]; then
        echo "file '$clip'" >> "$CONCAT_FILE"
    fi
done

echo "Concat list: $CONCAT_FILE"
echo "Clips ready: $(wc -l < "$CONCAT_FILE" | tr -d ' ')"

# =============================================================================
# CONCATENATE FINAL VIDEO
# =============================================================================
echo ""
echo "=== Concatenating final video ==="

ffmpeg -hide_banner -loglevel warning \
    -f concat -safe 0 -i "$CONCAT_FILE" \
    -c:v libx264 -preset slow -crf $CRF \
    -c:a aac -b:a 192k \
    -movflags +faststart \
    -y "$FINAL_OUTPUT"

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "=============================================="
echo "BUILD COMPLETE"
echo "=============================================="
echo ""
echo "Output: $FINAL_OUTPUT"
echo "Duration: $(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FINAL_OUTPUT" | xargs printf '%.1f') seconds"
echo "Size: $(du -h "$FINAL_OUTPUT" | cut -f1)"
echo ""
echo "Individual clips in: $CLIPS_DIR"
echo ""
echo "Next steps:"
echo "  1. Add voiceover track (see documentary/voiceover.md)"
echo "  2. Add music bed"
echo "  3. Fine-tune cuts in NLE if needed"
echo ""
