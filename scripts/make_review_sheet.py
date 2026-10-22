#!/usr/bin/env python3
"""Build a local HTML review sheet for the embed_cut roughs, so Hunter can dogfood them: a blind
ranking of the cuts that share a track, a verdict on every far jump, tags on cuts and clips as a
film plays, and a short check per film. The export is JSONL: chosen/rejected pairs from the
rankings plus single yes/no verdicts, ready for tuning embed_cut's knobs or fitting a reranker.

Nothing is uploaded. The sheet is written next to the roughs (karman-video-art/embed_cuts/) and
plays them by relative path. Answers are kept in the browser (localStorage) as you go and exported
with the Export button.

  python3 scripts/make_review_sheet.py      # writes embed_cuts/review_sheet.html
  open "<printed path>"

Re-run after new renders: every *_cut.json in embed_cuts/ becomes a film on the sheet (axis/ is
skipped; it only holds dwelling pieces). Clip keys are sha1(rel)[:12], the rule make_label_sheet.py
and reliability/ use, so review records join with the affect labels.
"""
import glob
import hashlib
import json
import os
import re
import shlex
from datetime import date
from pathlib import Path

OUT_DIR = Path.home() / "Projects" / "Ecosystems" / "Karman" / "karman-video-art" / "embed_cuts"
LABEL_SHEET = Path("/Volumes/2025_exSSD_2tb/Photography + Video/_embeddings/_found_footage_wer_iphone/label_sheet.html")
RETIRED_AXES = {"dwelling"}   # 2026-10-21, Hunter: "the dwelling atmosphere was a huge mistake"
RUT_MIN = 5                   # this many cuts in a row from one folder is worth a look


def main():
    films = [film(p) for p in sorted(glob.glob(str(OUT_DIR / "*_cut.json")))]
    tracks = {}
    for f in films:
        if f["track"]:
            tracks.setdefault(f["track"], []).append(f["name"])
    groups = [{"id": t, "track": t, "films": names} for t, names in tracks.items() if len(names) > 1]
    data = {"films": films, "groups": groups, "retired": sorted(RETIRED_AXES),
            "index": sorted({f.pop("proxy_root") for f in films}),
            "label_sheet": LABEL_SHEET.as_uri(), "built": date.today().isoformat()}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    out = OUT_DIR / "review_sheet.html"
    out.write_text(html)
    jumps = sum(c[4] == "F" for f in films for c in f["cuts"][1:])
    missing = [f["name"] for f in films if not f["src_ok"]]
    print(f"{len(films)} films, {len(groups)} shared-track group(s), {jumps} far jumps"
          + (f"; rough missing for {', '.join(missing)} (re-run its recipe)" if missing else ""))
    print(f"open: {out}")


def film(path):
    d = json.loads(Path(path).read_text())
    r, cuts = d["recipe"], d["cuts"]
    assert all(c["n"] == i + 1 for i, c in enumerate(cuts)), f"{path}: cut numbers out of order"
    plane = (arg(r, "--plane") or [None])[0]
    track = Path(d["track"]).name if d.get("track") else None
    src = f"{d['name']}_rough.mp4"
    return {"name": d["name"], "mode": d["mode"], "track": track, "plane": plane,
            "retired": plane in RETIRED_AXES, "recipe": shlex.join(r), "proxy_root": d.get("proxy_root"),
            "src": src, "src_ok": (OUT_DIR / src).exists(),
            # one row per cut: [t0, t1, rel, key, step, sim, date]
            "cuts": [[round(c["t0"], 2), round(c["t1"], 2), c["rel"], hashlib.sha1(c["rel"].encode()).hexdigest()[:12],
                      c["step"], round(c["sim"], 3), c.get("date")] for c in cuts],
            "ruts": ruts(cuts), "checks": checks(d, track)}


def arg(recipe, flag):
    return [recipe[i + 1] for i, x in enumerate(recipe[:-1]) if x == flag]


def ruts(cuts):
    """Stretches where consecutive cuts all come from one folder: where a walk may be stuck."""
    out, i = [], 0
    while i < len(cuts):
        j, folder = i, os.path.dirname(cuts[i]["rel"])
        while j + 1 < len(cuts) and os.path.dirname(cuts[j + 1]["rel"]) == folder:
            j += 1
        if j - i + 1 >= RUT_MIN:
            out.append({"from": i + 1, "to": j + 1, "t": round(cuts[i]["t0"], 2), "folder": folder})
        i = j + 1
    return out


