# Handoff Codex — ClipFactory SaaS V1

> **Pour Codex (ou tout autre agent) qui reprend ce projet.**
> Ce doc est la source de vérité de l'avancement. Lis-le en premier.
> Il est mis à jour à chaque étape par Claude Code (Opus 4.7).

Dernière mise à jour : 2026-05-21, par Codex (takeover V1 cleanup + verification).

---

## 1. Contexte et objectif

ClipFactory SaaS est un pivot complet du projet ClipFactory existant (app macOS + bot Discord, `/Users/augustindemeaux/ClipFactory`). On garde la pipeline (transcription + analyse + render FFmpeg) comme inspiration mais on construit un **vrai SaaS web multi-tenant** avec billing.

**Objectif business :** 200 EUR MRR via 7 clients Starter à 29 EUR/mois.

**Lecture obligatoire avant de coder :**
1. `docs/v1-scope.md` — définition de "fini" pour la V1, ce qui est IN et OUT
2. `docs/pipeline.md` — séquencement worker, les 17 étapes, vision candidate, logging coûts
3. `docs/api-contract.md` — endpoints, payload shapes, error codes
4. `/Users/augustindemeaux/ClipFactory/docs/benchmark-concurrents-saas.md` — positionnement campaign-first
5. `/Users/augustindemeaux/ClipFactory/docs/marges-saas.md` — modèle credits + marges cibles
6. `/Users/augustindemeaux/ClipFactory/workers/` — **lecture seule**, inspiration pipeline. Ne PAS copier tel quel (dépend de Codex CLI + MLX local, interdits en SaaS).

**Règle hard** : ne pas modifier `/Users/augustindemeaux/ClipFactory`.

**Décisions stratégiques déjà tranchées (avec codex et claude) :**

| Décision | Choix | Raison |
| --- | --- | --- |
| Moteur clipping | Pipeline maison sur cloud | Klap API = perte (4.44$/vidéo vs 0.97€ vendu), Wayin API = inspi pas backend |
| LLM analyse | Claude Haiku 4.5 | Bon rapport qualité/prix, supérieur à GPT pour ce type de tâche |
| Transcription | OpenAI gpt-4o-mini-transcribe | 0.003$/min, ridicule, dispense d'héberger Whisper |
| Bridge codex CLI | INTERDIT en prod SaaS | Compte ChatGPT perso = ban à 10 users |
| LLM local MLX | INTERDIT en prod SaaS | Ne scale pas, gardé pour app Mac perso uniquement |
| Vision V1 | **ACTIVÉE sur frames candidates** (2-3 par moment) | Différenciation produit vs Opus. Fallback `visual_score: null` si vision KO. |
| Scheduling V1 | DÉSACTIVÉ | V2 |
| API publique V1 | DÉSACTIVÉE | V2 |
| Mémoire campagne V1 | **ACTIVÉE version minimale** : tables + form + feedback good/bad stocké | Pas encore d'apprentissage auto, donnée collectée. |
| Pricing V1 | Un seul plan Starter 29€/300 credits | Reduce decision fatigue, mesurer marge réelle |
| Priorité hard | Pipeline > UI | Si choix : toujours pipeline fiable. UI minimale OK. |
| 1 credit = | 1 minute de vidéo source | Standard marché (Vugola, Wayin, Opus) |

---

## 2. Stack technique (verrouillée)

| Couche | Choix | Notes |
| --- | --- | --- |
| Frontend | Next.js 15 App Router + TS + Tailwind v4 + shadcn/ui | Cloudflare Pages |
| Backend API | FastAPI + asyncpg + pydantic-settings | Hetzner CPX21 |
| Worker | Python 3.11 + yt-dlp + FFmpeg + httpx | Même VPS que API au début |
| DB + Auth | Supabase (Postgres + magic-link) | Free tier OK pour démarrer |
| Storage | Cloudflare R2 (S3-compatible) | Egress GRATUIT — critique |
| Queue | Redis (sur VPS) | RQ ou simple BLPOP |
| Billing | Stripe Checkout + webhooks | Pas de Stripe Elements V1 |
| LLM | Anthropic Claude Haiku | `claude-haiku-4-5-20251001` |
| Transcript | OpenAI `gpt-4o-mini-transcribe` | 0.003$/min |
| Deploy front | Cloudflare Pages | Build SSR avec OpenNext si besoin |
| Deploy back | Docker compose sur Hetzner | API + Worker + Redis dans le même compose |

