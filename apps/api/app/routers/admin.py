"""Admin endpoints — restricted to profiles.is_admin = true.

All endpoints return aggregated data for the operator dashboard. No row-level
mutation here (admin actions like refund / ban are V2).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth import CurrentUser, admin_required
from ..db import get_pool

router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================
# Overview — top stats for the admin landing
# =============================================================


class AdminOverview(BaseModel):
    mrr_cents: int
    active_subscriptions: int
    users_total: int
    users_new_30d: int
    jobs_total: int
    jobs_running: int
    jobs_failed_30d: int
    clips_generated: int
    fallback_used_30d: int
    credits_outstanding: int


@router.get("/overview", response_model=AdminOverview)
async def overview(user: CurrentUser = Depends(admin_required)) -> AdminOverview:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select
              (select coalesce(sum(p.price_eur_cents), 0)::int
                 from subscriptions s
                 join plan_definitions p on p.code = s.plan_code
                where s.status in ('active', 'trialing')) as mrr_cents,
              (select count(*)::int
                 from subscriptions
                where status in ('active', 'trialing')) as active_subs,
              (select count(*)::int from profiles) as users_total,
              (select count(*)::int
                 from profiles
                where created_at >= now() - interval '30 days') as users_new_30d,
              (select count(*)::int from jobs) as jobs_total,
              (select count(*)::int
                 from jobs
                where status in (
                  'queued', 'downloading', 'transcribing', 'analyzing', 'rendering'
                )) as jobs_running,
              (select count(*)::int
                 from jobs
                where status = 'failed'
                  and queued_at >= now() - interval '30 days') as jobs_failed_30d,
              (select count(*)::int from clips) as clips_generated,
              (select count(*)::int
                 from jobs
                where fallback_used
                  and queued_at >= now() - interval '30 days') as fallback_used_30d,
              (select coalesce(sum(delta), 0)::int
                 from credit_ledger) as credits_outstanding
            """
        )
    return AdminOverview(
        mrr_cents=int(row["mrr_cents"]),
        active_subscriptions=int(row["active_subs"]),
        users_total=int(row["users_total"]),
        users_new_30d=int(row["users_new_30d"]),
        jobs_total=int(row["jobs_total"]),
        jobs_running=int(row["jobs_running"]),
        jobs_failed_30d=int(row["jobs_failed_30d"]),
        clips_generated=int(row["clips_generated"]),
        fallback_used_30d=int(row["fallback_used_30d"]),
        credits_outstanding=int(row["credits_outstanding"]),
    )


# =============================================================
# Users
# =============================================================


class AdminUserRow(BaseModel):
    user_id: str
    email: str
    full_name: str | None = None
    is_admin: bool
    plan_code: str | None = None
    sub_status: str | None = None
    credits_balance: int
    jobs_total: int
    created_at: datetime


@router.get("/users", response_model=list[AdminUserRow])
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(admin_required),
) -> list[AdminUserRow]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select
              p.user_id, p.email, p.full_name, p.is_admin, p.created_at,
              s.plan_code, s.status as sub_status,
              coalesce(
                (select sum(delta) from credit_ledger where user_id = p.user_id),
                0
              )::int as credits_balance,
              (select count(*) from jobs where user_id = p.user_id)::int as jobs_total
            from profiles p
            left join lateral (
              select plan_code, status from subscriptions
              where user_id = p.user_id and status in ('active','trialing','past_due')
              order by current_period_end desc nulls last
              limit 1
            ) s on true
            order by p.created_at desc
            limit $1 offset $2
            """,
            limit,
            offset,
        )
    return [
        AdminUserRow(
            user_id=str(r["user_id"]),
            email=r["email"],
            full_name=r["full_name"],
            is_admin=bool(r["is_admin"]),
            plan_code=r["plan_code"],
            sub_status=r["sub_status"],
            credits_balance=int(r["credits_balance"]),
            jobs_total=int(r["jobs_total"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


# =============================================================
# Jobs
# =============================================================


class AdminJobRow(BaseModel):
    job_id: str
    user_id: str
    user_email: str
    campaign_id: str | None = None
    source_url: str
    status: str
    current_step: str | None = None
    duration_seconds: int | None = None
    credits_charged: int | None = None
    total_cost_estimate_cents: int | None = None
    fallback_used: bool
    error_code: str | None = None
    queued_at: datetime


@router.get("/jobs", response_model=list[AdminJobRow])
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(admin_required),
) -> list[AdminJobRow]:
    pool = get_pool()
    async with pool.acquire() as conn:
        if status_filter:
            rows = await conn.fetch(
                """
                select j.id, j.user_id, p.email, j.campaign_id, j.source_url, j.status,
                       j.current_step, j.duration_seconds, j.credits_charged,
                       j.total_cost_estimate_cents, j.fallback_used,
                       j.error_code, j.queued_at
                from jobs j
                join profiles p on p.user_id = j.user_id
                where j.status = $1
                order by j.queued_at desc
                limit $2
                """,
                status_filter,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                select j.id, j.user_id, p.email, j.campaign_id, j.source_url, j.status,
                       j.current_step, j.duration_seconds, j.credits_charged,
                       j.total_cost_estimate_cents, j.fallback_used,
                       j.error_code, j.queued_at
                from jobs j
                join profiles p on p.user_id = j.user_id
                order by j.queued_at desc
                limit $1
                """,
                limit,
            )
    return [
        AdminJobRow(
            job_id=str(r["id"]),
            user_id=str(r["user_id"]),
            user_email=r["email"],
            campaign_id=str(r["campaign_id"]) if r["campaign_id"] else None,
            source_url=r["source_url"],
            status=r["status"],
            current_step=r["current_step"],
            duration_seconds=r["duration_seconds"],
            credits_charged=r["credits_charged"],
            total_cost_estimate_cents=r["total_cost_estimate_cents"],
            fallback_used=bool(r["fallback_used"]),
            error_code=r["error_code"],
            queued_at=r["queued_at"],
        )
        for r in rows
    ]


