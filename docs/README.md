# Documentation ClipFactory — index

> Point d'entrée de la doc. Contexte court pour les agents : `AGENTS.md` à la racine.
> Mise à jour : 2026-09-29.

## Commencer ici

| Doc | Pour quoi |
|---|---|
| [`pipeline-map-2026-09-29.md`](pipeline-map-2026-09-29.md) | **Carte du pipeline** : chaque étape, ce que la prod exécute, la meilleure version existante et où, modèles, ordre de consolidation |
| [`mac-studio-backend.md`](mac-studio-backend.md) | **Runbook en cours** : API + Redis + worker + ASR local sur le Mac Studio M1 Max, exposé par Tailscale Funnel |
| [`v1-scope.md`](v1-scope.md) | Ce qui est dans / hors V1 (source de vérité du périmètre) |
| [`handoff-codex.md`](handoff-codex.md) | Journal historique détaillé (état au 07/08 ; l'état courant est dans `AGENTS.md`) |

## Architecture

| Doc | Contenu |
|---|---|
| [`infrastructure.md`](infrastructure.md) | Découpage control plane / worker, phase actuelle tout-sur-le-Mac |
| [`deploy.md`](deploy.md) | Comptes, Stripe, R2, Vercel, Supabase auth, VPS (futur) |
| [`pipeline.md`](pipeline.md) | Séquencement du worker (chemins simple / story), scoring, continuité |
| [`api-contract.md`](api-contract.md) | Endpoints et payloads |
| [`db-schema.md`](db-schema.md) | Invariants et migrations |
| [`multi-source-series-rollout.md`](multi-source-series-rollout.md) | Séries multi-sources (plan Pro) |
| [`global-video-understanding.md`](global-video-understanding.md) | Compréhension vidéo globale |
| [`pipeline-improvements.md`](pipeline-improvements.md) | Pistes d'amélioration pipeline |

## Modèles et coûts

| Doc | Contenu |
|---|---|
| [`model-landscape.md`](model-landscape.md) | Paysage modèles mesuré (07/08) : ASR, vidéo native, juge |
| [`unit-economics.md`](unit-economics.md) | Coût par job, marge |

Les résultats de bancs récents (27/09, 28/09, banc du 29/09 en cours) vivent hors repo, dans `~/data clips/bench/` sur le Mac d'Augustin ; leurs conclusions sont reportées dans `pipeline-map-2026-09-29.md` et `models.lock`.

## Produit, web, ops

| Doc | Contenu |
|---|---|
| [`admin.md`](admin.md) | Dashboard admin |
| [`analytics.md`](analytics.md) | Événements analytics |
| [`seo.md`](seo.md) | SEO |
| [`security-audit.md`](security-audit.md) | Audit de sécurité (historique) |
| [`plan.md`](plan.md) | Plan produit |
| [`codex-brief.md`](codex-brief.md) | Brief historique pour Codex |

## Hors repo (privé, sur le Mac d'Augustin)

`~/data clips/docs-prives/` : audits Codex du 05/09, historique depuis août, concept « Second Brain de campagne et montage viral », recherches modèles. Non publiés parce que le repo est public (prospects, stratégie, détails de sécurité).
