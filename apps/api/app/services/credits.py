from __future__ import annotations

import asyncpg


async def get_balance(conn: asyncpg.Connection, user_id: str) -> int:
    row = await conn.fetchrow(
        "select coalesce(sum(delta), 0)::int as balance from credit_ledger where user_id = $1",
        user_id,
    )
    return int(row["balance"]) if row else 0


async def insert_ledger(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    delta: int,
    reason: str,
    job_id: str | None = None,
    subscription_id: str | None = None,
    note: str | None = None,
) -> None:
    await conn.execute(
        """
        insert into credit_ledger (user_id, delta, reason, job_id, subscription_id, note)
        values ($1, $2, $3, $4, $5, $6)
        """,
        user_id,
        delta,
        reason,
        job_id,
        subscription_id,
        note,
    )
