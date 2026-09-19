# tests/test_sync_timeline.py — end-to-end lip-sync timeline accuracy.
#
# Renders a synthetic lip-sync take whose frame brightness encodes song time
# (luma = 255 * (t mod 4) / 4), then reads the output back and checks that at every video
# time T the picture shows song time T. This is the test that catches accumulated drift
# from frame truncation, flash frames inserted on top of beats, and a schedule that starts
# at the first beat instead of song second zero.
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import carti_cut as cc  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

SR, DUR, BPM = 22050, 16.0, 130
TOL_MS = 40   # ~one frame at 30 fps; the ramp encodes each frame's START time, so the
              # instrument itself carries up to half a frame of bias. Lip-sync tolerance ~45 ms.
ACCUM_MS = 15  # drift at the end must equal drift at the start: no accumulation, ever


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    d = tmp_path_factory.mktemp("sync")
    t = np.arange(int(SR * DUR)) / SR
    sig = np.zeros_like(t)
    for b in np.arange(0, DUR, 60 / BPM):
        i, n = int(b * SR), int(0.05 * SR)
        sig[i:i + n] += np.sin(2 * np.pi * 80 * t[:n]) * np.exp(-t[:n] * 40)
    sig += 0.02 * np.random.default_rng(0).standard_normal(len(t))
    pcm = (sig / np.abs(sig).max() * 32000).astype(np.int16)
    with wave.open(str(d / "click.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c=black:s=320x180:r=30:d={DUR},geq=lum='255*mod(T,4)/4':cb=128:cr=128",
                    "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(d / "ramp.mp4")],
                   check=True)
    return d


def _drift_ms(video: Path) -> list[tuple[float, float]]:
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-vf",
                          "fps=10,crop=200:100:60:40,signalstats,"
                          "metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    rows = []
    for i, m in enumerate(re.findall(r"YAVG=([0-9.]+)", out)):
        T = i / 10.0
        shown = float(m) / 255 * 4.0    # geq writes full-range luma: decode song time mod 4 s
        d = ((shown - T + 2.0) % 4.0) - 2.0                  # wrap drift into [-2, 2)
        rows.append((T, d * 1000))
    return rows


def _render(synthetic, out, flash, stutter, monkeypatch):
    monkeypatch.setattr(cc, "FLASH_PROBABILITY", flash)
    monkeypatch.setattr(cc, "STUTTER_PROBABILITY", stutter)
    monkeypatch.setattr(cc, "SHRINK_PROBABILITY", 0.0)   # shrink/zoom would move the sampled
    monkeypatch.setattr(cc, "ZOOM_PROBABILITY", 0.0)     # region; they don't touch timing
    monkeypatch.setattr(sys, "argv", ["carti_cut.py", "--music", str(synthetic / "click.wav"),
                                      "--lipsync", str(synthetic / "ramp.mp4"),
                                      "--lipsync-offset", "0", "--seed", "7",
                                      "--output", str(out)])
    cc.main()
    return out / "carti_cut_v01.mp4"


@pytest.mark.parametrize("flash,stutter", [(0.0, 0.0), (1.0, 0.0), (0.4, 0.3)])
def test_lipsync_stays_within_one_frame(synthetic, tmp_path, monkeypatch, flash, stutter):
    video = _render(synthetic, tmp_path / f"f{flash}_s{stutter}", flash, stutter, monkeypatch)
    rows = _drift_ms(video)
    assert rows, "no frames decoded"
    # per-second medians (robust to the single inverted/white flash frame in a second)
    worst = 0.0
    for s in range(int(DUR) - 1):
        ds = [d for T, d in rows if s <= T < s + 1]
        med = float(np.median(ds))
        worst = max(worst, abs(med))
        assert abs(med) <= TOL_MS, f"video second {s}: shows song time off by {med:+.0f} ms"
    # the render must start at song second zero, not at the first detected beat
    first = [d for T, d in rows if T < 0.5]
    assert abs(float(np.median(first))) <= TOL_MS
    # and whatever constant offset the instrument sees, it must not grow across the render
    head = float(np.median([d for T, d in rows if T < 2]))
    tail = float(np.median([d for T, d in rows if DUR - 3 <= T < DUR - 1]))
    assert abs(tail - head) <= ACCUM_MS, f"drift accumulated: {head:+.0f} ms -> {tail:+.0f} ms"
