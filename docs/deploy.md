# Deploy runbook

> Sequence to get ClipFactory live on a custom domain. Order matters — don't deploy the worker before the DB is migrated.

## Prerequisites (accounts to create)

| Service | Why | Status |
| --- | --- | --- |
| Supabase EU (Frankfurt) | DB + Auth | ✓ done — project ref `jsjaizcnjvghoduvyyea` |
| Cloudflare R2 | Object storage | todo |
| Stripe FR | Billing | todo |
| OpenAI | Transcription (**whisper-1** — gpt-4o-mini-transcribe refuse les word timestamps) | ✓ opérationnel (clé worker) |
| OpenRouter | Primary LLM (validé : gemini-2.5-flash partout) | ✓ opérationnel (clé worker) |
| Anthropic | Fallback LLM (Haiku) | todo |
| VPS UE (OVH VPS-2 / Scaleway DEV1-M) | API + Redis control plane | todo |
| Mac Studio (worker) | Transcription + render (modèle pull) | machine possédée |
| Cloudflare Pages | Web frontend | todo |
| Domain (`clipfactory.app` or alt) | Public URL | todo |

## Step 1 — DB ready (already done locally)

Migrations 0001 → 0004 already applied via Supabase SQL editor on 2026-05-22. To redo from scratch on a fresh project:

```sql
-- Run in order in Supabase SQL Editor:
-- db/migrations/0001_init.sql
-- db/migrations/0002_campaigns_costs_vision.sql
-- db/migrations/0003_story_arcs.sql
-- db/migrations/0004_admin_flag.sql
```

Verify with `select count(*) from information_schema.tables where table_schema = 'public';` — should be 11.

## Step 2 — Stripe (≈ 15 min)

1. Create an FR Stripe account at `https://dashboard.stripe.com`.
2. **Products** → create "Starter" with a **recurring price** of 29 EUR / month (no trial in V1).
3. Copy the `price_…` ID into `STRIPE_STARTER_PRICE_ID`.
4. Update DB: `update plan_definitions set stripe_price_id = 'price_...' where code = 'starter';`
5. **Developers → Webhooks** → add endpoint `https://api.clipfactory.app/stripe/webhook` and select events:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.updated`
   - `customer.subscription.created`
   - `customer.subscription.deleted`
6. Copy the `whsec_…` signing secret into `STRIPE_WEBHOOK_SECRET`.
7. Get publishable + secret keys from **Developers → API keys**.

## Step 3 — Cloudflare R2 (≈ 10 min)

1. From Cloudflare dashboard → **R2** → Create bucket `clipfactory-clips` (auto-region EU).
2. **R2 → Manage API Tokens** → Create token with **Edit** permissions on the bucket. Save:
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
3. Note the account ID (top-right of the dashboard) → `R2_ACCOUNT_ID`.
4. Endpoint URL: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` → `R2_ENDPOINT_URL`.
5. **CORS**: presigned URLs require none — the client never hits R2 directly for V1. Skip.

## Step 4 — LLM keys (≈ 10 min)

- OpenAI: `platform.openai.com` → API keys → new key → `OPENAI_API_KEY`.
- OpenRouter: `openrouter.ai` → Keys → new key → `OPENROUTER_API_KEY`.
- Anthropic: `console.anthropic.com` → API keys → new key → `ANTHROPIC_API_KEY`.

Top up each account with a starting credit balance (~ $10–20 each is enough for the first weeks).

## Step 5 — Control plane VPS + worker Mac Studio (≈ 45 min)

> Architecture: see `docs/infrastructure.md`. The **control plane** (API + Redis + Caddy) lives on a small EU VPS that must answer 24/7. The **worker** (transcription + render) runs on the **Mac Studio** in a *pull* model: it connects out to the VPS to take jobs — nothing connects to the Mac. No Hetzner (hardened KYC); use OVH or Scaleway.

### 5.A — VPS control plane (OVH VPS-2 or Scaleway DEV1-M)

Target: 2-3 vCPU / 4 GB, EU (GDPR), Ubuntu 24.04.

1. Provision the VPS (OVH VPS-2 ~€8.49/mo HT, or Scaleway DEV1-M), Ubuntu 24.04, public SSH key.
2. SSH in, install only what the control plane needs (NOT ffmpeg/yt-dlp — the Mac renders):
   `apt update && apt install -y python3-venv redis-server caddy git`.
3. Clone repo, create `apps/api/.env` from `.env.example`, fill **every** value (DB, R2, Stripe, LLM keys…).
4. **Secure Redis** — it will be reached by the Mac from outside. Either:
   - Redis with `requirepass` + TLS, OR
   - a **Tailscale / Cloudflare Tunnel** between the Mac and the VPS, with Redis bound to the private interface only. Never expose Redis bare on the internet.
5. API venv + systemd: `python3 -m venv /opt/clipfactory-api/.venv && /opt/clipfactory-api/.venv/bin/pip install -e apps/api[dev]`; unit `clipfactory-api.service` → `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
6. Caddy (`/etc/caddy/Caddyfile`):
   ```
   api.clipfactory.app {
     reverse_proxy localhost:8000
   }
   ```
7. `systemctl enable --now caddy redis-server clipfactory-api`, then test `curl https://api.clipfactory.app/health` → `{"status":"ok"}`.

### 5.B — Worker on the Mac Studio (pull model)

