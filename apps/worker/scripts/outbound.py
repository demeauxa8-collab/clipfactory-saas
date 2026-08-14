"""Outbound machine — turn a list of prospects into finished clips to give away.

Cold outreach that asks for attention gets ignored. Outreach that hands over
three finished clips from someone's own last episode gets answered, and at
roughly 0.7 cent per source minute a batch of thirty prospects costs a few
euros. This script industrialises that: prospects in, ready-to-send folders out.

It drives the real pipeline through the real queue — no duplicated clipping
logic — so whatever a prospect receives is exactly what a paying customer gets.

Usage:

    # 1. Redis and the worker must be running:
    #      redis-server &
    #      cd apps/worker && python -m app.main
    #
    # 2. Queue a batch (creates one campaign per segment, one job per prospect):
    python scripts/outbound.py run prospects.json --operator you@example.com
    #
    # 3. Once the worker is done, collect the deliverables:
    python scripts/outbound.py collect prospects.json --operator you@example.com

Prospect file — a JSON list:

    [
      {
        "name": "Some Podcast",
        "contact": "hello@somepodcast.fr",
        "source_url": "https://www.youtube.com/watch?v=...",
        "segment": "podcaster",
        "audience": "optional override",
        "niche": "optional override"
      }
    ]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import redis.asyncio as redis_async

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import get_settings

JOBS_QUEUE_KEY = "clipfactory:jobs:queue"
CLIPS_PER_PROSPECT = 3

# Live pipeline states — anything else means the job is done, one way or another.
RUNNING_STATES = ("queued", "downloading", "transcribing", "analyzing", "rendering")


# The campaign brief steers which moments get picked, so it must describe the
# *prospect's* audience, not ours. These are defaults per segment; any prospect
# can override them field by field.
SEGMENT_BRIEFS: dict[str, dict[str, str]] = {
    "podcaster": {
        "audience": "People who already follow this show and share episodes with friends.",
        "niche": "Podcast",
        "tone": "Conversational, faithful to how the host actually speaks.",
        "goal": (
            "Make someone who has never heard this show want to play the full episode. "
            "Favour a complete thought over a shocking half-sentence."
        ),
    },
    "clipper": {
        "audience": (
            "Short-form viewers scrolling TikTok and Reels who stop for a strong claim "
            "and stay for the payoff."
        ),
        "niche": "Short-form entertainment",
        "tone": "Punchy, fast, hook in the first second.",
        "goal": (
            "Maximise watch-through on a cold scroll: open on the strongest line, keep "
            "the setup short, land a clear payoff before the end."
        ),
    },
}


@dataclass
class Prospect:
    name: str
    contact: str
    source_url: str
    segment: str
    audience: str | None = None
    niche: str | None = None

    @property
    def slug(self) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return s or "prospect"

    def brief(self) -> dict[str, str]:
        base = dict(SEGMENT_BRIEFS.get(self.segment, SEGMENT_BRIEFS["podcaster"]))
        if self.audience:
            base["audience"] = self.audience
        if self.niche:
            base["niche"] = self.niche
        return base


def load_prospects(path: str) -> list[Prospect]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise SystemExit("prospect file must be a JSON list")
    prospects: list[Prospect] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        for field in ("name", "contact", "source_url"):
            if not item.get(field):
                raise SystemExit(f"prospect #{i + 1} is missing '{field}'")
        p = Prospect(
            name=item["name"],
            contact=item["contact"],
            source_url=item["source_url"],
            segment=item.get("segment", "podcaster"),
            audience=item.get("audience"),
            niche=item.get("niche"),
        )
        if p.slug in seen:
            raise SystemExit(f"two prospects resolve to the same folder name: {p.slug}")
        seen.add(p.slug)
        prospects.append(p)
    return prospects


async def resolve_operator(conn: asyncpg.Connection, email: str) -> str:
    row = await conn.fetchrow("select user_id from profiles where email = $1", email)
    if row is None:
        raise SystemExit(f"no account found for {email}")
    return str(row["user_id"])


async def check_plan(conn: asyncpg.Connection, user_id: str) -> None:
    """Warns early rather than letting every job fail deep in the pipeline."""
    row = await conn.fetchrow(
        """
        select p.code, p.max_video_minutes, p.max_clips_per_video
          from subscriptions s
          join plan_definitions p on p.code = s.plan_code
         where s.user_id = $1 and s.status in ('trialing', 'active')
         order by s.current_period_end desc nulls last
         limit 1
        """,
        user_id,
    )
    if row is None:
        raise SystemExit(
            "The operator account has no active plan, so job creation would be refused.\n"
            "Give it an internal plan first (see docs/outbound.md)."
        )
    if int(row["max_video_minutes"]) < 60:
        print(
            f"  ! plan '{row['code']}' caps videos at {row['max_video_minutes']} min — "
            "most podcast episodes are longer and will fail on 'video_too_long'.",
            file=sys.stderr,
        )


async def get_or_create_campaign(
    conn: asyncpg.Connection, *, user_id: str, prospect: Prospect
) -> str:
    """One campaign per prospect: the brief is tailored to their audience."""
    name = f"Outbound — {prospect.name}"[:80]
    row = await conn.fetchrow(
        "select id from campaigns where user_id = $1 and name = $2",
        user_id,
        name,
    )
    if row is not None:
        return str(row["id"])

    brief = prospect.brief()
    row = await conn.fetchrow(
        """
        insert into campaigns (user_id, name, audience, niche, tone, goal)
        values ($1, $2, $3, $4, $5, $6)
        returning id
        """,
        user_id,
        name,
        brief["audience"],
        brief["niche"],
        brief["tone"],
        brief["goal"],
    )
    return str(row["id"])


async def find_job(
    conn: asyncpg.Connection, *, user_id: str, source_url: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select id, status, error_code, error_message
          from jobs
         where user_id = $1 and source_url = $2
         order by queued_at desc
         limit 1
        """,
        user_id,
        source_url,
    )


