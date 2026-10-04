"""Real production runner, isolated settings, disposable database and local media."""

from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import time
import tomllib
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg
from dotenv import dotenv_values

from .budget import Budget, duration_context, source_context
from .database import disposable_postgres
from .judge import judge_clip
from .metrics import clip_metrics
from .review import generate_review
from .sources import read_sources, sha256, verify_source

ROOT = Path(__file__).resolve().parents[4]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


class PreloadJournal:
    def __init__(self, source_directory, work_root):
        self.source_directory, self.work_root = source_directory, work_root

    def start(self, job_id, token):
        verify_source(self.source_directory)
        destination = self.work_root / job_id / token
        destination.mkdir(parents=True, mode=0o700)
        # Hard links are read-only; pipeline cleans only its own directory.
        os.link(self.source_directory / "source.mp4", destination / "source.mp4")
        data = json.loads((self.source_directory / "heatmap.json").read_text())
        # Accept raw frozen yt-dlp points, normalize to the production cache shape.
        if not isinstance(data, dict):
            data = {"points": data}
        write_json(destination / "heatmap.json", data)


@contextmanager
def frozen_transcript(source_directory, enabled):
    """Supply a verified experimental input; selection/render code stays unchanged."""
    if not enabled:
        yield
        return
    from app.models import Transcript, TranscriptSentence, TranscriptWord
    from app.pipeline import runner

    metadata = verify_source(source_directory)
    path = source_directory / "transcript.json"
    if sha256(path) != metadata.get("transcript_sha256"):
        raise ValueError("frozen transcript hash mismatch")
    data = json.loads(path.read_text())
    if not data.get("words") or any(
        not 0 <= w["start"] <= w["end"] <= metadata["duration"] + 1 for w in data["words"]
    ):
        raise ValueError("invalid frozen transcript clock")
    original = runner.transcribe

    async def cached_transcribe(source_path, **kwargs):
        if sha256(Path(source_path)) != metadata["sha256"]:
            raise ValueError("frozen transcript media mismatch")
        return Transcript(
            text=data["text"],
            language=data.get("language"),
            asr_backend=data.get("asr_backend", "openai"),
            words=[TranscriptWord(**w) for w in data["words"]],
            sentences=[TranscriptSentence(**s) for s in data.get("sentences", [])],
        )

    runner.transcribe = cached_transcribe
    try:
        yield
    finally:
        runner.transcribe = original


async def seed_source(pool, source, *, target=5):
    user = uuid4()
    campaign = source["campaign"]
    async with pool.acquire() as conn:
        await conn.execute(
            "insert into auth.users(id,email) values($1,'golden@example.invalid')", user
        )
        await conn.execute(
            "insert into subscriptions(user_id,plan_code,status) values($1,'starter','active')",
            user,
        )
        await conn.execute(
            "insert into credit_ledger(user_id,delta,reason) values($1,1000,'subscription_grant')",
            user,
        )
        await conn.execute(
            "update plan_definitions set max_clips_per_video=5,max_video_minutes=120 "
            "where code='starter'"
        )
        cid = await conn.fetchval(
            """insert into campaigns(user_id,name,audience,niche,tone,goal,example_hooks)
            values($1,'Golden reference',$2,$3,$4,$5,$6) returning id""",
            user,
            campaign["audience"],
            campaign["niche"],
            campaign["tone"],
            campaign["goal"],
            campaign["example_hooks"],
        )
        jid = await conn.fetchval(
            """insert into jobs(user_id,campaign_id,source_url,target_clip_count,credits_estimated)
            values($1,$2,$3,$4,1) returning id""",
            user,
            cid,
            "https://www.youtube.com/watch?v=" + source["id"],
            target,
        )
    return str(jid)


async def observe_steps(pool, job_id, done):
    times = defaultdict(float)
    previous, last = "starting", time.monotonic()
    while not done.is_set():
        async with pool.acquire() as conn:
            current = await conn.fetchval("select current_step from jobs where id=$1", job_id)
        now = time.monotonic()
        times[previous] += now - last
        previous, last = current or "starting", now
        try:
            await asyncio.wait_for(done.wait(), timeout=0.5)
        except TimeoutError:
            pass
    times[previous] += time.monotonic() - last
    return dict(times)