def checks(d, track):
    """Recipe-specific questions, each rated 1-5, with the time to jump to when answering."""
    r, cuts, out = d["recipe"], d["cuts"], []
    if d["mode"] == "prompts":
        prompts = arg(r, "-p") + arg(r, "--prompt")
        bounds = [round(len(cuts) * k / len(prompts)) for k in range(len(prompts))]   # as embed_cut splits them
        out += [{"id": f"section{k + 1}", "q": f"Section {k + 1} matches “{p}”", "t": round(cuts[b]["t0"], 2)}
                for k, (p, b) in enumerate(zip(prompts, bounds))]
    elif arg(r, "--prompt"):
        out.append({"id": "opening", "q": f"The opening reads as “{arg(r, '--prompt')[0]}”", "t": 0})
    if arg(r, "--toward"):
        out.append({"id": "toward", "q": f"The ending arrives at “{arg(r, '--toward')[0]}”",
                    "t": round(cuts[int(len(cuts) * 0.8)]["t0"], 2)})
    said = re.search(r"(\d{2,3})\s*bpm", track or "", re.I)
    if said and d.get("bpm") and abs(int(said[1]) - d["bpm"]) / int(said[1]) > 0.1:
        out.append({"id": "beat", "q": f"Cuts land on the beat (file says {said[1]} bpm, the detector heard {d['bpm']:.0f})", "t": 0})
    return out


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>embed_cut review</title>
<style>
:root{--bg:#f4f4f2;--card:#fff;--fg:#1b1c1f;--mut:#63666e;--line:#d6d7d3;--acc:#2f4fd0;--ok:#1f7a4d;--warn:#a5551b}
@media (prefers-color-scheme:dark){:root{--bg:#141518;--card:#1c1d21;--fg:#ecebe6;--mut:#9a9ca4;--line:#33353b;--acc:#8ea2f4;--ok:#6cc695;--warn:#e3a06a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:18px;margin:0;font-weight:650}.bar{flex:1;min-width:120px;height:8px;background:var(--line);border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--ok)}
button{font:inherit;font-size:14px;padding:6px 12px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}
button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}button.on{border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc);font-weight:600}
button:disabled{opacity:.4;cursor:default}a.btn{display:inline-block;text-decoration:none;font-size:14px;padding:6px 12px;border-radius:6px;background:var(--acc);color:#fff}
.intro{max-width:820px;margin:18px auto 0;padding:0 20px;color:var(--mut);font-size:14.5px}
main{max-width:1060px;margin:0 auto;padding:12px 20px 80px;display:grid;gap:18px}
.task{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px}.task.done{border-color:var(--ok)}
.task h2{font-size:16px;margin:0 0 4px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.task h2 .n{color:var(--mut);font-weight:500}
.task h2 .st{margin-left:auto;font-size:13px;font-weight:500;color:var(--mut);font-variant-numeric:tabular-nums}.task.done h2 .st{color:var(--ok)}
.task h3{font-size:14px;margin:14px 0 4px}.live{display:none;font-size:12px;font-weight:600;color:var(--acc)}.live.on{display:inline}
.why{color:var(--mut);font-size:14px;margin:0 0 12px;max-width:760px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:8px 0}.grid figure{margin:0}
.grid video,.player video{width:100%;aspect-ratio:9/16;background:#000;border-radius:4px;display:block}
.grid figcaption{font-size:14px;margin-top:4px;font-weight:650}.grid figcaption small{display:block;font-weight:400;font-size:12px;color:var(--mut);word-break:break-all}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}.row .lbl{font-size:14px;font-weight:600;min-width:72px}
input[type=range]{flex:1;min-width:140px;accent-color:var(--acc)}.tm{font-size:13px;color:var(--mut);font-variant-numeric:tabular-nums}
input[type=text]{font:inherit;font-size:14px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);flex:1;min-width:200px}
select{font:inherit;font-size:14px;padding:6px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);max-width:100%}
.player{display:grid;grid-template-columns:minmax(0,280px) minmax(0,1fr);gap:18px;margin-top:8px}
.readout{font:12.5px/1.55 ui-monospace,Menlo,monospace;color:var(--mut);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px 10px;word-break:break-all;margin:0 0 10px;min-height:4.8em}
.readout b{color:var(--fg)}kbd{font:12px ui-monospace,monospace;border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;background:var(--bg)}
.badge{font-size:12px;font-weight:600;color:var(--warn);border:1px solid var(--warn);border-radius:10px;padding:0 7px;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chips button{font-size:13px;padding:3px 9px}
.log{font:12px ui-monospace,monospace;color:var(--mut);max-height:130px;overflow:auto;margin:6px 0 0;padding:0;list-style:none}
.log li{display:flex;gap:8px;align-items:center}.log button{padding:0 6px;font-size:12px}
.q{display:flex;gap:6px 12px;align-items:center;flex-wrap:wrap;font-size:14px;margin:6px 0}.q span{flex:1;min-width:200px}.scale button{min-width:32px;padding:4px 6px}
ul.feeds{font-size:14px;margin:6px 0;padding-left:20px}ul.feeds li{margin:4px 0}
.note{font-size:13.5px;color:var(--mut);border-left:3px solid var(--line);padding:2px 0 2px 12px;margin:14px 0 0;max-width:760px}
code{font:12.5px ui-monospace,Menlo,monospace}textarea{width:100%;height:90px;font:12px ui-monospace,monospace;margin-top:8px;display:none}
@media (max-width:700px){.player{grid-template-columns:1fr}.player video{max-height:60vh;width:auto;margin:auto}}
</style></head><body>
<header><h1>embed_cut review</h1><div class="bar"><i id="fill"></i></div><span id="count" class="tm"></span>
<button id="dl" class="primary">Export JSONL</button><button id="cp">Copy</button></header>
<p class="intro" id="intro"></p><textarea id="ta" readonly></textarea>
<main>
<section class="task" id="t-rank"><h2><span class="n">1</span>Rank the cuts that share a track, blind<span class="st"></span></h2>
<p class="why">Same song, different rules. The cuts are lettered in a random order and play in sync (sound from A), so you judge what the rule made, not its name. Click the letters best to worst, then lock to see which was which. A ranking of four gives six chosen/rejected pairs.</p>
<div id="groups"></div></section>

<section class="task" id="t-jump"><h2><span class="n">2</span>Rate the far jumps<span class="live" data-keys="jump">keys live here</span><span class="st"></span></h2>
<p class="why">Encounter mode's whole bet, after Ernst: two images that sit far apart in the archive, cut together, should spark. Each jump plays the clip before it and the clip it lands on. <kbd>Y</kbd> lands · <kbd>N</kbd> doesn't · <kbd>R</kbd> replay · <kbd>←</kbd> <kbd>→</kbd> step. One film a sitting; it picks up where you left off.</p>
<div class="row"><select id="jfilm"></select></div>
<div class="player"><video id="jv" preload="metadata" playsinline></video>
<div><p class="readout" id="jread"></p><div class="row"><button id="jy" class="primary">Lands (Y)</button><button id="jn">Doesn't (N)</button><button id="jr">Replay (R)</button><button id="jp">←</button><button id="jx">→</button></div></div></div></section>

<section class="task" id="t-watch"><h2><span class="n">3</span>Watch a film and tag it<span class="live" data-keys="watch">keys live here</span><span class="st"></span></h2>
<p class="why">Play a film start to finish. The box shows the cut on screen: its clip, when it was shot, and how the rule picked it (<code>n</code> nearest, <code>F</code> far jump, with similarity). Tag as it plays: <kbd>G</kbd> good cut · <kbd>B</kbd> bad cut · <kbd>S</kbd> stuck, samey stretch · <kbd>X</kbd> never use this clip · <kbd>H</kbd> hero clip · <kbd>Space</kbd> play/pause. Then answer the checks under the player.</p>
<div class="row"><select id="wfilm"></select></div>
<div class="player"><video id="wv" preload="metadata" playsinline controls></video>
<div><p class="readout" id="wread"></p>
<div class="row chips"><button data-tag="good">Good cut (G)</button><button data-tag="bad">Bad cut (B)</button><button data-tag="stuck">Stuck (S)</button><button data-flag="never">Never use (X)</button><button data-flag="hero">Hero (H)</button></div>
<div id="ruts"></div><ul class="log" id="wlog"></ul><div id="checks"></div></div></div></section>

<section class="task" id="t-labels"><h2><span class="n">4</span>Finish the affect label sheet (60 clips)<span class="st"></span></h2>
<p class="why">The anchor axes (intensity, front_stage, poor_image) are still marked provisional: nobody has checked them against your eyes. RAV3RZ and COLD DECEMBER ENCOUNTER v02 were cut on those planes, and intensity drives affect_score. About a minute per clip; ten a sitting is fine. <b>Leave the Dwelling slider untouched</b> (untouched counts as unlabeled). No export of this sheet exists on disk yet; if you started it, your progress is still saved in that browser.</p>
<div class="row"><a class="btn" id="lsheet" target="_blank">Open the label sheet</a><label><input type="checkbox" id="ldone"> Done and exported</label></div></section>

<section class="task" id="t-out"><h2><span class="n">5</span>Export and hand off<span class="st"></span></h2>
<p class="why">Hit <b>Export JSONL</b> at the end of a sitting. Save the file into <code>karman-video-art/embed_cuts/reviews/</code> and commit it: unlike the roughs, your judgments can't be regenerated. Then tell Claude it's there.</p>
<h3>What your answers feed</h3><ul class="feeds">
<li><b>Never-use clips</b>: a blocklist the index skips. Pays off on the next render, no training needed.</li>
<li><b>Rankings and keepers</b>: which modes and knobs stay. COLD DECEMBER ENCOUNTER v01 and v02 differ in three knobs at once (plane, pattern, prompt), so that pair says which film wins, not which knob.</li>
<li><b>Jump verdicts</b>: whether the far jump works, split by plane (poor_image, intensity, none).</li>
<li><b>Stuck tags and cut tags</b>: tune momentum and top-k, or add a same-folder penalty to the walk.</li>
<li><b>Prompt and ending scores</b>: whether the text steering (<code>prompts</code>, <code>--toward</code>) actually steers.</li></ul>
<p class="note"><b>Is this DPO?</b> The data is shaped like it; the training isn't, yet. DPO fine-tunes a model directly on chosen/rejected pairs. embed_cut has no trained model: each cut comes from a nearest-neighbor rule with knobs you set. So the pairs do two jobs now: pick the knobs, and later fit a small reranker on top of the EmbeddingGemma vectors (the reward model that DPO folds in implicitly). Single yes/no verdicts like the jump ratings are usable without a partner too (the KTO setup). If a trained model ever enters the loop, the same file feeds it.</p></section>
</main>
<script>
const D = __DATA__;
const KEY="embed-cut-review-v1";let S={};try{S=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
for(const k of ["assign","rank","jumps","jpos","flags","checks"])S[k]=S[k]||{};S.tags=S.tags||[];
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};
const F=Object.fromEntries(D.films.map(f=>[f.name,f])),$=id=>document.getElementById(id),LET="ABCDEFGH";
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const mmss=t=>Math.floor((t||0)/60)+":"+String(Math.floor((t||0)%60)).padStart(2,"0");
const clip=c=>c?{rel:c[2],key:c[3]}:null;   // cut row: [t0, t1, rel, key, step, sim, date]
const at=(f,t)=>{const c=f.cuts;let lo=0,hi=c.length-1;while(lo<hi){const m=(lo+hi+1)>>1;if(c[m][0]<=t)lo=m;else hi=m-1}return lo};
const badge=f=>f.retired?' <span class="badge">'+esc(f.plane)+' · retired</span>':"";
const label=f=>f.name+" · "+f.mode+(f.plane?" · plane "+f.plane+(f.retired?" (retired)":""):"");
const playable=D.films.filter(f=>f.src_ok);
$("intro").innerHTML=`Dogfooding the roughs in this folder. Each task is one short sitting, and everything saves in this browser as you go, so you can stop mid-task and come back. The two MIRROR films aren't here: they only test the dwelling axis, which is retired. Films cut on <code>--plane dwelling</code> carry a <span class="badge">dwelling · retired</span> badge. Built ${esc(D.built)} from ${D.films.length} cut sheets; re-run <code>scripts/make_review_sheet.py</code> after new renders.`;

// 1 — blind ranking, one block per shared track
function renderGroups(){const box=$("groups");box.innerHTML="";
 if(!D.groups.length){box.innerHTML='<p class="why">No two films share a track yet.</p>';return}
 D.groups.forEach(g=>{let A=S.assign[g.id];
  if(!A||A.length!==g.films.length||!g.films.every(n=>A.includes(n))){A=[...g.films];
   for(let i=A.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[A[i],A[j]]=[A[j],A[i]]}S.assign[g.id]=A;S.rank[g.id]=null;save()}
  const R=S.rank[g.id]=S.rank[g.id]||{order:[],locked:false,note:""},el=document.createElement("div");
  el.innerHTML=`<h3>${esc(g.track)}</h3><div class="grid">${A.map((n,i)=>`<figure><video preload="metadata" playsinline ${i?"muted":""} src="${esc(F[n].src)}"></video>
   <figcaption>${LET[i]}${R.locked?`<small>${esc(n)}${badge(F[n])}</small>`:""}</figcaption></figure>`).join("")}</div>
   <div class="row"><button data-a="play">Play</button><input type="range" min="0" max="1000" value="0" data-a="seek"><span class="tm">0:00</span></div>
   <div class="row"><span class="lbl">Best → worst</span><span class="chips">${A.map((n,i)=>`<button data-l="${i}">${LET[i]}</button>`).join("")}</span>
   <b class="ord"></b><button data-a="undo">Undo</button><button data-a="lock" class="primary"></button></div>
   <div class="row"><input type="text" placeholder="Why did the winner win? (optional)" value="${esc(R.note)}"></div>`;
  const V=[...el.querySelectorAll("video")],m=V[0],seek=el.querySelector("[data-a=seek]"),tm=el.querySelector(".tm"),pb=el.querySelector("[data-a=play]");
  m.addEventListener("timeupdate",()=>{V.slice(1).forEach(v=>{if(!m.paused&&Math.abs(v.currentTime-m.currentTime)>.3)v.currentTime=m.currentTime});
   if(m.duration)seek.value=Math.round(1000*m.currentTime/m.duration);tm.textContent=mmss(m.currentTime)+" / "+mmss(m.duration)});
  m.addEventListener("ended",()=>{V.forEach(v=>v.pause());pb.textContent="Play"});
  pb.onclick=()=>{if(m.paused){V.forEach(v=>{v.currentTime=m.currentTime;v.play().catch(()=>{})});pb.textContent="Pause"}else{V.forEach(v=>v.pause());pb.textContent="Play"}};
  seek.oninput=()=>{const t=(m.duration||0)*seek.value/1000;V.forEach(v=>v.currentTime=t)};
  const lock=el.querySelector("[data-a=lock]"),undo=el.querySelector("[data-a=undo]");
  const draw=()=>{el.querySelector(".ord").textContent=R.order.map((l,i)=>(i+1)+". "+LET[l]).join("   ");
   el.querySelectorAll("[data-l]").forEach(b=>b.disabled=R.locked||R.order.includes(+b.dataset.l));
   lock.textContent=R.locked?"Unlock":"Lock & reveal";lock.disabled=!R.locked&&R.order.length<A.length;undo.disabled=R.locked||!R.order.length};
  el.querySelectorAll("[data-l]").forEach(b=>b.onclick=()=>{R.order.push(+b.dataset.l);save();draw()});
  undo.onclick=()=>{R.order.pop();save();draw()};
  lock.onclick=()=>{R.locked=!R.locked;save();renderGroups();progress()};
  el.querySelector("input[type=text]").oninput=e=>{R.note=e.target.value;save()};
  draw();box.appendChild(el)})}

// 2 — far-jump reel
const jv=$("jv"),jFilms=playable.filter(f=>f.cuts.some((c,i)=>i&&c[4]==="F"));let jf=F[S.jfilm]&&jFilms.includes(F[S.jfilm])?F[S.jfilm]:jFilms[0],stopAt=null;
const jumps=f=>f.cuts.map((c,i)=>i).filter(i=>i&&f.cuts[i][4]==="F");
const jcur=()=>{const J=jumps(jf);return [J,Math.min(S.jpos[jf.name]||0,J.length-1)]};
function jload(){jv.src=jf.src;S.jfilm=jf.name;save();jdraw()}
// play up to 2s of the clip before and 2.5s of the clip it lands on (at least 1s of each)
function jplay(){const [J,p]=jcur(),i=J[p],c=jf.cuts[i],pr=jf.cuts[i-1];jv.currentTime=Math.max(0,Math.min(Math.max(pr[0],c[0]-2),c[0]-1));stopAt=Math.max(Math.min(c[1],c[0]+2.5),c[0]+1);jv.play().catch(()=>{})}
function jdraw(){if(!jf){$("jread").textContent="No film with far jumps yet.";return}
 const [J,p]=jcur(),i=J[p],c=jf.cuts[i],pr=jf.cuts[i-1],v=(S.jumps[jf.name]||{})[i+1],done=Object.keys(S.jumps[jf.name]||{}).length;
 $("jread").innerHTML=`<b>Jump ${p+1} / ${J.length}</b> · cut ${i+1} at ${mmss(c[0])}${jf.plane?" · plane <b>"+esc(jf.plane)+"</b>":""} · sim ${c[5].toFixed(2)} · ${done} rated here<br>from ${esc(pr[2])}<br>to&nbsp;&nbsp; ${esc(c[2])}${v?"<br>your verdict: <b>"+(v==="lands"?"lands":"doesn't")+"</b>":""}`}
function jrate(v){const [J,p]=jcur();(S.jumps[jf.name]=S.jumps[jf.name]||{})[J[p]+1]=v;S.jpos[jf.name]=Math.min(p+1,J.length-1);save();jdraw();progress();if(p+1<J.length)jplay()}
function jstep(d){const [J,p]=jcur();S.jpos[jf.name]=Math.max(0,Math.min(p+d,J.length-1));save();jdraw();jplay()}
jv.addEventListener("timeupdate",()=>{if(stopAt!==null&&jv.currentTime>=stopAt){jv.pause();stopAt=null}});
$("jfilm").innerHTML=jFilms.map(f=>`<option value="${esc(f.name)}">${esc(label(f))} · ${jumps(f).length} jumps</option>`).join("");
$("jfilm").onchange=e=>{jf=F[e.target.value];jload()};$("jy").onclick=()=>jrate("lands");$("jn").onclick=()=>jrate("doesnt");
$("jr").onclick=jplay;$("jp").onclick=()=>jstep(-1);$("jx").onclick=()=>jstep(1);

// 3 — watch and tag
const wv=$("wv");let wf=F[S.wfilm]&&playable.includes(F[S.wfilm])?F[S.wfilm]:playable[0];
const wcur=()=>at(wf,wv.currentTime);
function wload(){wv.src=wf.src;S.wfilm=wf.name;save();wread();wruts();wlog();wchecks()}
function wread(){const i=wcur(),c=wf.cuts[i],fl=S.flags[c[3]];
 $("wread").innerHTML=`<b>cut ${i+1} / ${wf.cuts.length}</b> · ${mmss(c[0])} · ${c[4]==="F"?"<b>F far jump</b>":"n nearest"} · sim ${c[5].toFixed(2)}${c[6]?" · shot "+esc(c[6]):""}${badge(wf)}<br>${esc(c[2])}${fl?" · <b>"+fl.flag+"</b>":""}`}
function wtag(tag){const i=wcur();S.tags.push({film:wf.name,n:i+1,t:+wv.currentTime.toFixed(2),tag});save();wlog();progress()}
function wflag(flag){const i=wcur(),c=wf.cuts[i];if(S.flags[c[3]]&&S.flags[c[3]].flag===flag)delete S.flags[c[3]];else S.flags[c[3]]={flag,rel:c[2],film:wf.name,n:i+1};save();wread();wlog();progress()}
function wruts(){$("ruts").innerHTML=wf.ruts.length?`<div class="row"><span class="lbl">Possible ruts</span><span class="chips">${wf.ruts.map(r=>`<button data-t="${r.t}">${mmss(r.t)} · cuts ${r.from}–${r.to} · ${esc(r.folder)}</button>`).join("")}</span></div>`:""}
function wlog(){const items=[];S.tags.forEach((t,k)=>{if(t.film===wf.name)items.push({t:t.t,txt:t.tag+" cut "+t.n,del:()=>S.tags.splice(k,1)})});
 Object.entries(S.flags).forEach(([key,v])=>{if(v.film===wf.name)items.push({t:wf.cuts[v.n-1][0],txt:v.flag+" · "+v.rel,del:()=>delete S.flags[key]})});
 items.sort((a,b)=>b.t-a.t);const ul=$("wlog");ul.innerHTML="";
 items.forEach(it=>{const li=document.createElement("li");li.innerHTML=`<span>${mmss(it.t)}</span><span>${esc(it.txt)}</span>`;
  const x=document.createElement("button");x.textContent="×";x.onclick=()=>{it.del();save();wlog();wread();progress()};li.prepend(x);ul.appendChild(li)})}
function wchecks(){const C=S.checks[wf.name]=S.checks[wf.name]||{q:{}};
 const opts=(k,vals)=>vals.map(v=>`<button data-c="${k}" data-v="${v}" class="${C[k]===v?"on":""}">${v}</button>`).join("");
 $("checks").innerHTML=`<h3>Checks for this film</h3>
  <div class="q"><span>Pace</span><span class="chips">${opts("pace",["too slow","right","too fast"])}</span></div>
  <div class="q"><span>Keeper? (worth conforming to full res)</span><span class="chips">${opts("keeper",["yes","maybe","no"])}</span></div>
  ${wf.checks.map(q=>`<div class="q"><span>${esc(q.q)} <button data-go="${q.t}">go ${mmss(q.t)}</button></span><span class="chips scale">${[1,2,3,4,5].map(v=>`<button data-q="${q.id}" data-v="${v}" class="${C.q[q.id]===v?"on":""}">${v}</button>`).join("")}</span></div>`).join("")}
  <div class="row"><input type="text" id="wnote" placeholder="Anything else about this film" value="${esc(C.note)}"></div>`;
 $("wnote").oninput=e=>{C.note=e.target.value;save()}}
$("t-watch").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;const C=S.checks[wf.name];
 if(b.dataset.tag)wtag(b.dataset.tag);else if(b.dataset.flag)wflag(b.dataset.flag);
 else if(b.dataset.t||b.dataset.go){wv.currentTime=+(b.dataset.t||b.dataset.go);wv.play().catch(()=>{})}
 else if(b.dataset.c){C[b.dataset.c]=C[b.dataset.c]===b.dataset.v?undefined:b.dataset.v;save();wchecks();progress()}
 else if(b.dataset.q){C.q[b.dataset.q]=+b.dataset.v;save();wchecks()}});