async def cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    prospects = load_prospects(args.prospects)
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    queued = skipped = 0

    try:
        async with pool.acquire() as conn:
            user_id = await resolve_operator(conn, args.operator)
            await check_plan(conn, user_id)

            for p in prospects:
                existing = await find_job(conn, user_id=user_id, source_url=p.source_url)
                if existing is not None and not args.force:
                    print(f"  = {p.name}: already queued ({existing['status']}), skipping")
                    skipped += 1
                    continue

                campaign_id = await get_or_create_campaign(conn, user_id=user_id, prospect=p)
                row = await conn.fetchrow(
                    """
                    insert into jobs
                      (user_id, campaign_id, source_url, target_clip_count,
                       status, current_step, credits_estimated)
                    values ($1, $2, $3, $4, 'queued', 'queued', 1)
                    returning id
                    """,
                    user_id,
                    campaign_id,
                    p.source_url,
                    CLIPS_PER_PROSPECT,
                )
                job_id = str(row["id"])
                await redis.rpush(JOBS_QUEUE_KEY, json.dumps({"job_id": job_id}))
                print(f"  + {p.name}: queued {job_id}")
                queued += 1
    finally:
        await redis.aclose()
        await pool.close()

    print(f"\n{queued} queued, {skipped} skipped.")
    print("Start the worker if it is not running:  cd apps/worker && python -m app.main")
    print(f"Then collect with:  python scripts/outbound.py collect {args.prospects}")
    return 0


async def cmd_collect(args: argparse.Namespace) -> int:
    settings = get_settings()
    prospects = load_prospects(args.prospects)
    out_root = Path(args.out).expanduser()
    clips_root = Path(settings.storage_local_dir)
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    ready = waiting = failed = 0

    try:
        async with pool.acquire() as conn:
            user_id = await resolve_operator(conn, args.operator)

            for p in prospects:
                job = await find_job(conn, user_id=user_id, source_url=p.source_url)
                if job is None:
                    print(f"  ? {p.name}: no job — run the 'run' command first")
                    waiting += 1
                    continue
                if job["status"] in RUNNING_STATES:
                    print(f"  … {p.name}: {job['status']}")
                    waiting += 1
                    continue
                if job["status"] != "completed":
                    print(f"  x {p.name}: {job['status']} ({job['error_code'] or 'no code'})")
                    failed += 1
                    continue

                clips = await conn.fetch(
                    """
                    select idx, title, hook_text, r2_key, score_total
                      from clips where job_id = $1 order by idx asc
                    """,
                    job["id"],
                )
                if not clips:
                    print(f"  x {p.name}: completed but produced no clips")
                    failed += 1
                    continue

                dest = out_root / p.slug
                dest.mkdir(parents=True, exist_ok=True)
                copied = 0
                for c in clips:
                    src = clips_root / str(c["r2_key"])
                    if not src.exists():
                        print(f"    ! missing rendered file for clip {c['idx'] + 1}: {src}")
                        continue
                    shutil.copy2(src, dest / f"clip-{c['idx'] + 1}.mp4")
                    copied += 1

                (dest / "message.txt").write_text(compose_message(p, clips))
                print(f"  > {p.name}: {copied} clips → {dest}")
                ready += 1
    finally:
        await pool.close()

    print(f"\n{ready} ready to send, {waiting} still running, {failed} failed.")
    return 0


def compose_message(prospect: Prospect, clips: list[asyncpg.Record]) -> str:
    """A draft, not a template to send blind — edit the first line per prospect."""
    best = max(clips, key=lambda c: c["score_total"] or 0)
    hook = (best["hook_text"] or best["title"] or "").strip()
    lines = [
        f"To: {prospect.contact}",
        f"Subject: {CLIPS_PER_PROSPECT} clips from your last episode",
        "",
        f"Hi — I cut {CLIPS_PER_PROSPECT} vertical clips out of your latest video.",
        "They're attached. Yours to post, no strings, nothing to sign up for.",
        "",
        "The one I'd start with:",
        f'  "{hook}"' if hook else "  clip-1.mp4",
        "",
        "I build the tool that made them. If they're useful I'd genuinely like to",
        "know what you'd change — that feedback is worth more to me than a customer.",
        "",
        "— Augustin",
        "",
        "---",
        "What was generated:",
    ]
    for c in clips:
        lines.append(
            f"  clip-{c['idx'] + 1}.mp4 — score {c['score_total'] or '—'} — "
            f"{(c['title'] or 'untitled').strip()}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--operator",
        default=os.environ.get("OUTBOUND_OPERATOR_EMAIL", ""),
        help="email of the account the jobs run under (or OUTBOUND_OPERATOR_EMAIL)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="queue one job per prospect")
    run.add_argument("prospects")
    run.add_argument("--force", action="store_true", help="re-queue prospects already done")
    run.set_defaults(func=cmd_run)

    collect = sub.add_parser("collect", help="gather finished clips into send-ready folders")
    collect.add_argument("prospects")
    collect.add_argument("--out", default="./outbound", help="output directory")
    collect.set_defaults(func=cmd_collect)

    args = parser.parse_args()
    if not args.operator:
        raise SystemExit("--operator is required (or set OUTBOUND_OPERATOR_EMAIL)")
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
