"""A failed source only refunds credits actually debited for its job."""

from __future__ import annotations

from typing import Any

import pytest

from app.pipeline.runner import _mark_failed


class Connection:
    def __init__(self, status: str, net: int) -> None:
        self.status = status
        self.net = net
        self.statements: list[tuple[str, tuple[Any, ...]]] = []

    def acquire(self) -> Connection:
        return self

    def transaction(self) -> Connection:
        return self

    async def __aenter__(self) -> Connection:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def fetchrow(self, sql: str, *_args: object) -> dict[str, Any]:
        return {"status": self.status} if "from jobs" in sql else {"net": self.net}

    async def execute(self, sql: str, *args: Any) -> None:
        self.statements.append((sql, args))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "net", "expected_refund"),
    [
        ("downloading", 0, 0),
        ("rendering", -1, 1),
        ("failed", -1, 0),
    ],
)
async def test_failed_source_refund_is_bounded_by_real_debit(
    status: str, net: int, expected_refund: int
) -> None:
    conn = Connection(status, net)
    await _mark_failed(
        conn,  # type: ignore[arg-type]
        job_id="job",
        user_id="user",
        code="download_failed",
        step="download",
        message="Source failed",
        refund_credits=1,
    )
    refunds = [args[1] for sql, args in conn.statements if "insert into credit_ledger" in sql]
    assert refunds == ([expected_refund] if expected_refund else [])
    assert bool(conn.statements) is (status != "failed")
