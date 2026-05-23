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
| Durée min segment | 4 s |
| Durée max segment | 25 s |
| Durée totale clip | 20-60 s |
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
| 6 | transcribe | OpenAI `gpt-4o-mini-transcribe` (verbose_json + word timestamps) |
| 7 | select_segments | Claude Haiku : retourne 5-8 segments candidats `{start, end, hook, emotion, transcript_excerpt, why, suggested_title, suggested_hook}` |
| 8 | verify_segments | string match transcript_excerpt vs transcript réel (fuzzy ratio ≥ 0.7 sur la fenêtre). Drop hallucinations. |
| 9 | extract_frames + deep_vision | 2-3 frames par segment restant, Claude vision JSON `{decor, person_visible, energy, action, proof_objects, problems, visual_score}` |
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
| 8 | **build_video_map** | OpenRouter Qwen3-VL Flash, prompt = `VIDEO_MAP_SYSTEM_PROMPT` + frames + transcript résumé. Sortie : `{video_summary, events[]}` 20-40 events avec `{id, start, end, decor, people, objects, action, transcript_summary, visual_importance, narrative_role}` |
| 9 | **detect_story_arcs** | Claude Haiku texte sur video_map + transcript_lines + campaign. Sortie : 10-15 arcs `{title, arc_type, segments[], viral_reason, estimated_retention, continuity_risk}` |
| 10 | **verify_arcs** | Pour chaque arc, pour chaque segment : checker que les mots du transcript dans `[start, end]` existent vraiment. Sinon drop l'arc entier. |
| 11 | **deep_vision** sur top 5 | Top 5 arcs par `estimated_retention`. Pour chaque segment d'un arc top 5 : extract 4-6 frames (début, milieu, fin, +1-2 si > 15s). Claude vision : confirm decor/action/proof. Retourne `visual_score` agrégé par arc. |
| 12 | **score_and_pick_arcs** | poids `payoff_strength 25% + setup_clarity 20% + visual_proof 20% + retention 15% + campaign_fit 10% + editing_continuity 10%`. Top `target_clip_count`. |
| 13 | render_montage | Pour chaque arc retenu, FFmpeg : extract chaque segment, concat avec crossfade audio 150ms (`afade` + `acrossfade`), vertical 1080x1920, h264 |
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

## Vision globale (étape 8 story) — règle d'or

> **NE JAMAIS** envoyer toutes les frames à un seul appel LLM.

On bat avant d'envoyer :

- frames chunkées en batches de 20-30 par appel
- chaque appel reçoit le transcript résumé + la fenêtre temporelle des frames
- réponses concaténées en post-traitement
- coût cible : **< 5 cents par job sur 30 min de vidéo**

Provider : OpenRouter avec `qwen/qwen3-vl-flash` par défaut. Fallback Claude Haiku si le provider retourne erreur 2× consécutives.

---

## Continuity entre segments éloignés

Quand on concat 2 segments distants (genre 2:00 et 12:30 source), faire un **crossfade audio 150ms** :

```bash
ffmpeg -i seg1.mp4 -i seg2.mp4 -filter_complex \
  "[0:a][1:a]acrossfade=d=0.15[a]; \
   [0:v][1:v]concat=n=2:v=1:a=0[v]" \
  -map "[v]" -map "[a]" out.mp4
```

V1 : crossfade audio uniquement, pas de fondu visuel (cut sec image). Suffit pour rendre la transition propre.

---

## Scoring (étape 10 simple / 12 story)

**Single-window** :

```
total = 0.35·hook + 0.20·emotion + 0.25·visual + 0.15·campaign_fit + 0.05·editing
```

**Story arc** (poids différents) :

```
total = 0.25·payoff_strength + 0.20·setup_clarity + 0.20·visual_proof
      + 0.15·retention + 0.10·campaign_fit + 0.10·editing_continuity
```

Si `visual_score = null` (vision KO) : renormaliser le poids restant.

---

## Logging coût / marge (toutes les étapes, append-only)

Colonnes dans `jobs` (déjà créées en migration 0002 + ajouts 0003) :

| Colonne | Source |
| --- | --- |
| `duration_seconds` | étape 3 |
| `credits_charged` | étape finalize |
| `transcription_cost_cents` | étape 6 (durée × tarif) |
| `analysis_tokens` | somme tokens Claude (arcs + deep vision) |
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