**Versions de référence (au 2026-05-21) :**
- Node 24.x (Augustin a `v24.15.0` via nvm), npm 11.x (pnpm pas installé, on reste sur npm)
- Python 3.11+
- Next.js 15.x, React 19
- FastAPI 0.115+, asyncpg 0.30+
- Stripe API version : `2025-04-30.basil` (à fixer dans le code, jamais "latest")

---

## 3. Layout monorepo

```
/Users/augustindemeaux/clipfactory-saas/
├── apps/
│   ├── web/           Next.js — landing + auth + dashboard
│   ├── api/           FastAPI — REST + Stripe webhooks
│   └── worker/        Python — pipeline async
├── packages/
│   └── shared/        Types TS et constantes partagées (plans, statuts jobs)
├── db/
│   └── migrations/    SQL Supabase versionné
├── docs/
│   ├── plan.md                       Build order
│   ├── handoff-codex.md              CE FICHIER
│   ├── db-schema.md                  (à créer)
│   ├── api-contract.md               (à créer)
│   └── deploy.md                     (à créer)
└── README.md
```

---

## 4. État d'avancement

**Légende :** `[x]` fait — `[~]` en cours — `[ ]` à faire

- [x] **T1.** Repo skeleton + .gitignore + README + plan.md
- [x] **T2.** Handoff doc Codex (ce fichier)
- [x] **T3.** DB schema 0001 (base) -> `db/migrations/0001_init.sql` + `docs/db-schema.md`
- [x] **T4.** Next.js web skeleton + landing -> `apps/web/` (build prod OK, 12 routes)
- [x] **T5.** Supabase auth magic-link -> `apps/web/lib/supabase/*` + `/login` + `/auth/callback` + middleware
- [x] **T6.** V1 scope/API/pipeline docs -> `docs/v1-scope.md` + `docs/pipeline.md` + `docs/api-contract.md`
- [x] **T7.** DB schema 0002 campaigns/costs/vision -> `db/migrations/0002_campaigns_costs_vision.sql`
- [x] **T8.** FastAPI backend -> campaigns/jobs/clips/feedback/billing/credits
- [x] **T9.** Web app pages -> dashboard/campaign/job/billing
- [x] **T10.** Worker pipeline 17 étapes en code -> download/transcribe/analyze/vision/score/render/upload
- [~] **T11.** Local integration smoke test -> bloqué tant que DB/Redis/R2/Stripe/API keys réels ne sont pas branchés
- [ ] **T12.** Deploy runbook -> Cloudflare Pages + Hetzner + Supabase + R2 + Stripe

---

## 5. Journal des décisions (append-only)

### 2026-05-21 — Bootstrap

- Repo créé à `/Users/augustindemeaux/clipfactory-saas`, branche `main`, pas encore de remote.
- User Augustin : 13 ans, ne code pas ligne à ligne. Mode speedrun long. Préférence Apple HIG mais on reste pragma : Tailwind + shadcn permet ce look sans Sketch.
- Code en anglais (commentaires, identifiers), chat en français.
- Pas de Firebase, RN, Flutter. Pas de remplacement Matrix (autre projet — Mood).
- Le code de `/Users/augustindemeaux/ClipFactory/workers/` doit être **inspiration**, pas copié tel quel : il a des dépendances `mlx-whisper`, `codex CLI subprocess` qui ne marchent pas en SaaS.

### 2026-05-21 — DB schema posée

- Migration `0001_init.sql` couvre : `plan_definitions` (seed Starter), `profiles` (trigger auto-create depuis `auth.users`), `subscriptions`, `credit_ledger` (append-only + vue `credit_balances`), `jobs`, `clips`, `stripe_events` (idempotency).
- Enums : `subscription_status`, `credit_reason`, `job_status`.
- RLS activée partout. Client (anon/auth) lit ses propres lignes ; le backend (service_role) écrit tout le reste.
- Doc associée : `docs/db-schema.md`. Inclut invariants, math credits, politique de migrations.
- Pas encore appliquée à un projet Supabase réel — V1 = SQL prêt, applied manuellement à la création du projet.

