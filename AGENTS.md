# ClipFactory — contexte projet pour les agents (Codex, Claude, autres)

> Lu automatiquement au début de chaque session. Court par design : les détails sont dans `docs/` (index : `docs/README.md`).
> Dernière mise à jour : 2026-09-29.

## Le projet en 5 lignes

SaaS web qui transforme des vidéos longues (podcasts, interviews, face-caméra ; FR + EN) en **clips verticaux courts**, choisis et montés **pour une campagne** (audience, niche, ton, objectif), avec un score expliqué et un feedback par clip. Cibles : créateurs et **clippeurs pro** (payés à la vue). Objectif business : 1 000 € MRR ≈ 35 clients (Starter 29 €/mois, Pro 79 €/mois).
Fondateur : Augustin (designer / product, ne code pas ligne à ligne). Parle-lui **en français, simplement** ; code, commits et noms de fichiers **en anglais**.

## Monorepo

| Dossier | Rôle |
|---|---|
| `apps/web` | Next.js (Vercel : `clipfactory-saas.vercel.app`) |
| `apps/api` | FastAPI : auth, campagnes, jobs, séries, clips, crédits, Stripe |
| `apps/worker` | Pipeline Python : download → ASR → sélection LLM → vision → score → rendu EDL/FFmpeg → sous-titres → QC → stockage local (plus de R2 depuis le 29/09 ; l'API sert les clips via URL signées) |
| `db/migrations` | Schéma Supabase (Postgres EU) |
| `docs/` | Toute la doc — commencer par `docs/README.md` |
| `ops/macos/` | Services launchd du Mac Studio (voir `docs/mac-studio-backend.md`) |

## Règles d'or (ne jamais casser)

1. **L'horloge des coupes, c'est le transcript mot à mot.** Aucune seconde produite par un LLM ne part dans FFmpeg : le modèle cite des mots, le code les ancre sur les timestamps de l'ASR (`boundaries.anchor_arcs_to_transcript`).
2. **Pipeline > UI.** Entre une belle interface et une pipeline fiable, toujours la pipeline.
3. **Le repo est PUBLIC.** Jamais de `.env`, de clé, de nom de prospect ou de client, de contenu de DM, ni de rapport décrivant une faille de sécurité. Ces documents vivent hors repo (`~/data clips/docs-prives/` sur le Mac d'Augustin).
4. **Jamais de push sur `main`, de force-push ou de merge par un agent.** Une branche par sujet, PR en brouillon ; Augustin merge.
5. **Pas de migration ni d'écriture en base de prod** sans demande explicite. Le schéma de prod inclut déjà `20260907150016_restrict_client_job_and_profile_writes` (appliquée le 29/09).
6. **Modèles : une seule source de vérité** (`apps/worker/models.lock.toml`, lu par `settings.py` ; surcharge possible par variable d'environnement). Aucun modèle par défaut ne doit pointer vers un modèle qui expire (OpenRouter : `qwen3-vl-32b-instruct` le 09/10/2026, `gemini-2.5-flash` le 20/10/2026). Un modèle ne change que s'il **gagne au banc de test**, pas sur une annonce.
7. **Tester les modèles par groupes** : une stack complète par groupe, la même campagne de A à Z, et on juge les clips produits (pas de choix sur un banc d'étape isolée). Toujours sur le pipeline à sa meilleure version, figé sous un tag `pipeline-vtest-…` ; jamais un changement de pipeline et de modèle dans la même comparaison. Plan : `docs/model-test-plan.md`.
8. **Tester comme un vrai client** : Augustin lance les jobs depuis le site ; l'agent regarde les logs. Pas d'insertion manuelle en base pour « aider » un test.
9. **Pas d'abonnement ChatGPT/Codex comme moteur du SaaS** : le SaaS utilise des clés API (OpenRouter, OpenAI, Anthropic).
10. **Pas de code spéculatif.** Ce qui n'est pas branché au runner et mesuré n'est pas « fait ».

## État au 29/09/2026

- **Prod** : web sur Vercel ; API + worker **pas encore hébergés** → chantier en cours : tout sur le **Mac Studio M1 Max** (runbook `docs/mac-studio-backend.md`).
- **`main`** (75b1a76) : séries multi-sources (plan Pro) mergées. Le moteur de rendu EDL/V2 est présent mais **pas appelé** par le runner.
- **Consolidation** : PR #8 (`consolidate/pipeline-v1`, brouillon) — rendu via `clip_render`/EDL, ancrage strict, QC média, crédits atomiques (jeton de tentative, réservation `FOR UPDATE`, remboursement = débit net réel), séries multi-sources préservées, `apps/worker/models.lock.toml` (provisoire), correctif des mots whisper de durée nulle, `clip_judge.py` (désactivé), CI `pipeline-quality.yml`. 457 tests worker verts.
- **Carte du pipeline** : `docs/pipeline-map-2026-09-29.md` — où vit la meilleure version de chaque étape, ce que la prod exécute vraiment, ordre de consolidation.
- **Branches d'archive** (ne pas développer dessus, lire seulement) : `codex/full-stack-benchmark-2026-09-12` (Director 2.2 / Second Brain, non branchés), `codex/clipping-quality-2026-09-05`, `teste-pipeline`, `archive/pricp-prototype-2026-08-09`, `archive/draft/parallel-workers`, `archive/deploy/hetzner-setup`, `archive/infra/vps-bootstrap`.
- **PR ouvertes** : #5 (UI edit-axis), #3 (Vercel Analytics), #7 (pages SEO déjà en ligne).
- **Jamais mesuré à ce jour** : taux de clips publiables jugé par un humain ; job réel de bout en bout en prod. C'est la priorité avant toute nouvelle fonctionnalité.

## Commandes utiles

```bash
apps/worker/.venv/bin/pytest apps/worker -q
apps/api/.venv/bin/pytest apps/api -q
cd apps/web && npm run build
```

Sur le Mac d'Augustin, `/usr/bin/git` peut être bloqué par la licence Xcode : utiliser `/Library/Developer/CommandLineTools/usr/bin/git`.
