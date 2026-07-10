# Global video understanding - story-first clipping

> Objectif : permettre a ClipFactory de trouver des clips qui racontent une vraie histoire, meme quand le setup et le payoff sont eloignes dans la video.

Document de fondation conceptuelle. La pipeline story-first décrite ici est désormais **implémentée** — `docs/pipeline.md` est la spec d'exécution à jour.

> **Décisions modèles (màj 2026-07-08) :** config VALIDÉE en réel = **`google/gemini-2.5-flash`** sur les 3 rôles (texte, vision cheap, vision deep) via OpenRouter, avec `reasoning:{max_tokens:0}`. Le mix économique initial (Qwen3-VL cheap + DeepSeek texte) reste à re-benchmarker. Fallback Claude Haiku 4.5 configuré mais désactivé. Les mentions « Claude Haiku » pour la vision plus bas sont des **pistes initiales** — gardées pour l'historique.

---

## Probleme

La pipeline actuelle analyse surtout des moments candidats locaux :

1. transcription complete,
2. selection de segments texte de 20-60s,
3. vision sur 2-3 frames par candidat,
4. score,
5. rendu vertical.

Ca marche pour des clips simples, mais ca rate les meilleurs moments viraux quand l'interet vient d'une relation longue distance dans la video.

Exemple :

- a `02:00`, un mec achete une Lamborghini,
- a `12:30`, il a un accident avec cette meme Lamborghini.

Le passage de l'accident est interessant seul, mais le clip devient beaucoup plus fort si le montage montre :

1. le setup : il vient de l'acheter,
2. la transition : il part avec / il fait le malin,
3. le payoff : accident / voiture abimee / reaction.

Pour trouver ca, ClipFactory doit comprendre la video entiere sous forme compressee, pas seulement regarder des fenetres locales.

---

## Principe produit

ClipFactory ne doit pas seulement chercher des "moments forts".

Il doit chercher des **arcs narratifs** :

| Arc | Exemple |
| --- | --- |
| Setup -> payoff | achat voiture -> accident |
| Promesse -> echec | "je vais reussir" -> il rate |
| Avant -> apres | objet neuf -> objet casse |
| Defi -> resultat | challenge annonce -> reaction finale |
| Question -> revelation | mystere -> reponse visuelle |
| Phrase -> preuve visuelle | il dit un truc -> l'ecran prouve l'inverse |
| Decision -> consequence | il prend une decision -> probleme 10 min apres |

Le meilleur clip peut donc etre un montage de plusieurs segments eloignes, pas un seul extrait continu.

---

## Architecture cible

Nouvelle logique :

```text
Download / probe
    ->
Transcription complete
    ->
Scene detection + keyframes
    ->
Cheap global video map
    ->
Story arc detection
    ->
Vision forte sur top arcs seulement
    ->
Montage plan multi-segments
    ->
Render vertical + captions retimees
```

Le point important : on comprend toute la video, mais avec une representation compressee et pas chere.

---

## Etape 1 - Video map globale

Creer une timeline JSON de toute la video.

Inputs :

- transcript timestamps,
- scene changes via FFmpeg / OpenCV,
- keyframes extraites regulierement,
- contexte campagne.

Strategie frame sampling :

| Duree source | Sampling cible | Max frames globales |
| --- | ---: | ---: |
| 0-10 min | scene changes + 1 frame / 6s | 80 |
| 10-30 min | scene changes + 1 frame / 10s | 150 |
| 30-60 min | scene changes + 1 frame / 15s | 220 |

Ne jamais faire de vision image par image. La video map doit rester cheap.

Output attendu :

