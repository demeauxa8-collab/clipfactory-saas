# ClipFactory E2E Smoke

Playwright smoke test for a live staging or production deployment.

The test covers:

- Supabase magic-link sign-in.
- Optional Stripe Checkout test payment.
- Campaign creation.
- YouTube job submission.
- Job polling through the authenticated API.
- Clip contract checks: 1 to 3 clips, `score_breakdown`, and at least one segment.
- R2 presigned download URL check.
- Clip thumbs-up feedback.

## Local setup

```bash
cd apps/e2e
npm install
npx playwright install chromium
BASE_URL=https://clipfactory.app \
API_BASE_URL=https://api.clipfactory.app \
E2E_EMAIL=smoke@example.com \
E2E_YOUTUBE_URL=https://www.youtube.com/watch?v=REPLACE_WITH_SHORT_PUBLIC_VIDEO \
MAILTRAP_API_TOKEN=... \
MAILTRAP_ACCOUNT_ID=... \
MAILTRAP_INBOX_ID=... \
npm test
```

For a quick manual run, you can paste one fresh Supabase magic link instead of
configuring Mailtrap:

```bash
E2E_MAGIC_LINK='https://clipfactory.app/auth/callback?...' npm test
```

If the test account already has credits, skip Stripe Checkout:

```bash
E2E_SKIP_CHECKOUT=true npm test
```

If you already have an authenticated Playwright storage state:

```bash
E2E_AUTH_STATE=.auth/smoke.json E2E_SKIP_CHECKOUT=true npm test
```

## Required deployment settings

Use a staging or production deployment with real Supabase, Stripe test mode,
R2, Redis, API, and worker configured.

For Cloudflare Turnstile, either use Cloudflare's testing site/secret keys on
the smoke environment or keep `NEXT_PUBLIC_TURNSTILE_SITE_KEY=TODO` on staging.
The login form skips Turnstile only when the site key is missing or `TODO`.

## GitHub Actions

`.github/workflows/smoke.yml` runs on `main` pushes and manual dispatches when
the repository variable `SMOKE_ENABLED` is set to `true`.

Configure these repository secrets:

- `BASE_URL`
- `API_BASE_URL`
- `E2E_EMAIL`
- `E2E_YOUTUBE_URL`
- `MAILTRAP_API_TOKEN`
- `MAILTRAP_ACCOUNT_ID`
- `MAILTRAP_INBOX_ID`

Optional:

- `E2E_SKIP_CHECKOUT`
- `E2E_MAGIC_LINK`
