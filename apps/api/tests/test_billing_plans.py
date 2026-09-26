"""Paid-plan boundaries: never sell Pro at the Starter Stripe price."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import billing


class Connection:
    def __init__(self, rows: list[dict[str, Any] | None]) -> None:
        self.rows = rows

    async def fetchrow(self, *_args: object) -> dict[str, Any] | None:
        return self.rows.pop(0)


@pytest.fixture(autouse=True)
def stripe_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        billing,
        "get_settings",
        lambda: SimpleNamespace(
            stripe_secret_key="sk_test_placeholder",
            stripe_starter_price_id="price_starter",
            web_base_url="https://example.com",
        ),
    )


@pytest.mark.asyncio
async def test_pro_checkout_requires_its_own_active_price() -> None:
    # An active plan with no Stripe price must fail before customer creation.
    conn = Connection([{"stripe_price_id": None}])
    with pytest.raises(billing.BillingError) as exc:
        await billing.create_checkout_url(
            conn, user_id="user", email="person@example.com", plan_code="pro"  # type: ignore[arg-type]
        )
    assert exc.value.code == "plan_unavailable"
    assert not conn.rows


@pytest.mark.asyncio
async def test_existing_subscription_cannot_open_a_second_checkout() -> None:
    conn = Connection([{"stripe_price_id": "price_pro"}, {"plan_code": "starter"}])
    with pytest.raises(billing.BillingError) as exc:
        await billing.create_checkout_url(
            conn, user_id="user", email="person@example.com", plan_code="pro"  # type: ignore[arg-type]
        )
    assert exc.value.code == "subscription_exists"


@pytest.mark.asyncio
async def test_webhook_uses_billed_price_even_if_metadata_is_stale() -> None:
    conn = Connection([{"code": "pro"}])
    sub = {
        "items": {"data": [{"price": {"id": "price_pro"}}]},
        "metadata": {"plan_code": "starter"},
    }
    assert await billing._plan_code_for_subscription(conn, sub) == "pro"  # type: ignore[arg-type]
