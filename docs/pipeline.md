# Pipeline — worker steps

Source de vérité du séquencement worker. Le code dans `apps/worker/` doit suivre exactement cet ordre. Modifications de l'ordre passent par une mise à jour de ce doc.

---

## Cycle d'un job

Un job naît avec status `queued` côté API. Le worker le récupère via `BLPOP clipfactory:jobs:queue`. Le worker met à jour `jobs.status` et `jobs.current_step` à chaque transition.

```
queued
  ├─► downloading        (yt-dlp)
  │     └─► failed       (URL invalide, geo-block, etc.)
  ├─► transcribing       (OpenAI Whisper API)
  │     └─► failed       (audio extraction error)
  ├─► analyzing          (Claude texte + vision candidate)
  │     └─► failed       (LLM error after retries)
  ├─► rendering          (FFmpeg vertical 1080x1920)
  │     └─► failed       (FFmpeg error)
  └─► completed
```

`canceled` est réservé (V2 — user cancel). En V1 on ne propose pas de cancel.

---

## Les 17 étapes (ordonnées)

| # | Étape | Précondition | Échec = ? |
| ---: | --- | --- | --- |
| 1 | **Validate URL** | URL non vide, scheme http/https, host dans la whitelist (`youtube.com`, `youtu.be`, `vimeo.com` V1) | `failed: invalid_url` |
| 2 | **Download** | yt-dlp avec format `bestvideo*+bestaudio/best`, max 720p pour économiser CPU | `failed: download_failed` |
| 3 | **Probe duration** | ffprobe sur le fichier téléchargé | `failed: probe_failed` |
| 4 | **Check plan max** | `duration_seconds <= plan.max_video_minutes * 60` | `failed: video_too_long` (refund full credits) |
| 5 | **Debit credits** | balance suffisante après calcul réel | `failed: insufficient_credits` (refund estimated) |
| 6 | **Upload source to R2** | clé `sources/{user_id}/{job_id}.mp4` | `failed: storage_failed` |
| 7 | **Transcribe** | OpenAI `gpt-4o-mini-transcribe` (paramétrable env), résultat JSON avec timestamps mot par mot | `failed: transcription_failed` |
| 8 | **Select text candidates** | Claude Haiku, prompt avec campaign context, retourne 15-20 segments `{start, end, hook_score_text, emotion_score, why}` | `failed: analysis_failed` |
| 9 | **Extract candidate frames** | FFmpeg, 2-3 frames par candidat (début / milieu / moment fort), résolution 512 max, JPEG q=4 | retry 1× puis fallback `visual_score: null` |
| 10 | **Analyze frames** | Claude vision (multi-image), prompt par candidat : `{decor, person_visible, energy, action, proof, problems, visual_score}` | fallback `visual_score: null`, job continue |
| 11 | **Score & rank** | total = 0.35·hook + 0.20·emotion + 0.25·visual + 0.15·campaign_fit + 0.05·editing_ease | inline, jamais d'échec |
| 12 | **Pick top N** | `target_clip_count` (max 3 sur Starter) | inline |
| 13 | **Render vertical** | FFmpeg, 1080x1920, scale + pad + crop centre, audio AAC 128k, h264 main 4.1 | retry 1× puis `failed: render_failed` |
| 14 | **Burn captions** | ffmpeg `drawtext` ou ASS basique (V1 = minimal, pas de styles avancés) | inline, fallback : pas de captions si parsing transcript foire |
| 15 | **Upload clips to R2** | clé `clips/{user_id}/{job_id}/{idx}.mp4` | `failed: storage_failed` |
| 16 | **Save clips to DB** | insert dans `clips` avec score breakdown + rationale + transcript excerpt + visual_summary | inline (rollback si échec) |
| 17 | **Finalize** | `jobs.status = 'completed'`, `finished_at = now()`, log final cost row | inline |

---

## Vision candidate (étapes 9-10) — règle d'or

> **NE JAMAIS analyser toute la vidéo image par image.**

Pour chaque moment candidat retourné en étape 8, on extrait au plus **3 frames** :
- 1 frame au début du segment (`start + 0.2s`)
- 1 frame au milieu (`(start + end) / 2`)
- 1 frame proche d'un mot à forte intensité émotionnelle si détecté

Total frames par job (target = 3 clips, 15-20 candidats) : **45-60 frames max**.

Prompt vision (par candidat) demande, en JSON strict :

```json
{
  "decor": "studio podcast / car / desktop screen / outdoor / gaming setup / unknown",
  "person_visible": true,
  "energy": 0,
  "action": "talking head / reaction / pointing at screen / demo",
  "proof_objects": ["screen with number", "product", "face reaction"],
  "problems": ["dark", "no face", "unreadable slide"],
  "visual_score": 0
}
```

`energy` et `visual_score` sur 0-100.

Fallback `vision_unavailable` : si l'appel échoue 2× ou si frames non extractibles, le clip a `visual_score = null` et `visual_summary = "vision unavailable"`. Le job termine quand même — le score final est recalculé sans le terme visuel (renormalisé sur 95%).

---

## Logging coût / marge (étape 17, append-only)

Chaque job écrit à la fin (dans `jobs`) :

| Colonne | Source |
| --- | --- |
| `duration_seconds` | étape 3 |
| `credits_charged` | étape 5 |
| `transcription_cost_cents` | `ceil(minutes) * tarif_transcription_cents` |
| `analysis_tokens` | tokens Claude (étapes 8 + 10) |
| `vision_frames_count` | étape 9 |
| `render_seconds` | wall time étapes 13-14 |
| `storage_bytes` | somme `bytes` des clips uploadés |
| `total_cost_estimate_cents` | somme transcription + analyse + render (modèle interne) |
| `failed_step` | nom de l'étape qui a échoué (null si OK) |
| `retry_count` | nb retries cumulés |

Pas de table `cost_log` séparée en V1 — les colonnes dans `jobs` suffisent.

---

## Concurrence et limites

- Starter : 1 job concurrent par user (rejeté avant queue).
- Worker : `WORKER_CONCURRENCY=1` au début (Hetzner CPX21, 2 vCPU, on n'en lance qu'un à la fois).
- Retry budget par étape : **1** (sauf vision = 1 explicit + fallback).
- Pas de DLQ V1 : un job en `failed` reste dans `jobs` avec `error_code` + `error_message`, lisible par le user.
- Stockage source : supprimé après 14 jours (cron V2 — V1 = manuel).
- Clips R2 : gardés 60 jours (V2 cron, V1 = manuel).
