# ClipFactory Web

Next.js 15 frontend for ClipFactory SaaS.

## Run locally

```bash
cd apps/web
npm install
cp .env.example .env.local  # fill in real values
npm run dev                   # http://localhost:3000
```

## What's in here

| Route group | Purpose |
| --- | --- |
| `/`, `/features`, `/pricing`, `/faq`, `/about`, `/changelog` | Public marketing site |
| `/legal/terms`, `/legal/privacy` | Legal stubs |
| `/login` | Magic-link signup/signin (Supabase) |
| `/auth/callback`, `/auth/signout` | Auth flow plumbing |
| `/app`, `/app/campaigns/*`, `/app/jobs/*`, `/app/billing` | User dashboard (protected) |
| `/admin`, `/admin/users`, `/admin/jobs`, `/admin/finance` | Operator dashboard (is_admin only) |
| `/sitemap.xml`, `/robots.txt`, `/opengraph-image` | SEO |

## Auth model

Middleware `middleware.ts` calls `updateSession` from `lib/supabase/middleware.ts` on every request to refresh the Supabase session and gate `/app/*` and `/admin/*` (redirect to `/login` if not authenticated).

Admin layout `/admin/layout.tsx` performs an additional server-side `is_admin` check before rendering — non-admin users get redirected to `/app`.

API calls from client components go through `lib/api.ts` (`apiFetch`) which forwards the Supabase access token as a Bearer header. Server components use `lib/admin-api.ts` (`adminFetch`) for admin endpoints.

## Styling

Tailwind v4 (CSS-first, no `tailwind.config.js`). Tokens are defined in `app/globals.css` under `@theme`. Components live in `components/ui/` (button, container, input) and `components/marketing/`.

## Build

```bash
npm run typecheck   # TS strict
npm run build       # Next.js prod build
```
