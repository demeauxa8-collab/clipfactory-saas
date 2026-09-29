# API contract — ClipFactory V1

Backend : FastAPI, base URL `http://localhost:8000` (dev) → `https://api.clipfactory.app` (prod).

Auth : `Authorization: Bearer <supabase-jwt>` sauf `/health` et `/stripe/webhook`.

Toutes les réponses sont JSON. Erreurs métier renvoient `{ "detail": { "code": "...", "message": "..." } }` avec HTTP 4xx.

---

## Endpoints

### Public (no auth)

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/health` | — | `{ "status": "ok" }` |
| GET | `/public/stats` | — | `{ clips_generated, hours_processed, creators_active }` |
| POST | `/auth/turnstile/verify` | `{ "token": str }` | `{ "ok": true }` |
| POST | `/stripe/webhook` | Stripe event raw | `{ "received": true }` |

### Authenticated (Bearer Supabase JWT)

| Method | Path | Body | Returns | Rate limit |
| --- | --- | --- | --- | --- |
| GET | `/me` | — | `MeResponse` (profile + sub + credits) | — |
| GET | `/credits` | — | `{ "balance": int }` | — |
| GET | `/campaigns` | — | `Campaign[]` | — |
| POST | `/campaigns` | `CampaignCreate` | `Campaign` | 30/hour |
| GET | `/jobs` | — | `Job[]` (50 last) | — |
| POST | `/jobs` | `JobCreate` (incl. `campaign_id`) | `Job` | 10/min |
| GET | `/jobs/{id}` | — | `JobWithClips` | — |
| POST | `/series` | `SeriesCreate` | `SeriesOut` (ordered jobs) | 10/min |
| GET | `/series/{id}` | — | `SeriesOut` (ordered jobs) | — |
| POST | `/clips/{id}/feedback` | `FeedbackCreate` | `Feedback` | 60/min |
| GET | `/clips/{id}/download` | — | `{ url, expires_in_seconds }` (presigned R2 URL, TTL 10 min) | — |
| POST | `/billing/checkout` | `{ "plan_code": "starter" or "pro" }` | `{ "checkout_url": str }` | 5/hour |
| POST | `/billing/portal` | — | `{ "portal_url": str }` | 5/hour |

### Admin (Bearer + profiles.is_admin = true)

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/admin/overview` | — | `AdminOverview` (MRR, users, jobs, fallback usage…) |
| GET | `/admin/users?limit=&offset=` | — | `AdminUserRow[]` (email, plan, credits, jobs total, is_admin) |
| GET | `/admin/jobs?status=&limit=` | — | `AdminJobRow[]` (job + user email + cost + fallback flag) |
| GET | `/admin/finance?months=6` | — | `FinanceMonth[]` (revenue / cost split / margin per month) |

Non-admin users hitting `/admin/*` get HTTP 403 `{ detail: "admin_required" }`.

---

## Payload shapes

### CampaignCreate

```json
{
  "name": "string (max 80)",
  "audience": "string (max 200)",
  "niche": "string (max 80)",
  "tone": "string (max 80)",
  "goal": "string (max 200)",
  "avoid_topics": ["string", "..."],
  "example_hooks": ["string", "..."]
}
```

### Campaign

```json
{
  "id": "uuid",
  "name": "string",
  "audience": "string",
  "niche": "string",
  "tone": "string",
  "goal": "string",
  "avoid_topics": ["string"],
  "example_hooks": ["string"],
  "created_at": "iso8601"
}
```

### JobCreate

```json
{
  "campaign_id": "uuid",
  "source_url": "https://...",
  "target_clip_count": 3
}
```

### SeriesCreate

```json
{
  "campaign_id": "uuid",
  "source_urls": ["https://www.youtube.com/watch?v=...", "https://youtu.be/..."],
  "target_clip_count": 3
}
```

