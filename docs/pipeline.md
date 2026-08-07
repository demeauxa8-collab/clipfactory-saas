# Pipeline V1 — story-first

Source de vérité du worker. Le code dans `apps/worker/` doit suivre exactement ce qui est ici. Modifications de logique passent par un update de ce doc avant de toucher au code.

> **Décision majeure (2026-05-22)** : abandon de la pipeline single-window au profit d'une pipeline **story-first** qui peut produire un clip composé de plusieurs segments éloignés dans la vidéo source. Voir `docs/global-video-understanding.md` pour la justification produit. Cette pipeline-ci est la spec d'exécution.

---

## Modèle de données : clip = liste de segments

Un clip n'est plus `{start, end}`. C'est une **liste ordonnée de segments** :

```json
{
  "title": "Il achete une Lambo... et la detruit 10 min apres",
  "hook": "Il venait juste d'acheter cette Lamborghini.",
  "segments": [
    { "role": "setup",    "start": 118.4, "end": 135.0 },
    { "role": "payoff",   "start": 752.0, "end": 779.0 }
  ],
  "rationale": "Contraste fort entre achat recent et accident."
}
```

Cas dégénéré : `len(segments) == 1` → comportement single-window équivalent à l'ancienne V1.

Contraintes produit :

| Règle | Valeur |
| --- | ---: |
| Segments min | 1 |
| Segments max | 3 |
| Durée min segment | 3 s |
| Durée max segment | 30 s |
| Durée totale clip | 12-60 s |
| Premier segment | doit poser contexte/hook |
| Dernier segment | doit contenir payoff/preuve visuelle |

---

## Deux chemins, choisi sur la durée

```
duration_seconds
   < 300 (5 min)       →  PIPELINE SIMPLE   (12 étapes, single-window)
   ≥ 300              →  PIPELINE STORY    (16 étapes, multi-segments possible)
```

Pas de feature flag. Le `run_job()` décide à l'étape 4 quel chemin prendre selon la durée mesurée. Les deux chemins partagent le **même format de sortie** (`clips.segments jsonb`), donc tout en aval (render, upload, DB) est commun.

---

## Lifecycle status `jobs.status`

```
queued
  → downloading      (étapes 1-3)
  → transcribing     (étape 4)
  → analyzing        (étapes 5-10)
  → rendering        (étapes 11-14)
  → completed | failed | canceled
```

`current_step` est plus fin et reflète l'étape exacte (`validate_url`, `video_map`, `verify_arcs`, `render_montage`, etc.).

---

## Pipeline simple (vidéos < 5 min)

| # | Étape | Détail |
| ---: | --- | --- |
| 1 | validate_url | scheme http/https, host dans whitelist (`youtube.com`, `youtu.be`, `vimeo.com`) |
| 2 | download | yt-dlp `bv*[height<=720]+ba/best` mp4 |
| 3 | probe | ffprobe → `duration_seconds` |
| 4 | check_plan + initial_debit | si dur > plan.max → fail. Débit upfront du `credits_estimated`. |
| 5 | upload_source | clé `sources/{user_id}/{job_id}.mp4` (best-effort) |
| 6 | transcribe | OpenAI **`whisper-1`**, `timestamp_granularities=["word","segment"]` : on garde les mots horodatés ET les **phrases ponctuées** (428 sur notre vidéo de test — elles étaient jetées avant le 2026-08-07 ; ce sont elles qui donnent les vraies frontières de coupe). Audio extrait en mp3 mono 16 kHz (limite 25 Mo). Post-process : fusion des élisions françaises ("J","ai" → "J'ai") |
| 7 | select_segments | Modèle texte primary via env `PRIMARY_TEXT_MODEL` (validé : gemini-2.5-flash, `reasoning` off ; fallback Claude Haiku désactivé) : retourne 5-8 segments candidats `{start, end, hook, emotion, transcript_excerpt, why, suggested_title, suggested_hook}` |
| 8 | verify_segments | string match transcript_excerpt vs transcript réel (fuzzy ratio ≥ 0.7 sur la fenêtre). Drop hallucinations. |
| 9 | extract_frames + deep_vision | 2-3 frames par segment restant, Gemini 2.5 Flash vision (fallback Haiku) JSON `{decor, person_visible, energy, action, proof_objects, problems, visual_score}` |
| 10 | score_and_pick | poids `hook 35% + emotion 20% + visual 25% + campaign_fit 15% + editing 5%`. Garde top `target_clip_count`. |
| 11 | render | FFmpeg vertical 1080x1920, 1 segment = pas de concat |
| 12 | captions + upload + save + finalize | ASS burn-in, R2 upload, insert clips, debit final, cost log |

