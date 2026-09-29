#!/usr/bin/env python3
"""Score every T2 run (old sets in out/, decisive sets in outb/) against
ground truth I measured myself on 20-column grid overlays."""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).parent

# ---- ground truth, measured by hand on grid overlays (verify/*.jpg) ----
TRUTH = {
    # decisive sets
    "t2_head":    dict(face=0.63, tol=0.10, person=True, decor={"studio podcast", "other"},
                       screen=False, captions=False, note="face clearly RIGHT of centre"),
    "t2_screen":  dict(face=0.13, tol=0.10, person=True, decor={"desktop screen"},
                       screen=True, captions=False, note="webcam inset bottom-left"),
    "t2_caption": dict(face=0.48, tol=0.10, person=True, decor={"studio podcast", "other"},
                       screen=False, captions=True, note="big burned yellow text block"),
    # older sets (truth re-measured: B_screen was 0.075 in the first pass -> actually 0.14)
    "A_dubai":    dict(face=0.46, tol=0.10, person=True, decor={"outdoor"}, screen=False, captions=False),
    "B_screen":   dict(face=0.14, tol=0.10, person=True, decor={"desktop screen"}, screen=True, captions=False),
    "C_car":      dict(face=0.44, tol=0.12, person=True, decor={"car"}, screen=False, captions=False),
    "E_mixed":    dict(face=0.47, tol=0.12, person=True, decor={"other", "studio podcast"}, screen=False, captions=None),
}


def parse_json(txt):
    if not txt:
        return None, "empty"
    t = txt.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    try:
        return json.loads(t), "clean"
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0)), "repaired"
        except Exception:
            pass
    return None, "invalid"


def score_dir(d, prefix):
    rows = {}
    for f in sorted(pathlib.Path(d).glob(prefix + "*.json")):
        rec = json.loads(f.read_text())
        model, s = rec["model"], rec["set"]
        tr = TRUTH[s]
        u = rec.get("usage") or {}
        r = dict(lat=rec.get("latency_s"), err=rec.get("error"), cost=u.get("cost"),
                 tin=u.get("prompt_tokens"), tout=u.get("completion_tokens"),
                 provider=rec.get("provider"), finish=rec.get("finish_reason"))
        if rec.get("error"):
            r["json"] = "error"
            rows.setdefault(model, {})[s] = r
            continue
        obj, how = parse_json(rec.get("text"))
        r["json"] = how
        if obj:
            fx = obj.get("face_center_x")
            r["face"] = fx
            if isinstance(fx, (int, float)):
                r["face_err"] = round(abs(fx - tr["face"]), 3)
                r["face_ok"] = r["face_err"] <= tr["tol"]
            else:
                r["face_err"] = None
                r["face_ok"] = False
            pv = obj.get("person_visible")
            r["person"] = pv
            r["person_ok"] = (pv is tr["person"])
            dec = (obj.get("decor") or "").strip().lower()
            r["decor"] = dec
            r["decor_ok"] = any(k in dec or dec in k for k in tr["decor"])
            cap = obj.get("burned_captions")
            r["captions"] = cap
            r["captions_ok"] = None if tr["captions"] is None else (cap is tr["captions"])
            r["vscore"] = obj.get("visual_score")
            r["action"] = obj.get("action")
            r["proof"] = obj.get("proof_objects")
        rows.setdefault(model, {})[s] = r
    return rows


def merge(a, b):
    for m, sets in b.items():
        a.setdefault(m, {}).update(sets)
    return a


if __name__ == "__main__":
    rows = merge(score_dir(HERE / "outb", "t2b__"), score_dir(HERE / "out", "t2__"))
    (HERE / "t2_all_scored.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))

    DEC = ["t2_head", "t2_screen", "t2_caption"]
    ALL = DEC + ["A_dubai", "B_screen", "C_car", "E_mixed"]

    def agg(m, sets, keys):
        d = rows[m]
        ok = lambda k: sum(1 for s in sets if d.get(s, {}).get(k) is True)
        n = len(sets)
        return ok, n

    print("=" * 150)
    print("DECISIVE SETS ONLY (t2_head face=0.63 / t2_screen face=0.13 / t2_caption captions=True)")
    print(f"{'model':38s} {'face_ok':>8s} {'facerr':>22s} {'person':>7s} {'decor':>6s} {'capt':>5s} "
          f"{'json':>16s} {'lat':>6s} {'$/3sets':>9s}")
    out = []
    for m in rows:
        d = rows[m]
        if not all(s in d for s in DEC):
            continue
        fok = sum(1 for s in DEC if d[s].get("face_ok") is True)
        ferr = [d[s].get("face_err") for s in DEC]
        pok = sum(1 for s in DEC if d[s].get("person_ok") is True)
        dok = sum(1 for s in DEC if d[s].get("decor_ok") is True)
        cok = sum(1 for s in DEC if d[s].get("captions_ok") is True)
        js = [d[s].get("json") for s in DEC]
        clean = sum(1 for x in js if x == "clean")
        cost = sum((d[s].get("cost") or 0) for s in DEC)
        lat = sum((d[s].get("lat") or 0) for s in DEC) / 3
        faces = [d[s].get("face") for s in DEC]
        out.append((fok, pok + dok + cok, -cost, m, ferr, faces, pok, dok, cok, clean, js, lat, cost))
    for fok, _, _, m, ferr, faces, pok, dok, cok, clean, js, lat, cost in sorted(out, reverse=True):
        fe = " ".join("--" if x is None else f"{x:.2f}" for x in ferr)
        fv = " ".join("null" if x is None else (f"{x}" if not isinstance(x, float) else f"{x:.2f}") for x in faces)
        print(f"{m:38s} {fok}/3      err[{fe}] got[{fv}]  {pok}/3   {dok}/3  {cok}/3  "
              f"{clean}/3 clean {lat:6.1f} ${cost:.5f}")

    print()
    print("=" * 150)
    print("ALL 7 SETS")
    print(f"{'model':38s} {'face':>6s} {'person':>7s} {'decor':>6s} {'json_clean':>11s} {'meanlat':>8s} {'$/7':>10s}")
    out2 = []
    for m in rows:
        d = rows[m]
        ss = [s for s in ALL if s in d]
        if len(ss) < 5:
            continue
        fok = sum(1 for s in ss if d[s].get("face_ok") is True)
        pok = sum(1 for s in ss if d[s].get("person_ok") is True)
        dok = sum(1 for s in ss if d[s].get("decor_ok") is True)
        clean = sum(1 for s in ss if d[s].get("json") == "clean")
        cost = sum((d[s].get("cost") or 0) for s in ss)
        lat = sum((d[s].get("lat") or 0) for s in ss) / len(ss)
        out2.append((fok / len(ss), fok, len(ss), pok, dok, clean, lat, cost, m))
    for _, fok, n, pok, dok, clean, lat, cost, m in sorted(out2, reverse=True):
        print(f"{m:38s} {fok}/{n}    {pok}/{n}     {dok}/{n}    {clean}/{n}        {lat:6.1f}  ${cost:.5f}")