```json
{
  "video_summary": "Video vlog autour de l'achat puis de l'accident d'une Lamborghini.",
  "events": [
    {
      "id": "evt_001",
      "start": 118.4,
      "end": 145.2,
      "decor": "concession automobile",
      "people": "homme face camera",
      "objects": ["Lamborghini", "cles", "showroom"],
      "action": "il presente la voiture qu'il vient d'acheter",
      "transcript_summary": "Il explique qu'il vient d'acheter la Lambo.",
      "visual_importance": 85,
      "narrative_role": "setup"
    },
    {
      "id": "evt_014",
      "start": 748.0,
      "end": 781.5,
      "decor": "route exterieure",
      "people": "homme choque pres de la voiture",
      "objects": ["Lamborghini abimee", "route", "degats"],
      "action": "la voiture est accidentee et il reagit",
      "transcript_summary": "Il realise que la voiture est endommagee.",
      "visual_importance": 95,
      "narrative_role": "payoff"
    }
  ]
}
```

Modeles possibles pour cette etape :

- `qwen3-vl-flash` : bon candidat par defaut si le cout est prioritaire,
- `gemini-2.5-flash-lite` : bon candidat alternatif cheap,
- Claude Haiku : garder en fallback ou comparaison, mais probablement trop cher pour tout le global.

---

## Etape 2 - Detection des arcs narratifs

A partir de la video map + transcript, chercher des relations entre evenements.

Le modele ne doit pas seulement scorer les evenements un par un. Il doit proposer des arcs.

Output attendu :

```json
{
  "story_arcs": [
    {
      "title": "Il achete une Lamborghini et l'abime 10 minutes apres",
      "arc_type": "setup_payoff",
      "segments": [
        {
          "role": "setup",
          "event_id": "evt_001",
          "start": 118.4,
          "end": 135.0,
          "reason": "montre clairement l'achat et la voiture neuve"
        },
        {
          "role": "payoff",
          "event_id": "evt_014",
          "start": 752.0,
          "end": 779.0,
          "reason": "montre la consequence visuelle forte"
        }
      ],
      "viral_reason": "contraste fort entre achat recent et accident",
      "estimated_retention": 88,
      "continuity_risk": "low"
    }
  ]
}
```

---

## Etape 3 - Vision forte uniquement sur les meilleurs arcs

La vision globale doit etre cheap. La verification forte doit arriver seulement apres filtrage.

Regle :

- generer 20-40 evenements dans la video map,
- generer 10-15 arcs narratifs,
- garder top 5 arcs,
- analyser plus finement seulement ces top 5.

Pour les top arcs, extraire plus de frames autour des segments :

- debut segment,
- milieu segment,
- fin segment,
- frame avant / apres si necessaire,
- max 6-8 frames par segment.

But de la vision forte :

- verifier que le decor est bien coherent,
- verifier que les objets importants sont visibles,
- verifier que le payoff est comprehensible sans regarder toute la video,
- verifier que deux segments eloignes peuvent etre colles sans perdre le spectateur,
- detecter les problemes : flou, ecran illisible, sujet hors cadre, contexte ambigu.

---

## Etape 4 - Montage multi-segments

Le clip final ne doit plus etre seulement `{start, end}`.

Nouveau format :

```json
{
  "title": "Il achete une Lambo... et la detruit 10 minutes apres",
  "hook": "Il venait juste d'acheter cette Lamborghini.",
  "segments": [
    {
      "role": "setup",
      "start": 118.4,
      "end": 135.0
    },
    {
      "role": "transition",
      "start": 146.0,
      "end": 155.5
    },
    {
      "role": "payoff",
      "start": 752.0,
      "end": 779.0
    }
  ],
  "rationale": "Le clip marche grace au contraste entre achat recent et consequence rapide."
}
```

Contraintes produit :

| Regle | Valeur |
| --- | ---: |
| Segments max | 3 |
| Duree min segment | 4s |
| Duree max segment | 25s |
| Duree totale clip | 20-60s |
| Segment 1 | doit poser le contexte ou le hook |
| Dernier segment | doit contenir payoff / reaction / preuve visuelle |

Le rendu doit concatener les segments puis retimer les sous-titres sur la timeline finale.

---

## Scoring propose

Pour scorer un arc narratif :