---

## Pipeline story-first (vidéos ≥ 5 min)

| # | Étape | Détail |
| ---: | --- | --- |
| 1 | validate_url | idem |
| 2 | download | idem |
| 3 | probe | idem |
| 4 | check_plan + initial_debit | idem |
| 5 | upload_source | idem |
| 6 | transcribe | idem |
| 7 | **scene_detection + frame_sampling** | FFmpeg `select='gt(scene,0.4)'` + sampling régulier. Cap selon durée : `<10min→80`, `10-30→150`, `>30→220` frames |
| 8 | **build_video_map** | Modèle vision cheap via env `VISION_CHEAP_MODEL` (validé : gemini-2.5-flash, `reasoning` off), prompt = `VIDEO_MAP_SYSTEM_PROMPT` + frames + transcript résumé. Sortie : `{video_summary, events[]}` 20-40 events avec `{id, start, end, decor, people, objects, action, transcript_summary, visual_importance, narrative_role}` |
| 9 | **detect_story_arcs** | Modèle texte primary (env `PRIMARY_TEXT_MODEL`) sur video_map + transcript_lines + campaign. Sortie montage-v2 : 8-12 arcs de 1-3 segments `{title, arc_type, segments[], viral_reason, estimated_retention, continuity_risk, link_reason, campaign_fit, campaign_fit_reason}` |
| 9b | **anchor_arcs** (2026-08-07) | `boundaries.anchor_arcs_to_transcript()` : retrouve dans le transcript les mots que le modèle a CITÉS et recale la fenêtre dessus (appariement flou ±15 s), puis étend la fin pour englober `payoff_line`. **C'est ici qu'on cesse de croire les timestamps du LLM** — voir l'encadré ci-dessous. |
| 10 | **verify_arcs** | Pour chaque arc, pour chaque segment : checker que les mots du transcript dans `[start, end]` existent vraiment. Sinon drop l'arc entier. ⚠️ Vérifie le CONTENU, pas la POSITION : sans l'étape 9b, une dérive de 8 s passait avec un ratio de 1.0. |
| 11 | **deep_vision** sur top 5 | Top 5 arcs par `estimated_retention`. Pour chaque segment d'un arc top 5 : extract 4-6 frames (début, milieu, fin, +1-2 si > 15s). Gemini 2.5 Flash vision (fallback Haiku) : confirm decor/action/proof. Retourne `visual_score` agrégé par arc. |
| 12 | **score_and_pick_arcs** | poids montage-v2 : `visual_proof 28% + hook_strength 20% + payoff_strength 18% + campaign_fit 12% + editing_continuity 12% + retention 10%` (voir section Scoring). Top `target_clip_count`. |
| 13 | render_montage | Pour chaque arc retenu, FFmpeg : cadrage PAR SEGMENT (face-crop 9:16 plein cadre ou fit+blur), transitions par joint (cut sec / dip-to-white 0,10 s selon `joint_compatibility`), concat avec crossfade audio 150 ms, vertical 1080x1920, h264. Garde anti-noir par segment avant rendu |
| 14 | retime_captions | Mots du transcript dans la fenêtre source → recalculés sur la timeline finale (offset cumulatif des segments précédents). ASS burn-in. |
| 15 | upload + save | clé `clips/{user_id}/{job_id}/{idx}.mp4`. Insert clips avec `segments jsonb`. |
| 16 | finalize | debit final, cost log (transcription + video_map_cost + arcs_text_cost + deep_vision_cost + render_seconds + storage). |

