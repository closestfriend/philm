#!/bin/bash
# =============================================================================
# THE POSTMODERN ZOO - Documentary Assembly Script
# =============================================================================
# Adam Curtis meets Continental Philosophy
# =============================================================================

set -e

# Configuration
SOURCE_ZOO="/Volumes/Vault_Σ/photography_shot_by_me/photography_and_archaeology(web)/recordings_various_cameras/zoo-spring-2025-misc"
SOURCE_NYC="/Volumes/Vault_Σ/photography_shot_by_me/photography_and_archaeology(web)/recordings_various_cameras/SUMMER_2025_NYC_LA"
SOURCE_TIKTOK="/Volumes/Vault_Σ/photography_shot_by_me/movie files mpeg4 quicktime/mpeg4 movies"
OUTPUT_DIR="/Users/wer/video-analyzer-v2/documentary/output/postmodern_zoo"
CLIPS_DIR="$OUTPUT_DIR/clips"
FINAL_OUTPUT="$OUTPUT_DIR/the_postmodern_zoo.mp4"

# Video settings
WIDTH=1920
HEIGHT=1080
FPS=25
CRF=18

mkdir -p "$CLIPS_DIR"

echo "=============================================="
echo "THE POSTMODERN ZOO - Assembly"
echo "=============================================="
echo ""