# =============================================================
# Finance — monthly cost breakdown
# =============================================================


class FinanceMonth(BaseModel):
    month: str  # YYYY-MM
    revenue_cents: int
    transcription_cost_cents: int
    video_map_cost_cents: int
    deep_vision_cost_cents: int
    text_analysis_cost_cents: int
    storage_bytes: int
    jobs_completed: int
    jobs_failed: int


@router.get("/finance", response_model=list[FinanceMonth])
async def finance(
    months: int = Query(default=6, ge=1, le=24),
    user: CurrentUser = Depends(admin_required),
) -> list[FinanceMonth]:
    pool = get_pool()
    cutoff = (datetime.now(UTC) - timedelta(days=months * 31)).replace(day=1)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            with months as (
              select date_trunc(
                'month',
                generate_series(
                  date_trunc('month', $1::timestamptz),
                  date_trunc('month', now()),
                  interval '1 month'
                )
              ) as m
            ),
            costs as (
              select date_trunc('month', queued_at) as m,
                     sum(coalesce(transcription_cost_cents, 0))::bigint as transcription,
                     sum(coalesce(video_map_cost_cents, 0))::bigint as video_map,
                     sum(coalesce(deep_vision_cost_cents, 0))::bigint as deep_vision,
                     sum(coalesce(total_cost_estimate_cents, 0)
                         - coalesce(transcription_cost_cents, 0)
                         - coalesce(video_map_cost_cents, 0)
                         - coalesce(deep_vision_cost_cents, 0))::bigint as text_analysis,
                     sum(coalesce(storage_bytes, 0))::bigint as storage_bytes,
                     count(*) filter (where status = 'completed')::int as completed,
                     count(*) filter (where status = 'failed')::int as failed
                from jobs
                where queued_at >= $1
                group by 1
            ),
            revenue as (
              -- Approximate MRR per month: active subs on the 1st x plan price.
              select date_trunc('month', s.current_period_start) as m,
                     sum(p.price_eur_cents)::bigint as revenue_cents
                from subscriptions s
                join plan_definitions p on p.code = s.plan_code
                where s.status in ('active','trialing','past_due')
                  and s.current_period_start >= $1
                group by 1
            )
            select to_char(months.m, 'YYYY-MM') as month,
                   coalesce(revenue.revenue_cents, 0)::bigint as revenue_cents,
                   coalesce(costs.transcription, 0)::bigint as transcription_cost_cents,
                   coalesce(costs.video_map, 0)::bigint as video_map_cost_cents,
                   coalesce(costs.deep_vision, 0)::bigint as deep_vision_cost_cents,
                   coalesce(costs.text_analysis, 0)::bigint as text_analysis_cost_cents,
                   coalesce(costs.storage_bytes, 0)::bigint as storage_bytes,
                   coalesce(costs.completed, 0)::int as jobs_completed,
                   coalesce(costs.failed, 0)::int as jobs_failed
              from months
              left join costs on costs.m = months.m
              left join revenue on revenue.m = months.m
             order by months.m asc
            """,
            cutoff,
        )
    return [
        FinanceMonth(
            month=r["month"],
            revenue_cents=int(r["revenue_cents"]),
            transcription_cost_cents=int(r["transcription_cost_cents"]),
            video_map_cost_cents=int(r["video_map_cost_cents"]),
            deep_vision_cost_cents=int(r["deep_vision_cost_cents"]),
            text_analysis_cost_cents=int(r["text_analysis_cost_cents"]),
            storage_bytes=int(r["storage_bytes"]),
            jobs_completed=int(r["jobs_completed"]),
            jobs_failed=int(r["jobs_failed"]),
        )
        for r in rows
    ]