---

## Anti-hallucination : étape 10 / 8

Le LLM peut inventer des moments qui n'existent pas. **Garde-fou obligatoire avant render** :

```python
def verify_segment(transcript_words, start, end, expected_excerpt) -> bool:
    actual = " ".join(w.word for w in transcript_words if start <= w.start <= end)
    ratio = SequenceMatcher(None, actual.lower(), expected_excerpt.lower()).ratio()
    return ratio >= 0.7
```

Si un arc a un segment qui rate la vérification → l'arc complet est drop. On préfère 2 clips solides que 3 clips dont 1 hallucination.

---

## Ancrage sur le transcript (étape 9b) — la règle d'or

> **Aucune seconde émise par un LLM ne part directement dans ffmpeg.**

Mesuré le 2026-08-07 sur données réelles : **sur 7 arcs sur 8, les mots cités par
le modèle commençaient 0,7 à 8,1 s après le `start` qu'il déclarait**. Le modèle
lit le marqueur `[t]` d'une ligne de transcript comme un début, tout en citant des
mots situés plusieurs secondes plus loin dans cette ligne. Les clips ouvraient
donc sur la mise en route.

Le principe : le modèle **cite** (phrase d'ouverture, `payoff_line`), le code
**date**. Le transcript mot à mot est l'horloge de référence — gratuite, exacte,
déjà calculée.

Deux dépendances non évidentes :

1. **Les phrases ponctuées de whisper.** L'API renvoie `segments` (texte ponctué +
   bornes) en plus de `words` (sans ponctuation) : on les jetait. Récupérées via
   `timestamp_granularities=["word","segment"]` → **428 vraies phrases** contre 73
   devinées auparavant sur le même audio.
2. **La détection de silences ne marche pas sur du whisper.** Les mots reviennent
   quasi collés (écart inter-mots médian ET p90 = 0,000 s), donc un seuil en
   VALEUR s'effondre sur son plancher. Le secours utilise désormais un critère de
   RANG (les 12 % plus grands écarts), qui dégrade proprement sur n'importe quelle
   source.

Effets mesurés : dérive médiane 1,88 s → **0,12 s** (max 8,14 → 0,12), segments
correctement calés 3/7 → **7/7**, punchline à l'intérieur du clip 7/8 → **8/8**,
et les arcs sous le plancher de 12 s sont **réparés** (fin poussée à la prochaine
fin de phrase) au lieu d'être jetés en silence.

Corollaire pour le choix des modèles : un modèle incapable de dater un événement
reste utilisable pour la video-map et la deep vision, puisque **ces timecodes-là
viennent des frames qu'on extrait nous-mêmes**. Voir `docs/model-landscape.md`.

---

## Vision globale (étape 8 story) — règle d'or

> **NE JAMAIS** envoyer toutes les frames à un seul appel LLM.

On bat avant d'envoyer :

- frames chunkées en batches de 20-30 par appel
- chaque appel reçoit le transcript résumé + la fenêtre temporelle des frames
- réponses concaténées en post-traitement
- coût cible : **< 5 cents par job sur 30 min de vidéo**

Provider : OpenRouter, modèle via env `VISION_CHEAP_MODEL` (validé : `google/gemini-2.5-flash` avec `reasoning:{max_tokens:0}` — sans ça le raisonnement consomme le budget tokens et tronque le JSON). Fallback Claude Haiku configuré mais désactivé (`ENABLE_FALLBACK=false`).

---

## Continuity entre segments éloignés (montage-v2, 2026-07-08)

Le montage multi-segments est le concept central : 1 à 3 moments distants
assemblés quand ils forment un vrai fil narratif (`link_reason` obligatoire
dans la réponse LLM pour tout arc multi-segments).

