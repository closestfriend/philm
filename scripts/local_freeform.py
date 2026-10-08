#!/usr/bin/env python3
"""Free-form local analysis — Qwen3-VL with NO schema constraint.

The schema benchmark showed a 4B model can't hold strict JSON. This asks it to do
what small VLMs are actually good at: describe footage in free prose. Same clips as
the Gemini meter (first K), frame-based, unconstrained. For quality eyeballing.
"""
import base64, glob, json, os, sys, time
from pathlib import Path
import requests
from video_analyzer.local import extract_frames

GEM_DIR = sys.argv[sys.argv.index("--gemini-dir")+1] if "--gemini-dir" in sys.argv else None
OUT = sys.argv[sys.argv.index("--out")+1] if "--out" in sys.argv else "./freeform_results"
K = int(sys.argv[sys.argv.index("--k")+1]) if "--k" in sys.argv else 6
MODEL = os.getenv("OLLAMA_MODEL", "qwen3-vl:4b")
FRAMES = int(os.getenv("OLLAMA_FRAMES", "8"))
URL = "http://localhost:11434/api/chat"

PROMPT = (
    "You are a perceptive film archivist cataloguing a video clip from these "
    "extracted frames. In 3-6 sentences, describe: the subject/content; the setting; "
    "the mood and atmosphere; notable visual qualities (light, color, motion, grain, "
    "composition); and how an editor might use this shot. Be specific and evocative, "
    "not generic. End with 4-8 lowercase keyword tags, comma-separated."
)

def main():
    outdir = Path(OUT); outdir.mkdir(parents=True, exist_ok=True)
    clips = []
    for f in sorted(glob.glob(GEM_DIR + "/*.json")):
        if "_cost_report" in f: continue
        d = json.load(open(f)); clips.append((d["clip"], d["path"]))
    clips = clips[:K]
    print(f"Free-form {MODEL} ({FRAMES} frames) on {len(clips)} clips\n", flush=True)
    for i, (name, path) in enumerate(clips, 1):
        if not os.path.exists(path):
            print(f"[{i}] {name}: missing, skip", flush=True); continue
        t0 = time.time()
        frames = extract_frames(Path(path), num_frames=FRAMES)
        imgs = [base64.b64encode(Path(fr).read_bytes()).decode() for fr in frames]
        try:
            r = requests.post(URL, json={"model": MODEL, "stream": False,
                "messages": [{"role": "user", "content": PROMPT, "images": imgs}]}, timeout=600)
            r.raise_for_status()
            text = r.json()["message"]["content"]
        except Exception as e:
            text = f"[ERROR] {e}"
        for fr in frames:
            try: os.unlink(fr)
            except OSError: pass
        dt = time.time() - t0
        json.dump({"clip": name, "seconds": round(dt, 1), "freeform": text},
                  open(outdir / f"{name}.json", "w"), indent=2)
        print(f"[{i}/{len(clips)}] {name}  {dt:.0f}s\n{text[:400]}\n{'-'*60}", flush=True)
    print(f"\nOutputs -> {outdir}")

if __name__ == "__main__":
    main()