### 2026-05-21 — Web app + auth

- **T4 — apps/web** : Next.js 15.5 + React 19 + Tailwind v4 + TS strict + typedRoutes. Landing complète : hero "Less random virals", section "How it works" 3 steps, section "score breakdown" avec exemple Clip 1 — 87, pricing Starter 29€ unique, footer legal. Pages legal (terms/privacy) en stubs minimaux. 404 propre. Build prod initial OK, puis 12 routes après pages app. `npm install` = 74 packages, OK.
- **T5 — auth Supabase** : Magic-link via `signInWithOtp`. Composants split serveur (`lib/supabase/server.ts`) / browser (`lib/supabase/browser.ts`) / middleware (`lib/supabase/middleware.ts`). Middleware Next.js applique `updateSession` partout sauf assets statiques. Route `/auth/callback` échange le code OAuth contre une session. Route POST `/auth/signout`. `/app` est protégée et redirige sur `/login?next=/app` si non connecté. `/login` redirige sur `/app` si connecté.
- **Stack note** : pas de pnpm sur la machine d'Augustin → on reste sur npm. Tailwind v4 utilise `@import "tailwindcss"` + `@theme { ... }` dans `globals.css` (CSS-first, plus de `tailwind.config.js`).
- **Pas encore branché à un vrai projet Supabase.** Codex doit créer un projet Supabase EU, appliquer `db/migrations/0001_init.sql` dans le SQL editor, et remplir `apps/web/.env.local` avec les valeurs Supabase (URL + anon key).

### 2026-05-21 — Recadrage scope V1 + backend posé

- **Recadrage scope.** V1 = produit complet (campagnes + vision sur candidats + score expliqué + feedback), pas juste landing + auth + 1 plan. Scheduling/API/MCP restent V2. Source de vérité : `docs/v1-scope.md`.
- **Migration 0002 posée.** Ajoute `campaigns`, `campaign_feedback`, colonnes coûts/marge sur `jobs` (transcription_cost_cents, analysis_tokens, vision_frames_count, render_seconds, storage_bytes, total_cost_estimate_cents, failed_step, retry_count, current_step, source_r2_key), colonnes vision/contexte sur `clips` (visual_summary, transcript_excerpt). RLS sur campaigns + feedback.
- **Pipeline 17 étapes documentée.** Vision uniquement sur 2-3 frames par moment candidat (max ~60 frames/job). Fallback `vision_unavailable` si vision KO → job termine quand même avec `visual_score: null` et score renormalisé.
- **Logging coût/marge obligatoire.** Pas de table séparée — colonnes dans `jobs`. Estimations OK V1 si pas mesuré exact.
- **Backend FastAPI : structure initiale posée** (`settings.py`, `db.py`, `auth.py`, `schemas.py`, services credits/queue/storage/jobs, routers health/me/jobs/clips, `main.py` avec lifespan + CORS). État courant corrigé dans l'entrée "Codex takeover cleanup + verification" ci-dessous.
- **API à compléter à ce moment-là** : routers `campaigns`, `feedback`, `billing`, schemas associés, service `campaigns.py`, service `billing.py`, `campaign_id` obligatoire sur `JobCreate`. Ces éléments sont maintenant présents dans le code.

### 2026-05-21 — Codex takeover cleanup + verification

- Nettoyage repo : suppression des artefacts générés visibles (`.DS_Store`, `*.egg-info`, lock Word temporaire) et `.gitignore` renforcé (`*.egg-info/`, `~$*`, `*.tsbuildinfo`).
- Backend API complété et vérifié : endpoints campaigns, jobs, clips, feedback, credits, billing Checkout/webhook. Les retours Stripe pointent vers `/app/billing`, pas `/billing`.
- Fix important crédits worker : débit basé sur la durée réelle après probe FFmpeg, vérification du solde avant débit, refund limité aux crédits réellement débités. Ça évite les refunds gratuits si le job échoue avant débit.
- Fix important API job detail : `GET /jobs/{id}` renvoie correctement `visual_summary`, `transcript_excerpt` et `score_breakdown` normalisé pour les clips.
- Worker pipeline présent en code : yt-dlp, FFmpeg probe/render, OpenAI transcription, Claude analyse texte, Claude vision sur frames candidates, scoring, captions ASS, upload R2, cost logging DB.
- Vérification locale OK avec env factice : `npm run typecheck`, `npm run build`, `ruff check app` API/worker, `python -m compileall -q app` API/worker, import FastAPI, import worker.
- Blocage restant : pas encore de vrai test end-to-end avec Supabase Postgres, Redis, R2, Stripe, OpenAI et Anthropic branchés.

