"""A failed source only refunds credits actually debited for its job.

The worker's single failure path (``job_state.fail_job``) must keep the
multi-source guarantees: no refund without a debit, never twice for a terminal
job, and a series pre-claim is converted into a fenced attempt.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.pipeline.job_state import claim_job, fail_job

ACTIVE = {"downloading", "transcribing", "analyzing", "rendering"}


class Connection:
    def __init__(self, status: str, net: int) -> None:
        self.status = status
        self.net = net
        self.statements: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> Connection:
        return self

    async def __aenter__(self) -> Connection:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def fetchrow(self, sql: str, *_args: object) -> dict[str, Any] | None:
        if "from profiles" in sql:
            return {"user_id": "user"}
        if "from jobs" in sql:
            return {"id": "job"} if self.status in ACTIVE else None
        raise AssertionError(sql)

    async def fetchval(self, sql: str, *_args: object) -> int:
        assert "credit_ledger" in sql
        # _reserved() returns the negated net of this job's debits and refunds.
        return self.net

    async def execute(self, sql: str, *args: Any) -> None:
        self.statements.append((sql, args))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "net", "expected_refund"),
    [
        ("downloading", 0, 0),  # failed before the reservation: nothing to refund
        ("rendering", -1, 1),  # one credit reserved: refund exactly one
        ("rendering", -3, 3),
        ("failed", -1, 0),  # already terminal: never refund twice
    ],
)
async def test_failed_source_refund_is_bounded_by_real_debit(
    status: str, net: int, expected_refund: int
) -> None:
    conn = Connection(status, net)
    owned = await fail_job(
        conn,  # type: ignore[arg-type]
        job_id="job",
        user_id="user",
        token="attempt",
        code="download_failed",
        step="download",
        message="Source failed",
    )
    refunds = [args[1] for sql, args in conn.statements if "insert into credit_ledger" in sql]
    assert refunds == ([expected_refund] if expected_refund else [])
    assert owned is (status in ACTIVE)
    assert bool(conn.statements) is (status in ACTIVE)


class ClaimConnection:
    def __init__(self) -> None:
        self.sql = ""

    async def fetchrow(self, sql: str, *_args: object) -> None:
        self.sql = sql
        return None


@pytest.mark.asyncio
async def test_claim_accepts_series_preclaim_but_not_an_active_attempt() -> None:
    conn = ClaimConnection()
    await claim_job(conn, "00000000-0000-0000-0000-000000000001")  # type: ignore[arg-type]
    normalized = " ".join(conn.sql.split())
    assert "status = 'queued'" in normalized
    assert "status = 'downloading' and current_step = 'series_claimed'" in normalized