Au rendu, chaque **joint** entre deux segments adjacents est classé par
`score.joint_compatibility(vision_a, vision_b)` à partir de la deep vision
par segment :

- `continuous` (même décor, même présence personne) → **cut sec** + crossfade
  audio 150 ms (comportement historique) ;
- `scene_change` (décors différents, ou vision manquante) → **dip-to-white
  0,10 s** de part et d'autre du joint (fade-out blanc fin du segment sortant,
  fade-in blanc début de l'entrant, cuits dans les intermédiaires), audio
  toujours en acrossfade 150 ms. La "téléportation" devient une transition
  intentionnelle.

Le même classement alimente la pénalité de continuité du scoring (-3 par
joint continu, -8 par changement de scène, -6 si vision absente) — plus
d'écrasement forfaitaire des montages.

Le **cadrage est décidé par segment** (plus par clip) : plan visage →
crop 9:16 plein cadre centré sur `face_center_x` (renvoyé par la deep
vision) ; plan écran/slide → fit+blur letterbox. Les captions portent une
MarginV par événement selon le segment (400 plein cadre, 620 fit+blur) et
les groupes karaoké sont coupés aux joints. La garde anti-frames-noires
(blackdetect) s'applique au début de chaque segment.

---

## Améliorations qualité du rendu (implémentées 2026-06)

Livré sur `main` (merge `draft/parallel-workers`). Roadmap complète : `docs/pipeline-improvements.md`. Aucune de ces briques n'ajoute de coût LLM/vision (elles réutilisent les word timestamps et la deep vision déjà calculés).

| Brique | Où (code) | Effet |
| --- | --- | --- |
| Snapping des bords de segment | `pipeline/boundaries.py` (`snap_arc_segments`), appelé après `verify_arcs` (`current_step = snap_segments`, les 2 chemins) | cale `start`/`end` sur silence / fin de phrase via word timestamps → plus de coupe en plein mot |
| Loudnorm -14 LUFS | `pipeline/ffmpeg.py` (`loudnorm=I=-14:TP=-1.5:LRA=11`) | volume constant entre clips |
| Gate QC post-rendu | `runner.py` (`render_qc_failed`) + `ffmpeg.py` (`volumedetect`) | rejette un clip muet / cassé / hors tolérance de durée avant l'upload |
| Sous-titres karaoké | `pipeline/captions.py` (1 event par mot, override couleur `\c` + scale) | mot prononcé surligné en temps réel |
| Persist `why` par segment | `runner.py` (`_segments_to_jsonb`) + `score.py` | la justification LLM de chaque segment est stockée (explicabilité) |

Livré ensuite (passe qualité 2026-07-06 → 2026-07-08, commits `7463048`/`5255a96`) :

| Brique | Où (code) | Effet |
| --- | --- | --- |
| Recadrage face-aware par segment | `ffmpeg.py` (`_vertical_face_crop_vf`), `prompts.py`/`vision.py` (`face_center_x`) | visage plein cadre (~50 % de hauteur) sur les plans visage, fit+blur réservé aux écrans |
| Élisions françaises | `transcribe.py` (`merge_french_elisions`) | whisper-1 renvoie "J","ai" sans apostrophe → "J'ai" (U+2019) partout (captions, excerpts, prompts) |
| Captions style Submagic | `captions.py` | MAJUSCULES, 2-3 mots/groupe coupés sur pauses et joints, wrap `\N` + shrink `\fs` anti-débordement, highlight vert #00E676 jamais sur mots-outils |
| Snap frontières v2 | `boundaries.py` | frontières de phrase par gaps adaptatifs (p85) — la ponctuation n'existe pas dans les mots whisper ; extension avant jusqu'à +8 s pour finir la phrase |
| Garde anti-noir | `ffmpeg.py` (`detect_black_open_for_segments`) + `runner.py` | plus d'ouverture de segment sur des frames noires |
| Transitions par joint | `ffmpeg.py` (`transitions=`), `score.py` (`joint_compatibility`) | dip-to-white 0,10 s sur changement de scène, cut sec sinon |
| Cache source | `ffmpeg.py` (`yt_dlp_download`) | re-runs idempotents, plus de re-téléchargement YouTube (403 sur répétition) |

