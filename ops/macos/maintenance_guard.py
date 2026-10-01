"""Refuse routine maintenance while a pipeline attempt is active."""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps/api"))
os.chdir(REPO / "apps/api")

from app.settings import get_settings


async def main() -> int:
    try:
        conn = await asyncpg.connect(
            get_settings().database_url, statement_cache_size=0, timeout=10,
        )
        try:
            count = await conn.fetchval(
                "select count(*) from jobs "
                "where status in ('downloading', 'transcribing', 'analyzing', 'rendering')"
            )
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001 - hide credentials and fail closed
        print(f"Maintenance refused: database check failed ({type(exc).__name__}).")
        return 1
    if count:
        print(f"Maintenance refused: {count} active job(s). Wait for completion.")
        return 1
    print("Maintenance allowed: no active pipeline attempt.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
