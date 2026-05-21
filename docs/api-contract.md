# API contract — ClipFactory V1

Backend : FastAPI, base URL `http://localhost:8000` (dev) → `https://api.clipfactory.app` (prod).

Auth : `Authorization: Bearer <supabase-jwt>` sauf `/health` et `/stripe/webhook`.

Toutes les réponses sont JSON. Erreurs métier renvoient `{ "detail": { "code": "...", "message": "..." } }` avec HTTP 4xx.

---

## Endpoints

### Public

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/health` | — | `{ "status": "ok" }` |
| POST | `/stripe/webhook` | Stripe event raw | `{ "received": true }` |

### Authenticated

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/me` | — | `MeResponse` (profile + sub + credits) |
| GET | `/credits` | — | `{ "balance": int }` |
| GET | `/campaigns` | — | `Campaign[]` |
| POST | `/campaigns` | `CampaignCreate` | `Campaign` |
| GET | `/jobs` | — | `Job[]` |
| POST | `/jobs` | `JobCreate` (must include `campaign_id`) | `Job` |
| GET | `/jobs/{id}` | — | `JobWithClips` |
| GET | `/jobs/{id}/clips` | — | `Clip[]` |
| POST | `/clips/{id}/feedback` | `FeedbackCreate` | `Feedback` |
| POST | `/billing/checkout` | `{ "plan_code": "starter" }` | `{ "checkout_url": str }` |

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

### Job

See `apps/api/app/schemas.py::JobOut` — adds `campaign_id`, `current_step`, cost columns once T12 migration ships.

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
  "score_total": 87,
  "score_breakdown": {
    "hook": 92,
    "emotion": 80,
    "visual": 88,
    "campaign_fit": 90,
    "editing_difficulty": 75
  },
  "width": 1080,
  "height": 1920
}
```

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
| `checkout.session.completed` | Create / upsert subscription, grant 300 credits via `credit_ledger` (reason: `subscription_grant`). |
| `invoice.paid` | If `billing_reason = subscription_cycle`, grant 300 credits (reason: `subscription_renewal`). |
| `customer.subscription.updated` | Update local subscription status, period end. |
| `customer.subscription.deleted` | Mark subscription `canceled`. Credits already granted are not revoked. |

Idempotency: every event is recorded in `stripe_events(event_id PK)` before processing. Replay = no-op.

---

## Error codes (stable)

| Code | HTTP | Reason |
| --- | ---: | --- |
| `missing_authorization` | 401 | no Authorization header |
| `invalid_token` | 401 | JWT invalid |
| `token_expired` | 401 | JWT expired |
| `no_active_subscription` | 422 | user has no active sub when creating a job |
| `insufficient_credits` | 422 | balance <= 0 |
| `clip_count_exceeded` | 422 | target_clip_count > plan max |
| `concurrent_jobs_exceeded` | 422 | user has too many running jobs |
| `campaign_not_found` | 404 | invalid campaign_id on POST /jobs |
| `job_not_found` | 404 | |
| `clip_not_found` | 404 | |
| `invalid_url` | 422 | source_url scheme/host not allowed |

---

## Pagination

V1 = aucune pagination explicite. `GET /jobs` retourne les 50 derniers par défaut. `GET /campaigns` retourne tout.
