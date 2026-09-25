"""Boundary checks for multi-video series submissions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import SeriesCreate
from app.services import jobs as jobs_svc
from app.services.jobs import JobError
from app.services.series import create_series


def test_series_requires_two_to_five_sources() -> None:
    with pytest.raises(ValidationError):
        SeriesCreate(campaign_id="campaign", source_urls=["https://youtu.be/one"])
    with pytest.raises(ValidationError):
        SeriesCreate(
            campaign_id="campaign",
            source_urls=[f"https://youtu.be/video-{i}" for i in range(6)],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("urls", "code"),
    [
        (["https://youtu.be/one", "https://youtu.be/one"], "duplicate_source"),
        (["https://youtu.be/one", "https://example.com/two"], "unsupported_source"),
    ],
)
async def test_invalid_series_rejected_before_database_access(urls: list[str], code: str) -> None:
    payload = SeriesCreate(campaign_id="campaign", source_urls=urls)
    with pytest.raises(JobError) as exc:
        await create_series(None, user_id="user", payload=payload)  # type: ignore[arg-type]
    assert exc.value.code == code


@pytest.mark.asyncio
async def test_starter_cannot_create_multi_video_series(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        def transaction(self) -> Connection:
            return self

        async def __aenter__(self) -> Connection:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def execute(self, *_args: object) -> None:
            return None

    async def starter_subscription(*_args: object) -> dict[str, int]:
        return {"max_series_sources": 1}

    monkeypatch.setattr(jobs_svc, "_active_subscription", starter_subscription)
    payload = SeriesCreate(
        campaign_id="campaign",
        source_urls=["https://youtu.be/one", "https://youtu.be/two"],
    )
    with pytest.raises(JobError) as exc:
        await create_series(Connection(), user_id="user", payload=payload)  # type: ignore[arg-type]
    assert exc.value.code == "series_not_in_plan"