1. Install tooling: `brew install python@3.11 ffmpeg yt-dlp`.
2. Clone repo, create `apps/worker/.env` from `.env.example`. **Important**: `REDIS_URL` points to the **secured Redis endpoint of the VPS** (not `localhost`). Fill DB (Supabase) / R2 / OpenAI / OpenRouter / Anthropic.
3. Venv + install: `python3.11 -m venv .venv && .venv/bin/pip install -e apps/worker[dev]`.
4. Run the worker as a permanent service via **launchd** (a `com.clipfactory.worker` LaunchAgent that runs `python -m app.main` and auto-restarts). Quick test: `python -m app.main` inside tmux.
5. Verify: the worker `BLPOP`s the VPS Redis and processes jobs. No inbound port on the Mac's network.

> BUILD/TEST phase (before first paying customer): you can run everything on the Mac (API included) behind a **Cloudflare Tunnel**, with no VPS at all. The 5.A/5.B split activates at the first paying customer. See `docs/infrastructure.md` §6.

## Step 6 — Cloudflare Pages (≈ 15 min)

1. Cloudflare → **Workers & Pages → Pages** → connect GitHub → select `clipfactory-saas` repo.
2. Framework preset: Next.js. Root: `apps/web`. Build command: `npm install && npm run build`.
3. Environment variables (production):
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL=https://api.clipfactory.app`
   - `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`
   - `NEXT_PUBLIC_SITE_URL=https://clipfactory.app`
4. Custom domain: `clipfactory.app`. Set DNS records as instructed.
5. ⚠️ Next.js 15 SSR + middleware on Pages requires the **`@cloudflare/next-on-pages`** adapter. If the build fails on first try, follow `https://developers.cloudflare.com/pages/framework-guides/nextjs/ssr/`. Fallback: Vercel (zero friction, free tier covers V1).

## Step 7 — Supabase auth callback whitelist

Supabase → **Authentication → URL Configuration** → add to the redirect allowlist:

- `http://localhost:3000/auth/callback`
- `https://clipfactory.app/auth/callback`

Without this, the magic-link callback returns "Invalid redirect" in prod.

## Step 7.b — Google OAuth (sign-in with Google)

The login page has a "Continue with Google" button. To activate it:

### Google Cloud Console (~ 10 min)

1. Open `https://console.cloud.google.com` and create a new project named "ClipFactory" (or reuse one).
2. **APIs & Services → OAuth consent screen**:
   - User Type: **External**
   - App name: `ClipFactory`, support email: `hello@clipfactory.app`
   - Authorised domain: `clipfactory.app`
   - Scopes: `openid`, `email`, `profile`
   - Publishing status: **In production** (otherwise only test users can sign in)
3. **APIs & Services → Credentials → + Create credentials → OAuth client ID**:
   - Type: **Web application**
   - Name: `ClipFactory Web`
   - Authorised JavaScript origins:
     - `http://localhost:3000`
     - `https://clipfactory.app`
   - Authorised redirect URIs:
     - `https://jsjaizcnjvghoduvyyea.supabase.co/auth/v1/callback`
4. Copy the **Client ID** and **Client Secret**.

### Supabase (~ 2 min)

1. Open `https://supabase.com/dashboard/project/jsjaizcnjvghoduvyyea/auth/providers`.
2. Find **Google** in the list → toggle **Enable**.
3. Paste the Client ID and Client Secret from Google Cloud.
4. Save. Done.

### Verify

Open `http://localhost:3000/login` (dev) → click "Continue with Google" → Google consent screen → redirected back to `/app`. Profile row is auto-created by the `handle_new_user` trigger; the email auto-flips `is_admin = true` for `demeauxa8@gmail.com`.

Common pitfalls:
- Forgot to add the production origin → button works locally but 400 in prod.
- Forgot to add the Supabase callback URL on the Google side → "redirect_uri_mismatch" error.
- OAuth consent screen left in "Testing" mode → only listed test users can sign in.

## Step 8 — Smoke test (11-step user flow)

See `docs/handoff-codex.md` section "Smoke test". To validate the full flow before announcing the product to anyone, including yourself (founder is auto-admin, see migration 0004).

## Step 9 — Monitoring (minimum viable)

- VPS: enable provider backups (OVH/Scaleway snapshot).
- Uptime Robot or Better Uptime: ping `https://api.clipfactory.app/health` every 5 min.
- Stripe dashboard email alerts on payment failures.
- Supabase dashboard → Settings → Database → enable connection pool alerts.
- Cron-style task: nightly `select count(*) from jobs where status = 'failed' and queued_at > now() - interval '1 day';` → if > 5 send email.

## Rollback procedure

If a deploy breaks prod:

1. Cloudflare Pages: revert to the previous deployment in the **Deployments** tab — instant.
2. API: `git checkout <previous-tag> && systemctl restart clipfactory-api clipfactory-worker`.
3. DB: migrations are forward-only. To "undo" 0004 (`is_admin`), write `0005_revert_admin.sql` rather than editing 0004.
4. Stripe: webhook events are idempotent thanks to `stripe_events.event_id` PK — replays are safe.

## Cost budget at 7 Starter customers

Source of truth: `docs/unit-economics.md`.

The current model uses a small OVH/Scaleway control plane VPS (the worker runs on
the owned Mac Studio), VAT-included pricing, and Stripe France fees:

| Scenario | Margin / mo after VAT + Stripe |
| --- | ---: |
| Mixed usage, official providers | ~120€ |
| Conservative heavy-story usage | ~75-90€ |

Re-check real margins after the first 20 completed production jobs.
