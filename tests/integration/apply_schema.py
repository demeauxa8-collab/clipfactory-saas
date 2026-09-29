"""Apply the repository schema to a disposable local PostgreSQL database.

Used by the per-test fixture in ``conftest.py`` and, as a script, to prepare the
shared ``clipfactory_test`` database that ``apps/api/tests/test_series_postgres.py``
expects. Supabase roles and ``auth.uid()`` are simulated. Refuses any non-local DSN.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

ROOT = Path(__file__).resolve().parents[2]


async def apply_schema(conn: asyncpg.Connection) -> None:
    for role in ("anon", "authenticated", "service_role"):
        if not await conn.fetchval("select 1 from pg_roles where rolname = $1", role):
            await conn.execute(f'create role "{role}"')
    await conn.execute("""
        create schema auth;
        create table auth.users (id uuid primary key, email text);
        create function auth.uid() returns uuid language sql stable as
          $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
        grant usage on schema public, auth to anon, authenticated, service_role;
        alter default privileges in schema public grant all on tables
          to anon, authenticated, service_role;
        alter default privileges in schema public grant all on sequences
          to anon, authenticated, service_role;
    """)
    for migration in sorted((ROOT / "db" / "migrations").glob("*.sql")):
        sql = migration.read_text()
        if os.environ.get("CLIPFACTORY_TEST_BUILTIN_UUID") == "1":
            # Optional runtime without contrib extensions. This affects baseline
            # UUID generation only; CI runs full PostgreSQL and every file verbatim.
            sql = sql.replace(
                'create extension if not exists "uuid-ossp";',
                "create function uuid_generate_v4() returns uuid "
                "language sql volatile as $$ select gen_random_uuid() $$;",
            )
            sql = sql.replace('create extension if not exists "pgcrypto";', "")
        await conn.execute(sql)


async def _main() -> None:
    dsn = os.environ["CLIPFACTORY_TEST_DATABASE_URL"]
    parsed = urlparse(dsn)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path != "/clipfactory_test":
        sys.exit("Refusing: only a local clipfactory_test database may be migrated")
    conn = await asyncpg.connect(dsn)
    try:
        if await conn.fetchval("select to_regclass('public.jobs') is not null"):
            print("schema already applied")
            return
        await apply_schema(conn)
        print("schema applied")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
