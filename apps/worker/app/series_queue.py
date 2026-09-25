"""Claim the next source of a clip series without relying on a Redis handoff.

Queued series sources live in Postgres. This keeps their order recoverable if a
worker restarts between two videos, while ordinary single-source jobs continue
to use the existing Redis queue.
"""

from __future__ import annotations

import asyncpg


async def claim_next_series_job(pool: asyncpg.Pool) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            with candidate as (
              select j.id
                from jobs j
               where j.series_id is not null
                 and (
                   j.status = 'queued'
                   or (j.status = 'downloading'
                       and j.current_step = 'series_claimed'
                       and j.started_at < now() - interval '2 minutes')
                 )
                 and exists (
                   select 1 from subscriptions s
                    where s.user_id = j.user_id
                      and s.status in ('trialing', 'active')
                 )
                 and not exists (
                   select 1 from jobs earlier
                    where earlier.series_id = j.series_id
                      and earlier.series_position < j.series_position
                      and earlier.status not in ('completed', 'failed', 'canceled')
                 )
                 and not exists (
                   select 1 from jobs active
                    where active.user_id = j.user_id
                      and active.id <> j.id
                      and active.status in
                        ('downloading', 'transcribing', 'analyzing', 'rendering')
                 )
               order by j.queued_at, j.series_position
               for update of j skip locked
               limit 1
            )
            update jobs j
               set status = 'downloading',
                   current_step = 'series_claimed',
                   started_at = now(),
                   updated_at = now()
              from candidate
             where j.id = candidate.id
            returning j.id
            """
        )
    return str(row["id"]) if row else None
