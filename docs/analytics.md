# Analytics & tracking

ClipFactory captures product + behaviour data first-party (in our own Supabase) and
optionally mirrors it to PostHog. First-party always works with zero external setup;
PostHog turns on the moment a key is present.

## Architecture

```
Web (Next.js)  ─┬─ pageviews + clicks ─────────► PostHog (autocapture, optional)
                └─ track() ──► POST /events ──┐
API (FastAPI)  ── middleware + domain events ─┼─► analytics_events (Supabase)  ← source of truth
Worker         ── pipeline stage events ──────┘        │
                                                       └─► PostHog mirror (optional, server-side)
```

- **First-party sink**: table `public.analytics_events` (migration `0005`). One row per
  event, `source in ('web','api','worker')`, free-form `properties jsonb`.
- **PostHog mirror**: enabled per surface by a key. Empty key = no-op.
  - Web: `NEXT_PUBLIC_POSTHOG_KEY` / `NEXT_PUBLIC_POSTHOG_HOST`
  - API: `POSTHOG_API_KEY` / `POSTHOG_HOST`
  - Worker: `POSTHOG_API_KEY` / `POSTHOG_HOST`

## Guarantees

- Analytics **never breaks a request or a job** — every path swallows its own errors.
- Analytics **never adds latency** — events are scheduled fire-and-forget on their own
  DB connection, never inside a domain transaction.
- **No raw PII** in `analytics_events`: we store `user_id` (FK) but never email/name.

## Event taxonomy

| Event | Source | Key properties |
| --- | --- | --- |
| `pageview` | web | `path` |
| `login_attempt` | web | `method` (`magic_link` \| `google`) |
| `upgrade_clicked` | web | `has_active` |
| `job_submit_clicked` | web | `campaign_id`, `target_clip_count` |
| `clip_download_clicked` | web | `clip_id` |
| `clip_feedback_clicked` | web | `clip_id`, `kind` |
| `api_request` | api | `method`, `route` (template), `status` — **auto on every call** |
| `job_created` | api | `job_id`, `campaign_id`, `target_clip_count`, `source_host` |
| `campaign_created` | api | `campaign_id`, `niche`, `tone` |
| `checkout_started` | api | `plan_code` |
| `billing_webhook` | api | `type` (Stripe event type) |
| `clip_download` | api | `clip_id` |
| `clip_feedback` | api | `clip_id`, `kind` |
| `job_started` | worker | `job_id`, `target_clip_count`, `primary_provider` |
| `job_completed` | worker | `clips`, `mode`, `duration_seconds`, `cost_cents`, `credits_charged`, `fallback_used` |
| `job_failed` | worker | `code`, `step` |

Plus PostHog **autocapture** (every click / input / pageview) when the web key is set —
that is the "track everything" layer with no manual instrumentation.

## Reading the data

- SQL: query `public.analytics_events` or the `public.analytics_daily` rollup view.
- API: `GET /admin/analytics?days=14` (admin-only) returns event volume + unique users.
- PostHog: funnels, retention, session replay (when the key is configured).

## Activation checklist

1. Apply migration `db/migrations/0005_analytics_events.sql` to Supabase.
2. (Optional) Create a PostHog project (EU) and set the three keys above.
3. Deploy. First-party events flow immediately; PostHog the moment the key lands.