| Signal | Poids |
| --- | ---: |
| Payoff strength | 25% |
| Setup clarity | 20% |
| Visual proof | 20% |
| Retention / curiosity | 15% |
| Campaign fit | 10% |
| Editing continuity | 10% |

Definitions :

- `payoff_strength` : est-ce que la fin recompense vraiment le spectateur ?
- `setup_clarity` : comprend-on vite pourquoi la suite compte ?
- `visual_proof` : voit-on clairement l'objet/action qui rend l'histoire credible ?
- `retention` : est-ce que le spectateur a envie de rester jusqu'au payoff ?
- `campaign_fit` : est-ce que l'arc sert la niche/audience de la campagne ?
- `editing_continuity` : est-ce que les segments peuvent etre colles proprement ?

---

## Plan d'implementation dans ce repo

Fichiers probablement concernes :

| Fichier | Changement |
| --- | --- |
| `apps/worker/app/models.py` | ajouter `VideoEvent`, `StoryArc`, `MontageSegment`, `MontageCandidate` |
| `apps/worker/app/prompts.py` | ajouter prompts `video_map` et `story_arc_detection` |
| `apps/worker/app/pipeline/vision.py` | ajouter provider cheap global vision + top-arc verification |
| `apps/worker/app/pipeline/analyze.py` | passer de single-window candidates a story arcs |
| `apps/worker/app/pipeline/ffmpeg.py` | ajouter `render_montage_clip()` avec concat segments |
| `apps/worker/app/pipeline/runner.py` | inserer `build_video_map` avant scoring, puis brancher montage |
| `db/migrations/` | ajouter `jobs.video_map jsonb`, `clips.segments jsonb`, `clips.rendered_duration_seconds` |
| `docs/pipeline.md` | mettre a jour seulement quand l'implementation est decidee |

Important : garder l'ancien rendu `{start, end}` en fallback. Tous les clips ne doivent pas forcement etre multi-segments.

---

## Flags conseilles

Ajouter des variables d'environnement pour tester sans tout casser :

```text
ENABLE_GLOBAL_VIDEO_MAP=false
ENABLE_STORY_ARCS=false
ENABLE_MULTI_SEGMENT_RENDER=false
VISION_GLOBAL_PROVIDER=qwen
VISION_GLOBAL_MODEL=qwen3-vl-flash
VISION_ARC_PROVIDER=openrouter
VISION_ARC_MODEL=google/gemini-2.5-flash   # decision finale (Claude Haiku = fallback uniquement)
MAX_GLOBAL_VISION_FRAMES=150
MAX_STORY_ARCS=15
MAX_TOP_ARCS_FOR_DEEP_VISION=5
```

---

## Prompt de depart pour Claude

Donner ce prompt a Claude avant de coder :

```text
Lis d'abord:
- docs/handoff-codex.md
- docs/v1-scope.md
- docs/pipeline.md
- docs/global-video-understanding.md

Objectif: ajouter une architecture story-first pour trouver des clips dont le setup et le payoff sont eloignes dans la video.

Ne casse pas la pipeline V1 existante. Ajoute les nouveaux concepts derriere des flags:
- video map globale
- story arcs
- montage multi-segments

Contraintes:
- ne jamais analyser toute la video image par image
- utiliser une video map compressee
- garder le rendu single-window en fallback
- code en anglais, docs/chat en francais
- ne pas modifier /Users/augustindemeaux/ClipFactory

Commence par proposer le plan de fichiers, puis implemente par petites PR logiques.
```

---

## Definition de succes

Cette evolution est reussie quand ClipFactory peut trouver et rendre un clip comme :

```text
02:00 - il achete une Lamborghini
12:30 - il a un accident avec cette Lamborghini
=> clip final: setup + payoff en montage vertical coherent
```

Sans exploser la marge :

- vision cheap pour comprendre toute la video,
- vision forte seulement sur les meilleurs arcs,
- max 2-3 segments dans le clip final,
- logs cout/marge par job.
