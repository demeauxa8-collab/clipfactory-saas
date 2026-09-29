#!/usr/bin/env python3
"""Score the T2 runs against ground truth established by reading the frames
myself with a 0.025-step vertical grid (/tmp/gt_*.png, /tmp/b_zoom4.png)."""
import json, pathlib, re

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

GT = {
    # face = mean horizontal position of the main speaker's face, measured on the grid
    "A_dubai":  dict(face=0.465, person=True, decor_kw=["outdoor"], captions=False,
                     per_frame=[0.45, 0.46, 0.47, 0.47, 0.47],
                     must_see=["dubai", "gratte", "immeub", "tour", "skyline", "building",
                               "palm", "palmier", "piece", "coin", "terrasse", "balcon", "city"]),
    # webcam inset bottom-left of a screen recording: face measured at 0.135-0.140
    "B_screen": dict(face=0.137, person=True, decor_kw=["desktop", "screen"], captions=False,
                     per_frame=[0.135, 0.135, 0.140, 0.135, 0.140],
                     must_see=["semrush", "trends", "google", "montre", "gps", "keyword",
                               "mot", "graph", "chart", "cpc", "volume", "dashboard", "browser"]),
    "C_car":    dict(face=0.415, person=True, decor_kw=["car"], captions=False,
                     per_frame=[None, 0.42, 0.44, 0.42, 0.38],
                     must_see=["porsche", "volant", "steering", "wheel", "parking",
                               "garage", "dashboard", "tableau de bord", "car"]),
    "E_mixed":  dict(face=0.44, person=True, decor_kw=["other", "outdoor"], captions=True,
                     per_frame=[None, None, 0.47, 0.44, 0.42],
                     must_see=["phone", "smartphone", "telephone", "dog", "chien", "petback",
                               "leash", "laisse", "aed", "100", "22h47", "listing", "annonce"]),
}
TOL = 0.10
TIGHT = 0.06


def extract_json(txt):
    if not txt:
        return None, "empty"
    clean = txt.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-zA-Z]*\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean), "clean"
    except Exception:
        pass
    m = re.search(r"\{.*\}", clean, re.S)
    if m:
        try:
            return json.loads(m.group(0)), "salvaged"
        except Exception:
            pass
    return None, "invalid"


rows = {}
for f in sorted(OUT.glob("t2__*.json")):
    r = json.loads(f.read_text())
    model, s = r["model"], r["set"]
    gt = GT[s]
    e = {"lat": r.get("latency_s"), "err": r.get("error"),
         "cost": (r.get("usage") or {}).get("cost"),
         "in": (r.get("usage") or {}).get("prompt_tokens"),
         "out": (r.get("usage") or {}).get("completion_tokens"),
         "provider": r.get("provider"), "finish": r.get("finish_reason")}
    if r.get("error"):
        e["json"] = "error"
        rows.setdefault(model, {})[s] = e
        continue
    obj, how = extract_json(r.get("text"))
    e["json"] = how
    if obj is None:
        e["raw_tail"] = (r.get("text") or "")[-200:]
        rows.setdefault(model, {})[s] = e
        continue
    fx = obj.get("face_center_x")
    e["face"] = fx
    try:
        e["face_err"] = abs(float(fx) - gt["face"])
    except Exception:
        e["face_err"] = None
    e["face_ok"] = e["face_err"] is not None and e["face_err"] <= TOL
    e["face_tight"] = e["face_err"] is not None and e["face_err"] <= TIGHT
    e["person"] = obj.get("person_visible")
    e["person_ok"] = bool(obj.get("person_visible")) == gt["person"]
    dec = str(obj.get("decor", "")).lower()
    e["decor"] = obj.get("decor")
    e["decor_ok"] = any(k in dec for k in gt["decor_kw"])
    e["captions"] = obj.get("burned_captions")
    e["captions_ok"] = bool(obj.get("burned_captions")) == gt["captions"]
    e["vscore"] = obj.get("visual_score")
    e["action"] = obj.get("action")
    e["proof"] = obj.get("proof_objects")
    e["problems"] = obj.get("problems")
    blob = " ".join(str(x).lower() for x in (obj.get("proof_objects") or [])) + " " + dec + " " + str(obj.get("action", "")).lower()
    e["proof_hits"] = sum(1 for k in gt["must_see"] if k in blob)
    rows.setdefault(model, {})[s] = e

agg = []
for model, d in rows.items():
    n = len(d)
    ok = lambda k: sum(1 for s in d.values() if s.get(k))
    errs = [s["face_err"] for s in d.values() if s.get("face_err") is not None]
    cost = sum((s.get("cost") or 0) for s in d.values())
    agg.append(dict(model=model, n=n,
                    face=ok("face_ok"), tight=ok("face_tight"), person=ok("person_ok"),
                    decor=ok("decor_ok"), capt=ok("captions_ok"),
                    jsonc=sum(1 for s in d.values() if s.get("json") == "clean"),
                    mae=round(sum(errs) / len(errs), 3) if errs else None,
                    maxerr=round(max(errs), 3) if errs else None,
                    proof=sum(s.get("proof_hits", 0) for s in d.values()),
                    cost4=round(cost, 6),
                    lat=round(sum((s.get("lat") or 0) for s in d.values()) / max(1, n), 1),
                    faces={s: d[s].get("face") for s in sorted(d)}))

# quality score: face accuracy weighted heaviest, then person/decor/captions
for r in agg:
    r["score"] = r["face"] * 3 + r["tight"] * 1 + r["person"] * 2 + r["decor"] * 2 + r["capt"] * 1 + r["jsonc"] * 1
agg.sort(key=lambda r: (-r["score"], r["mae"] if r["mae"] is not None else 9, r["cost4"]))

MAXS = 4 * (3 + 1 + 2 + 2 + 1 + 1)
print(f"GROUND TRUTH  A_dubai={GT['A_dubai']['face']}  B_screen={GT['B_screen']['face']}  "
      f"C_car={GT['C_car']['face']}  E_mixed={GT['E_mixed']['face']}   (tol +/-{TOL}, tight +/-{TIGHT})")
print()
hdr = f"{'model':38s} {'sc':>3}/{MAXS} {'face':>5} {'±.06':>5} {'pers':>5} {'dec':>4} {'cap':>4} {'json':>5} {'MAE':>6} {'max':>6} {'proof':>6} {'cost4':>9} {'lat':>5}  faces A/B/C/E"
print(hdr); print("-" * len(hdr) + "-" * 26)
for r in agg:
    f = r["faces"]
    print(f"{r['model']:38s} {r['score']:>3}/{MAXS} {r['face']:>3}/4 {r['tight']:>3}/4 {r['person']:>3}/4 "
          f"{r['decor']:>2}/4 {r['capt']:>2}/4 {r['jsonc']:>3}/4 {str(r['mae']):>6} {str(r['maxerr']):>6} "
          f"{r['proof']:>6} {r['cost4']:>9.6f} {r['lat']:>5.1f}  "
          f"{f.get('A_dubai')}/{f.get('B_screen')}/{f.get('C_car')}/{f.get('E_mixed')}")

json.dump(rows, open(HERE / "t2_scored.json", "w"), ensure_ascii=False, indent=1)
