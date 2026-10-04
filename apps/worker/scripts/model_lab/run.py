"""Run the frozen editorial method against shared inputs, using OpenRouter only."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.golden.budget import Budget, BudgetExceeded, duration_context, source_context
from app.golden.harness import write_json
from app.golden.sources import read_sources, sha256, verify_source

CODE = Path(__file__).resolve().parents[4]


def ensure_media_tools():
    missing = [tool for tool in ("ffmpeg", "ffprobe") if not shutil.which(tool)]
    if missing:
        raise ValueError("media tools missing from PATH before paid calls: " + ", ".join(missing))


def stage_source(shared, target, meta, *, resume):
    target.mkdir(parents=True, exist_ok=resume)
    if resume and (target / "source.mp4").exists():
        if (
            sha256(target / "transcript.json") != meta["transcript_sha256"]
            or sha256(target / "source.mp4") != meta["sha256"]
        ):
            raise ValueError("resumed source content changed")
    else:
        if any(target.iterdir()):
            raise ValueError("incomplete source staging requires inspection")
        os.link(shared / "source.mp4", target / "source.mp4")
        shutil.copyfile(shared / "transcript.json", target / "transcript.json")


async def execute(args):
    ensure_media_tools()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CODE, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=CODE, text=True).strip():
        raise ValueError("commit the method before paid requests")
    if not args.credentials_file.exists():
        raise ValueError("lab credentials file missing")
    document = tomllib.loads(args.models_lock.read_text())
    lock_hash = sha256(args.models_lock)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run = args.resume_run or args.root / "runs" / (stamp + "-" + revision[:10])
    if args.resume_run:
        previous_identity = json.loads((run / "identity.json").read_text())
        if previous_identity["models_sha256"] != lock_hash or previous_identity[
            "source_config_sha256"
        ] != sha256(args.config):
            raise ValueError("cannot resume with changed models or sources")
        previous_ledger = json.loads((run / "cost_ledger.json").read_text())
        if Decimal(previous_ledger["cap_usd"]) != Decimal(args.budget):
            raise ValueError("resuming cannot change the original budget")
        if any(e.get("bound_violation") for e in previous_ledger["requests"]):
            raise BudgetExceeded("prior bound violation prohibits more requests")
        shutil.copyfile(run / "cost_ledger.json", run / f"ledger-before-{stamp}.json")
        shutil.copyfile(run / "report.json", run / f"report-before-{stamp}.json")
    else:
        run.mkdir(parents=True, mode=0o700)
    os.environ.update(
        MODEL_LAB_ROOT=str(run),
        MODEL_LAB_LOCK=str(args.models_lock.resolve()),
        MODEL_LAB_CREDENTIALS=str(args.credentials_file.resolve()),
    )
    sys.path.insert(0, str(Path(__file__).parent))
    import deliver_workflow as delivery

    p = delivery.p
    prices = {
        m: {
            "input": str(Decimal(str(v["usd_per_mtok_input"])) / 1000000),
            "output": str(Decimal(str(v["usd_per_mtok_output"])) / 1000000),
        }
        for m, v in document["models"].items()
        if "usd_per_mtok_input" in v
    }
    catalog = json.loads(args.catalog.read_text())
    for model in {p.MODELS[0], p.AUDIT, p.FRAME_MODEL, p.VISION}:
        price = next(m["pricing"] for m in catalog["data"] if m["id"] == model)
        if any(
            Decimal(price[k]) > Decimal(prices[model][v])
            for k, v in (("prompt", "input"), ("completion", "output"))
        ):
            raise ValueError("model catalog price exceeds frozen lock")
    budget = Budget(
        args.budget,
        run / (f"recovery-ledger-{stamp}.json" if args.resume_run else "cost_ledger.json"),
        prices,
        prior_entries=previous_ledger["requests"] if args.resume_run else None,
        max_cap="7",
    )
    original_call = p.call

    async def measured_call(*a, **kwargs):
        video = kwargs.get("video")
        token = None
        if video:
            seconds = float(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(video),
                    ],
                    text=True,
                )
            )
            token = duration_context.set(seconds)
        before = len(budget.entries)
        try:
            return await original_call(*a, **kwargs)
        finally:
            if token is not None:
                duration_context.reset(token)
            cache = Path(a[3])
            clip = re.search(r"candidate-(\d+)", cache.name)
            for entry in budget.entries[before:]:
                entry["method_stage"] = kwargs.get("stage", "selection")
                entry["candidate_id"] = int(clip.group(1)) if clip else None
                entry["candidate_key"] = (cache.parent.name + "/" + clip.group(1)) if clip else None
            budget.save()

    p.call = measured_call
    p.NET = asyncio.Semaphore(1)
    results = []
    identity = {
        "git_sha": revision,
        "models_sha256": lock_hash,
        "source_config_sha256": sha256(args.config),
        "method": args.root.name if args.root.name in {"B", "C"} else "B",
        "transport": "OpenRouter only",
        "warm_shared_transcripts": True,
    }
    if args.resume_run:
        identity = {
            **previous_identity,
            "recovery_git_sha": revision,
            "original_runner_method": previous_identity["method"],
            "method": identity["method"],
        }
    write_json(run / "identity.json", identity)
    shutil.copyfile(args.models_lock, run / "models.lock.toml")
    try:
        with budget.intercept():
            for position, source in enumerate(read_sources(args.config), 1):
                shared = args.shared_root / source["id"]
                meta = verify_source(shared)
                if sha256(shared / "transcript.json") != meta.get("transcript_sha256"):
                    raise ValueError("shared transcript hash mismatch")
                target = run / "production/sources" / source["id"]
                stage_source(shared, target, meta, resume=bool(args.resume_run))
                p.write(
                    target / "media.json",
                    {
                        "path": str(target / "source.mp4"),
                        "duration_seconds": meta["duration"],
                        "sha256": meta["sha256"],
                    },
                )
                config = {
                    **source,
                    "position": position,
                    "category": "podcast",
                    "title": meta["title"],
                    "creator": meta.get("creator", ""),
                    "url": "https://www.youtube.com/watch?v=" + source["id"],
                }
                p.BRIEFS["podcast"] = json.dumps(source["campaign"], ensure_ascii=False)
                source_context.set(source["id"])
                try:
                    clips = await delivery.produce(
                        config,
                        p.MODELS[0],
                        max_rounds=3 if args.resume_run else 2,
                        reuse_paid_candidates=bool(args.resume_run),
                    )
                    results.append({"source_id": source["id"], "clips": clips})
                except BudgetExceeded:
                    raise
                except Exception as error:
                    results.append(
                        {
                            "source_id": source["id"],
                            "error_type": type(error).__name__,
                            "error": str(error)[:300],
                        }
                    )
    finally:
        if args.resume_run:
            temporary = run / "cost_ledger.resume.tmp"
            shutil.copyfile(budget.path, temporary)
            temporary.replace(run / "cost_ledger.json")
        write_json(
            run / "report.json",
            {
                **identity,
                "sources": results,
                "charged_or_reserved_usd": str(budget.committed),
                "cap_usd": args.budget,
            },
        )
    print("Premium method report: " + str(run / "report.json"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shared-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--models-lock", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--budget", default="7.00")
    parser.add_argument(
        "--resume-run", type=Path, help="Reuse paid candidates and cumulative ledger"
    )
    asyncio.run(execute(parser.parse_args()))


if __name__ == "__main__":
    main()
