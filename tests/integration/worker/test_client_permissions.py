from uuid import uuid4

import asyncpg
import pytest

pytestmark = pytest.mark.asyncio


async def test_client_can_edit_own_name_but_cannot_become_admin(db_pool, account):
    async with db_pool.acquire() as conn, conn.transaction():
        await conn.execute("set local role authenticated")
        await conn.fetchval(
            "select set_config('request.jwt.claim.sub', $1, true)", str(account[0])
        )
        assert (
            await conn.fetchval(
                "update profiles set full_name = 'Alice' returning full_name"
            )
            == "Alice"
        )
        for column, value in [
            ("is_admin", "true"),
            ("email", "'other@example.com'"),
            ("stripe_customer_id", "'customer_fake'"),
        ]:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(f"update profiles set {column} = {value}")


async def test_client_cannot_insert_job_bypassing_api(db_pool, account):
    async with db_pool.acquire() as conn:  # noqa: SIM117 -- transaction needs conn
        async with conn.transaction():
            await conn.execute("set local role authenticated")
            await conn.fetchval(
                "select set_config('request.jwt.claim.sub', $1, true)", str(account[0])
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(
                        """insert into jobs (user_id, source_url, target_clip_count,
                        credits_estimated) values ($1, 'https://youtu.be/bypass', 10, 0)""",
                        account[0],
                    )


async def test_balance_view_honors_caller_and_other_profile_is_hidden(db_pool, account):
    other = uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "insert into auth.users values ($1, 'other@example.com')", other
        )
        await conn.execute(
            """insert into credit_ledger (user_id, delta, reason)
                              values ($1, 999, 'subscription_grant')""",
            other,
        )
        async with conn.transaction():
            await conn.execute("set local role authenticated")
            await conn.fetchval(
                "select set_config('request.jwt.claim.sub', $1, true)", str(account[0])
            )
            rows = await conn.fetch("select * from credit_balances")
            assert [(r["user_id"], r["balance"]) for r in rows] == [(account[0], 10)]
            assert (
                await conn.fetchval(
                    "select count(*) from profiles where user_id = $1", other
                )
                == 0
            )
            assert (
                await conn.execute(
                    "update profiles set full_name = 'Hijacked' where user_id = $1",
                    other,
                )
                == "UPDATE 0"
            )
        async with conn.transaction():
            await conn.execute("set local role anon")
            assert await conn.fetchval("select count(*) from credit_balances") == 0