Encore en roadmap (non implémenté) : cadrage par scène À L'INTÉRIEUR d'un segment (un segment mixte visage+écran garde un seul mode), suivi du visage sur les gestes (crop statique), courbe d'énergie audio, dédup/diversité des arcs (MMR), trim des silences, variantes de titre/hook, thumbnail, juge vidéo natif (`docs/clip-judge.md`, worktree redesign). Voir `docs/pipeline-improvements.md`.

## Scoring (étape 10 simple / 12 story)

**Single-window** :

```
total = 0.35·hook + 0.20·emotion + 0.25·visual + 0.15·campaign_fit + 0.05·editing
```

**Story arc** (poids montage-v2, 2026-07-08) :

```
total = 0.28·visual_proof + 0.20·hook_strength + 0.18·payoff_strength
      + 0.12·campaign_fit + 0.12·editing_continuity + 0.10·retention
```

- `hook_strength` : noté sur **ce qui est réellement prononcé** dans les 2,5
  premières secondes de la fenêtre (`words_in_window`), pas sur le champ
  `opening_words` que le modèle contrôle — sinon il suffit d'écrire une belle
  phrase pour échapper à la pénalité d'attaque molle. Liste des connecteurs
  interdits partagée avec le prompt (source unique).
- `campaign_fit` : 0.5 × auto-évaluation LLM (`campaign_fit` renvoyé par
  arc avec `campaign_fit_reason`) + 0.5 × match mots-clés FLOU
  (difflib ≥ 0.8 : tolère les fautes du brief, "buinesse" ≈ "business").
- `editing_continuity` : pénalité par joint selon `joint_compatibility`
  (voir section continuity), plus de multiplicateur anti-montage.
- Pénalité ×0.55 si aucune personne visible sur tout le clip.

Si `visual_score = null` (vision KO) : renormaliser le poids restant.

---

## Logging coût / marge (toutes les étapes, append-only)

Colonnes dans `jobs` (déjà créées en migration 0002 + ajouts 0003) :

| Colonne | Source |
| --- | --- |
| `duration_seconds` | étape 3 |
| `credits_charged` | étape finalize |
| `transcription_cost_cents` | étape 6 (durée × tarif) |
| `analysis_tokens` | somme tokens LLM (arcs + deep vision) |
| `vision_frames_count` | total frames envoyées en vision (cheap + deep) |
| `video_map_cost_cents` | nouveau (étape 8 story) |
| `deep_vision_cost_cents` | nouveau (étape 11 story) |
| `render_seconds` | wall time étapes 13-14 |
| `storage_bytes` | somme bytes uploadés |
| `total_cost_estimate_cents` | somme calculée |
| `failed_step` | nom de l'étape d'échec |
| `retry_count` | cumul retries |

---

## Concurrence et limites

- Starter : 1 job concurrent par user
- Worker : `WORKER_CONCURRENCY=1`
- Retry budget par étape externe (LLM, vision, transcription) : **1**
- Pipeline story sur vidéo 30 min : cible totale **< 8 minutes wall-time** (transcription dominant)
- Stockage source : 14 jours (cron V2)
- Clips R2 : 60 jours (cron V2)

---

## Définition de succès

ClipFactory peut rendre un clip comme :

```
02:00  → il achète une Lamborghini      (setup, 17s)
12:30  → il a un accident avec          (payoff, 27s)
─────────────────────────────────────────────────────
clip final : vertical 1080x1920, 44s, crossfade audio 150ms
            score 88, rationale = "contraste achat/accident"
```

Sans exploser la marge :

- video map cheap (< 5 cents)
- deep vision seulement top 5 arcs
- log coût détaillé par job
- 1 credit / minute source débité quoi qu'il arrive
