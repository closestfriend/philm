#!/usr/bin/env python3
"""Build a local HTML labeling sheet: Hunter rates ~60 iPhone clips on the axes in affect_anchors.json
(one slider per axis, worded by its `label`), and those labels become the ground truth that the
embedding anchors are validated against.

Nothing is uploaded. The sheet is a plain local file that plays the silent 360p proxies, the same
silent picture the embedding model saw. Ratings are kept in the browser (localStorage) as you go
and exported to a JSON file with the Export button.

  python3 scripts/make_label_sheet.py              # writes label_set.json + label_sheet.html
  open "<printed path>/label_sheet.html"

Sample = every iPhone clip that already has a written catalogue description (so labels can be
compared with the Qwen/Gemini reading too), plus random clips spread across folders. Fixed seed,
so re-running gives the same set.
"""
import glob
import json
import os
import random
import sys
from pathlib import Path

MEDIA = Path("/Volumes/2025_exSSD_2tb/Photography + Video")
PROXIES = MEDIA / "_proxies" / "_found_footage_wer_iphone"
EMB = MEDIA / "_embeddings" / "_found_footage_wer_iphone"
CATALOG = MEDIA / "_cloud_catalog"
ORIG_PREFIX = str(MEDIA / "_found_footage_wer_iphone") + "/"
ANCHORS = Path(__file__).resolve().parent / "affect_anchors.json"
TOTAL, SEED = 60, 11
MIN_DUR, MAX_DUR = 3.0, 75.0   # short enough to judge in one watch, long enough to mean something


def key_for(rel):
    import hashlib
    return hashlib.sha1(rel.encode()).hexdigest()[:12]


