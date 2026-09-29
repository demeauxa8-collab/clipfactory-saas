#!/usr/bin/env python3
"""judge6 scoring. Truth from the word-accurate whisper labelling supplied with the set."""
import json, pathlib, re

HERE = pathlib.Path(__file__).parent
TRUTH = {  # (publiable, debut_coupe, fin_coupe)
    "j1_clean_intro":     (True,  False, False),
    "j2_clean_google":    (False, True,  False),
    "j3_clean_motsalea":  (False, True,  True),
    "j4_bad_midsentence": (False, True,  False),
    "j5_bad_realmontage": (False, False, True),
    "j6_bad_deadair":     (False, True,  True),
}


def parse(txt):
    if not txt:
        return None
    t = re.sub(r"^```(?:json)?\s*", "", txt.strip())
    t = re.sub(r"\s*```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


rows = {}
for f in sorted((HERE / "out3").glob("*__judge_*.json")):
    rec = json.loads(f.read_text())
    clip = rec["tag"].replace("judge_", "")
    obj = parse(rec.get("text"))
    u = rec.get("usage") or {}
    p, d, fin = TRUTH[clip]
    r = dict(cost=u.get("cost"), lat=rec.get("latency_s"), tin=u.get("prompt_tokens"))
    if obj:
        r["pub"] = obj.get("publiable")
        r["pub_ok"] = (obj.get("publiable") is p)
        r["d"] = obj.get("phrase_coupee_au_debut")
        r["d_ok"] = (obj.get("phrase_coupee_au_debut") is d)
        r["f"] = obj.get("phrase_coupee_a_la_fin")
        r["f_ok"] = (obj.get("phrase_coupee_a_la_fin") is fin)
        r["first"] = obj.get("premier_mot_entendu")
        r["last"] = obj.get("dernier_mot_entendu")
        r["dead"] = obj.get("moment_mort")
    else:
        r["json"] = "invalid"
    rows.setdefault(rec["model"], {})[clip] = r

(HERE / "t3_scored.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
print(f"{'model':32s} {'publiable':>10s} {'bords':>7s}  {'$ / 6 clips':>12s} {'$ / clip':>9s}  detail")
for m, d in rows.items():
    pub = sum(1 for c in TRUTH if d.get(c, {}).get("pub_ok"))
    bord = sum(1 for c in TRUTH for k in ("d_ok", "f_ok") if d.get(c, {}).get(k))
    cost = sum((d.get(c, {}).get("cost") or 0) for c in TRUTH)
    det = " ".join(f"{c.split('_')[0]}:{'P' if d.get(c,{}).get('pub') else 'x'}"
                   f"{'+' if d.get(c,{}).get('d_ok') else '-'}{'+' if d.get(c,{}).get('f_ok') else '-'}"
                   for c in TRUTH)
    print(f"{m:32s} {pub:>6}/6 {bord:>5}/12  ${cost:>11.5f} ${cost/6:>8.5f}  {det}")
print()
print("REFERENCE google/gemini-3.6-flash (mesure precedente) : 6/6 publiabilite, 11/12 bords, $0.0115/clip")
print()
print("premier/dernier mot entendu (le juge doit ENTENDRE le son) :")
for m, d in rows.items():
    print("--", m)
    for c in TRUTH:
        r = d.get(c, {})
        print(f"   {c:20s} first={str(r.get('first'))[:44]:46s} last={str(r.get('last'))[:34]}")
