# B0 — Référence mesurée (golden)

> Spec pour **Codex sur le Mac Studio**. Étape B0 de `docs/roadmap.md`. Lis aussi `AGENTS.md` et `docs/model-test-plan.md`.
> Branche : `feat/b0-golden` (cette spec en est le premier commit). PR en brouillon vers `main`. **Tu ne merges pas, tu ne déploies pas.** Les échanges passent par la PR (description = ton rapport ; Claude répond en commentaires ; `@augustin` = question bloquante).

## Objectif

Savoir, chiffres à l'appui, **combien de clips sont publiables aujourd'hui**, et disposer d'un banc qui rejoue exactement le même test après chaque changement (B1, B2…, puis la phase C).

Livrables : (0) le Studio sur des modèles qui ne vont pas disparaître, (1) les vidéos de référence figées, (2) un harnais qui fait tourner le **vrai pipeline** dessus, (3) des métriques automatiques, (4) le juge de clip en observation, (5) une page où Augustin note les clips, (6) le calcul d'accord juge ↔ Augustin.

## Règles

- **Aucun appel payant dans les tests unitaires** (fournisseurs mockés). Les runs golden réels sont payants : **plafond 3 $ par run complet**, coût total affiché dans le rapport.
- **Aucune écriture dans la base de prod**, aucun crédit client consommé : le harnais utilise une **Postgres jetable locale** (même mécanique que la CI : `tests/integration/apply_schema.py`).
- **Ne pas modifier le comportement du pipeline** dans B0 (pas de correctif de fins, de prompts, de cadrage : c'est B1+). B0 mesure l'existant.
- Le repo est public : **la liste des vidéos golden et les clips produits restent hors repo** (`~/clipfactory-golden/` sur le Studio).

## 0. Prérequis : modèles durables

Le `.env` du worker force aujourd'hui `PRIMARY_TEXT_MODEL=google/gemini-2.5-flash` (retiré d'OpenRouter le 20/10) et `PRIMARY_VISION_DEEP_MODEL` / `VISION_CHEAP_MODEL=qwen/qwen3-vl-32b-instruct` (retiré le **09/10**). Une référence mesurée sur des modèles morts ne sert à rien.

