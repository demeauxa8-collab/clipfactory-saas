"""Recompute free measurements from retained media manifests; no provider calls."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from .harness import ROOT, report, write_json
from .metrics import clip_metrics
from .review import generate_review
from .sources import verify_source


def recompute_report(run: Path, sources_root: Path):
    previous = json.loads((run / "report.json").read_text())
    ledger = json.loads((run / "cost_ledger.json").read_text())
    budget = SimpleNamespace(
        cap=Decimal(ledger["cap_usd"]),
        entries=ledger["requests"],
        committed=sum(
            (Decimal(e["charged_or_reserved_usd"]) for e in ledger["requests"]), Decimal(0)
        ),
    )
    sources = previous["sources"]
    for source in sources:
        directory = run / source["source_id"]
        meta = verify_source(sources_root / source["source_id"])
        raw = json.loads((sources_root / source["source_id"] / "heatmap.json").read_text())
        heatmap = raw.get("points") if isinstance(raw, dict) else raw
        transcript_file = directory / "transcript.json"
        if transcript_file.exists():
            transcript = json.loads(transcript_file.read_text())["transcript"]
            for clip in source["clips"]:
                render = json.loads(
                    (directory / f"clip_{clip['idx']:02d}.manifest.json").read_text()
                )
                clip["metrics"] = clip_metrics(render, transcript, heatmap, meta["duration"])
                if isinstance(clip["score_breakdown"], str):
                    clip["score_breakdown"] = json.loads(clip["score_breakdown"])
        write_json(directory / "manifest.json", source)
    identity = {
        k: previous[k]
        for k in (
            "run_id",
            "git_sha",
            "models_sha256",
            "config_sha256",
            "pricing_catalog_sha256",
            "requirements_sha256",
            "runtime_versions",
        )
    }
    identity["metrics_revision_git_sha"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    identity["metrics_recomputed_at"] = datetime.now(UTC).isoformat()
    result = report(run, sources, budget, time.monotonic() - previous["elapsed_seconds"], identity)
    generate_review(run)
    return result
