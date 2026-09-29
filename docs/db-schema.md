# DB Schema — ClipFactory SaaS V1

Target: Supabase Postgres 15+.
Migrations (à appliquer dans l'ordre) :
- `db/migrations/0001_init.sql` — base (profiles, subscriptions, credit_ledger, jobs, clips, stripe_events)
- `db/migrations/0002_campaigns_costs_vision.sql` — campagnes, feedback, colonnes coûts / vision
- `db/migrations/0003_story_arcs.sql` — story-first pipeline (video_map, segments multi-fenêtres, fallback tracking)
- `db/migrations/0004_admin_flag.sql` — flag admin + public stats
- `db/migrations/0005_analytics_events.sql` — `analytics_events` + vue `analytics_daily` (appliquée le 2026-06-23)
- `db/migrations/0006_clip_series.sql` — limite de sources par forfait, séries multi-vidéos et ordre de traitement. Appliquée au projet Supabase `jsjaizcnjvghoduvyyea` le 2026-09-25 (`20260925153547 clip_series_pro_plan`). Le `0005_job_leasing.sql` d'une ancienne branche devra porter un numéro ultérieur s'il est repris.

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
| `clip_series` | Group of 2–5 ordered source jobs for one campaign | written by API |
| `clips` | Rendered output clips | written by worker |
| `stripe_events` | Webhook idempotency | written by webhook handler |

## Key invariants

- **Append-only ledger.** `credit_ledger` never deletes/updates. The balance is `sum(delta)`. View `credit_balances` exposes it. Migrate to a materialized view + incremental refresh if `select balance from credit_balances` ever exceeds 50ms.
- **Idempotent billing.** Every Stripe event is recorded in `stripe_events` BEFORE processing. If the same `event_id` arrives twice, we skip.
- **Job status is a strict ENUM.** Worker transitions must follow `queued -> downloading -> transcribing -> analyzing -> rendering -> completed | failed | canceled`. No skipping.
- **One profile per auth.users.** Created automatically via `on_auth_user_created` trigger.
- **Source URL is required.** V1 does not support uploads. `source_kind` defaults to `'youtube'` for future-proofing.
- **`credits_estimated` is charged at dequeue,** `credits_charged` is the final after run. Refund = positive ledger entry with `reason = 'job_refund'`.
- **Un clip = liste ordonnée de segments** (depuis migration 0003). `clips.segments jsonb` est la source de vérité. `length == 1` = single-window (cas dégénéré, soit pipeline simple soit story-arc à un seul segment). `length > 1` = montage multi-segments. Les champs `start_seconds` / `end_seconds` sont conservés pour compat client mais valent désormais `segments[0].start` / `segments[-1].end` et ne décrivent plus une fenêtre continue dans la source.

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
- insert own standalone `jobs` (only with `status = 'queued'` and `series_id is null`)

Series rows are readable by their owner. Only the API inserts series rows and
their jobs. The worker claims one queued series job when all earlier jobs are
terminal; each clip remains attached to the job for its source video.
`plan_definitions.max_series_sources = 1` disables multi-video series for that
plan; higher values permit up to five sources.
Pro is seeded at 79 EUR/month, 1,000 credits/month and five sources, with
`is_active = false` until its Stripe price is configured. Starter remains at
29 EUR/month, 300 credits/month and one source. The migration grants
authenticated users SELECT on their own series only; creation goes through
the API using the service role.

Everything else (updates to `subscriptions`, `credit_ledger` inserts, `clips` inserts, `stripe_events`) goes through the FastAPI backend using the service_role key, which bypasses RLS.

## Migration policy

- Migrations are numbered `0001_*.sql`, `0002_*.sql`, etc.
- Never edit a migration once committed. Add a new one.
- Each migration must be idempotent enough to be reapplied on a fresh DB.
- Apply via Supabase SQL editor (V1) or `supabase migration up` (V2 when we automate).

## Migration 0003 — story-first additions

Appliquée en 2026-05-22, ajoute le support de la pipeline story-first.

### `jobs` — nouvelles colonnes

| Colonne | Type | Rôle |
| --- | --- | --- |
| `video_map` | `jsonb` | Sortie compressée de la vision cheap globale (≥ 5 min) : `{ video_summary, events[] }` avec 20-40 events `{id, start, end, decor, people, objects, action, transcript_summary, visual_importance, narrative_role}`. |
| `eval_secondary` | `jsonb` | Résultat parallèle d'un run sur secondary provider (utilisé quand `EVAL_SAMPLE_RATE > 0` pour A/B benchmark). Null la plupart du temps. |
| `video_map_cost_cents` | `integer` | Coût vision cheap chunked (étape 8 story). |
| `deep_vision_cost_cents` | `integer` | Coût vision deep sur top 5 arcs (étape 11 story). |
| `primary_provider` | `text` | Nom du provider primary utilisé (`openrouter` ou `anthropic` selon config). Sert au tracking marge. |
| `fallback_used` | `boolean` | `true` si le worker a basculé sur fallback (parse error / timeout / 5xx sur primary). Indexé partiel `where fallback_used = true` pour analytics. |

### `clips` — nouvelles colonnes

| Colonne | Type | Rôle |
| --- | --- | --- |
| `segments` | `jsonb` | Liste ordonnée `[{role, start, end, transcript_excerpt}]`. `role ∈ {setup, transition, payoff, single}`. Source de vérité du clip. |
| `rendered_duration_seconds` | `numeric(10, 3)` | Durée du fichier rendu après concat + crossfade. Peut être légèrement < somme des durées des segments à cause du fondu audio. |

Backfill : les clips existants reçoivent automatiquement `segments = [{role: 'single', start: start_seconds, end: end_seconds, transcript_excerpt}]`.

### Vue `clips_with_context`

```sql
create or replace view public.clips_with_context as
  select c.id as clip_id, c.job_id, c.user_id, j.campaign_id,
         c.idx, c.title, c.score_total, c.score_breakdown,
         c.segments, c.rendered_duration_seconds, c.r2_key, c.created_at
    from public.clips c
    join public.jobs j on j.id = c.job_id;
```

Utilisée par les requêtes analytics (taux de feedback par campagne, par mode story vs simple) sans avoir à refaire le join à chaque fois.

---

## Migration 0004 — admin flag + public stats

Appliquée en 2026-05-22.

### `profiles` — nouvelle colonne

| Colonne | Type | Rôle |
| --- | --- | --- |
| `is_admin` | `boolean not null default false` | Gate l'accès à `/admin/*` côté API (dep `admin_required`) et côté layout Next.js. Index partiel `where is_admin = true`. |

### Trigger `handle_new_user` mis à jour

Auto-flip `is_admin = true` au signup pour `email = 'demeauxa8@gmail.com'`. Le trigger est idempotent — il préserve `is_admin = true` si déjà set en cas de réexécution.

### Vue `public.public_stats`

```sql
create or replace view public.public_stats as
  select
    (select count(*)::bigint from public.clips) as clips_generated,
    (select coalesce(round(sum(duration_seconds) / 3600.0)::bigint, 0)
       from public.jobs where status = 'completed') as hours_processed,
    (select count(distinct user_id)::bigint
       from public.jobs where queued_at >= now() - interval '60 days') as creators_active;

grant select on public.public_stats to anon, authenticated;
```

Lue sans auth via `GET /public/stats`, alimente les compteurs live sur la landing.

---

## Open questions

- **Job cancellation by user :** V1 ship without it (we don't refund running jobs). Add a `POST /jobs/:id/cancel` later if needed.
- **Soft delete vs hard delete :** V1 hard delete on cascade. RGPD compliance to revisit before public launch.
- **Audit log :** out of scope V1.
- **`eval_secondary` cleanup :** si on active `EVAL_SAMPLE_RATE > 0` en V1.1, prévoir un job de purge ou un TTL pour éviter de gonfler la table jobs avec des dumps JSON inutiles après analyse.
