# Brief Codex — ClipFactory SaaS (à donner à Codex)

> Ce doc est un message ready-to-paste à donner à Codex pour qu'il prenne en charge les tâches longues pendant qu'Augustin et Claude bossent en live sur le reste.

---

## Message à coller à Codex

```
Salut Codex.

Tu reprends ClipFactory SaaS — repo local /Users/augustindemeaux/clipfactory-saas, remote github.com/demeauxa8-collab/clipfactory-saas.

AVANT TOUT CHOSE — lis ces 4 fichiers, dans l'ordre :
1. docs/handoff-codex.md   (tout l'état du projet, sections 0 à 12)
2. docs/v1-scope.md         (périmètre V1)
3. docs/security-audit.md   (5 Medium à fixer, c'est ta P1)
4. docs/deploy.md           (runbook pour la P0)

Pour le reste, tout est dans /docs : pipeline.md, api-contract.md, db-schema.md, admin.md, seo.md, global-video-understanding.md.

ÉTAT ACTUEL :
- Code V1 complet et pushé : worker story-first pipeline + API + web (landing + dashboard user + admin) + 4 migrations DB + SEO complet.
- Tout compile : tsc OK (web), ruff + imports OK (api + worker).
- Supabase est branché, migrations 0001-0004 appliquées.
- Les .env contiennent les vraies clés Supabase, mais TODO pour Stripe / R2 / OpenAI / OpenRouter / Anthropic (Augustin doit créer ces comptes).
- Pas encore déployé. Pas encore de smoke test live.

CONTRAINTES HARD (ne JAMAIS enfreindre) :
- Ne modifie pas /Users/augustindemeaux/ClipFactory (c'est l'ancien repo Mac perso d'Augustin, lecture seule pour inspiration).
- Ne mets pas Codex CLI / MLX local dans le SaaS — interdit, ne scale pas multi-tenant.
- Ne commit JAMAIS un secret. Les .env sont gitignorés, vérifie avant chaque git add -A.
- Ne touche pas une migration déjà mergée (0001 à 0004) — nouvelle migration 0005_*.sql à la place.
- Code en anglais, docs et messages de commit en anglais, conversation en français.
- Pas d'emojis dans le code.
- Conventional commits : feat(api): ..., fix(worker): ..., chore(db): ...
- Si une décision touche le scope V1, lis docs/v1-scope.md avant d'agir.
- Si tu hésites, ajoute une entrée Blocker en section 11 du handoff et stoppe proprement.

PARTAGE DU TRAVAIL :
- Claude pilote en live (Chrome MCP pour Supabase / Vercel deploy, code review, décisions strategy).
- Augustin crée les comptes externes (Stripe, R2, OpenAI, OpenRouter, Anthropic, Hetzner, domaine, Google Cloud).
- Toi (Codex), tu prends les tâches longues en autonomie listées ci-dessous, dans l'ordre.

═══════════════════════════════════════════════════════════════════

P0 — DÉPLOIEMENT VPS Hetzner (le plus impactant)

Objectif : faire tourner l'API + worker + Redis sur un VPS Hetzner CPX21 à Falkenstein, derrière Caddy avec TLS auto pour api.clipfactory.app.

Prérequis (Augustin te donnera quand prêt) :
- IP du VPS + clé SSH
- Domain `clipfactory.app` (ou alternative) pointé chez Cloudflare DNS
- Les vraies valeurs pour STRIPE_*, R2_*, OPENAI_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY

Travail à faire (suivre docs/deploy.md step 5) :
1. SSH dans le VPS, apt install : docker.io, docker-compose-v2, ffmpeg, yt-dlp, redis-server, caddy, git
2. Clone repo, créer apps/api/.env et apps/worker/.env à partir des .env.example, remplir toutes les valeurs
3. Provisionner Python venv pour api et worker
4. Écrire deux unités systemd : clipfactory-api.service et clipfactory-worker.service
   - api : `uvicorn app.main:app --host 127.0.0.1 --port 8000` dans /opt/clipfactory-api/.venv
   - worker : `python -m app.main` dans /opt/clipfactory-worker/.venv
5. Caddyfile : reverse proxy api.clipfactory.app → localhost:8000, TLS automatique
6. systemctl enable + start, vérifier `curl https://api.clipfactory.app/health` = {"status":"ok"}
7. Tester la connexion DB depuis le serveur : `psql $DATABASE_URL -c 'select count(*) from jobs'`
8. Documenter la procédure dans docs/deploy.md (sections "Step 5 bare metal" / "Step 5 docker"), avec les chemins systemd réels utilisés.

