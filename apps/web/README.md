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
| `/preview/journey` | End-to-end customer journey QA, no API or charge |
| `/preview/redesign`, `/preview/processing` | Historical design and motion labs (`noindex`) |
| `/sitemap.xml`, `/robots.txt`, `/opengraph-image` | SEO |

## Auth model

Middleware `middleware.ts` calls `updateSession` from `lib/supabase/middleware.ts` on every request to refresh the Supabase session and gate `/app/*` and `/admin/*` (redirect to `/login` if not authenticated).

Admin layout `/admin/layout.tsx` performs an additional server-side `is_admin` check before rendering — non-admin users get redirected to `/app`.

API calls from client components go through `lib/api.ts` (`apiFetch`) which forwards the Supabase access token as a Bearer header. Server components use `lib/admin-api.ts` (`adminFetch`) for admin endpoints.

## Styling

The canonical UI/UX specification is [`../../docs/ui-ux-system.md`](../../docs/ui-ux-system.md). Read it before changing the landing, onboarding, processing, paywall, result, or workspace.

Tailwind v4 is CSS-first; there is no `tailwind.config.js`.

- Global tokens: `app/globals.css` under `@theme`.
- Product aliases and shared chrome: `app/product.css`.
- Accessible primitives: `components/ui/`.
- Product primitives: `components/product/`.
- Canonical landing: `components/prototypes/redesign/apple-edit-axis.tsx` and `edit-axis-story.tsx`.
- Canonical processing: `components/prototypes/processing/signal-timeline.tsx`.
- Machine-readable decisions: `.21st/design.json`.

The visual direction is Apple Pro / Final Cut-inspired graphite with one action blue (`#0071e3`). Campaign intent, source timecode, transcript words, visible proof, and the delivered clip must remain connected. Do not reintroduce orange branding, multiple blues, purple mesh gradients, generic metric-card dashboards, fake progress, or decorative infinite motion.

## UI preview and state QA

```text
/preview/journey
/preview/journey?screen=brief&state=error
/preview/journey?lab=1
/preview/processing?v=3&state=loading
/preview/processing?v=3&state=error
/preview/redesign?v=6&clean=1
```

The guided journey has six visible stages: sign in, campaign, source, build, review, and workspace. The contextual paywall appears when the first ready clip is played; it is not a separate numbered stage.

Before handing off a UI change, verify keyboard navigation, reduced motion, loading/empty/error/success, long copy, and screenshots at 390px and 1440px.

## Build

```bash
npm run typecheck   # TS strict
npm run build       # Next.js prod build
```