def export_source(directory, metadata, job, rows):
    checkpoints = {}
    for stage in ("transcript", "selection", "render_outcomes", "model_trace"):
        files = list((directory / "jobs").rglob(stage + ".json"))
        if files:
            shutil.copyfile(files[-1], directory / (stage + ".json"))
            checkpoints[stage] = json.loads(files[-1].read_text())
    transcript = checkpoints.get("transcript", {}).get("transcript")
    heatmap = metadata.get("heatmap_points")
    clips = []
    outcomes = checkpoints.get("render_outcomes", {}).get("outcomes", [])
    for row in rows:
        idx = row["idx"]
        media = f"clip_{idx:02d}.mp4"
        shutil.copyfile(directory / row["r2_key"], directory / media)
        outcome = next(
            o for o in outcomes if o.get("clip_index") == idx and o["status"] == "delivered"
        )
        render = json.loads((directory / outcome["manifest_key"]).read_text())
        write_json(directory / f"clip_{idx:02d}.manifest.json", render)
        shots = render["edl"]["shots"]
        segments = [
            {
                "start_seconds": s["source_in_ms"] / 1000,
                "end_seconds": s["source_out_ms"] / 1000,
                "from_word_id": s["from_word_id"],
                "to_word_id": s["to_word_id"],
                "quote": " ".join(
                    w["word"] for w in transcript["words"][s["from_word_id"] : s["to_word_id"] + 1]
                ),
            }
            for s in shots
        ]
        clips.append(
            {
                "idx": idx,
                "media": media,
                "sha256": sha256(directory / media),
                "title": row["title"],
                "rationale": row["rationale"],
                "score_total": row["score_total"],
                "score_breakdown": row["score_breakdown"],
                "segments": segments,
                "transcript_excerpt": " … ".join(s["quote"] for s in segments),
                "metrics": clip_metrics(render, transcript, heatmap, metadata["duration"]),
            }
        )
    return {
        "source_id": metadata["id"],
        "source_sha256": metadata["sha256"],
        "duration_seconds": metadata["duration"],
        "heatmap_available": metadata["heatmap_available"],
        "job_status": job["status"],
        "error_code": job["error_code"],
        "requested_clips": job["target_clip_count"],
        "clips": clips,
        "model_trace": checkpoints.get("model_trace", {}).get("model_trace", {}),
    }


