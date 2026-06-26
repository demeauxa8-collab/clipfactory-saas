# Validation locale — premier vrai clip

Objectif : faire tourner la pipeline ClipFactory sur **une vraie vidéo YouTube** en local, sans toucher à R2, Stripe, Hetzner ni domaine. Coût estimé : **~10 $** (OpenAI + OpenRouter combinés sur une vidéo de 5–10 min).

Si les clips produits sont regardables → on déploie. Sinon → on corrige avant de claquer 40 €/mois d'infra.

---

## 0. État de la prep (déjà fait pour toi)

- Code patché : le worker peut écrire les clips sur disque (`STORAGE_BACKEND=local` → `/tmp/clipfactory-clips`). Plus besoin de R2 pour cette étape.
- `apps/worker/.env` mis à jour avec `STORAGE_BACKEND=local`.
- Binaires `redis-server` et `ffmpeg` installés via brew (`yt-dlp` est déjà dans le venv worker).
- Migrations Supabase 0001→0004 déjà appliquées sur le projet `jsjaizcnjvghoduvyyea`.

**Tu n'as plus qu'à coller 2 clés et lancer 4 commandes.**

---

## 1. Récupérer les 2 clés (cet aprem, ~15 min)

Onglets à ouvrir dans Chrome :

| Service | URL | Action | Coût initial |
| --- | --- | --- | --- |
| OpenAI | `https://platform.openai.com/api-keys` | Sign up → **Billing → Add credit balance** (5 $ suffit) → **API keys → Create new** | 5 $ |
| OpenRouter | `https://openrouter.ai/settings/keys` | Sign up (Google OK) → **Credits → Top up** (5 $ suffit) → **Keys → Create Key** | 5 $ |

Garde les 2 clés sous la main, format :
- OpenAI : `sk-proj-…` ou `sk-…`
- OpenRouter : `sk-or-v1-…`

---

## 2. Coller les clés dans `apps/worker/.env`

Édite **2 lignes** (les autres sont déjà OK) :

```
OPENAI_API_KEY=sk-proj-<colle ici>
OPENROUTER_API_KEY=sk-or-v1-<colle ici>
```

> Anthropic (fallback) reste en `sk-ant-TODO`. C'est OK : `ENABLE_FALLBACK=true` mais l'OpenRouter primary couvre tout le pipeline. Le fallback ne se déclenche que sur erreur, et dans ce cas le job échouera proprement plutôt que de faire un appel Anthropic vide.

---

## 3. SQL une fois — accorder un abonnement et des crédits à ton compte

Tu vas signer dans l'app via magic-link (étape 5) pour créer ta ligne `auth.users`. Une fois ça fait, ouvre Supabase SQL Editor sur le projet `clipfactory` et colle :

```sql
-- 1) Active subscription Starter + 300 crédits pour demeauxa8@gmail.com
with u as (
  select id from auth.users where email = 'demeauxa8@gmail.com'
)
insert into subscriptions (user_id, plan_code, status, current_period_end)
select id, 'starter', 'active', now() + interval '1 year' from u
on conflict (user_id) do update
  set plan_code='starter', status='active',
      current_period_end=now() + interval '1 year';

with u as (
  select id from auth.users where email = 'demeauxa8@gmail.com'
)
insert into credit_ledger (user_id, delta, reason, note)
select id, 300, 'manual_grant', 'local validation' from u;

-- 2) Vérif
select email, (select sum(delta) from credit_ledger where user_id = u.id) as credits
  from auth.users u where email = 'demeauxa8@gmail.com';
```

Doit retourner `credits = 300`.

---

## 4. Lancer les 4 process (4 terminaux séparés)

```bash
# Terminal A — Redis
redis-server

# Terminal B — API
cd /Users/augustindemeaux/clipfactory-saas/apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal C — Worker (le plus important — c'est lui qui produit les clips)
cd /Users/augustindemeaux/clipfactory-saas/apps/worker
.venv/bin/python -m app.main

# Terminal D — Web
cd /Users/augustindemeaux/clipfactory-saas/apps/web
npm run dev
```

Le worker doit logger `worker.ready` au démarrage.

---

## 5. Lancer une vraie vidéo

1. Ouvre `http://localhost:3000/login`, sign up avec `demeauxa8@gmail.com` → clique le magic-link reçu par mail.
2. Tu atterris sur `/app`. Si tu vois `0 credits` → tu as oublié l'étape 3, retournes-y.
3. Va sur `/app/campaigns/new` → crée une campagne (ex : audience = "créateurs tech", niche = "lifestyle", ton = "punchy", goal = "growth"). Save.
4. Va sur la fiche campagne → soumets **une vidéo YouTube courte (3-4 min)** pour commencer. Suggestions :
   - Court trailer : `https://www.youtube.com/watch?v=W5tKLAB1XCQ` (Inception trailer, 2:32)
   - Court interview : choisis n'importe quelle vidéo YouTube < 5 min, publique, sans age-gate.
5. Page `/app/jobs/<id>` : la progression défile (`downloading → transcribing → analyzing → rendering → completed`).

Quand le job est `completed` :
```bash
open /tmp/clipfactory-clips/clips/$(ls /tmp/clipfactory-clips/clips/)/
```

Tes 3 clips MP4 sont là. Ouvre-les dans QuickTime.

---

## 6. Vidéo longue (chemin story-first)

Une fois la pipeline simple validée, relance avec une vidéo **≥ 5 min** pour tester le chemin story (multi-segments) :
- Podcast court : `https://www.youtube.com/watch?v=8jPQjjsBbIc` (Jocko Willink, ~10 min, anglais punchy)
- Ou n'importe quelle vidéo YouTube > 5 min.

Le worker passe alors par `video_map` → `story_arcs` → `verify_arcs` → `deep_vision`. Le coût grimpe (15-30 cents par vidéo de 10 min), mais c'est le vrai différenciateur produit.

---

## 7. Si ça plante

| Symptôme | Solution |
| --- | --- |
| `worker.bad_payload` | Tu as poussé un mauvais JSON dans Redis — non, ne fais pas ça, passe par l'API |
| `pipeline.failed step=download` | URL YouTube invalide ou vidéo en age-restricted/private — change |
| `pipeline.failed step=transcribe` | Clé OpenAI vide ou pas de crédit → recharge billing |
| `pipeline.failed step=video_map`/`story_arcs` | Clé OpenRouter vide ou pas de crédit → recharge top up |
| Clip vide à `0 bytes` | FFmpeg a planté sur le concat — check le log worker, partage-le |
| Pas de magic-link reçu | Supabase rate-limit sur les magic-links — attends 1 min, retry |

Logs worker en JSON. Pour les lire propre :
```bash
.venv/bin/python -m app.main | jq -R 'fromjson? // .'
```

---

## 8. Ce qu'on regarde après le premier clip

- **Score breakdown** : est-ce que la pondération produit des choix qui ont du sens ?
- **Hook texte proposé** : est-ce que ça donne envie de cliquer ?
- **Cohérence du montage** sur le chemin story : le setup mène-t-il au payoff ?
- **Coût** : check `select total_cost_estimate_cents from jobs order by finished_at desc limit 1;` — si > 50 cents pour 10 min, faut ajuster avant prod.
- **Captions** : burn-in ASS lisible, bonne synchro ?

À partir de là, on décide : déploiement, ou itération sur les prompts/scoring.
