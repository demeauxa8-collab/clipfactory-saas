# Admin dashboard

> Operator dashboard for ClipFactory. Hidden behind `profiles.is_admin = true`.

## Who has access

- The trigger `public.handle_new_user` (see migration 0004) auto-grants `is_admin = true` to the founder email `demeauxa8@gmail.com` at first signup.
- To promote another user manually, run:
  ```sql
  update public.profiles set is_admin = true where email = 'someone@example.com';
  ```
- 2FA on Supabase is **required** before opening the dashboard to additional admins (see security audit L6).

## Routes (Next.js)

| Route | What it shows |
| --- | --- |
| `/admin` | Overview cards: MRR, active subs, users total/new30d, jobs running/failed30d, clips lifetime, fallback usage, credits outstanding. |
| `/admin/users` | All users with plan, sub status, credit balance, job count, join date, admin flag. Paginated `?limit=&offset=`. |
| `/admin/jobs` | All jobs with filter `?status=`. Shows user email, source URL, status badge, current step, duration, credits charged, cost €, fallback flag, error code. |
| `/admin/finance` | Monthly P&L: revenue minus broken-down costs (transcription, video map, deep vision, text LLM), gross margin, storage usage, completed/failed counts. |

## Gating layers

The dashboard is locked by **two** independent checks:

1. **Middleware** (`apps/web/middleware.ts`) — redirects unauthenticated requests on `/admin/*` to `/login?next=...`.
2. **Layout server check** (`apps/web/app/admin/layout.tsx`) — server-side Supabase query on `profiles.is_admin`; non-admin users get redirected to `/app`.
3. **API dep** (`apps/api/app/auth.py::admin_required`) — every `/admin/*` endpoint also verifies `is_admin` on each request. A non-admin user who bypasses the UI still gets `403 admin_required`.

## Backend endpoints

See `docs/api-contract.md` section "Admin". Implemented in `apps/api/app/routers/admin.py`. All responses are aggregated; **no row-level mutation** in V1 (admin actions like manual refund / ban are V2).

## Data sources

- **Overview / users / jobs**: read directly from `profiles`, `subscriptions`, `jobs`, `credit_ledger`, `clips`.
- **Finance**: combines `jobs.{transcription_cost_cents, video_map_cost_cents, deep_vision_cost_cents, total_cost_estimate_cents}` with `subscriptions.current_period_start × plan_definitions.price_eur_cents`. Numbers are estimates — wire to real provider invoices in V2.

## Limits and known gaps (V1 → V2)

- No edit / write actions yet. To refund credits, `insert into credit_ledger (..., reason = 'manual_adjustment')` via SQL editor.
- No banning. To suspend a user, drop their active subscription manually + revoke remaining credits via ledger entry.
- No real-time refresh. Pages are server-rendered; refresh to see new data. (V2: SWR + `?live=1`.)
- No drill-down on individual job (`/admin/jobs/:id`) yet — for now click into the user's regular `/app/jobs/:id` view as the same user (requires impersonation, V2).
- No audit log of admin actions. To add before scaling the admin team.
