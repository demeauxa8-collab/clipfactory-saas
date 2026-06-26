"""Parallel worker fleet — the running worker's job engine.

`apps/worker/app/main.py` runs `Supervisor.run()`. The queue lives in Postgres
(jobs table); workers claim atomically with FOR UPDATE SKIP LOCKED + a fleet-wide
advisory lock. Requires migration 0005 (claimed_at / heartbeat_at / attempts).
See docs/architecture/parallel-workers.md.

Modules:
  claim.py       — atomic Postgres job claim (FOR UPDATE SKIP LOCKED) + heartbeat
  supervisor.py  — asyncio task-pool: claim loop, N slots, render semaphore
  reaper.py      — periodic stale-job sweep → requeue / fail + refund
"""