Livrable : push une branche `deploy/hetzner-setup` avec :
- Un dossier infra/ contenant les unités systemd, le Caddyfile, et un script bootstrap.sh idempotent
- docs/deploy.md mis à jour avec la procédure exacte
- docs/handoff-codex.md section 4 : cocher T32 + ajouter entrée datée au journal section 5

═══════════════════════════════════════════════════════════════════

P1 — FIX 5 MEDIUM SECURITY (avant ouverture publique)

Voir docs/security-audit.md sections M1 à M5. Les 3 High sont déjà fix.

M1 — Content-Security-Policy + security headers (apps/web)
  Fichier : apps/web/next.config.ts
  Ajouter une fonction async headers() qui pose : X-Frame-Options DENY, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy camera=() microphone=(), Content-Security-Policy strict.
  CSP de départ proposé dans docs/security-audit.md M1 — ajuste selon ce que Supabase + Stripe injectent réellement. Test : Chrome DevTools console → 0 erreur CSP sur toutes les pages.

M2 — CORS prod guard (apps/api)
  Déjà partiellement fait dans apps/api/app/main.py::_assert_safe_cors — vérifie que tout est OK en passant ENV=prod + CORS_ALLOW_ORIGINS=* dans un test local. Doit refuser de démarrer.

M3 — Stripe webhook tolerance
  Rien à changer. Documente juste dans docs/api-contract.md que la tolérance Stripe par défaut (5 min) + l'idempotency via stripe_events.event_id PK suffit.

M4 — Cloudflare Turnstile sur /login (anti-bot magic-link)
  - Côté Cloudflare : créer un widget Turnstile, récupérer la site key et la secret key.
  - Côté web : ajouter le script Turnstile + un widget invisible sur apps/web/app/login/login-form.tsx.
  - Côté backend : impossible de vérifier le token dans Supabase Auth directement sans un Edge Function — préfère côté API : ajouter un endpoint POST /auth/turnstile/verify qui prend le token, le valide contre l'API Turnstile, et qui doit être appelé AVANT signInWithOtp / signInWithOAuth depuis le client. Si invalide → bloquer.
  - Variables : TURNSTILE_SITE_KEY (public), TURNSTILE_SECRET_KEY (api), à ajouter aux .env.example.

M5 — Scrub user emails dans les logs
  - apps/api : ajouter un structlog processor qui détecte les patterns email (regex \b[\w.+-]+@[\w-]+\.[\w.-]+\b) dans les log values et les hash en SHA256 prefixé par "email_sha256:".
  - apps/worker : pareil.
  - Tester en log un message qui contient un email et vérifier qu'il sort hashé.

Livrable : push une branche `security/medium-fixes` avec les 5 fixes, un commit par M, et docs/security-audit.md mis à jour (cocher chaque M, mettre à jour la checklist pre-prod en bas du doc).

═══════════════════════════════════════════════════════════════════

P2 — SMOKE TEST E2E AUTOMATISÉ (Playwright)

Objectif : un script Playwright qui exécute les 11 étapes du handoff section 10 contre un déploiement live (staging ou prod) et qui retourne PASS/FAIL.

Travail :
1. Nouveau dossier apps/e2e/ avec un package.json séparé, Playwright installé.
2. Écrire test/smoke.spec.ts qui :
   - Sign up via magic-link (mode test Supabase, utiliser un email Mailtrap ou similaire pour récupérer le lien)
   - OU sign in via Google si Turnstile permet le bot — sinon skip cette branche en smoke.
   - Stripe Checkout en mode test, carte 4242 4242 4242 4242, vérifier credits arrivés.
   - Créer une campagne.
   - Submit une vidéo YouTube courte (Big Buck Bunny, ~ 1 min).
   - Poll /jobs/:id jusqu'à status = completed (timeout 5 min).
   - Vérifier que 1 à 3 clips sont visibles, score_breakdown présent, segments[].length >= 1.
   - Download du clip (présigned R2 URL), vérifier HTTP 200 + content-type video/mp4.
   - Donner un thumbs up.