def report(run, sources, budget, start, identity):
    clips = [c for s in sources for c in s["clips"]]
    costs = defaultdict(Decimal)
    for entry in budget.entries:
        costs[entry["stage"]] += Decimal(entry["charged_or_reserved_usd"])
    n = len(clips)
    rates = {
        key: sum(bool(c["metrics"][key]) for c in clips) / n if n else None
        for key in (
            "suspended_ending",
            "any_segment_suspended",
            "dependent_opening",
            "cut_inside_word",
            "duration_in_target_15_60",
        )
    }
    verdicts = [c["judge"] for c in clips if "publishable" in c.get("judge", {})]
    data = {
        **identity,
        "sources": sources,
        "delivered_clips": n,
        "requested_clips": sum(s["requested_clips"] for s in sources),
        "metrics": rates,
        "durations_seconds": sorted(c["metrics"]["duration_seconds"] for c in clips),
        "duration_summary_seconds": (
            {
                "min": min(c["metrics"]["duration_seconds"] for c in clips),
                "median": statistics.median(c["metrics"]["duration_seconds"] for c in clips),
                "max": max(c["metrics"]["duration_seconds"] for c in clips),
            }
            if clips
            else None
        ),
        "black_seconds": sum(c["metrics"]["black_seconds"] for c in clips),
        "silence_seconds": sum(c["metrics"]["silence_seconds"] for c in clips),
        "heatmap_sources": sum(s["heatmap_available"] for s in sources),
        "cost_cap_usd": str(budget.cap),
        "cost_charged_or_reserved_usd": str(budget.committed),
        "cost_per_clip_usd": str(budget.committed / n) if n else None,
        "costs_by_stage_usd": dict(costs),
        "cost_provider_reported_usd": str(
            sum(
                (
                    Decimal(e["charged_or_reserved_usd"])
                    for e in budget.entries
                    if e["accounting"] == "provider_reported"
                ),
                Decimal(0),
            )
        ),
        "cost_tariff_usd": str(
            sum(
                (
                    Decimal(e["charged_or_reserved_usd"])
                    for e in budget.entries
                    if e["accounting"] in {"usage_tariff", "asr_duration_tariff"}
                ),
                Decimal(0),
            )
        ),
        "cost_uncertain_reserved_usd": str(
            sum(
                (
                    Decimal(e["charged_or_reserved_usd"])
                    for e in budget.entries
                    if "upper_bound" in e["accounting"] or e["accounting"] == "reserved"
                ),
                Decimal(0),
            )
        ),
        "blocked_requests": sum(e["accounting"] == "blocked_before_send" for e in budget.entries),
        "elapsed_seconds": time.monotonic() - start,
        "judge_count": len(verdicts),
        "judge_publishable_count": sum(v["publishable"] for v in verdicts),
        "judge_rejection_reasons": dict(
            Counter(r for v in verdicts if not v["publishable"] for r in set(v["reasons"]))
        ),
        "cost_bound_violated": any(e.get("bound_violation") for e in budget.entries),
        "human_publishability": None,
        "status": "provisional_mini_reference",
    }
    write_json(run / "report.json", data)
    lines = [
        "# Golden provisional reference",
        "",
        f"Run: `{identity['run_id']}`",
        "",
        f"Code SHA: `{identity['git_sha']}`; models lock SHA-256: `{identity['models_sha256']}`.",
        "",
        f"Delivered: {n}/{data['requested_clips']}. "
        f"Cost charged or conservatively reserved: ${budget.committed} / ${budget.cap}.",
        f"Elapsed: {data['elapsed_seconds']:.1f}s. "
        f"Native-video judge: {len(verdicts)} verdicts; "
        f"{data['judge_publishable_count']} publishable (model opinion).",
        "Human publishability and judge agreement: pending human ratings.",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *[f"| {k} | {v:.1%} |" if v is not None else f"| {k} | N/A |" for k, v in rates.items()],
        f"| Black / silence seconds | {data['black_seconds']:.3f} / "
        f"{data['silence_seconds']:.3f} |",
        f"| Sources with heatmap | {data['heatmap_sources']}/{len(sources)} |",
        "",
        "## Definitions and limitations",
        "",
        "Closed FR/EN connector/pronoun flags are heuristics; "
        "articles alone are not marked dependent. "
        "Sentence-end tolerance: 0.5s against terminal punctuation in the ASR transcript. "
        "Word-cut tolerance: 1ms. Target duration: 15-60s.",
        "Heatmap: top 10% of buckets ranked by value; "
        "repeated shots count their playback duration; "
        "1,000 seeded "
        "same-duration random windows. Missing curves are N/A.",
        "OpenRouter cost uses response usage.cost including discarded answers and retries. "
        "OpenAI direct ASR uses returned duration at $0.006/min rounded up to seconds; "
        "OpenRouter ASR uses usage.cost when available, retaining its reserve otherwise. "
        "Anthropic uses usage "
        "tariffs. Ambiguous requests retain the pre-call upper bound. Provider invoices are "
        "not reconciled.",
        "Stage wall times are sampled every 0.5s; HTTP ledger contains precise request "
        "durations. Budget guard stops before a request whose conservative bound does not "
        "fit. No paid call is silently retried by the harness.",
        "",
        "## Sources",
        "",
    ]
    for s in sources:
        lines.append(
            f"- {s['source_id']}: {s['job_status']}, "
            f"{len(s['clips'])}/{s['requested_clips']}; "
            f"${s.get('cost_usd', '0')}; {s.get('elapsed_seconds', 0):.1f}s."
        )
        lines += ["", "| Stage | USD charged / reserved |", "|---|---:|"]
        lines += [
            f"| {stage} | {value} |"
            for stage, value in sorted(s.get("costs_by_stage_usd", {}).items())
        ]
        lines += ["", "| Pipeline step | Wall seconds (sampled) |", "|---|---:|"]
        lines += [
            f"| {step} | {value:.2f} |"
            for step, value in sorted(s.get("stage_wall_seconds", {}).items())
        ]
        lines.append("")
    lines += [
        "## Cost detail",
        "",
        f"Provider-reported charges: ${data['cost_provider_reported_usd']}.",
        f"ASR / Anthropic usage tariff calculation: ${data['cost_tariff_usd']}.",
        f"Uncertain conservative reserves: ${data['cost_uncertain_reserved_usd']}.",
        f"Requests blocked before sending: {data['blocked_requests']}.",
        f"A request cost bound was violated: {data['cost_bound_violated']}.",
        "",
        "## Duration distribution",
        "",
        str(data["duration_summary_seconds"]),
        "",
        "## Judge rejection reasons (model opinion)",
        "",
        "| Reason | Clips |",
        "|---|---:|",
    ]
    lines += [
        f"| {reason} | {count} |"
        for reason, count in sorted(data["judge_rejection_reasons"].items())
    ]
    (run / "report.md").write_text("\n".join(lines) + "\n")
    return data