def main():
    manifest = [json.loads(l) for l in (EMB / "manifest.jsonl").read_text().splitlines() if l.strip()]
    by_rel = {r["rel"]: r for r in manifest}
    catalogued = []
    for p in glob.glob(str(CATALOG / "*.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if d.get("path", "").startswith(ORIG_PREFIX):
            rel = os.path.splitext(d["path"][len(ORIG_PREFIX):])[0] + ".mp4"
            if rel in by_rel:
                catalogued.append(rel)
    rng = random.Random(SEED)
    chosen = list(dict.fromkeys(catalogued))
    pool = [r for r in manifest if MIN_DUR <= r["dur"] <= MAX_DUR and r["rel"] not in chosen]
    folders = {}
    for r in pool:
        folders.setdefault(os.path.dirname(r["rel"]) or ".", []).append(r["rel"])
    for v in folders.values():
        rng.shuffle(v)
    order = list(folders)
    rng.shuffle(order)
    while len(chosen) < TOTAL and any(folders.values()):   # round-robin across folders
        for f in order:
            if folders[f] and len(chosen) < TOTAL:
                chosen.append(folders[f].pop())
    rng.shuffle(chosen)
    clips = [{"key": by_rel[r]["key"], "rel": r, "dur": by_rel[r]["dur"],
              "catalogued": r in catalogued, "src": (PROXIES / r).as_uri()} for r in chosen]
    (EMB / "label_set.json").write_text(json.dumps(
        [{k: c[k] for k in ("key", "rel", "dur", "catalogued")} for c in clips], indent=1))
    axes = [[k, v["label"]["name"], v["label"]["ask"], *v["label"]["scale"]]
            for k, v in json.loads(ANCHORS.read_text())["axes"].items()]
    html = TEMPLATE.replace("__CLIPS__", json.dumps(clips)).replace("__AXES__", json.dumps(axes))
    (EMB / "label_sheet.html").write_text(html)
    print(f"{len(clips)} clips ({sum(c['catalogued'] for c in clips)} catalogued, "
          f"{len({os.path.dirname(c['rel']) for c in clips})} folders)")
    print(f"open: {EMB / 'label_sheet.html'}")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Affect labels</title>
<style>
:root{--bg:#f4f4f2;--card:#fff;--fg:#1b1c1f;--mut:#63666e;--line:#d6d7d3;--acc:#2f4fd0;--ok:#1f7a4d}
@media (prefers-color-scheme:dark){:root{--bg:#141518;--card:#1c1d21;--fg:#ecebe6;--mut:#9a9ca4;--line:#33353b;--acc:#8ea2f4;--ok:#6cc695}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:18px;margin:0;font-weight:650}.bar{flex:1;min-width:120px;height:8px;background:var(--line);border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--ok)}button{font:inherit;padding:7px 14px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}
button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
.intro{max-width:760px;margin:18px auto 0;padding:0 20px;color:var(--mut);font-size:14.5px}
main{max-width:1000px;margin:0 auto;padding:12px 20px 80px;display:grid;gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:18px}
.card.done{border-color:var(--ok)}video{width:100%;max-height:420px;background:#000;border-radius:4px}
.meta{font:12px ui-monospace,Menlo,monospace;color:var(--mut);margin:6px 0 0;word-break:break-all}
.row{display:grid;grid-template-columns:150px 1fr 34px;gap:10px;align-items:center;margin-bottom:8px}
.row label{font-weight:600;font-size:14px}.row small{display:block;font-weight:400;color:var(--mut);font-size:12px}
.row output{font-variant-numeric:tabular-nums;text-align:right;color:var(--mut)}.row output.set{color:var(--fg);font-weight:650}
input[type=range]{width:100%;accent-color:var(--acc)}input[type=range].unset{opacity:.35}
.kind{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:14px;margin:0 0 8px 160px}
.flags{display:flex;gap:18px;flex-wrap:wrap;font-size:14px;margin-top:6px}
textarea{width:100%;height:90px;font:12px ui-monospace,monospace;margin-top:8px;display:none}
@media (max-width:700px){.card{grid-template-columns:1fr}.row{grid-template-columns:110px 1fr 30px}.kind{margin-left:0}}
</style></head><body>
<header><h1>Affect labels</h1><div class="bar"><i id="fill"></i></div><span id="count">0 / 0</span>
<button id="dl" class="primary">Export labels</button><button id="cp">Copy JSON</button></header>
<p class="intro">Read reparatively (Sedgwick): ask what each clip offers or sustains, not what it exposes. Rate what the <b>picture</b> does to you. The clips play silent, exactly as the model saw them, so ignore any sound you remember. Leave a slider alone if you cannot tell; untouched sliders count as unlabeled. About a minute per clip. Your answers save in this browser as you go, so you can stop and come back. Press Export when finished, then tell Claude where the file landed.</p>
<textarea id="ta" readonly></textarea><main id="main"></main>
<script>
const CLIPS = __CLIPS__;
const AXES = __AXES__;   // [key, name, ask, min, max] from affect_anchors.json
const KEY="affect-labels-v2";let S={};try{S=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};
const isDone=c=>{const s=S[c.key]||{};return s.skip||AXES.some(a=>s[a[0]]!==undefined)};
function progress(){const n=CLIPS.filter(isDone).length;document.getElementById("count").textContent=n+" / "+CLIPS.length;
 document.getElementById("fill").style.width=(100*n/CLIPS.length)+"%";
 CLIPS.forEach(c=>document.getElementById("c"+c.key).classList.toggle("done",isDone(c)))}
const main=document.getElementById("main");
CLIPS.forEach((c,i)=>{const s=S[c.key]||{};const d=document.createElement("section");d.className="card";d.id="c"+c.key;
 let rows=AXES.map(a=>{const v=s[a[0]];return `<div class="row"><label>${a[1]}<small>${a[2]}</small></label>
  <input type="range" min="${a[3]}" max="${a[4]}" step="1" value="${v!==undefined?v:Math.round((a[3]+a[4])/2)}" class="${v===undefined?"unset":""}" data-k="${a[0]}">
  <output class="${v!==undefined?"set":""}">${v!==undefined?v:"–"}</output></div>`}).join("");
 d.innerHTML=`<div><video src="${c.src}" controls loop muted preload="metadata" playsinline></video>
  <p class="meta">${i+1}. ${c.rel} · ${c.dur.toFixed(0)}s${c.catalogued?" · has catalogue text":""}</p></div>
  <div>${rows}
  <div class="flags"><label><input type="checkbox" data-f="hauntological" ${s.hauntological?"checked":""}> A lost future is in this (Fisher)</label>
  <label><input type="checkbox" data-f="cruel_optimism" ${s.cruel_optimism?"checked":""}> An attachment that hurts (Berlant)</label>
  <label><input type="checkbox" data-f="punctum" ${s.punctum?"checked":""}> This one pricks me (Barthes)</label>
  <label><input type="checkbox" data-f="skip" ${s.skip?"checked":""}> Skip, cannot judge</label></div></div>`;
 d.addEventListener("input",e=>{const t=e.target;S[c.key]=S[c.key]||{};
  if(t.dataset.k){S[c.key][t.dataset.k]=+t.value;t.classList.remove("unset");const o=t.nextElementSibling;o.textContent=t.value;o.className="set"}
  else if(t.dataset.f){S[c.key][t.dataset.f]=t.checked}
  save();progress()});main.appendChild(d)});
function payload(){const labels={};CLIPS.forEach(c=>{if(isDone(c))labels[c.key]=Object.assign({rel:c.rel},S[c.key])});
 return JSON.stringify({version:1,exported:new Date().toISOString(),labels},null,1)}
document.getElementById("dl").onclick=()=>{const b=new Blob([payload()],{type:"application/json"});const a=document.createElement("a");
 a.href=URL.createObjectURL(b);a.download="affect_labels_"+new Date().toISOString().slice(0,10)+".json";a.click()};
document.getElementById("cp").onclick=async()=>{const t=payload();try{await navigator.clipboard.writeText(t)}catch(e){const ta=document.getElementById("ta");ta.style.display="block";ta.value=t;ta.select()}};
progress();
</script></body></html>
"""

if __name__ == "__main__":
    main()
