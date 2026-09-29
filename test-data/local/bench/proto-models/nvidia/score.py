#!/usr/bin/env python3
"""Score judge6 outputs against the word-level ground truth."""
import json, glob, os, re, sys, pathlib

HERE = pathlib.Path(__file__).parent

# truth: (publiable, debut_coupe, fin_coupe)
TRUTH = {
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
    t = txt.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except Exception:
            return None


def score(dirs):
    rows = {}
    for d in dirs:
        for f in sorted(glob.glob(str(HERE / d / "*J_*.json"))):
            rec = json.load(open(f))
            clip = rec["tag"].replace("J_", "")
            if clip not in TRUTH:
                continue
            m = rec["model"]
            r = rows.setdefault(m, {"pub": 0, "edge": 0, "n": 0, "cost": 0.0, "lat": [],
                                    "fail": [], "out_tok": 0, "detail": {}})
            r["n"] += 1
            u = rec.get("usage") or {}
            r["cost"] += float(u.get("cost") or 0)
            r["out_tok"] += int(u.get("completion_tokens") or 0)
            r["lat"].append(rec.get("latency_s") or 0)
            j = parse(rec.get("text"))
            tp, td, tf = TRUTH[clip]
            if not j:
                r["fail"].append(clip)
                r["detail"][clip] = "PARSE_FAIL/" + str(rec.get("error"))[:60]
                continue
            gp = bool(j.get("publiable"))
            gd = bool(j.get("phrase_coupee_au_debut"))
            gf = bool(j.get("phrase_coupee_a_la_fin"))
            ok_p = gp == tp
            r["pub"] += ok_p
            r["edge"] += (gd == td) + (gf == tf)
            r["detail"][clip] = (f"pub={gp}{'OK' if ok_p else 'XX'} "
                                 f"deb={gd}{'ok' if gd == td else 'XX'} "
                                 f"fin={gf}{'ok' if gf == tf else 'XX'} "
                                 f"1er='{str(j.get('premier_mot_entendu'))[:14]}' "
                                 f"dern='{str(j.get('dernier_mot_entendu'))[:14]}'")
    print(f"{'model':<52} {'pub/6':<6} {'bords/12':<9} {'$ total':<10} {'$/clip':<10} {'lat med':<8} fails")
    for m, r in sorted(rows.items(), key=lambda x: (-x[1]['pub'], -x[1]['edge'])):
        lat = sorted(r["lat"])[len(r["lat"]) // 2] if r["lat"] else 0
        cpc = r["cost"] / max(r["n"], 1)
        print(f"{m:<52} {r['pub']}/6    {r['edge']}/12      "
              f"{r['cost']:<10.5f} {cpc:<10.5f} {lat:<8.1f} {r['fail']}")
    print()
    for m, r in sorted(rows.items()):
        print("###", m, f"(out_tok total={r['out_tok']})")
        for c in sorted(TRUTH):
            tp, td, tf = TRUTH[c]
            print(f"   {c:<20} truth(pub={tp},deb={td},fin={tf})  -> {r['detail'].get(c,'MISSING')}")
        print()
    return rows


if __name__ == "__main__":
    score(sys.argv[1:] or ["out_judge"])