3. Workflow GitHub Actions .github/workflows/smoke.yml qui lance Playwright sur le déploiement après chaque push sur main.

Livrable : push une branche `e2e/playwright-smoke`. README dans apps/e2e/ avec instructions pour lancer en local (BASE_URL=... npx playwright test).

═══════════════════════════════════════════════════════════════════

P3 — MONITORING MVP

Objectif : être alerté si l'API tombe ou si le worker crash ou si plus de 5 jobs échouent en 1h.

1. Uptime Robot ou Better Uptime — créer 2 monitors HTTP :
   - GET https://api.clipfactory.app/health → 200 toutes les 5 min, alert email + SMS si down 2× consécutifs
   - GET https://clipfactory.app → 200 toutes les 5 min
2. Sentry (free tier OK) — créer 2 projets : clipfactory-api (Python), clipfactory-web (Next.js).
   - apps/api : pip install sentry-sdk[fastapi], init dans main.py avec dsn depuis env SENTRY_DSN_API.
   - apps/web : npm install @sentry/nextjs, configurer instrumentation.ts.
3. Cron alert jobs failed : créer un cron Hetzner qui exécute toutes les heures :
   `psql $DATABASE_URL -tc "select count(*) from jobs where status='failed' and queued_at > now() - interval '1 hour';"`
   et si > 5, envoie un email via Resend ou un curl à un webhook Slack.

Livrable : branche `monitoring/setup`, docs/deploy.md mis à jour avec une section Monitoring contenant les URLs des dashboards.

═══════════════════════════════════════════════════════════════════

P4 — POLISH UI MARKETING (basse priorité, après les 3 premiers payants)

Bullet list de ce qui peut être amélioré, dans l'ordre :
1. Hover transitions plus douces sur les boutons (Tailwind transition-colors duration-150).
2. Loading skeleton sur PublicStats (pendant le fetch initial — actuellement on affiche "—").
3. Animation d'entrée subtile sur les cards "How it works" (fade + translate-y) avec Intersection Observer.
4. Page /pricing : tooltips détaillés sur les features de chaque plan.
5. Page /features : ajouter une mini démo visuelle par feature (screenshot ou loop GIF).
6. Page /faq : accordion expand/collapse au lieu de tout afficher en list.

Pas obligatoire V1, à toi de voir si tu finis les P0-P3 d'abord.

═══════════════════════════════════════════════════════════════════

FORMAT DE RAPPORT

Après chaque tâche P0/P1/P2/P3 terminée :
1. Push une branche dédiée (pas de force-push sur main).
2. Update docs/handoff-codex.md : cocher la task section 4, ajouter une entrée datée au journal section 5 avec un résumé court (3-5 bullets max), garder l'append-only.
3. Si tu bloques sur un truc (credentials manquants, ambiguïté, dépendance externe), ajoute une entrée précise dans section 11 "Blockers" du handoff avec ce qu'il te faut.
4. Ne crée pas de PR vers main automatiquement — laisse Augustin / Claude reviewer et merger.

Commence par P0. Pose des questions de clarification AVANT de coder si quelque chose dans le brief est ambigu.
```

---

## Notes pour Augustin

- Ce brief est fait pour être copié-collé tel quel à Codex.
- Codex va naturellement lire les fichiers cités → pas besoin de lui re-expliquer le projet.
- S'il pose des questions pendant le travail, oriente-le vers `docs/handoff-codex.md`.
- Les 4 priorités P0 → P3 sont dans l'ordre logique. P0 (deploy) débloque P1 + P2.
- P4 (polish) peut totalement attendre — ne le laisse pas s'y perdre avant qu'on ait un payant.
