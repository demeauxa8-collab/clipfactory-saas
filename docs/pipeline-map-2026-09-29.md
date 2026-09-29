# Carte du pipeline ClipFactory — 29 septembre 2026

Étape 1 du plan de consolidation (carte → `models.lock` → test golden). Inventaire en lecture seule du Mac, de GitHub et de 110 sessions Codex. Rien n'a été modifié, déplacé ou relancé pour l'établir.

## En une phrase

La meilleure version de presque chaque étape existe, mais **elle n'est commitée nulle part** : elle vit dans le worktree `~/clipfactory-full-stack-test`, pendant que la prod (`origin/main` 75b1a76) tourne sur l'ancien chemin de rendu, avec des modèles que les bancs de septembre déconseillent, sans aucun test Python en CI.

## 1. Où est le code

13 copies du pipeline sur le Mac, 7 versions distinctes de `runner.py`, **2 dépôts git** pour le même projet.

| Abrév. | Emplacement | Base | État | Verdict |
|---|---|---|---|---|
| **MAIN** | `origin/main` 75b1a76 (worktree `~/clipfactory-multi-source`) | 29/09 | Prod. Multi-source mergé. Rendu legacy. | **Base de consolidation** |
| **FST** | `~/clipfactory-full-stack-test` | f17e129 + ~1 900 lignes modifiées + 30 modules non suivis (~19 400 l.) | Rien de commité. Modif. jusqu'au 25/09. | **Source principale à reporter** |
| CQ | `~/clipfactory-clipping-quality` | f17e129 | Sous-ensemble strict de FST (`git diff` identique à l'octet) | Doublon → archiver |
| TP | `~/clipfactory-test-pipeline` | f17e129 | Copie du 07/09, plus ancienne que CQ (+ `archives/` 829 Mo dont l'ancien app Mac) | Doublon → archiver |
| PRICP | `~/Documents/autre/ChatGPT/clips factory saas pricp` | c1cb783 (07/08), **2ᵉ dépôt git** | 78 fichiers non suivis : Second Brain d'origine (09/08) | Déjà copié dans FST → archiver |
| SAAS | `~/clipfactory-saas` (`main` local) | f17e129 | 9 commits de retard | À mettre à jour (`pull`) |
| WTFT | `.claude/worktrees/free-trial-paywall` | 254de07, poussé | Paywall trial, `outbound.py`, migration `0006_free_trial` (collision de n°) | À reporter (entitlements + outbound) |
| — | branche locale `draft/parallel-workers` | 26/06, 55 commits de retard | Leasing/reaper/supervisor, migration `0005_job_leasing` (collision) | Plus tard (scalabilité) |
| — | branche `codex/architecture-backend` | eac742b, poussé | +34 l. `openrouter.py` (repli si `reasoning` refusé) + 5 docs | À reporter (petit) |
| SEO, GSC, UIR | `~/clipfactory-seo`, `~/clipfactory-gsc-verify`, `~/Documents/Codex/2026-08-21/clipfactory-ui-redesign` | web uniquement | SEO **déployé depuis un worktree sale** | Hors pipeline — commiter le SEO séparément |
| RED, BEI | `~/clipfactory-redesign`, `~/clipfactory-beige` | mai–juin | Pipeline v1 (11 modules) | Archiver |
| DL | `~/Downloads/clipfactory-saas-main` | zip de f17e129 | Pas un dépôt | Supprimable |
| DATA | `~/clipfactory-data/campaigns/*/scripts`, `bench/*.py` | — | Scripts de campagne **forkés et non versionnés** | Rapatrier dans `apps/worker/scripts/` |

`~/ClipFactory` (ancien bot Mac) n'existe plus : il reste `~/ClipFactory.zip` et une copie dans `TP/archives/local/legacy-desktop/`.

## 2. La carte, étape par étape

« Prod » = ce que `origin/main` exécute vraiment (fermeture des imports depuis `main.py → run_job`). « Meilleure » = meilleure version existante avec preuve.

| # | Étape | Prod (origin/main) | Meilleure version existante | Où | Preuve | Décision |
|---|---|---|---|---|---|---|
| 1 | Ingestion | `ffmpeg.yt_dlp_download` + garde SSRF + canonicalisation YouTube | = prod | MAIN | tests | **Garder MAIN** |
| 2 | Transcription | `transcribe.py`, whisper-1 | = prod | partout identique | 21/08, 27/09, 28/09 : aucun ASR ne bat whisper-1 en FR | **Garder**. Corriger `.env.example` (dit `gpt-4o-mini-transcribe`, cassé) |
| 3 | Sélection candidats | `story_arcs` + `analyze`, gemini-2.5-flash | même code, autre modèle | MAIN | 27/09 : seul gemini-3.8-flash passe les contrôles de citation ; 2.5-flash échoue le multi-source | Garder le code, **modèle à trancher au golden** (2.5 vs 3.8) |
| 4 | Vérif. arcs | `verify.py` 94 l. | `verify.py` 119 l. (vérif. par couverture) | FST | 2 → 0 coupes mi-mot | **Reporter FST** |
| 5 | Ancrage / bornes / snap | `boundaries.py` 1003 l. | `boundaries.py` 1044 l. (ancrage strict) | FST | idem | **Reporter FST** |
| 6 | Vision | `video_map` + `vision`, qwen3-vl-32b | = prod | partout identique | 08/08 : Qwen 73 évts/0,003 $ vs Gemini 67/0,012 $ | **Garder** |
| 7 | Score / classement | `score.py` 1222 l. | = prod | MAIN | **aucune évaluation qualité** | Garder, à mesurer |
| 8 | Director / Second Brain / recherche | absent | `editorial_director_v22`, `editorial_beats`, `editorial_reflex_qc`, `editorial_knowledge`, `knowledge_*`, `campaign_research_*`, `*_authority` (27 modules, ~20 000 l.) | FST (seul) | Fins suspendues 3/3 → 0/3 sur **un seul** run de 3 clips ; payoff perdu sur 1 ; 7 tests en échec dans PRICP ; **jamais appelé par le runner** | **Reporter sur branche, désactivé par défaut**. N'entre qu'en gagnant au golden |
| 9 | Montage / rendu | `ffmpeg.render_montage_clip` (legacy). `editor_v2`, `edl*` présents mais **jamais appelés** | `clip_render` → `editor_v2` → `edl` / `edl_render` (EDL actif, rendu 1 passe) | FST | QC technique 7/7 ; 3 versions d'`edl.py` divergentes (MAIN 818, FST 980, PRICP 970) | **Reporter FST** |
| 10 | Sous-titres | `captions.py` (ASS legacy) | `edl_captions` 588 l. (sans chevauchement, 2 lignes) | FST | replay 05/09 | **Reporter FST** |
| 11 | Cadrage | fit_blur / face crop statique | = prod | MAIN | 28/09 : bandes noires sur Gaspar ; recadrage vision non actif | **Ouvert** — après golden |
| 12 | Audio / musique | `audio_*` présents, jamais rendus | = prod | MAIN | aucune | Laisser dormant |
| 13 | QC | `validate_rendered_clip` | QC média étendu (noir/silence) + `editorial_qc` | FST | 7/7 | **Reporter FST** |
| 14 | Juge de clip | **absent** | **absent partout** | — | 07/08 : gemini-3.6-flash vidéo 6/6 publiables, 11/12 bords, 0,0115 $/clip | **À construire** — c'est le juge du golden |
| 15 | Jobs / crédits | BLPOP Redis, débit non atomique, remboursement possible sans débit (B01) ; séries `SKIP LOCKED` | `job_state` (réservation `for update`), `job_artifacts`, annulation, timeouts sous-processus | FST **+** MAIN | tests Postgres des deux côtés | **Fusionner les deux corrections** (conflit certain dans `runner.py`/`main.py`) |
| 16 | Multi-source | `series_queue.py` (une source par clip) | = prod | MAIN | 14 tests | **Garder MAIN**. Montage cross-source : banc seulement |
| 17 | Provider LLM | `openrouter.py` 173 l. | 231 l. (repli `reasoning`) | FST / architecture-backend | — | **Reporter** |
| 18 | Sécurité DB | `profiles.is_admin` modifiable par `anon`/`authenticated` (**vérifié en prod le 29/09**) | migration `20260907150016_restrict_client_job_and_profile_writes.sql` | FST, CQ (non suivie) | — | **Appliquer en premier** |
| 19 | Bench / scripts | `render_v2_fixture_variants.py` | `benchmark_clipping`, `compare_full_stack`, `full_stack_benchmark`, `render_matched_comparison` + scripts campagne DATA | FST, DATA | — | Reporter FST ; rapatrier DATA |
| 20 | CI | `smoke.yml` (toujours `skipped`), keepalive | `pipeline-quality.yml` | FST | — | **Reporter** — la CI doit lancer pytest |

## 3. Modèles : ce qui tourne vs ce que les bancs disent

| Étape | Prod (`settings.py`) | `.env.example` | Verdict des bancs | Proposition `models.lock` (à confirmer au golden) |
|---|---|---|---|---|
| ASR | whisper-1 | gpt-4o-mini-transcribe ❌ | whisper-1 seul fiable en FR | **whisper-1** |
| Sélection / verify / score | gemini-2.5-flash | deepseek-chat-v3.2 ❌ (retiré) | gemini-3.8-flash seul valide en multi-source (27/09) | **duel 2.5-flash vs 3.8-flash** au golden |
| Vision deep + cheap | qwen3-vl-32b | gemini-2.5-flash / qwen3-vl-flash ❌ (retiré) | qwen3-vl-32b retenu le 08/08 | **qwen3-vl-32b** |
| Juge | — | — | gemini-3.6-flash vidéo (07/08) | **gemini-3.6-flash** (à construire) |
| Secours | claude-haiku-4.5 | idem | jamais mesuré | haiku-4.5 |

Rejetés avec preuve : gpt-4o-mini-transcribe, gpt-transcribe, Groq whisper-large-v3, Voxtral (OpenRouter), AssemblyAI (FR), Qwen3-ASR 1.7B, famille flash-lite, gemini-3-flash-preview, qwen3.7-flash, minimax-m3, qwen3.8-omni-flash, gpt-5.4-mini, deepseek-chat-v3.2, qwen3-vl-flash. Deepgram Nova-3 : secours anglais seulement (WER FR 23,7 %).

## 4. Ce qui n'a jamais été mesuré

- **Aucun taux de clips publiables jugé par un humain** : `reviews.template.jsonl` du 12/09 contient 7 fiches toutes à `null`.
- **Aucun job réel de bout en bout** queue → API → worker → R2 → facturation. `api.clipfactory.app` ne résout pas.
- Le re-run « A à Z » du 28/09 n'est **pas reproductible** : exécuté hors runner, sans script conservé, 2 clips sur 6 corrigés à la main.
- Les runs sur la source Gaspar (595 s, job `2221f645`) sont comparables entre eux, mais **aucun n'utilise le même code**.

## 5. Ordre de consolidation proposé

1. **Sécurité** — appliquer la migration RLS en prod (seule action urgente, indépendante du reste).
2. **Sauvegarde** — commiter FST tel quel sur une branche poussée (`archive/full-stack-2026-09-25`), et archiver CQ, TP, PRICP. Plus rien ne dépend du disque.
3. **Branche `consolidate/pipeline-v1`** depuis `origin/main` 75b1a76, reporter dans cet ordre :
   a. `verify`, `boundaries`, `edl*`, `editor_v2`, `clip_render`, `edl_captions`, QC média (lot « qualité », rendu EDL actif) ;
   b. `job_state` / `job_artifacts` réconciliés avec les corrections crédits/séries de MAIN ;
   c. `openrouter.py` (repli `reasoning`), `.env.example` alignés sur `settings.py` ;
   d. `pipeline-quality.yml` + tests ;
   e. Director / Second Brain derrière un flag **désactivé**.
4. **`models.lock`** (étape 2) puis **`make golden`** (étape 3) : 3 sources fixes (Gaspar FR, Latasha EN, un podcast FR), juge gemini-3.6-flash + revue humaine, métriques fixes. Le Director et gemini-3.8-flash n'entrent que s'ils gagnent.
5. Paywall trial + `outbound.py` (WTFT), migrations renumérotées.

## 6. Documents sources

- Rapports Codex : `docs/inventaire-code-conversation-2026-09-05.md`, `docs/audit-consolidation-backend-clipping-2026-09-05.md` (non suivis dans `~/clipfactory-saas`), `~/clipfactory-clipping-quality/docs/clipping-quality-strategy-2026-09-12.md`, `~/clipfactory-data/full-stack-run-2026-09-12/REPORT.md`.
- Bancs : `docs/model-landscape.md`, `~/clipfactory-data/bench/multisource-2026-09-27/rapport.md`, `~/clipfactory-data/bench/full-rerun-2026-09-28/REPORT.md`.
- Campagne : `~/clipfactory-data/campaigns/tFNkSz9z8jg-2026-09-20/`.
