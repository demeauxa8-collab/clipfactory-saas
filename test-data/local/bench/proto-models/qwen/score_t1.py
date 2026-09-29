#!/usr/bin/env python3
"""T1 scoring against ground truth I read myself off the 20 frames (verify/map_sheet.jpg).

Ground truth per frame timestamp:
 3.0 outdoor Dubai talking head + coin | 32.6 BLACK FRAME | 62.2 indoor atrium head
 91.8 parking garage head | 121.4 dark head + burned "1. La recherche"
 151.0 SCREEN random-french-words site | 180.6 head holding phone w/ analytics
 210.2 SCREEN google homepage | 239.8 SCREEN aliexpress home | 269.4 SCREEN aliexpress gps watch
 299.0 SCREEN google trends | 328.6 hand holding phone playing product video (boy blue jacket)
 358.2 dark + burned "2. On cree le site..." | 387.8 atrium head + burned "16H38 83EUR"
 417.4 Porsche steering wheel, NO face | 447.0 indoor showroom head
 476.6 SCREEN shopify analytics | 506.2 SCREEN shopify analytics | 535.8 SCREEN google ads
 565.4 purple-lit bedroom head
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).parent

SCREEN_WINDOWS = [(140, 165), (200, 225), (230, 255), (260, 285), (290, 315),
                  (465, 490), (495, 520), (525, 550)]
HEAD_WINDOWS = [(0, 12), (55, 75), (85, 100), (375, 400), (440, 460), (555, 580)]
CAR_WINDOW = (410, 430)

# things visible somewhere in the frames -> a model naming them is grounded
GROUNDED = ["aliexpress", "google trends", "shopify", "google ads", "porsche", "steering",
            "dubai", "coin", "phone", "smartphone", "webcam", "dashboard", "analytics",
            "parking", "garage", "search"]
# things NOT visible in ANY of the 20 frames -> naming them is a hallucination
HALLUCINATED = ["dog", "chien", "puppy", "cat", "leash", "laisse", "microphone", "mic ",
                "whiteboard", "notebook", "book", "guitar", "gaming", "console", "headset",
                "coffee", "cup", "beach", "pool", "plane", "avion", "gym"]


def parse(txt):
    if not txt:
        return None, "empty"
    t = re.sub(r"^```(?:json)?\s*", "", txt.strip())
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


def cover(ev, lo, hi):
    for e in ev:
        try:
            s, en = float(e.get("start")), float(e.get("end"))
        except Exception:
            continue
        if s < hi and en > lo:
            yield e


rows = []
for f in sorted((HERE / "out").glob("t1__*.json")):
    rec = json.loads(f.read_text())
    m = rec["model"]
    u = rec.get("usage") or {}
    r = dict(model=m, lat=rec.get("latency_s"), cost=u.get("cost"),
             tin=u.get("prompt_tokens"), tout=u.get("completion_tokens"),
             finish=rec.get("finish_reason"), err=rec.get("error"))
    obj, how = parse(rec.get("text"))
    r["json"] = how
    if obj:
        ev = obj.get("events") or []
        r["n_events"] = len(ev)
        r["in_range"] = 15 <= len(ev) <= 35
        try:
            r["span"] = (round(min(float(e["start"]) for e in ev)),
                         round(max(float(e["end"]) for e in ev)))
        except Exception:
            r["span"] = None
        blob = json.dumps(obj, ensure_ascii=False).lower()
        # screen detection: does an event covering a screen window say desktop/screen?
        sc_ok = 0
        for lo, hi in SCREEN_WINDOWS:
            hit = [e for e in cover(ev, lo, hi)]
            txt = json.dumps(hit, ensure_ascii=False).lower()
            if any(k in txt for k in ("desktop", "screen", "ecran", "écran", "browser", "website")):
                sc_ok += 1
        r["screen_ok"] = f"{sc_ok}/{len(SCREEN_WINDOWS)}"
        hd_ok = 0
        for lo, hi in HEAD_WINDOWS:
            txt = json.dumps([e for e in cover(ev, lo, hi)], ensure_ascii=False).lower()
            if ("desktop" not in txt and "screen" not in txt) and txt != "[]":
                hd_ok += 1
        r["head_ok"] = f"{hd_ok}/{len(HEAD_WINDOWS)}"
        txt = json.dumps([e for e in cover(ev, *CAR_WINDOW)], ensure_ascii=False).lower()
        r["car_ok"] = ("car" in txt or "porsche" in txt or "steering" in txt or "voiture" in txt)
        r["grounded"] = sorted({g for g in GROUNDED if g in blob})
        r["halluc"] = sorted({h for h in HALLUCINATED if h in blob})
        r["n_grounded"] = len(r["grounded"])
        r["n_halluc"] = len(r["halluc"])
    rows.append(r)

(HERE / "t1_scored.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
print(f"{'model':38s} {'json':>9s} {'ev':>4s} {'span':>12s} {'screen':>7s} {'head':>5s} {'car':>4s} "
      f"{'grnd':>5s} {'hall':>5s} {'lat':>6s} {'cost$':>10s}")
for r in sorted(rows, key=lambda x: -(x.get("n_grounded") or 0)):
    if r.get("err"):
        print(f"{r['model']:38s} ERROR {str(r['err'])[:70]}")
        continue
    print(f"{r['model']:38s} {r['json']:>9s} {r.get('n_events'):>4} {str(r.get('span')):>12s} "
          f"{r.get('screen_ok'):>7s} {r.get('head_ok'):>5s} {str(r.get('car_ok')):>5s} "
          f"{r.get('n_grounded'):>5} {r.get('n_halluc'):>5} {r.get('lat'):>6} ${r.get('cost')}")
print()
for r in rows:
    if r.get("halluc"):
        print(r["model"], "HALLUCINATED:", r["halluc"])
