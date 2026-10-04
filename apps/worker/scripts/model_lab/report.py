"""Export A/B/C clips and costs privately. Never infer a winner from missing clips."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from decimal import Decimal
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def latest(root):
    candidates = sorted((root / "runs").glob("*/cost_ledger.json"))
    return candidates[-1].parent if candidates else None


def export(root):
    rows, costs, accounting = [], {}, {}
    methods = ("A", "B", "C") if latest(root / "C") else ("A", "B")
    for method in methods:
        run = latest(root / method)
        if run is None:
            costs[method] = "0"
            continue
        ledger = load(run / "cost_ledger.json")
        costs[method] = ledger["charged_or_reserved_usd"]
        accounting[method] = {
            "provider_reported_usd": str(
                sum(
                    (
                        Decimal(e["charged_or_reserved_usd"])
                        for e in ledger["requests"]
                        if e.get("accounting", "unspecified") == "provider_reported"
                    ),
                    Decimal(0),
                )
            ),
            "other_charged_or_reserved_usd": str(
                sum(
                    (
                        Decimal(e["charged_or_reserved_usd"])
                        for e in ledger["requests"]
                        if e.get("accounting", "unspecified") != "provider_reported"
                    ),
                    Decimal(0),
                )
            ),
        }
        sources = (
            load(run / "report.json").get("sources", []) if (run / "report.json").exists() else []
        )
        if method in {"B", "C"}:
            sources = [load(f) for f in (run / "production/delivery").glob("*.json")]
        for source in sources:
            source_id = source.get("source_id") or source["source"]["id"]
            clips = source.get("clips", [])
            if not clips:
                continue
            entries = [e for e in ledger["requests"] if e["source"] == source_id]
            total = sum((Decimal(e["charged_or_reserved_usd"]) for e in entries), Decimal(0))
            specific = {}
            if method in {"B", "C"}:
                for clip in clips:
                    key = (
                        Path(clip["path"]).parent.name
                        + "/"
                        + f"{clip['candidate']['candidate_id']:02}"
                    )
                    specific[key] = sum(
                        (
                            Decimal(e["charged_or_reserved_usd"])
                            for e in entries
                            if e.get("candidate_key") == key
                        ),
                        Decimal(0),
                    )
            shared = total - sum(specific.values(), Decimal(0))
            for idx, clip in enumerate(clips, 1):
                directory = root / method / "clips" / source_id
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"clip_{idx:02}.mp4"
                if method == "A":
                    media = run / source_id / clip["media"]
                    duration = clip["metrics"]["duration_seconds"]
                    ending = clip["segments"][-1]["quote"]
                    closed = not clip["metrics"]["suspended_ending"]
                    direct = None
                    allocated = total / len(clips)
                    title = clip["title"]
                else:
                    media = Path(clip["path"])
                    duration = clip["duration_seconds"]
                    ending = clip["candidate"]["excerpt"].split(" … ")[-1]
                    closed = "fin_coupee" not in clip["judge"]["reasons"]
                    key = (
                        Path(clip["path"]).parent.name
                        + "/"
                        + f"{clip['candidate']['candidate_id']:02}"
                    )
                    direct = specific[key]
                    allocated = direct + shared / len(clips)
                    title = clip["candidate"]["title"]
                shutil.copyfile(media, path)
                row = {
                    "method": method,
                    "source_id": source_id,
                    "clip": idx,
                    "title": title,
                    "duration_seconds": round(duration, 3),
                    "ending_words": " ".join(ending.split()[-18:]),
                    "closed_ending_automatic": closed,
                    "native_judge_publishable": clip.get("judge", {}).get("publishable"),
                    "native_judge_reasons": clip.get("judge", {}).get("reasons", []),
                    "premium_qualified": clip.get("premium_qualified")
                    if method in {"B", "C"}
                    else None,
                    "diagnostic_only": bool(clip.get("diagnostic")),
                    "delivery_note": clip.get("delivery_note", ""),
                    "direct_api_usd": str(direct) if direct is not None else "unattributed",
                    "allocated_api_usd": str(allocated),
                    "video": str(path.relative_to(root)),
                }
                path.with_suffix(".json").write_text(json.dumps(row, ensure_ascii=False, indent=2))
                rows.append(row)
    preparation = root / "preparation-ledger.json"
    # Preparation is carried into A by --prior-ledger, not added a second time.
    uncarried = (
        Decimal(load(preparation)["charged_or_reserved_usd"])
        if preparation.exists() and latest(root / "A") is None
        else Decimal(0)
    )
    total = sum((Decimal(v) for v in costs.values()), uncarried)
    source_counts = {
        m: {
            source: sum(r["method"] == m and r["source_id"] == source for r in rows)
            for source in {r["source_id"] for r in rows if r["method"] == m}
        }
        for m in methods
    }
    if rows:
        with (root / "CLIPS.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    status = {
        "clips": rows,
        "costs_usd": costs,
        "accounting": accounting,
        "total_charged_or_reserved_usd": str(total),
        "caps_usd": {
            "A": "8.00",
            "B": "7.00",
            **({"C": "2.00"} if "C" in methods else {}),
            "total": "15.00",
        },
        "complete": (
            all(source_counts[m].keys() == source_counts["A"].keys() for m in methods)
            and all(
                len(source_counts[m]) == 2
                and all(count == 3 for count in source_counts[m].values())
                for m in methods
            )
        ),
        "human_rating": "pending",
        "native_judge_publishable": {
            m: sum(r["method"] == m and r["native_judge_publishable"] is True for r in rows)
            for m in methods
        },
        "B_premium_qualified": sum(
            r["method"] == "B" and r["premium_qualified"] is True for r in rows
        ),
        "editorial_qualified": {
            m: sum(r["method"] == m and r["premium_qualified"] is True for r in rows)
            for m in methods
            if m != "A"
        },
    }
    (root / "COMPARISON.json").write_text(json.dumps(status, ensure_ascii=False, indent=2))
    lines = [
        "# Comparaison méthode " + " / ".join(methods),
        "",
        f"Coût payé ou réservé : **{total:.6f} $** sur 15,00 $ maximum.",
        "",
        "A : pipeline du produit, budget 8 $. B : méthode éditoriale premium, budget 7 $.",
        "Mêmes sources et transcriptions gelées. A et B partagent le verrou premium ; "
        "C, quand présent, utilise le verrou de production. Transcription déjà existante "
        "hors coût du run ; nouvelle transcription partagée imputée au plafond A.",
        "",
        "Coût attribué : tous les appels de la source, y compris essais et passages rejetés. "
        "A répartit ce coût entre les clips livrés. B et C isolent les appels propres au candidat "
        "et répartissent les frais communs et rejets. Ces allocations ne sont pas des factures par clip.",
        "Les fins sont évaluées automatiquement, sans validation humaine.",
        "Les candidats de diagnostic restent signalés : leur livraison ne signifie pas "
        "qu'ils passent les seuils éditoriaux de leur méthode.",
        "",
        "Coûts : " + "; ".join(f"{m} : {costs[m]} $" for m in methods) + ".",
        "Avis du juge natif : "
        + "; ".join(f"{m} {status['native_judge_publishable'][m]}/6" for m in methods)
        + ".",
        "Seuils éditoriaux : "
        + "; ".join(f"{m} {count}/6" for m, count in status["editorial_qualified"].items())
        + ".",
        "C : méthode B avec Gemini 3.8 Flash, plafond 2 $. Son juge utilise également Flash, "
        "alors que A/B utilisent Pro : les avis ne sont pas directement comparables."
        if "C" in methods
        else "",
        "",
        "| Méthode | Source | Clip | Durée | Coût attribué | État | Derniers mots |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    lines.extend(
        f"| {r['method']} | {r['source_id']} | {r['clip']} | "
        f"{r['duration_seconds']:.2f} s | {Decimal(r['allocated_api_usd']):.4f} $ | "
        f"{'À revoir — diagnostic' if r['diagnostic_only'] else 'Avis positif' if r['native_judge_publishable'] else 'Avis négatif'} | "  # noqa: E501
        f"{r['ending_words'].replace('|', '/')} |"
        for r in rows
    )
    if not status["complete"]:
        lines.extend(["", "**Expérience incomplète : aucun vainqueur établi.**"])
    else:
        lines.extend(
            ["", f"**{len(rows)} médias livrés. Aucun vainqueur établi sans notation humaine.**"]
        )
    (root / "COMPARISON.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"clips": len(rows), "cost_usd": str(total), "complete": status["complete"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    export(parser.parse_args().root)