1. `~/clipfactory-prod` sur `main` (`git switch main && git pull --ff-only`, `ops/macos/update.sh`, `doctor` vert).
2. Dans `apps/worker/.env` du Studio, **supprimer** les lignes `OPENAI_TRANSCRIBE_MODEL`, `PRIMARY_TEXT_MODEL`, `PRIMARY_VISION_DEEP_MODEL`, `VISION_CHEAP_MODEL`, `FALLBACK_TEXT_MODEL`, `FALLBACK_VISION_MODEL` → c'est `apps/worker/models.lock.toml` qui s'applique (provisoire jusqu'à la phase C). Ne pas afficher le reste du fichier. Redémarrer le worker.
3. **Tracer les modèles réellement utilisés** : à chaque job, écrire dans l'artefact du job (`job_artifacts.checkpoint_job`, sans migration) le modèle effectif de chaque étape (transcription, texte, vision deep, vision cheap, juge) et si un repli a servi. Test unitaire.
4. Un job prod de contrôle par Augustin depuis le site (une vidéo courte) doit finir `completed` avec les nouveaux modèles. Rapporte les modèles tracés.

## 1. Vidéos de référence figées

- `~/clipfactory-golden/sources/<youtube_id>/` : `source.mp4` (≤ 720p), `heatmap.json` (courbe « most replayed » si dispo), `meta.json` (titre, durée, langue, nombre de voix, téléchargé le). Téléchargées **une seule fois**, jamais réécrites.
- `~/clipfactory-golden/sources.toml` : la liste, avec pour chaque source une campagne de test (audience, niche, ton, objectif, 3 hooks d'exemple). Augustin fournit les ids et valide les briefs ; propose 8 sources : FR solo, FR à 2 voix (×3), EN (×2), une longue (~30 min), une avec écran/slides si possible.
- Le hash SHA-256 de chaque `source.mp4` est écrit dans `meta.json` et vérifié à chaque run.

## 2. Harnais `apps/worker/scripts/golden_run.py`

- Démarre une Postgres jetable, applique le schéma, crée un utilisateur et une campagne de test par source, crédite ce qu'il faut **dans cette base jetable uniquement**.
- Pour chaque source : crée le job, **pré-dépose `source.*` et `heatmap.json` dans le dossier de travail du job** (le court-circuit de `yt_dlp_download` évite tout téléchargement), puis appelle **`run_job`** — exactement le code de prod.
- `STORAGE_BACKEND=local` vers `~/clipfactory-golden/runs/<run_id>/<source_id>/`. Par source : les MP4, le transcript mot à mot, l'artefact du job, et un `manifest.json` : pour chaque clip, segments (début/fin en secondes et en index de mots), citations, titre, raison, scores, durée rendue, modèles effectifs, coûts et temps par étape.
- **5 clips par source** (le harnais peut dépasser la limite produit de 3) → 8 sources × 5 = **40 clips**.
- `run_id` = date + SHA du code + hash du `models.lock` ; écrit dans le rapport. Deux runs sur le même code et les mêmes modèles doivent être comparables.
- Option `--sources a,b` pour ne relancer qu'une partie ; option `--judge/--no-judge`.

## 3. Métriques automatiques (gratuites, déterministes)

Dans `apps/worker/app/golden/metrics.py`, testées unitairement :

| Métrique | Définition |
|---|---|
| Fin suspendue | le dernier mot du clip (et de chaque segment) est dans une liste fermée FR/EN de mots qui appellent une suite (et, mais, donc, si, que, parce, alors, because, and, but, so, if, that…) **ou** la fin ne coïncide pas avec une fin de phrase du transcript |
| Ouverture dépendante | le premier mot est un connecteur ou un pronom sans référent (et, mais, donc, alors, ça, il, elle, ils, so, and, but, it, they…) |
| Coupe dans un mot | une borne tombe à l'intérieur d'un mot (comparaison aux timestamps mot) |
| Noir / silence | réutiliser le QC média existant |
| Durées | distribution, part dans la cible |
| Recoupement audience | part de la durée des clips dans le top 10 % de la courbe « most replayed », comparée à une fenêtre aléatoire de même durée (si heatmap) |
| Coût / temps | par source et total ; coût par clip |

Sortie : `report.md` + `report.json` dans le dossier du run.

## 4. Juge de clip en observation

`clip_judge.py` existe (désactivé par défaut). Le harnais l'appelle sur chaque clip rendu (vidéo native, modèle du `models.lock`), stocke le verdict JSON à côté du clip, **ne bloque rien, ne reclasse rien**. Rubrique : `publishable`, `reasons[]` dans la liste fermée ci-dessous, `hook_0_3s` 0–4, une phrase d'explication.

**Liste fermée de raisons de rejet** (la même partout : juge, page de notation, plus tard le site) : `fin_coupee`, `ouverture_sans_contexte`, `accroche_faible`, `chute_absente`, `promesse_non_tenue`, `hors_brief`, `cadrage`, `sous_titres`, `trop_long`, `trop_court`, `audio`, `autre`.

## 5. Page de notation pour Augustin

`golden_review.py` génère `~/clipfactory-golden/runs/<run_id>/review/index.html`, autonome (fonctionne en ouvrant le fichier, ou en zip vers un autre Mac) :

- les 40 clips **mélangés et anonymisés** (aucun score, modèle, titre interne ni verdict du juge visible) ; lecteur vidéo ; transcript du clip dépliable ;
- par clip : **publiable oui / non**, **raisons** (cases de la liste fermée), **accroche 0–4**, commentaire libre ;
- progression « 12 / 40 », sauvegarde automatique dans le navigateur, bouton **Exporter** → `ratings.csv` à déposer dans le dossier du run ;
- en français, lisible sur un écran de MacBook, utilisable au clavier (o / n, flèches).

## 6. Accord juge ↔ Augustin et rendement de départ

`golden_agreement.py` lit `ratings.csv` + les verdicts du juge et écrit dans le rapport : **rendement publiable** (part des clips notés publiables par Augustin), **κ de Cohen** sur « publiable », **rappel** du juge sur les rejets d'Augustin, matrice de confusion, raisons les plus fréquentes (Augustin vs juge). Ces chiffres décident de B3.

## Critères de sortie de B0

1. Studio sur `main`, modèles durables, modèles tracés par job ; job de contrôle prod OK.
2. Les 8 sources figées, briefs validés par Augustin.
3. Un run golden complet : 40 clips, `report.md` avec toutes les métriques, coût ≤ 3 $, verdicts du juge stockés.
4. Page de notation ouverte et testée par Augustin sur 3 clips.
5. Tests verts (unitaires sans réseau ; harnais testé sur une source factice de quelques secondes).
6. PR en brouillon avec, dans la description : commandes exactes, coût, durée du run, tableau des métriques, ce qui n'est pas fait.

Ensuite, hors Codex : ⏸ Augustin note les 40 clips (~2 à 3 h, en plusieurs fois) → Codex lance `golden_agreement.py` → le rendement de départ est connu → B1.