### Choix infra à venir (à valider quand on déploie)

- **Région Hetzner :** Falkenstein (Allemagne) — latence FR correcte, RGPD natif
- **Région Cloudflare R2 :** auto (eu)
- **Domaine :** non choisi — propositions : `clipfactory.app`, `clipfactory.io`, `clipfact.io`
- **Supabase région :** `eu-west-1` (Frankfurt)

---

## 6. Services externes à créer (par Augustin, AVANT de déployer)

| Service | Pourquoi | Coût/mo | Action |
| --- | --- | --- | --- |
| Supabase project EU | DB + Auth | 0€ (free) | `https://supabase.com/dashboard` |
| Cloudflare R2 bucket | Storage clips | ~5€/100GB | `https://dash.cloudflare.com/?to=/:account/r2` |
| Stripe account FR | Billing | 0€ + 1.4%+0.25€/tx | `https://dashboard.stripe.com` |
| OpenAI API | Transcription | ~variable | clé séparée projet SaaS |
| Anthropic API | Analyse | ~variable | clé séparée projet SaaS |
| Hetzner CPX21 | Worker + API | ~7€/mo | Falkenstein |
| Domaine | Public | ~1€/mo | Cloudflare Registrar ou Gandi |

**Important** : aucune clé API n'est commitée. Tout passe par `.env` local et `.env` sur le VPS. Les `.env.example` sont commités avec des placeholders.

---

## 7. Variables d'environnement (référence)

Une seule source de vérité par couche. Synchroniser quand tu changes.