# Function to extract clip
extract_clip() {
    local src="$1"
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
# MOVEMENT I: THE ENCLOSURE
# =============================================================================
echo ""
echo "=== MOVEMENT I: THE ENCLOSURE ==="
echo ""

# Scene 1: The Swan
echo "Scene 1: The Swan"
extract_clip "$SOURCE_ZOO/M2U00247.MPG" "00:00:00" "5"  "01_swan_glides"
extract_clip "$SOURCE_ZOO/M2U00247.MPG" "00:00:20" "10" "02_swan_rests"
extract_clip "$SOURCE_ZOO/M2U00256.MPG" "00:00:05" "6"  "03_snake_coiled"
extract_clip "$SOURCE_ZOO/M2U00256.MPG" "00:00:36" "5"  "04_snake_camouflaged"
extract_clip "$SOURCE_ZOO/M2U00256.MPG" "00:00:50" "5"  "05_snake_framed"

# Scene 2: The Refusal
echo "Scene 2: The Refusal"
extract_clip "$SOURCE_ZOO/M2U00276.MPG" "00:00:22" "3"  "06_woman_notices"
extract_clip "$SOURCE_ZOO/M2U00276.MPG" "00:00:30" "2"  "07_woman_turns"
extract_clip "$SOURCE_ZOO/M2U00276.MPG" "00:00:39" "2"  "08_woman_covers"
extract_clip "$SOURCE_ZOO/M2U00276.MPG" "00:00:41" "5"  "09_woman_sustained"

# Scene 3: The Mask
echo "Scene 3: The Mask"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:00:26" "9"  "10_lyotard_book"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:00:35" "15" "11_book_display"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:03:00" "5"  "12_driver_stares"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:03:05" "5"  "13_mask_on"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:03:10" "10" "14_masked_driver"

# =============================================================================
# MOVEMENT II: THE GLITCH
# =============================================================================
echo ""
echo "=== MOVEMENT II: THE GLITCH ==="
echo ""

# Scene 4: Digital Decay
echo "Scene 4: Digital Decay"
extract_clip "$SOURCE_ZOO/M2U00250.MPG" "00:00:03" "4"  "15_digital_chaos"
extract_clip "$SOURCE_ZOO/M2U00251.MPG" "00:00:00" "3"  "16_pure_noise"
extract_clip "$SOURCE_ZOO/M2U00226.MPG" "00:00:30" "3"  "17_screen_glitch"
extract_clip "$SOURCE_ZOO/M2U00267.MPG" "00:00:00" "4"  "18_moire_pattern"
extract_clip "$SOURCE_ZOO/M2U00284.MPG" "00:00:20" "8"  "19_corrupted_bird"
extract_clip "$SOURCE_ZOO/M2U00246.MPG" "00:00:12" "4"  "20_violent_pan"

# Scene 5: Screen Within Screen
echo "Scene 5: Screen Within Screen"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:05:05" "6"  "21_blue_interior"
extract_clip "$SOURCE_ZOO/M2U00226.MPG" "00:00:00" "5"  "22_infotainment"
extract_clip "$SOURCE_ZOO/M2U00231.MPG" "00:00:00" "5"  "23_computer_screen"
extract_clip "$SOURCE_ZOO/M2U00231.MPG" "00:00:34" "5"  "24_desktop_shift"

# =============================================================================
# MOVEMENT III: THE PRECESSION
# =============================================================================
echo ""
echo "=== MOVEMENT III: THE PRECESSION ==="
echo ""

# Scene 6: The Chemtrail
echo "Scene 6: The Chemtrail"
TIKTOK_FILE="$SOURCE_TIKTOK/nunca-hab_-a-visto-este-descaro-con-la-manipulación-del-clima-les-da-igual-todo.tiktoksss.app-tiktok-downloader.mp4"
extract_clip "$TIKTOK_FILE" "00:00:00" "14" "25_plane_distant"
extract_clip "$TIKTOK_FILE" "00:00:15" "14" "26_plane_zoom"
extract_clip "$TIKTOK_FILE" "00:00:30" "85" "27_plane_releases"
extract_clip "$TIKTOK_FILE" "00:01:56" "28" "28_trails_linger"

# Scene 7: The Zoo Returns
echo "Scene 7: The Zoo Returns"
extract_clip "$SOURCE_ZOO/M2U00248.MPG" "00:00:00" "6"  "29_flamingos_return"
extract_clip "$SOURCE_ZOO/M2U00252.MPG" "00:01:05" "5"  "30_snake_eyes"
extract_clip "$SOURCE_ZOO/M2U00261.MPG" "00:00:46" "4"  "31_rattlesnake"
extract_clip "$SOURCE_ZOO/M2U00243.MPG" "00:00:14" "4"  "32_camera_handoff"
extract_clip "$SOURCE_ZOO/M2U00268.MPG" "00:00:17" "3"  "33_woman_gaze"

# Scene 8: Coda
echo "Scene 8: Coda"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:06:00" "6"  "34_parked_night"
extract_clip "$SOURCE_ZOO/M2U00227.MPG" "00:05:20" "5"  "35_masked_final"

# =============================================================================
# BLACK FRAMES FOR PAUSES
# =============================================================================
echo ""
echo "=== Creating black frames ==="
ffmpeg -hide_banner -loglevel error \
    -f lavfi -i "color=black:s=${WIDTH}x${HEIGHT}:d=3" \
    -c:v libx264 -preset fast -crf $CRF \
    -y "$CLIPS_DIR/black_3s.mp4"

ffmpeg -hide_banner -loglevel error \
    -f lavfi -i "color=black:s=${WIDTH}x${HEIGHT}:d=2" \
    -c:v libx264 -preset fast -crf $CRF \
    -y "$CLIPS_DIR/black_2s.mp4"

# =============================================================================
# CREATE CONCAT LIST
# =============================================================================
echo ""
echo "=== Creating concat list ==="

CONCAT_FILE="$OUTPUT_DIR/concat_list.txt"
cat > "$CONCAT_FILE" << 'CONCAT'
# MOVEMENT I: THE ENCLOSURE
file 'clips/01_swan_glides.mp4'
file 'clips/02_swan_rests.mp4'
file 'clips/03_snake_coiled.mp4'
file 'clips/04_snake_camouflaged.mp4'
file 'clips/05_snake_framed.mp4'
file 'clips/black_2s.mp4'
file 'clips/06_woman_notices.mp4'
file 'clips/07_woman_turns.mp4'
file 'clips/08_woman_covers.mp4'
file 'clips/09_woman_sustained.mp4'
file 'clips/black_2s.mp4'
file 'clips/10_lyotard_book.mp4'
file 'clips/11_book_display.mp4'
file 'clips/12_driver_stares.mp4'
file 'clips/13_mask_on.mp4'
file 'clips/14_masked_driver.mp4'
file 'clips/black_3s.mp4'

# MOVEMENT II: THE GLITCH
file 'clips/15_digital_chaos.mp4'
file 'clips/16_pure_noise.mp4'
file 'clips/17_screen_glitch.mp4'
file 'clips/18_moire_pattern.mp4'
file 'clips/19_corrupted_bird.mp4'
file 'clips/20_violent_pan.mp4'
file 'clips/black_2s.mp4'
file 'clips/21_blue_interior.mp4'
file 'clips/22_infotainment.mp4'
file 'clips/23_computer_screen.mp4'
file 'clips/24_desktop_shift.mp4'
file 'clips/black_3s.mp4'

# MOVEMENT III: THE PRECESSION
file 'clips/25_plane_distant.mp4'
file 'clips/26_plane_zoom.mp4'
file 'clips/27_plane_releases.mp4'
file 'clips/28_trails_linger.mp4'
file 'clips/black_2s.mp4'
file 'clips/29_flamingos_return.mp4'
file 'clips/30_snake_eyes.mp4'
file 'clips/31_rattlesnake.mp4'
file 'clips/32_camera_handoff.mp4'
file 'clips/33_woman_gaze.mp4'
file 'clips/black_2s.mp4'
file 'clips/34_parked_night.mp4'
file 'clips/35_masked_final.mp4'
file 'clips/black_3s.mp4'
CONCAT

echo "Concat list created"

# =============================================================================
# CONCATENATE FINAL VIDEO
# =============================================================================
echo ""
echo "=== Concatenating final video ==="

cd "$OUTPUT_DIR"
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
echo "Duration: $(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FINAL_OUTPUT" 2>/dev/null | xargs printf '%.1f') seconds"
echo "Size: $(du -h "$FINAL_OUTPUT" | cut -f1)"
echo ""
echo "Clips in: $CLIPS_DIR"
echo ""
echo "Next steps:"
echo "  1. Record voiceover from documentary/scripts/the_postmodern_zoo.md"
echo "  2. Add ambient/drone music bed"
echo "  3. Color grade: desaturated, lifted blacks"
echo "  4. Mix V/O + music in DAW or NLE"
echo ""