async def run_sources(args, dsn, run, budget, identity):
    from app.pipeline.runner import run_job
    from app.providers.openrouter import OpenRouterProvider
    from app.settings import get_settings

    spec = importlib.util.spec_from_file_location(
        "golden_apply_schema", ROOT / "tests/integration/apply_schema.py"
    )
    schema = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(schema)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    results, start = [], time.monotonic()
    try:
        async with pool.acquire() as conn:
            await schema.apply_schema(conn)
        for source in read_sources(args.config, args.sources):
            source_directory = args.root / "sources" / source["id"]
            metadata = verify_source(source_directory)
            heatmap = json.loads((source_directory / "heatmap.json").read_text())
            metadata["heatmap_points"] = (
                heatmap.get("points") if isinstance(heatmap, dict) else heatmap
            )
            directory = run / source["id"]
            directory.mkdir(mode=0o700)
            os.environ["STORAGE_LOCAL_DIR"] = str(directory)
            get_settings.cache_clear()
            source_context.set(source["id"])
            duration_context.set(metadata["duration"])
            jid = await seed_source(pool, source, target=getattr(args, "target_clips", 5))
            done = asyncio.Event()
            watch = asyncio.create_task(observe_steps(pool, jid, done))
            source_start = time.monotonic()
            try:
                with frozen_transcript(source_directory, getattr(args, "reuse_transcripts", False)):
                    await run_job(
                        pool, jid, attempt_journal=PreloadJournal(source_directory, run / ".work")
                    )
            finally:
                done.set()
                steps = await watch
            async with pool.acquire() as conn:
                job = dict(await conn.fetchrow("select * from jobs where id=$1", jid))
                rows = await conn.fetch("select * from clips where job_id=$1 order by idx", jid)
            result = export_source(directory, metadata, job, rows)
            write_json(directory / "job.json", job)
            result["stage_wall_seconds"] = steps
            if args.judge:
                for clip in result["clips"]:
                    duration_context.set(clip["metrics"]["duration_seconds"])
                    try:
                        verdict = await judge_clip(
                            directory / clip["media"],
                            provider=OpenRouterProvider(),
                            model=get_settings().clip_judge_model,
                            campaign=source["campaign"],
                            transcript=clip["transcript_excerpt"],
                        )
                    except Exception as exc:
                        verdict = {"mode": "observation_only", "error_type": type(exc).__name__}
                    clip["judge"] = verdict
                    write_json(directory / f"clip_{clip['idx']:02d}.judge.json", verdict)
            result["elapsed_seconds"] = time.monotonic() - source_start
            entries = [e for e in budget.entries if e["source"] == source["id"]]
            result["cost_usd"] = str(
                sum((Decimal(e["charged_or_reserved_usd"]) for e in entries), Decimal(0))
            )
            result["costs_by_stage_usd"] = {
                stage: str(
                    sum(
                        (
                            Decimal(e["charged_or_reserved_usd"])
                            for e in entries
                            if e["stage"] == stage
                        ),
                        Decimal(0),
                    )
                )
                for stage in {e["stage"] for e in entries}
            }
            write_json(directory / "manifest.json", result)
            results.append(result)
            report(run, results, budget, start, identity)
            generate_review(run)
            print(
                f"Source complete: {len(result['clips'])}/5 clips, "
                f"{result['job_status']}; total ${budget.committed}",
                flush=True,
            )
    finally:
        await pool.close()
    report(run, results, budget, start, identity)
    generate_review(run)
    return run


