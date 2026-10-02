"""Portable blind review. Media and the identity mapping remain private."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from pathlib import Path

from .judge import REASONS

HTML = """<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Notation des clips</title><style>
*{box-sizing:border-box}body{margin:0;background:#10151c;color:#eef1f5;font:16px system-ui;line-height:1.5}
header{padding:18px 28px;border-bottom:1px solid #303845;display:flex;justify-content:space-between;align-items:center}
h1{font-size:20px;margin:0}main{max-width:1120px;margin:24px auto;padding:0 24px;display:grid;grid-template-columns:minmax(280px,1fr) minmax(320px,1fr);gap:32px}
video{width:100%;height:min(69vh,640px);background:#000;border-radius:12px}button,input,textarea{font:inherit}
button{padding:10px 16px;border:1px solid #657183;border-radius:8px;background:#222d3a;color:white;cursor:pointer}button[aria-pressed=true]{background:#3b70dd;border-color:#84a8fb}
button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #a4c2ff;outline-offset:3px}fieldset{border:0;padding:0;margin:22px 0}legend{font-weight:650;margin-bottom:10px}.choices{display:flex;gap:8px;flex-wrap:wrap}
.reasons{display:grid;grid-template-columns:1fr 1fr;gap:8px}label{cursor:pointer}textarea{width:100%;min-height:90px;background:#1b2430;border:1px solid #657183;color:white;border-radius:8px;padding:10px}details{margin:15px 0;color:#c8d0dc}summary{cursor:pointer}.muted{color:#acb7c7;font-size:14px}.nav{display:flex;justify-content:space-between;gap:8px}#warning{color:#ffcb83}#empty{padding:35px} @media(max-width:760px){main{grid-template-columns:1fr}video{height:60vh}header{padding:15px}}
</style><header><div><h1>Notation des clips</h1><div class="muted" id="progress"></div></div><button id="export">Exporter les notes</button></header>
<main id="main"><section><video id="video" controls preload="metadata"></video><details><summary>Lire le transcript</summary><p id="transcript"></p></details></section>
<section><h2 id="title"></h2><p class="muted">Juge le clip tel qu’il est. Les notes sont sauvegardées dans ce navigateur.</p>
<fieldset><legend>Publiable en l’état ?</legend><div class="choices"><button id="yes">Oui · O</button><button id="no">Non · N</button></div></fieldset>
<fieldset><legend>Raisons du rejet</legend><div id="reasons" class="reasons"></div></fieldset>
<fieldset><legend>Accroche dans les 3 premières secondes</legend><div id="hooks" class="choices"></div><p class="muted">0 = aucune accroche · 4 = très forte</p></fieldset>
<label for="comment">Commentaire facultatif</label><textarea id="comment"></textarea><p id="warning" role="status"></p>
<div class="nav"><button id="prev">← Précédent</button><button id="next">Suivant →</button></div><p class="muted">Raccourcis : O / N, puis flèches pour changer de clip.</p></section></main>
<script id="data" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent),clips=D.clips,key='golden-review-'+D.run_id;
let ratings={},index=0;try{ratings=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){document.getElementById('warning').textContent='Sauvegarde locale indisponible : exporte tes notes avant de fermer.'}
const $=id=>document.getElementById(id);const complete=r=>r&&typeof r.publishable==='boolean'&&Number.isInteger(r.hook_0_3s);
function current(){return ratings[clips[index].clip_id]||(ratings[clips[index].clip_id]={reasons:[],comment:''})}
function save(){try{localStorage.setItem(key,JSON.stringify(ratings))}catch(e){$('warning').textContent='Sauvegarde locale indisponible : exporte tes notes.'}refresh()}
function refresh(){const r=current();$('yes').setAttribute('aria-pressed',r.publishable===true);$('no').setAttribute('aria-pressed',r.publishable===false);
document.querySelectorAll('[data-reason]').forEach(e=>e.checked=r.reasons.includes(e.dataset.reason));document.querySelectorAll('[data-hook]').forEach(e=>e.setAttribute('aria-pressed',r.hook_0_3s===Number(e.dataset.hook)));
$('progress').textContent=clips.filter(c=>complete(ratings[c.clip_id])).length+' / '+clips.length+' clips notés';}
function show(){if(!clips.length){$('main').textContent='Aucun clip livré dans ce run.';return}const c=clips[index];$('title').textContent='Clip '+(index+1)+' / '+clips.length;$('video').src=c.media;$('transcript').textContent=c.transcript;$('comment').value=current().comment||'';refresh()}
Object.entries(D.reasons).forEach(([code,name])=>{const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.reason=code;input.onchange=()=>{const r=current();r.reasons=r.reasons.filter(x=>x!==code);if(input.checked)r.reasons.push(code);save()};label.append(input,document.createTextNode(' '+name));$('reasons').append(label)});
for(let n=0;n<=4;n++){const b=document.createElement('button');b.textContent=n;b.dataset.hook=n;b.onclick=()=>{current().hook_0_3s=n;save()};$('hooks').append(b)}
$('yes').onclick=()=>{current().publishable=true;current().reasons=[];save()};$('no').onclick=()=>{current().publishable=false;save()};$('comment').oninput=()=>{current().comment=$('comment').value;save()};
function move(step){index=(index+step+clips.length)%clips.length;show()}$('prev').onclick=()=>move(-1);$('next').onclick=()=>move(1);
document.addEventListener('keydown',e=>{if(e.target.matches('input,textarea')||e.ctrlKey||e.metaKey||e.altKey)return;if(e.key.toLowerCase()==='o')$('yes').click();if(e.key.toLowerCase()==='n')$('no').click();if(e.key==='ArrowRight'){e.preventDefault();move(1)}if(e.key==='ArrowLeft'){e.preventDefault();move(-1)}});
function csv(value){let s=String(value??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'}
$('export').onclick=()=>{let rows=[['clip_id','publishable','reasons','hook_0_3s','comment']];for(const c of clips){const r=ratings[c.clip_id];if(complete(r))rows.push([c.clip_id,r.publishable,r.reasons.join('|'),r.hook_0_3s,r.comment])}const blob=new Blob(['\ufeff'+rows.map(r=>r.map(csv).join(',')).join('\\r\\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ratings.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};show();
</script></html>"""


def generate_review(run: Path):
    report = json.loads((run / "report.json").read_text())
    directory = run / "review"
    (directory / "clips").mkdir(parents=True, exist_ok=True, mode=0o700)
    clips, mapping = [], {}
    for source in report["sources"]:
        for clip in source["clips"]:
            identity = source["source_id"] + ":" + str(clip["idx"])
            opaque = hashlib.sha256((report["run_id"] + identity).encode()).hexdigest()[:24]
            media = f"clips/{opaque}.mp4"
            shutil.copyfile(run / source["source_id"] / clip["media"], directory / media)
            clips.append(
                {"clip_id": opaque, "media": media, "transcript": clip["transcript_excerpt"]}
            )
            mapping[opaque] = {"source_id": source["source_id"], "idx": clip["idx"]}
    random.Random(report["run_id"]).shuffle(clips)
    payload = json.dumps(
        {
            "run_id": hashlib.sha256(report["run_id"].encode()).hexdigest()[:16],
            "clips": clips,
            "reasons": REASONS,
        },
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    (directory / "index.html").write_text(HTML.replace("__DATA__", payload))
    (run / "review_mapping.json").write_text(json.dumps(mapping, indent=2))
    return directory / "index.html"