wv.addEventListener("timeupdate",wread);
$("wfilm").innerHTML=playable.map(f=>`<option value="${esc(f.name)}">${esc(label(f))}</option>`).join("");
$("wfilm").onchange=e=>{wf=F[e.target.value];wload()};

// keys go to whichever player card you touched last
let active=null;const setActive=id=>{active=id;document.querySelectorAll("[data-keys]").forEach(x=>x.classList.toggle("on",x.dataset.keys===id))};
["jump","watch"].forEach(id=>$("t-"+id).addEventListener("pointerdown",()=>setActive(id)));
document.addEventListener("keydown",e=>{if(e.metaKey||e.ctrlKey||e.altKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;const k=e.key.toLowerCase();
 if(active==="jump"&&jf){if(k==="y")jrate("lands");else if(k==="n")jrate("doesnt");else if(k==="r")jplay();else if(e.key==="ArrowRight")jstep(1);else if(e.key==="ArrowLeft")jstep(-1);else return}
 else if(active==="watch"&&wf){if(k===" "){if(e.target===wv)return;wv.paused?wv.play():wv.pause()}else if(k==="g")wtag("good");else if(k==="b")wtag("bad");else if(k==="s")wtag("stuck");else if(k==="x")wflag("never");else if(k==="h")wflag("hero");else return}
 else return;e.preventDefault()});

// 4 — label sheet
$("lsheet").href=D.label_sheet;$("ldone").checked=!!S.labels_done;$("ldone").onchange=e=>{S.labels_done=e.target.checked;save();progress()};

// progress + export
function progress(){const set=(id,txt,done)=>{$(id).querySelector(".st").textContent=txt;$(id).classList.toggle("done",!!done)};
 const gl=D.groups.filter(g=>(S.rank[g.id]||{}).locked).length,jt=jFilms.reduce((s,f)=>s+jumps(f).length,0),jr=jFilms.reduce((s,f)=>s+Object.keys(S.jumps[f.name]||{}).length,0);
 const wc=playable.filter(f=>{const c=S.checks[f.name];return c&&c.pace&&c.keeper}).length,tags=S.tags.length,flags=Object.keys(S.flags).length;
 set("t-rank",gl+" / "+D.groups.length+" ranked",D.groups.length&&gl===D.groups.length);
 set("t-jump",jr+" / "+jt+" rated",jt&&jr===jt);
 const pl=(n,w)=>n+" "+w+(n===1?"":"s");
 set("t-watch",wc+" / "+playable.length+" films checked · "+pl(tags,"tag")+" · "+pl(flags,"clip flag"),playable.length&&wc===playable.length);
 set("t-labels",S.labels_done?"done":"not yet",S.labels_done);
 const parts=[[gl,D.groups.length],[jr,jt],[wc,playable.length],[S.labels_done?1:0,1]].filter(p=>p[1]);
 const frac=parts.reduce((s,p)=>s+p[0]/p[1],0)/parts.length;$("fill").style.width=(100*frac)+"%";$("count").textContent=Math.round(100*frac)+"% through"}
function records(){const out=[{kind:"meta",sheet:"embed_cut review v1",exported:new Date().toISOString(),built:D.built,index:D.index,retired_axes:D.retired}];
 D.films.forEach(f=>out.push({kind:"film",film:f.name,mode:f.mode,plane:f.plane,retired:f.retired,recipe:f.recipe}));
 D.groups.forEach(g=>{const R=S.rank[g.id];if(!R||!R.locked)return;const names=R.order.map(l=>S.assign[g.id][l]);
  out.push({kind:"ranking",group:g.track,order:names,note:R.note||undefined});
  for(let i=0;i<names.length;i++)for(let j=i+1;j<names.length;j++)out.push({kind:"pair",group:g.track,chosen:names[i],rejected:names[j],margin:j-i})});
 for(const [film,v] of Object.entries(S.jumps)){const f=F[film];if(!f)continue;
  for(const [n,lab] of Object.entries(v)){const c=f.cuts[n-1];out.push({kind:"jump",film,n:+n,label:lab,prev:clip(f.cuts[n-2]),next:clip(c),sim:c[5],plane:f.plane})}}
 S.tags.forEach(t=>{const f=F[t.film];if(!f)return;const c=f.cuts[t.n-1];out.push({kind:"cut_tag",film:t.film,n:t.n,t:t.t,tag:t.tag,step:c[4],sim:c[5],prev:clip(f.cuts[t.n-2]),next:clip(c)})});
 for(const [key,v] of Object.entries(S.flags))out.push({kind:"clip_flag",key,rel:v.rel,flag:v.flag,film:v.film,n:v.n});
 for(const [film,c] of Object.entries(S.checks)){const f=F[film];if(!f||!(c.pace||c.keeper||c.note||Object.keys(c.q).length))continue;
  out.push({kind:"film_check",film,pace:c.pace,keeper:c.keeper,answers:f.checks.filter(q=>c.q[q.id]).map(q=>({id:q.id,q:q.q,score:c.q[q.id]})),note:c.note||undefined})}
 return out.map(r=>JSON.stringify(r)).join("\n")+"\n"}
$("dl").onclick=()=>{const b=new Blob([records()],{type:"application/x-ndjson"}),a=document.createElement("a");
 a.href=URL.createObjectURL(b);a.download="embed_cut_review_"+new Date().toISOString().slice(0,10)+".jsonl";a.click()};
$("cp").onclick=async()=>{const t=records();try{await navigator.clipboard.writeText(t)}catch(e){const ta=$("ta");ta.style.display="block";ta.value=t;ta.select()}};

renderGroups();if(jf){$("jfilm").value=jf.name;jload()}else jdraw();if(wf){$("wfilm").value=wf.name;wload()}progress();
</script></body></html>
"""

if __name__ == "__main__":
    main()