def execute(args):
    from app.settings import Settings, get_settings

    if (Path.cwd() / ".env").exists():
        raise ValueError("run from a checkout root without a .env file")
    runtime = {}
    for line in (ROOT / "apps/worker/requirements.lock").read_text().splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.strip().split("==", 1)
            if name in {"openai", "anthropic", "httpx", "asyncpg", "pydantic"}:
                actual = importlib.metadata.version(name)
                if actual != version:
                    raise ValueError(f"runtime dependency {name} differs from requirements.lock")
                runtime[name] = actual

    # Clear all inherited settings and use only three whitelisted credentials.
    credentials = dotenv_values(args.credentials_file) if args.credentials_file else {}
    for field in Settings.model_fields:
        os.environ.pop(field.upper(), None)
    for name in ("OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID"):
        os.environ.pop(name, None)
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ[name] = credentials.get(name) or ""
    openrouter_asr = getattr(args, "asr_backend", "openai") == "openrouter"
    if openrouter_asr and not os.environ["OPENAI_API_KEY"]:
        os.environ["OPENAI_API_KEY"] = "unused-offline"
    if not os.environ["OPENAI_API_KEY"] or not os.environ["OPENROUTER_API_KEY"]:
        raise ValueError("benchmark provider credentials missing")
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if dirty:
        raise ValueError("commit benchmark code before paid run")
    lock = (getattr(args, "models_lock", None) or ROOT / "apps/worker/models.lock.toml").resolve()
    os.environ["MODELS_LOCK_PATH"] = str(lock)
    lock_sha = sha256(lock)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + git_sha[:10] + "-" + lock_sha[:10]
    run = args.root / "runs" / run_id
    run.mkdir(parents=True, mode=0o700)
    document = tomllib.loads(lock.read_text())
    prices = {
        m: {
            "input": str(Decimal(str(p["usd_per_mtok_input"])) / 1000000),
            "output": str(Decimal(str(p["usd_per_mtok_output"])) / 1000000),
        }
        for m, p in document["models"].items()
        if "usd_per_mtok_input" in p
    }
    prices.update(
        {
            m: {"minute": str(p["usd_per_minute"])}
            for m, p in document["models"].items()
            if "usd_per_minute" in p
        }
    )
    catalog = json.loads(args.catalog.read_text())
    for model in [v["model"] for v in document["stages"].values() if v["provider"] == "openrouter"]:
        if "input" not in prices.get(model, {}):  # STT is not in the chat catalog
            continue
        actual = next(m["pricing"] for m in catalog["data"] if m["id"] == model)
        if Decimal(actual["prompt"]) > Decimal(prices[model]["input"]) or Decimal(
            actual["completion"]
        ) > Decimal(prices[model]["output"]):
            raise ValueError("catalog prices increased: review cost bounds")
    shutil.copyfile(lock, run / "models.lock.toml")
    shutil.copyfile(args.config, run / "sources.toml")
    write_json(run / "pricing.json", prices)
    identity = {
        "run_id": run_id,
        "git_sha": git_sha,
        "models_sha256": lock_sha,
        "config_sha256": sha256(args.config),
        "pricing_catalog_sha256": sha256(args.catalog),
        "requirements_sha256": sha256(ROOT / "apps/worker/requirements.lock"),
        "runtime_versions": runtime,
        "asr_backend": getattr(args, "asr_backend", "openai"),
        "reused_transcripts": getattr(args, "reuse_transcripts", False),
        "target_clips": getattr(args, "target_clips", 5),
    }
    prior = json.loads(args.prior_ledger.read_text())["requests"] if args.prior_ledger else []
    budget = Budget(args.budget, run / "cost_ledger.json", prices, prior, max_cap="8")
    with disposable_postgres(args.pg_bin) as dsn:
        os.environ.update(
            DATABASE_URL=dsn,
            STORAGE_BACKEND="local",
            STORAGE_LOCAL_DIR=str(run),
            WORKER_TMP_DIR=str(run / ".work"),
            CLIP_JUDGE_ENABLED="false",
            ENV="dev",
            ASR_BACKEND=getattr(args, "asr_backend", "openai"),
        )
        get_settings.cache_clear()
        with budget.intercept():
            asyncio.run(run_sources(args, dsn, run, budget, identity))
    print("Golden report: " + str(run / "report.md"), flush=True)
    return run