The request accepts 2–5 distinct YouTube URLs. `target_clip_count` applies to
each video, within the plan's per-video limit. The active plan's
`max_series_sources` must allow the requested source count; Starter has no
multi-video access. `SeriesOut.jobs` keeps the source
order and exposes each job's `series_id` and `series_position`. Sources run one
after another; a failed video does not block later videos. Credits are charged
separately from each detected source duration. The clip's `job_id` identifies its
source. A series does not combine footage from different videos into one clip.

Pro costs 79 EUR/month, grants 1,000 credits per billing period and allows up
to five sources per series. Starter costs 29 EUR/month, grants 300 credits and
allows single-source jobs only. Pro checkout is unavailable while its dedicated
Stripe price is missing or the plan is inactive. Existing subscribers manage
their subscription through `/billing/portal`.

### TurnstileVerifyRequest

```json
{
  "token": "cf-turnstile-response-token"
}
```

Notes :
- Used by `/login` before Supabase magic-link or Google OAuth.
- The endpoint validates the token against Cloudflare Turnstile with `TURNSTILE_SECRET_KEY`.
- If `NEXT_PUBLIC_TURNSTILE_SITE_KEY` is missing client-side, local dev skips Turnstile.

### Job

See `apps/api/app/schemas.py::JobOut` — adds `campaign_id`, `current_step`, cost columns once T12 migration ships.

### ClipSegment

```json
{
  "role": "setup" | "transition" | "payoff" | "single",
  "start": 118.4,
  "end": 135.0,
  "transcript_excerpt": "string"
}
```

`role = "single"` correspond au cas dégénéré single-window (pipeline simple ou clip story-arc à un seul segment).

### Clip

```json
{
  "id": "uuid",
  "job_id": "uuid",
  "idx": 0,
  "title": "string|null",
  "hook_text": "string|null",
  "rationale": "string|null",
  "visual_summary": "string|null",
  "transcript_excerpt": "string|null",
  "start_seconds": 12.34,
  "end_seconds": 42.5,
  "duration_seconds": 30.16,
  "rendered_duration_seconds": 30.05,
  "segments": [
    {
      "role": "setup",
      "start": 118.4,
      "end": 135.0,
      "transcript_excerpt": "il vient d'acheter cette Lamborghini"
    },
    {
      "role": "payoff",
      "start": 752.0,
      "end": 779.0,
      "transcript_excerpt": "et il a tout détruit en sortant du parking"
    }
  ],
  "score_total": 87,
  "score_breakdown": {
    "payoff_strength": 88,
    "setup_clarity": 82,
    "visual_proof": 90,
    "retention": 84,
    "campaign_fit": 80,
    "editing_continuity": 70
  },
  "width": 1080,
  "height": 1920
}
```

Notes :
- `segments` est la source de vérité. `start_seconds` = `segments[0].start`, `end_seconds` = `segments[-1].end`. Ces deux champs sont conservés pour compat client mais ne décrivent plus une fenêtre continue dans la source.
- `rendered_duration_seconds` est la durée du fichier rendu (peut être légèrement < somme des durées des segments à cause du crossfade audio 150 ms).
- `score_breakdown` a deux schémas possibles selon le chemin emprunté par le worker :
  - **Story arc** : `{ payoff_strength, setup_clarity, visual_proof, retention, campaign_fit, editing_continuity }`
  - **Simple single-window** : `{ hook, emotion, visual, campaign_fit, editing_difficulty }`
  Le client doit afficher les clés présentes, pas en deviner.

### FeedbackCreate

```json
{
  "kind": "good" | "bad",
  "note": "string (optional, max 500)"
}
```

### Feedback

```json
{
  "id": "uuid",
  "clip_id": "uuid",
  "kind": "good" | "bad",
  "note": "string|null",
  "created_at": "iso8601"
}
```

---

## Stripe webhook events handled

| Event | Effect |
| --- | --- |
| `checkout.session.completed` | Create / upsert subscription, grant the purchased plan's credits via `credit_ledger` (reason: `subscription_grant`). |
| `invoice.paid` | If `billing_reason = subscription_cycle`, grant the purchased plan's credits (reason: `subscription_renewal`). |
| `customer.subscription.updated` | Update local plan, status and period end from the billed Stripe price. |
| `customer.subscription.deleted` | Mark subscription `canceled`. Credits already granted are not revoked. |