### apps/web/.env.local

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
```

### apps/api/.env

```
DATABASE_URL=postgresql://...        # Supabase Postgres connection string (pooled)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=           # backend-only, JAMAIS exposée client
SUPABASE_JWT_SECRET=                 # vérifier les JWT côté API
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_STARTER_PRICE_ID=
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_CLIPS=clipfactory-clips
R2_PUBLIC_BASE_URL=                  # ou presigned URLs seulement
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
WEB_BASE_URL=http://localhost:3000
ENV=dev                              # dev | prod
```

### apps/worker/.env

Hérite de `apps/api/.env`. Ajoute :

```
WORKER_CONCURRENCY=1
WORKER_TMP_DIR=/tmp/clipfactory
YT_DLP_COOKIES_FILE=                 # optionnel si YouTube bloque
FFMPEG_THREADS=4
```

---

## 8. Conventions de code

- **TS strict** : `strict: true` dans tous les tsconfig
- **Python** : type hints partout, pydantic pour les DTOs, ruff + black
- **Naming** : `snake_case` Python, `camelCase` TS, `PascalCase` composants React
- **Errors** : pas de `try/except` qui mange l'erreur. Logger structuré (JSON) + remonter
- **Pas de console.log/print sauvages** : logger configuré (web : `pino`, api/worker : `structlog`)
- **Migrations DB** : numérotées `0001_xxx.sql`, jamais éditées une fois mergées — nouvelle migration à la place
- **Tests** : minimaux V1 (pas de TDD), juste un smoke test e2e
- **Pas d'emojis** dans le code

---

## 9. Comment reprendre le travail (pour Codex)

1. **Lire ce doc en entier.** Section 4 = état actuel.
2. **Lire `docs/plan.md`** pour le build order.
3. **Lire les deux docs source** dans `/Users/augustindemeaux/ClipFactory/docs/`.
4. **Vérifier `git status`** et `git log --oneline -20` sur le repo.
5. **Lancer la dernière task en `pending`** (la plus basse en numéro).
6. **Avant d'éditer**, ouvrir le fichier concerné s'il existe — ne jamais écraser sans lire.
7. **À chaque step terminé** :
   - Mettre à jour la case `[x]` section 4
   - Ajouter une ligne au journal section 5 (date + résumé court)
   - Commit avec message conventionnel : `feat(web): ...`, `feat(api): ...`, etc.
8. **Si bloqué** : ajouter une entrée "Blockers" en section 10 et stopper proprement.

---

## 10. Blockers / questions ouvertes

Blocker actif pour valider la V1 en vrai :
- Créer/brancher les services réels : Supabase Postgres/Auth, Redis local ou VPS, R2, Stripe test, OpenAI API, Anthropic API.
- Appliquer les migrations `0001_init.sql` puis `0002_campaigns_costs_vision.sql`.
- Lancer un job test complet sur une vraie vidéo courte et vérifier crédits, coût, clips R2, feedback, webhook Stripe.

Questions à arbitrer avant deploy :
- Choix du domaine final
- Compte Stripe FR créé ?
- Décision sur le bouton "Cancel subscription" — V1 = lien vers Stripe Customer Portal ?

---

## 11. Inventaire des fichiers (mis à jour à chaque édition)

```
clipfactory-saas/
├── .gitignore                          [21/05]
├── README.md                           [21/05]
├── apps/web/                           [21/05]
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── next-env.d.ts
│   ├── postcss.config.mjs
│   ├── middleware.ts                   Session Supabase à chaque request
│   ├── .env.example
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css                 Tailwind v4 + @theme tokens
│   │   ├── page.tsx                    Landing
│   │   ├── not-found.tsx
│   │   ├── login/
│   │   │   ├── page.tsx
│   │   │   └── login-form.tsx          Client component, OTP magic-link
│   │   ├── auth/
│   │   │   ├── callback/route.ts       Exchange code -> session
│   │   │   └── signout/route.ts        POST signout
│   │   ├── app/
│   │   │   ├── layout.tsx              Layout app protégée
│   │   │   ├── page.tsx                Dashboard jobs + credits
│   │   │   ├── billing/page.tsx        Billing + Checkout
│   │   │   ├── campaigns/new/          Création campagne
│   │   │   ├── campaigns/[id]/         Détail campagne + submit job
│   │   │   └── jobs/[id]/              Monitoring job + clips
│   │   └── legal/
│   │       ├── terms/page.tsx
│   │       └── privacy/page.tsx
│   ├── components/
│   │   ├── ui/{button,container,input}.tsx
│   │   └── marketing/{nav,footer}.tsx
│   └── lib/
│       ├── utils.ts
│       └── supabase/{server,browser,middleware}.ts
├── apps/api/                           [21/05]
│   ├── pyproject.toml
│   ├── .env.example
│   ├── README.md
│   └── app/
│       ├── __init__.py
│       ├── main.py                     FastAPI app + lifespan + CORS
│       ├── settings.py                 pydantic-settings
│       ├── db.py                       asyncpg pool
│       ├── auth.py                     Supabase JWT verify
│       ├── schemas.py                  Pydantic DTOs
│       ├── routers/{health,me,jobs,clips,campaigns,feedback,credits,billing}.py
│       └── services/{credits,queue,storage,jobs,campaigns,billing}.py
├── apps/worker/                        [21/05]
│   ├── pyproject.toml
│   ├── .env.example
│   ├── README.md
│   └── app/
│       ├── main.py                     Loop Redis BLPOP
│       ├── settings.py                 pydantic-settings
│       ├── db.py                       asyncpg helpers
│       ├── storage.py                  R2 upload
│       └── pipeline/
│           ├── runner.py               Orchestration 17 étapes + credits/costs
│           ├── transcribe.py           OpenAI transcription
│           ├── analyze.py              Claude text candidate selection
│           ├── vision.py               Claude vision frames candidates
│           ├── score.py                Score explained
│           ├── captions.py             ASS captions
│           └── ffmpeg.py               Probe/render/helpers
├── db/migrations/
│   ├── 0001_init.sql                   [21/05]  V1 base
│   └── 0002_campaigns_costs_vision.sql [21/05]  V1 scope expansion
└── docs/
    ├── plan.md                         [21/05]
    ├── handoff-codex.md                [21/05]  CE FICHIER
    ├── db-schema.md                    [21/05]
    ├── v1-scope.md                     [21/05]  SOURCE DE VÉRITÉ scope V1
    ├── pipeline.md                     [21/05]  17 étapes worker
    └── api-contract.md                 [21/05]  endpoints + payload shapes
```

À mettre à jour à chaque nouveau fichier.
