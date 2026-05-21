# DB Schema — ClipFactory SaaS V1

Target: Supabase Postgres 15+.
Migration: `db/migrations/0001_init.sql`.

## Overview

```
auth.users  (Supabase managed)
   │ 1
   ▼ 1
profiles ────────► subscriptions ──► plan_definitions
   │ 1
   ├──► jobs ──► clips
   └──► credit_ledger  (append-only)

stripe_events  (idempotency, no FK)
```

## Tables

| Table | Purpose | Owner |
| --- | --- | --- |
| `plan_definitions` | Pricing plans + per-plan limits | seeded once, edited rarely |
| `profiles` | App-level user data linked to `auth.users` | auto-created by trigger |
| `subscriptions` | Stripe subscription mirror | written by webhook handler |
| `credit_ledger` | Append-only credit movements | written by webhook + worker |
| `jobs` | Clipping job lifecycle | written by API + worker |
| `clips` | Rendered output clips | written by worker |
| `stripe_events` | Webhook idempotency | written by webhook handler |

## Key invariants

- **Append-only ledger.** `credit_ledger` never deletes/updates. The balance is `sum(delta)`. View `credit_balances` exposes it. Migrate to a materialized view + incremental refresh if `select balance from credit_balances` ever exceeds 50ms.
- **Idempotent billing.** Every Stripe event is recorded in `stripe_events` BEFORE processing. If the same `event_id` arrives twice, we skip.
- **Job status is a strict ENUM.** Worker transitions must follow `queued -> downloading -> transcribing -> analyzing -> rendering -> completed | failed | canceled`. No skipping.
- **One profile per auth.users.** Created automatically via `on_auth_user_created` trigger.
- **Source URL is required.** V1 does not support uploads. `source_kind` defaults to `'youtube'` for future-proofing.
- **`credits_estimated` is charged at dequeue,** `credits_charged` is the final after run. Refund = positive ledger entry with `reason = 'job_refund'`.

## Credit math

A user has credits if `credit_balances.balance > 0` for that `user_id`. Estimating credits for a job:

```
estimated = max(1, ceil(duration_minutes))
```

Charged after run:

```
charged = estimated  # V1: no overrun beyond max_video_minutes (enforced at submit)
```

If a job fails before render starts: full refund via `'job_refund'` entry.

## RLS posture

The Next.js client uses the Supabase anon key with the user's JWT. Direct table reads are allowed for owned rows:

- read own `profiles`, `subscriptions`, `credit_ledger`, `jobs`, `clips`
- insert own `jobs` (only with `status = 'queued'`)

Everything else (updates to `subscriptions`, `credit_ledger` inserts, `clips` inserts, `stripe_events`) goes through the FastAPI backend using the service_role key, which bypasses RLS.

## Migration policy

- Migrations are numbered `0001_*.sql`, `0002_*.sql`, etc.
- Never edit a migration once committed. Add a new one.
- Each migration must be idempotent enough to be reapplied on a fresh DB.
- Apply via Supabase SQL editor (V1) or `supabase migration up` (V2 when we automate).

## Open questions

- **Job cancellation by user :** V1 ship without it (we don't refund running jobs). Add a `POST /jobs/:id/cancel` later if needed.
- **Soft delete vs hard delete :** V1 hard delete on cascade. RGPD compliance to revisit before public launch.
- **Audit log :** out of scope V1.
