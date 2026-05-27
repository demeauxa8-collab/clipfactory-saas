# ClipFactory SaaS

Campaign-first AI clipping engine for creators and agencies.

> Upload long videos, get publish-ready shorts scored by hook, emotion, visual context and campaign fit.

## Goal

Reach 200 EUR MRR with ~7 paying Starter customers (29 EUR/month each).

## Monorepo layout

```
apps/
  web/      Next.js 15 — landing + dashboard (Cloudflare Pages)
  api/      FastAPI — auth, jobs, billing webhooks (VPS Hetzner)
  worker/   Python pipeline — download / transcribe / analyze / render
packages/
  shared/   Shared types and constants
db/
  migrations/  SQL migrations for Supabase Postgres
docs/
```

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js 15, TypeScript, Tailwind v4, shadcn/ui |
| Backend API | FastAPI (Python 3.11+), asyncpg |
| Worker pipeline | yt-dlp, OpenAI transcription, OpenRouter primary, Anthropic fallback, FFmpeg |
| DB + Auth | Supabase (Postgres + magic-link auth) |
| Object storage | Cloudflare R2 (S3-compatible, free egress) |
| Queue | Redis on the API VPS |
| Billing | Stripe Checkout + webhooks |
| Hosting | Web on Cloudflare Pages, API+Worker on Hetzner CPX32 |
| LLM | OpenRouter (DeepSeek + Gemini + Qwen), Anthropic Haiku fallback, OpenAI gpt-4o-mini-transcribe |

## Pricing — V1

Single plan to start, others enabled later.

| Plan | Price | Credits | Limits |
| --- | ---: | ---: | --- |
| Starter | 29 EUR/mo | 300 | 30 min/video, 3 clips/video, 1 concurrent job |

`1 credit = 1 minute of source video`. Charged against the user's monthly bucket as the worker consumes minutes.

## V1 scope (MVP — must ship)

- Landing page selling the campaign-first angle
- Email magic-link signup (Supabase Auth)
- Stripe Checkout (single Starter plan)
- Dashboard: paste YouTube URL, see job progress, download clips
- Backend: queue jobs, run pipeline, write clips to R2, debit credits
- Credit ledger so we never run a job without credits

## Out of scope for V1

Scheduling, API access, MCP, brand templates, advanced editor, face tracking, and billing portal upgrades. All shipped in V2 once we have 5+ paying customers.

## Status

Bootstrapping. See [docs/plan.md](docs/plan.md) for the build order.
