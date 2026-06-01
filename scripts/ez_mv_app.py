#!/usr/bin/env python3
"""
EZ_MV — Beat-sync music video composer + Drift contemplative montage.
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

from drift_core import (
    build_composition as drift_build_composition,
    ffprobe_duration as drift_probe_duration,
    get_video_files,
    plan_segments,
)


def pick_folder(title="Select folder") -> str | None:
    """Open native macOS folder picker via osascript. Returns path string or None if cancelled."""
    result = subprocess.run(
        ["osascript", "-e", f'POSIX path of (choose folder with prompt "{title}")'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip().rstrip("/") or None


def pick_file(title="Select file") -> str | None:
    """Open native macOS file picker via osascript. Returns path string or None if cancelled."""
    result = subprocess.run(
        ["osascript", "-e", f'POSIX path of (choose file with prompt "{title}")'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


st.set_page_config(page_title="EZ_MV", page_icon="🎬", layout="wide")
st.title("EZ_MV")
st.caption("Beat-sync music video composer + contemplative decay montage")

# ─── SIDEBAR: SETTINGS ─────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")
    output_dir = Path(st.text_input("Output folder", value=str(Path.home() / "ez_mv_output")))
    output_dir.mkdir(parents=True, exist_ok=True)
    st.caption("Used by both EZ_MV and Drift.")

    philm_dir_input = st.text_input("Philm analysis folder (optional)", value="")
    philm_dir = Path(philm_dir_input) if philm_dir_input.strip() else None

# ─── TABS ──────────────────────────────────────────────────────────────────────

tab_ezmv, tab_drift = st.tabs(["EZ_MV ⚡", "Drift 🌫"])

# ══════════════════════════════════════════════════════════════════════════════
# EZ_MV TAB
# ══════════════════════════════════════════════════════════════════════════════

with tab_ezmv:

    # ─── MUSIC TRACK ─────────────────────────────────────────────────────────

    st.header("1. Music Track")
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
                st.session_state["_music_folder_pending"] = folder
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

    # ─── CLIP POOL ───────────────────────────────────────────────────────────

    st.header("2. Clips")
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
                st.session_state["_clips_folder_pending"] = folder
                st.rerun()

    VIDEO_EXTS = {".mov", ".mp4", ".mxf", ".avi", ".mkv", ".m4v", ".mpg", ".mpeg"}

    clips_exclude = st.text_input(
        "Exclude subfolder (optional)",
        key="clips_exclude",
        placeholder="e.g. photography by hunter karman",
        help="Any clip whose path contains this string will be skipped",
    )

    clips_config: list[dict] = []
    clip_files = []

    if clips_folder:
        clips_folder_path = Path(clips_folder)
        if not clips_folder_path.is_dir():
            st.error(f"Folder not found: `{clips_folder}`")
        else:
            clip_files = sorted(
                p for p in clips_folder_path.rglob("*")
                if p.suffix.lower() in VIDEO_EXTS
                and (not clips_exclude or clips_exclude not in str(p))
            )
            if not clip_files:
                st.warning("No video files found in that folder.")

    if clips_folder and Path(clips_folder).is_dir() and clip_files:
        st.success(f"✓ {len(clip_files)} clip{'s' if len(clip_files) != 1 else ''} found — select which to include:")

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

        cols_per_row = 4
        rows = [clip_files[i:i+cols_per_row] for i in range(0, len(clip_files), cols_per_row)]

        for row in rows:
            cols = st.columns(cols_per_row)
            for col, clip in zip(cols, row):
                with col:
                    if thumbs.get(clip):
                        st.image(str(thumbs[clip]), use_container_width=True)
                    else:
                        st.markdown("*(no preview)*")

                    enabled = st.checkbox(clip.stem, value=True, key=f"chk_{clip}")

                    auto_offset = None
                    if philm_dir and philm_dir.is_dir():
                        auto_offset = load_philm_offset(philm_dir, clip.stem)

                    default_offset = auto_offset if auto_offset is not None else 0.0
                    label = "offset (s)" + (" ✦" if auto_offset is not None else "")
                    offset = st.number_input(
                        label, min_value=0.0, value=default_offset,
                        step=0.5, key=f"off_{clip}"
                    )

                    if enabled:
                        clips_config.append({"path": clip, "offset": offset})

    # ─── LIP-SYNC CLIP ───────────────────────────────────────────────────────

    st.header("Lip-sync clip (optional)")

    if "lipsync_path" not in st.session_state:
        st.session_state["lipsync_path"] = ""
    if "_lipsync_path_pending" in st.session_state:
        st.session_state["lipsync_path"] = st.session_state.pop("_lipsync_path_pending")

    _lc1, _lc2 = st.columns([5, 1])
    with _lc1:
        lipsync_path_str = st.text_input("Performer clip", key="lipsync_path",
                                          placeholder="Path to lip-sync clip (optional)")
    with _lc2:
        st.write("")
        if st.button("📂", key="browse_lipsync", help="Browse for file"):
            f = pick_file("Select lip-sync clip")
            if f:
                st.session_state["_lipsync_path_pending"] = f
                st.rerun()

    lipsync_clip = None
    lipsync_weight = 3.0
    lipsync_offset = 0.0

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
                lipsync_offset = st.number_input(
                    "Song offset (s)",
                    min_value=-60.0, max_value=60.0, value=0.0, step=0.5,
                    help="Shift clip timing relative to the song. Negative = clip starts earlier; positive = later."
                )
        else:
            st.warning("File not found or unsupported format.")

    # ─── CUT PARAMETERS ──────────────────────────────────────────────────────

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

    # ─── GENERATE ────────────────────────────────────────────────────────────

    st.header("4. Generate")

    ready = music_path and len(clips_config) >= 2
    if not ready:
        st.info("Select a music track and at least 2 clips to continue.")

    if ready and st.button("⚡ Generate MV", type="primary", use_container_width=True,
                            key="btn_ezmv_generate"):
        video_duration = probe_duration(music_path)

        with st.status("Generating...", expanded=True) as status:
            st.write(f"Music: `{music_path.name}` ({video_duration:.1f}s)")

            st.write("Detecting beats...")
            raw_beats, tempo = detect_beats(music_path)
            beat_times = apply_cut_density(raw_beats, cut_density)
            st.write(f"✓ {tempo:.1f} BPM → {len(beat_times)} cut points at {cut_density}x density")

            all_clips = list(clips_config)
            if lipsync_clip:
                all_clips.append({"path": lipsync_clip, "offset": lipsync_offset,
                                   "lip_sync": True, "weight": lipsync_weight})

            schedule, seed = build_cut_schedule(
                beat_times, all_clips, video_duration, flash_prob, stutter_prob
            )
            flash_n = sum(1 for s in schedule if s["flash_before"])
            stutter_n = sum(1 for s in schedule if s["stutter"])
            ls_n = sum(1 for s in schedule if s.get("lip_sync"))
            detail = f"{flash_n} flashes, {stutter_n} stutters" + (f", {ls_n} lip-sync" if ls_n else "")
            st.write(f"✓ {len(schedule)} cuts — {detail} (seed: {seed})")

            existing = sorted(output_dir.glob("ez_mv_v*.mp4"))
            next_v = len(existing) + 1
            output_path = output_dir / f"ez_mv_v{next_v:02d}.mp4"
            st.write(f"Output: `{output_path}`")

            if "flash_dir" not in st.session_state:
                st.session_state["flash_dir"] = Path(tempfile.mkdtemp(prefix="ez_mv_flash_"))
            if "white_flash" not in st.session_state:
                st.session_state["white_flash"] = generate_flash_frame(st.session_state["flash_dir"])
            white_flash = st.session_state["white_flash"]

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


# ══════════════════════════════════════════════════════════════════════════════
# DRIFT TAB
# ══════════════════════════════════════════════════════════════════════════════

with tab_drift:

    # ─── VIDEO FOLDER ────────────────────────────────────────────────────────

    st.header("1. Videos")

    if "drift_videos_folder" not in st.session_state:
        st.session_state["drift_videos_folder"] = ""
    if "_drift_videos_folder_pending" in st.session_state:
        st.session_state["drift_videos_folder"] = st.session_state.pop("_drift_videos_folder_pending")

    _dv1, _dv2 = st.columns([5, 1])
    with _dv1:
        drift_videos_folder = st.text_input("Videos folder", key="drift_videos_folder")
    with _dv2:
        st.write("")
        if st.button("📂", key="browse_drift_videos", help="Browse for folder"):
            folder = pick_folder("Select videos folder")
            if folder:
                st.session_state["_drift_videos_folder_pending"] = folder
                st.rerun()

    drift_video_files = []
    drift_clips_selected = []
    DRIFT_VIDEO_EXTS = {".mov", ".mp4", ".avi", ".mkv", ".mpg", ".mpeg", ".mts", ".m4v"}

    drift_exclude = st.text_input(
        "Exclude subfolder (optional)",
        key="drift_exclude",
        placeholder="e.g. photography by hunter karman",
        help="Any clip whose path contains this string will be skipped",
    )

    if drift_videos_folder:
        dvf_path = Path(drift_videos_folder)
        if not dvf_path.is_dir():
            st.error(f"Folder not found: `{drift_videos_folder}`")
        else:
            drift_video_files = sorted(
                f for f in dvf_path.rglob("*")
                if f.suffix.lower() in DRIFT_VIDEO_EXTS
                and (not drift_exclude or drift_exclude not in str(f))
            )
            if not drift_video_files:
                st.warning("No video files found in that folder.")
            else:
                st.success(f"✓ {len(drift_video_files)} clip{'s' if len(drift_video_files) != 1 else ''} found")

                if "drift_thumbnails" not in st.session_state or \
                        st.session_state.get("drift_thumb_dir_key") != drift_videos_folder:
                    st.session_state["drift_thumb_dir_key"] = drift_videos_folder
                    dt_dir = Path(tempfile.mkdtemp(prefix="drift_thumbs_"))
                    dt = {}
                    with st.spinner("Generating previews..."):
                        for clip in drift_video_files:
                            tp = dt_dir / f"{clip.stem}.jpg"
                            try:
                                extract_thumbnail(clip, tp)
                                dt[clip] = tp
                            except Exception:
                                dt[clip] = None
                    st.session_state["drift_thumbnails"] = dt

                dt = st.session_state["drift_thumbnails"]
                cols_per_row = 4
                rows = [drift_video_files[i:i+cols_per_row]
                        for i in range(0, len(drift_video_files), cols_per_row)]
                drift_clips_selected = []
                for row in rows:
                    cols = st.columns(cols_per_row)
                    for col, clip in zip(cols, row):
                        with col:
                            if dt.get(clip):
                                st.image(str(dt[clip]), use_container_width=True)
                            else:
                                st.markdown("*(no preview)*")
                            if st.checkbox(clip.stem, value=True, key=f"drift_chk_{clip}"):
                                drift_clips_selected.append(clip)

    # ─── AUDIO FILE ──────────────────────────────────────────────────────────

    st.header("2. Audio")

    if "drift_audio_path" not in st.session_state:
        st.session_state["drift_audio_path"] = ""
    if "_drift_audio_path_pending" in st.session_state:
        st.session_state["drift_audio_path"] = st.session_state.pop("_drift_audio_path_pending")

    _da1, _da2 = st.columns([5, 1])
    with _da1:
        drift_audio_path = st.text_input("Audio file", key="drift_audio_path",
                                          placeholder="Path to audio track")
    with _da2:
        st.write("")
        if st.button("📂", key="browse_drift_audio", help="Browse for file"):
            f = pick_file("Select audio file")
            if f:
                st.session_state["_drift_audio_path_pending"] = f
                st.rerun()

    drift_audio_valid = False
    drift_audio_dur = 0.0
    if drift_audio_path.strip():
        dap = Path(drift_audio_path.strip())
        if dap.exists():
            drift_audio_valid = True
            drift_audio_dur = drift_probe_duration(str(dap))
            st.caption(f"`{dap.name}` — {drift_audio_dur:.1f}s")
        else:
            st.error(f"File not found: `{drift_audio_path}`")

    # ─── PARAMETERS ──────────────────────────────────────────────────────────

    st.header("3. Parameters")

    pr1, pr2, pr3 = st.columns(3)
    with pr1:
        drift_decay = st.slider("Decay intensity", 0.0, 1.0, 0.7, 0.05,
                                 help="How extreme the visual degradation gets by the end")
        st.caption("0 = clean throughout · 1 = severe")
    with pr2:
        drift_min_hold = st.slider("Min hold (s)", 2.0, 30.0, 8.0, 1.0,
                                    help="Minimum duration per clip segment")
    with pr3:
        drift_max_hold = st.slider("Max hold (s)", 5.0, 60.0, 20.0, 1.0,
                                    help="Maximum duration per clip segment")

    pr4, pr5, pr6 = st.columns(3)
    with pr4:
        drift_split = st.slider("Split chance", 0.0, 0.5, 0.15, 0.05,
                                 help="Probability of a split-screen segment",
                                 format="%.2f")
        st.caption(f"{drift_split*100:.0f}% of segments")
    with pr5:
        drift_pip = st.slider("PiP chance", 0.0, 0.5, 0.10, 0.05,
                               help="Probability of a picture-in-picture segment",
                               format="%.2f")
        st.caption(f"{drift_pip*100:.0f}% of segments")
    with pr6:
        drift_seed_val = st.number_input("Seed", min_value=-1, max_value=99999,
                                          value=-1, step=1,
                                          help="-1 = random each run")
        st.caption("–1 = random" if drift_seed_val < 0 else f"seed: {drift_seed_val}")

    # Composition preview
    if drift_audio_valid and drift_audio_dur > 0:
        preview_seed = None if drift_seed_val < 0 else drift_seed_val
        preview_segs = plan_segments(drift_audio_dur, drift_min_hold, drift_max_hold,
                                      drift_split, drift_pip, seed=preview_seed)
        type_counts: dict[str, int] = {}
        for s in preview_segs:
            type_counts[s["type"]] = type_counts.get(s["type"], 0) + 1
        summary = ", ".join(f"{c} {t}" for t, c in type_counts.items())
        st.info(f"Estimated **{len(preview_segs)} segments** — {summary}")

    # ─── GENERATE ────────────────────────────────────────────────────────────

    st.header("4. Generate")

    drift_ready = bool(drift_clips_selected) and drift_audio_valid
    if not drift_ready:
        st.info("Select a video folder and audio file to continue.")

    if drift_ready and st.button("🌫 Generate Drift", type="primary", use_container_width=True,
                                  key="btn_drift_generate"):
        with st.status("Generating drift composition...", expanded=True) as drift_status:
            st.write(f"Audio: `{Path(drift_audio_path).name}` ({drift_audio_dur:.1f}s)")
            st.write(f"Videos: {len(drift_clips_selected)} clips selected")

            progress_bar = st.progress(0)
            progress_text = st.empty()

            def on_drift_progress(current, total):
                progress_bar.progress(current / total)
                seg_total = total - 2
                if current <= seg_total:
                    progress_text.text(f"Composing segment {current}/{seg_total}")
                elif current == total - 1:
                    progress_text.text("Concatenating segments...")
                else:
                    progress_text.text("Mixing audio...")

            drift_output = drift_build_composition(
                videos=",".join(str(p) for p in drift_clips_selected),
                audio=drift_audio_path.strip(),
                output_dir=str(output_dir),
                decay_intensity=drift_decay,
                min_hold=drift_min_hold,
                max_hold=drift_max_hold,
                split_chance=drift_split,
                pip_chance=drift_pip,
                seed=(None if drift_seed_val < 0 else drift_seed_val),
                progress_callback=on_drift_progress,
            )

            progress_bar.progress(1.0)
            progress_text.text("Done!")
            drift_status.update(label="✓ Complete!", state="complete")

        st.success(f"Saved to `{drift_output}`")
