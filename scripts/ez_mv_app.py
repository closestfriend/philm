#!/usr/bin/env python3
"""
EZ_MV — Beat-sync music video composer.
Run: uv run streamlit run scripts/ez_mv_app.py
"""

import json
import subprocess
import tempfile
from pathlib import Path

import streamlit as st

from ez_mv_core import (
    apply_cut_density,
    assemble,
    detect_beats,
    extract_thumbnail,
    generate_flash_frame,
    build_cut_schedule,
    load_philm_offset,
    probe_duration,
)

def pick_folder(title="Select folder") -> str | None:
    """Open native macOS folder picker via osascript. Returns path string or None if cancelled."""
    result = subprocess.run(
        ["osascript", "-e", f'POSIX path of (choose folder with prompt "{title}")'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None  # user cancelled
    return result.stdout.strip().rstrip("/") or None


st.set_page_config(page_title="EZ_MV", page_icon="🎬", layout="wide")
st.title("EZ_MV")
st.caption("Beat-sync music video composer")

# ─── SIDEBAR: SETTINGS ─────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")
    output_dir = Path(st.text_input("Output folder", value=str(Path.home() / "ez_mv_output")))
    output_dir.mkdir(parents=True, exist_ok=True)

    philm_dir_input = st.text_input("Philm analysis folder (optional)", value="")
    philm_dir = Path(philm_dir_input) if philm_dir_input.strip() else None

# ─── MUSIC TRACK ───────────────────────────────────────────────────────────────

st.header("1. Music Track")
# Apply any pending folder picked by the browse button (must happen before widget renders)
if "music_folder" not in st.session_state:
    st.session_state["music_folder"] = str(Path.home())
if "_music_folder_pending" in st.session_state:
    st.session_state["music_folder"] = st.session_state.pop("_music_folder_pending")

_mc1, _mc2 = st.columns([5, 1])
with _mc1:
    music_folder = st.text_input("Music folder", key="music_folder")
with _mc2:
    st.write("")
    if st.button("📂", key="browse_music", help="Browse for folder"):
        folder = pick_folder("Select music folder")
        if folder:
            st.session_state["_music_folder_pending"] = folder  # separate key — avoid widget conflict
            st.rerun()

music_path = None
music_files = []

if music_folder:
    music_folder_path = Path(music_folder)
    if not music_folder_path.is_dir():
        st.error(f"Folder not found: `{music_folder}`")
    else:
        music_files = sorted(
            p for p in music_folder_path.iterdir()
            if p.suffix.lower() in (".wav", ".mp3", ".aiff", ".m4a", ".flac")
        )
        if not music_files:
            st.warning("No audio files found in that folder.")
        else:
            st.success(f"✓ {len(music_files)} track{'s' if len(music_files) != 1 else ''} found")

if music_files:
    selected_music = st.selectbox(
        "Select track",
        options=music_files,
        format_func=lambda p: p.name,
    )
    music_path = selected_music
    st.caption(f"`{music_path}`")

# ─── CLIP POOL ─────────────────────────────────────────────────────────────────

st.header("2. Clips")
# Apply any pending folder picked by the browse button (must happen before widget renders)
if "clips_folder" not in st.session_state:
    st.session_state["clips_folder"] = ""
if "_clips_folder_pending" in st.session_state:
    st.session_state["clips_folder"] = st.session_state.pop("_clips_folder_pending")

_cc1, _cc2 = st.columns([5, 1])
with _cc1:
    clips_folder = st.text_input("Clips folder", key="clips_folder")
with _cc2:
    st.write("")
    if st.button("📂", key="browse_clips", help="Browse for folder"):
        folder = pick_folder("Select clips folder")
        if folder:
            st.session_state["_clips_folder_pending"] = folder  # separate key — avoid widget conflict
            st.rerun()

VIDEO_EXTS = {".mov", ".mp4", ".mxf", ".avi", ".mkv", ".m4v", ".mpg", ".mpeg"}

clips_config: list[dict] = []  # [{path, offset, enabled}]

if clips_folder:
    clips_folder_path = Path(clips_folder)
    if not clips_folder_path.is_dir():
        st.error(f"Folder not found: `{clips_folder}`")
    else:
        clip_files = sorted(
            p for p in clips_folder_path.iterdir()
            if p.suffix.lower() in VIDEO_EXTS
        )
        if not clip_files:
            st.warning("No video files found in that folder.")

if clips_folder and Path(clips_folder).is_dir() and clip_files:
    st.success(f"✓ {len(clip_files)} clip{'s' if len(clip_files) != 1 else ''} found — select which to include:")

    # Generate thumbnails (cached by session state)
    if "thumbnails" not in st.session_state or st.session_state.get("thumb_dir_key") != clips_folder:
        st.session_state["thumb_dir_key"] = clips_folder
        thumb_dir = Path(tempfile.mkdtemp(prefix="ez_mv_thumbs_"))
        thumbs = {}
        with st.spinner("Generating previews..."):
            for clip in clip_files:
                thumb_path = thumb_dir / f"{clip.stem}.jpg"
                try:
                    extract_thumbnail(clip, thumb_path)
                    thumbs[clip] = thumb_path
                except Exception:
                    thumbs[clip] = None
        st.session_state["thumbnails"] = thumbs

    thumbs = st.session_state["thumbnails"]

    # Render clip checklist in 4-column grid
    cols_per_row = 4
    rows = [clip_files[i:i+cols_per_row] for i in range(0, len(clip_files), cols_per_row)]

    for row in rows:
        cols = st.columns(cols_per_row)
        for col, clip in zip(cols, row):
            with col:
                # Thumbnail
                if thumbs.get(clip):
                    st.image(str(thumbs[clip]), use_container_width=True)
                else:
                    st.markdown("*(no preview)*")

                # Checkbox
                enabled = st.checkbox(clip.stem, value=True, key=f"chk_{clip}")

                # Auto-fill offset from philm if available
                auto_offset = None
                if philm_dir and philm_dir.is_dir():
                    auto_offset = load_philm_offset(philm_dir, clip.stem)

                default_offset = auto_offset if auto_offset is not None else 0.0
                label = f"offset (s)" + (" ✦" if auto_offset is not None else "")
                offset = st.number_input(
                    label, min_value=0.0, value=default_offset,
                    step=0.5, key=f"off_{clip}"
                )

                if enabled:
                    clips_config.append({"path": clip, "offset": offset})

# ─── LIP-SYNC CLIP ─────────────────────────────────────────────────────────────

st.header("Lip-sync clip (optional)")

if "lipsync_path" not in st.session_state:
    st.session_state["lipsync_path"] = ""
if "_lipsync_path_pending" in st.session_state:
    st.session_state["lipsync_path"] = st.session_state.pop("_lipsync_path_pending")

_lc1, _lc2 = st.columns([5, 1])
with _lc1:
    lipsync_path_str = st.text_input("Performer clip", key="lipsync_path", placeholder="Path to lip-sync clip (optional)")
with _lc2:
    st.write("")
    if st.button("📂", key="browse_lipsync", help="Browse for file"):
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose file with prompt "Select lip-sync clip")'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            p = result.stdout.strip()
            if p:
                st.session_state["_lipsync_path_pending"] = p
                st.rerun()

lipsync_clip = None
lipsync_weight = 3.0

if lipsync_path_str.strip():
    lp = Path(lipsync_path_str.strip())
    if lp.exists() and lp.suffix.lower() in VIDEO_EXTS:
        lipsync_clip = lp

        col_thumb, col_ctrl = st.columns([1, 2])
        with col_thumb:
            if "lipsync_thumb" not in st.session_state or st.session_state.get("lipsync_thumb_key") != str(lp):
                st.session_state["lipsync_thumb_key"] = str(lp)
                thumb_dir = Path(tempfile.mkdtemp(prefix="ez_mv_ls_"))
                thumb_path = thumb_dir / "lipsync_thumb.jpg"
                try:
                    extract_thumbnail(lp, thumb_path)
                    st.session_state["lipsync_thumb"] = str(thumb_path)
                except Exception:
                    st.session_state["lipsync_thumb"] = None
            if st.session_state.get("lipsync_thumb"):
                st.image(st.session_state["lipsync_thumb"], use_container_width=True)

        with col_ctrl:
            lipsync_weight = st.slider(
                "Appearance frequency",
                min_value=1.0, max_value=10.0, value=3.0, step=0.5,
                help="Weight vs each B-roll clip at 1.0 — 3 means ~3× more likely than any single B-roll clip"
            )
            n_broll = len(clips_config)
            if n_broll > 0:
                pct = lipsync_weight / (n_broll + lipsync_weight) * 100
                st.caption(f"~{pct:.0f}% of cuts will be lip-sync")
    else:
        st.warning("File not found or unsupported format.")

# ─── CUT PARAMETERS ────────────────────────────────────────────────────────────

st.header("3. Cut Parameters")

col1, col2, col3 = st.columns(3)

with col1:
    cut_density = st.slider(
        "Cut density",
        min_value=0.25, max_value=2.0, value=1.0, step=0.25,
        help="0.25 = every 4 beats (slow) · 1.0 = every beat · 2.0 = every half-beat (chaos)"
    )
    density_label = {0.25: "every 4 beats", 0.5: "every 2 beats", 1.0: "every beat", 2.0: "every half-beat"}
    st.caption(density_label.get(cut_density, f"{cut_density}x"))

with col2:
    flash_prob = st.slider(
        "Flash frequency",
        min_value=0.0, max_value=0.5, value=0.25, step=0.05,
        help="Probability of white flash frame before each cut"
    )
    st.caption(f"{flash_prob*100:.0f}% of cuts")

with col3:
    stutter_prob = st.slider(
        "Stutter frequency",
        min_value=0.0, max_value=0.3, value=0.15, step=0.05,
        help="Probability of repeating a clip back-to-back"
    )
    st.caption(f"{stutter_prob*100:.0f}% of cuts")

# ─── GENERATE ──────────────────────────────────────────────────────────────────

st.header("4. Generate")

ready = music_path and len(clips_config) >= 2
if not ready:
    st.info("Select a music track and at least 2 clips to continue.")

if ready and st.button("⚡ Generate MV", type="primary", use_container_width=True):
    video_duration = probe_duration(music_path)

    with st.status("Generating...", expanded=True) as status:
        st.write(f"Music: `{music_path.name}` ({video_duration:.1f}s)")

        # Beat detection
        st.write("Detecting beats...")
        raw_beats, tempo = detect_beats(music_path)
        beat_times = apply_cut_density(raw_beats, cut_density)
        st.write(f"✓ {tempo:.1f} BPM → {len(beat_times)} cut points at {cut_density}x density")

        # Cut schedule — merge lip-sync clip into pool if provided
        all_clips = list(clips_config)
        if lipsync_clip:
            all_clips.append({"path": lipsync_clip, "offset": 0.0, "lip_sync": True, "weight": lipsync_weight})

        schedule, seed = build_cut_schedule(
            beat_times, all_clips, video_duration, flash_prob, stutter_prob
        )
        flash_n = sum(1 for s in schedule if s["flash_before"])
        stutter_n = sum(1 for s in schedule if s["stutter"])
        ls_n = sum(1 for s in schedule if s.get("lip_sync"))
        detail = f"{flash_n} flashes, {stutter_n} stutters" + (f", {ls_n} lip-sync" if ls_n else "")
        st.write(f"✓ {len(schedule)} cuts — {detail} (seed: {seed})")

        # Versioned output path
        existing = sorted(output_dir.glob("ez_mv_v*.mp4"))
        next_v = len(existing) + 1
        output_path = output_dir / f"ez_mv_v{next_v:02d}.mp4"
        st.write(f"Output: `{output_path}`")

        # Flash frame — reuse across runs via session state
        if "flash_dir" not in st.session_state:
            st.session_state["flash_dir"] = Path(tempfile.mkdtemp(prefix="ez_mv_flash_"))
        if "white_flash" not in st.session_state:
            st.session_state["white_flash"] = generate_flash_frame(st.session_state["flash_dir"])
        white_flash = st.session_state["white_flash"]

        # Segment extraction + assembly
        progress_bar = st.progress(0)
        progress_text = st.empty()

        def on_progress(current, total):
            progress_bar.progress(current / total)
            progress_text.text(f"Extracting segment {current}/{total}")

        assemble(schedule, white_flash, music_path, output_path, video_duration, on_progress)

        progress_bar.progress(1.0)
        progress_text.text("Done!")
        status.update(label="✓ Complete!", state="complete")

    st.success(f"Saved to `{output_path}`")

    # Save session metadata
    meta = {
        "output": str(output_path),
        "music": str(music_path),
        "seed": seed,
        "tempo": tempo,
        "cuts": len(schedule),
        "cut_density": cut_density,
        "flash_prob": flash_prob,
        "stutter_prob": stutter_prob,
        "clips": [str(c["path"]) for c in clips_config],
        "lipsync_clip": str(lipsync_clip) if lipsync_clip else None,
        "lipsync_weight": lipsync_weight if lipsync_clip else None,
    }
    meta_path = output_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2))
    st.caption(f"Session saved to `{meta_path}`")
