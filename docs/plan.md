# Build plan — ClipFactory SaaS V1

> **Scope** : voir `docs/v1-scope.md`. **Pipeline** : voir `docs/pipeline.md`. **API** : voir `docs/api-contract.md`.

Target: 200 EUR MRR via 7 Starter customers @ 29 EUR.

## Priorité absolue

1. backend solide
2. pipeline qui marche de bout en bout
3. crédits / billing fiables
4. worker qui génère vraiment des clips
5. stockage R2 + DB cohérents
6. coûts / marges loggés

Si choix entre "belle UI" et "pipeline fiable" : **toujours pipeline fiable**.

## Build order

| # | Étape | Statut | Notes |
| ---: | --- | --- | --- |
| 1 | Repo skeleton + docs init | ✓ | `README.md`, `docs/plan.md` |
| 2 | DB schema 0001 (base) | ✓ | `db/migrations/0001_init.sql` |
| 3 | Next.js skeleton + landing | ✓ | Build prod OK, 12 routes après pages app |
| 4 | Auth Supabase magic-link | ✓ | `/login`, `/auth/callback`, middleware |
| 5 | Recadrer docs (v1-scope + pipeline + api-contract) | ✓ | Docs canoniques posées |
| 6 | DB schema 0002 (campaigns + costs + vision) | ✓ | `db/migrations/0002_*.sql` |
| 7 | FastAPI backend (campaigns + jobs + clips + billing) | ✓ | Import FastAPI OK, ruff OK |
| 8 | Stripe Checkout + webhook + credit grant | ✓ | Checkout + webhook + idempotency DB, test réel Stripe restant |
| 9 | Worker pipeline 17 étapes (single-window) | ✓ | Remplacé par T18 (story-first) |
| 10 | Web pages app (dashboard, campaigns, job, billing) | ✓ | Typecheck/build OK |
| 11 | Smoke test end-to-end | ~ | nécessite Supabase/Redis/R2/Stripe/OpenAI/OpenRouter/Anthropic réels |
| 12 | Deploy runbook | en attente | Cloudflare Pages + Hetzner |
| 18 | Pipeline story-first rewrite | ✓ | Voir `docs/pipeline.md` — deux chemins (simple < 5 min / story ≥ 5 min), provider OpenRouter + fallback Haiku, migration 0003 |

## External services à créer par Augustin

Voir `docs/handoff-codex.md` section 6. Addition story-first : **créer un compte OpenRouter** (`https://openrouter.ai`) et provisionner une clé `OPENROUTER_API_KEY`. C'est devenu le provider primary pour texte + vision.

## Budget targets

Estimation post-rewrite story-first (passage de Claude Haiku partout → mix DeepSeek/Gemini/Qwen via OpenRouter + Haiku en fallback uniquement).

| Item | Cost/mo |
| --- | ---: |
| Hetzner CPX21 worker | ~7 EUR |
| Supabase free + R2 small | ~5 EUR |
| OpenAI Whisper API (7 users × 300 min) | ~7 EUR |
| OpenRouter LLM mix (DeepSeek texte + Gemini deep vision + Qwen video map) | ~12 EUR |
| Anthropic Haiku fallback (uniquement sur erreur primary) | ~1 EUR |
| Stripe fees | ~6 EUR |
| Domaine | ~1 EUR |
| **Total infra** | **~39 EUR** |
| Revenue @ 7 × Starter | **203 EUR** |
| Margin | **~164 EUR** |

> Note : la marge LLM réelle reste à mesurer sur les premiers jobs prod. `EVAL_SAMPLE_RATE` permettra de comparer primary vs fallback sur un échantillon pour ajuster.

## État vérifié localement

Dernière vérification : 2026-05-21.

- Web : `npm run typecheck` OK, `npm run build` OK.
- API : `ruff check app` OK, `python -m compileall -q app` OK, import FastAPI OK.
- Worker : `ruff check app` OK, `python -m compileall -q app` OK, import pipeline OK.
- Pas encore validé : job complet avec vrais services externes et vraie vidéo.
