from __future__ import annotations

import asyncpg

from ..schemas import Campaign, CampaignCreate


async def list_campaigns(conn: asyncpg.Connection, user_id: str) -> list[Campaign]:
    rows = await conn.fetch(
        """
        select id, name, audience, niche, tone, goal,
               avoid_topics, example_hooks, created_at
          from campaigns
         where user_id = $1
         order by created_at desc
        """,
        user_id,
    )
    return [
        Campaign(
            id=str(r["id"]),
            name=r["name"],
            audience=r["audience"],
            niche=r["niche"],
            tone=r["tone"],
            goal=r["goal"],
            avoid_topics=list(r["avoid_topics"] or []),
            example_hooks=list(r["example_hooks"] or []),
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def create_campaign(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    payload: CampaignCreate,
) -> Campaign:
    row = await conn.fetchrow(
        """
        insert into campaigns
          (user_id, name, audience, niche, tone, goal, avoid_topics, example_hooks)
        values ($1, $2, $3, $4, $5, $6, $7, $8)
        returning id, name, audience, niche, tone, goal,
                  avoid_topics, example_hooks, created_at
        """,
        user_id,
        payload.name,
        payload.audience,
        payload.niche,
        payload.tone,
        payload.goal,
        payload.avoid_topics,
        payload.example_hooks,
    )
    return Campaign(
        id=str(row["id"]),
        name=row["name"],
        audience=row["audience"],
        niche=row["niche"],
        tone=row["tone"],
        goal=row["goal"],
        avoid_topics=list(row["avoid_topics"] or []),
        example_hooks=list(row["example_hooks"] or []),
        created_at=row["created_at"],
    )


async def get_campaign(
    conn: asyncpg.Connection, *, user_id: str, campaign_id: str
) -> Campaign | None:
    row = await conn.fetchrow(
        """
        select id, name, audience, niche, tone, goal,
               avoid_topics, example_hooks, created_at
          from campaigns
         where id = $1 and user_id = $2
        """,
        campaign_id,
        user_id,
    )
    if row is None:
        return None
    return Campaign(
        id=str(row["id"]),
        name=row["name"],
        audience=row["audience"],
        niche=row["niche"],
        tone=row["tone"],
        goal=row["goal"],
        avoid_topics=list(row["avoid_topics"] or []),
        example_hooks=list(row["example_hooks"] or []),
        created_at=row["created_at"],
    )