Idempotency: every event and its business changes are committed in one database
transaction. Processing failure rolls both back and returns HTTP 503 for a
Stripe retry. Replay of a committed event is a no-op.

Signature replay window: `apps/api/app/services/billing.py::construct_event()` uses `stripe.Webhook.construct_event(...)` without overriding the SDK tolerance, so Stripe's default 5-minute timestamp tolerance applies. This is acceptable for V1 because webhook payloads are only accepted over HTTPS and duplicate events are rejected by the `stripe_events.event_id` primary key before business logic runs.

---

## Error codes (stable)

| Code | HTTP | Reason |
| --- | ---: | --- |
| `missing_authorization` | 401 | no Authorization header |
| `invalid_token` | 401 | JWT invalid |
| `token_expired` | 401 | JWT expired |
| `turnstile_not_configured` | 503 | Turnstile secret missing on API |
| `turnstile_unavailable` | 502 | Cloudflare verification endpoint unavailable |
| `turnstile_failed` | 403 | Turnstile token invalid |
| `no_active_subscription` | 422 | user has no active sub when creating a job |
| `insufficient_credits` | 422 | balance <= 0 |
| `clip_count_exceeded` | 422 | target_clip_count > plan max |
| `concurrent_jobs_exceeded` | 422 | user has too many running jobs |
| `campaign_not_found` | 404 | invalid campaign_id on POST /jobs |
| `job_not_found` | 404 | |
| `clip_not_found` | 404 | |
| `invalid_url` | 422 | source_url scheme/host not allowed |
| `admin_required` | 403 | endpoint /admin/* without profiles.is_admin = true |
| `rate_limit_exceeded` | 429 | per-user or per-IP slowapi limit hit |

---

## Pagination

V1 = aucune pagination explicite. `GET /jobs` retourne les 50 derniers par défaut. `GET /campaigns` retourne tout. `GET /admin/users` accepte `limit` (default 50, max 200) et `offset`. `GET /admin/jobs` accepte `limit` (default 100, max 500) et `status` filter.

---

## Admin payload shapes

### AdminOverview

```json
{
  "mrr_cents": 8700,
  "active_subscriptions": 3,
  "users_total": 12,
  "users_new_30d": 5,
  "jobs_total": 142,
  "jobs_running": 1,
  "jobs_failed_30d": 4,
  "clips_generated": 312,
  "fallback_used_30d": 7,
  "credits_outstanding": 1450
}
```

### AdminUserRow

```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "full_name": "string|null",
  "is_admin": false,
  "plan_code": "starter|null",
  "sub_status": "active|trialing|past_due|canceled|null",
  "credits_balance": 287,
  "jobs_total": 14,
  "created_at": "iso8601"
}
```

### AdminJobRow

```json
{
  "job_id": "uuid",
  "user_id": "uuid",
  "user_email": "...",
  "campaign_id": "uuid|null",
  "source_url": "https://...",
  "status": "queued|...|completed|failed",
  "current_step": "video_map|story_arcs|deep_vision|render|...",
  "duration_seconds": 1230,
  "credits_charged": 21,
  "total_cost_estimate_cents": 18,
  "fallback_used": false,
  "error_code": "string|null",
  "queued_at": "iso8601"
}
```

### FinanceMonth

```json
{
  "month": "2026-05",
  "revenue_cents": 8700,
  "transcription_cost_cents": 63,
  "video_map_cost_cents": 31,
  "deep_vision_cost_cents": 92,
  "text_analysis_cost_cents": 18,
  "storage_bytes": 4823910000,
  "jobs_completed": 21,
  "jobs_failed": 1
}
```

### PublicStats

```json
{
  "clips_generated": 312,
  "hours_processed": 87,
  "creators_active": 4
}
```
