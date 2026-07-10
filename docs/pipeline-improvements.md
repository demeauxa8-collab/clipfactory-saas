# Pipeline — améliorations qualité & compréhension

> Document de travail (2026-06-16). Ce n'est **pas** encore la source de vérité d'exécution (`docs/pipeline.md` reste la spec en vigueur). Ce doc liste les briques à ajouter à la pipeline pour améliorer (a) la **qualité du clip rendu** et (b) la **compréhension de la vidéo / l'explicabilité des choix**. Chaque brique est ancrée sur un fichier réel du worker.

> **Statut au 2026-07-08 — largement livré.** Briques **1 (snapping des bords — réécrit en v2 le 2026-07-06 : gaps adaptatifs), 2 (loudnorm -14 LUFS), 3 (gate QC), 4 (persist `why`), 5 (sous-titres karaoké — refaits style Submagic le 2026-07-06)** et **6 (recadrage face-aware — livré 2026-07-06/08 : crop 9:16 plein cadre par segment piloté par `face_center_x` de la deep vision, sans dépendance CV locale)** sont **implémentées et mergées dans `main`** (avec tests, 71 au total). Restent en roadmap : **7 (énergie audio), 8 (dédup/diversité arcs), 9 (trim silences), 10 (variantes méta), 11 (thumbnail)** + nouveaux candidats : cadrage par scène intra-segment, suivi du visage sur les gestes, juge vidéo natif. Récap côté exécution : `docs/pipeline.md` § « Améliorations qualité du rendu ».

---

## Pourquoi ce doc

La pipeline de **sélection** (comprendre la vidéo → trouver des arcs narratifs) est déjà solide : video map cheap, story arcs, vérification anti-hallucination, deep vision sur le top 5, scoring pondéré. Voir `docs/pipeline.md` et `docs/global-video-understanding.md`.

Les plus gros trous restants sont :

1. **en bout de chaîne** — le rendu (`ffmpeg.py`, `captions.py`) est encore brut comparé à Opus Clip / Submagic ;
2. **quelques signaux de compréhension faciles** que l'on peut ajouter parce que **les données sont déjà disponibles** (timestamps mot-à-mot, video map, deep vision).

Règle de priorisation (cf. `feedback`) : **pipeline/backend avant le polish UI**, et **pas de code spéculatif** — on ne code que ce qui améliore directement la qualité d'un clip livré.

---

## Vue d'ensemble (par où commencer)

| # | Brique | Catégorie | Fichier principal | Impact | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | Snapping des bords de segment | Compréhension | `pipeline/story_arcs.py` + nouveau util | ★★★ | ★ |
| 2 | Normalisation loudness (-14 LUFS) | Qualité rendu | `pipeline/ffmpeg.py` | ★★ | ★ |
| 3 | Gate QC sur le clip rendu | Qualité rendu | `pipeline/runner.py` + `ffmpeg.py` | ★★★ | ★ |
| 4 | Persister le `why` par segment | Explicabilité | `pipeline/runner.py` | ★★ | ★ |
| 5 | Sous-titres karaoké (mot actif) | Qualité rendu | `pipeline/captions.py` | ★★★ | ★★ |
| 6 | Recadrage intelligent (face-aware) | Qualité rendu | `pipeline/vision.py` + `ffmpeg.py` | ★★★ | ★★★ |
| 7 | Courbe d'énergie audio | Compréhension | `pipeline/video_map.py` + `ffmpeg.py` | ★★ | ★★ |
| 8 | Diversité / dédup des arcs | Compréhension | `pipeline/score.py` | ★★ | ★ |
| 9 | Trim silences / fillers intra-segment | Qualité rendu | `pipeline/captions.py` + `ffmpeg.py` | ★★ | ★★ |
| 10 | Variantes titre / hook / hashtags | Explicabilité | nouveau `pipeline/metadata.py` | ★★ | ★ |
| 11 | Thumbnail / poster frame par clip | Qualité rendu | `pipeline/ffmpeg.py` + `runner.py` | ★ | ★★ |

**Lot recommandé pour démarrer** (non-risqué, données déjà présentes, rapide) : **1 + 2 + 3 + 4**.
**Deuxième vague** (le vrai saut visuel) : **5 + 6**.

---

## 1. Compréhension de la vidéo (mieux choisir)

### 1.1 Snapping des bords de segment — *le plus rentable*

**Constat.** Le LLM rend des `start`/`end` approximatifs (`story_arcs.py`), et on les rend tels quels (`ffmpeg.py`). Résultat : des clips qui démarrent au milieu d'un mot ou coupent une phrase en deux. C'est *la* chose qui fait qu'un clip « sonne » fini ou cassé.

**Technique.** On a déjà les timestamps mot-à-mot (`transcript.words`). Pour chaque segment :

- caler le `start` sur le **début de phrase / silence** le plus proche en amont (à ±1,5 s de tolérance) ;
- caler le `end` sur la **fin de phrase / silence** le plus proche en aval ;
- détection de « frontière » = trou inter-mots > ~350 ms, ou ponctuation forte (`. ! ?`) si dispo dans le texte.

Implémentation : nouvel util `pipeline/boundaries.py` (`snap_segment(words, start, end) -> (start, end)`), appelé juste après `verify_arcs` dans `runner.py`, avant la deep vision et le render.

**Impact ★★★ / Effort ★** — purement local, aucune dépendance externe, aucun coût LLM.

### 1.2 Courbe d'énergie audio

**Constat.** On cherche les bons moments via transcript + frames éparses. On rate les pics **non-verbaux** : rire, cri, silence dramatique, drop musical — signaux de viralité forts.

**Technique.** Un passage ffmpeg de mesure de loudness donne une courbe par seconde, injectée dans la video map pour pondérer `visual_importance` et aider la sélection d'arcs.

```bash
# RMS / volume par fenêtre
ffmpeg -i source.mp4 -af astats=metadata=1:reset=1 -f null -
# ou loudness perceptuelle (EBU R128)
ffmpeg -i source.mp4 -af ebur128=metadata=1 -f null -
```

On parse la sortie en une liste `(t_seconds, loudness)` → résumé par event de la video map (`video_map.py`), puis exposé au prompt story arcs comme signal supplémentaire (« moments à forte énergie audio »).

**Impact ★★ / Effort ★★** — un passage ffmpeg de plus + parsing, pas de coût LLM additionnel.

### 1.3 Diversité / dédup des arcs

**Constat.** `rank_and_pick` (`score.py:200`) prend juste le top N par score. Rien n'empêche deux clips retenus de couvrir le même moment → l'utilisateur reçoit des quasi-doublons.

**Technique.** Pénalité de chevauchement temporel à la sélection (style **MMR — Maximal Marginal Relevance**) : on sélectionne glouton, et chaque candidat déjà retenu pénalise les candidats qui recouvrent ses segments source (overlap IoU sur l'axe temps). Garantit N clips *différents*.

**Impact ★★ / Effort ★** — logique pure dans `score.py`.

---

## 2. Qualité du clip rendu (le plus gros écart vs concurrents)

### 2.1 Recadrage intelligent (face-aware) — *le plus gros saut visuel*

**Constat.** Aujourd'hui c'est un crop centre bête (`ffmpeg.py`) :

```
scale=-2:1920,crop=1080:1920,setsar=1
```

Si le sujet est décentré, en plan large, ou en partage d'écran → il est coupé. C'est le différenciateur visuel de tous les outils du marché (Opus / Submagic font de l'auto-reframe qui suit le visage).

**Technique.** On fait **déjà** un passage vision sur les top arcs (`deep_vision_for_arc`). Il suffit que la vision retourne une **zone d'intérêt** (focus `left | center | right`, ou bbox normalisée du visage / de l'action), puis on décale le `x` du crop :

```
# crop décalé : on garde la largeur 1080 mais on centre sur le sujet
scale=-2:1920,crop=1080:1920:x=<offset>:y=0,setsar=1
```

V1 simple : 3 positions (gauche / centre / droite) suffisent pour 90 % des cas (talking head décentré, gameplay, slide). V2 : suivi continu / split-screen.

**Impact ★★★ / Effort ★★★** — il faut enrichir `VisionResult` (champ `focus`/`bbox`), le prompt deep vision, et le crop ffmpeg. Mais c'est le saut de qualité le plus visible.

### 2.2 Sous-titres karaoké (mot actif surligné)

**Constat.** Les captions actuelles (`captions.py`) sont statiques, blanches, par paquets de 5 mots, sans highlight du mot prononcé.

**Technique.** Le surlignage mot-par-mot est *la* feature « ça fait pro » du short-form, et on a **déjà** les timestamps mot par mot. Deux approches en ASS (déjà notre format) :

- tags **`\k`** (karaoké natif ASS) sur chaque mot d'une ligne, avec une couleur secondaire pour le mot actif ;
- ou un **event par mot** avec override de couleur (`\c`) plus contrôlable (taille « punch », couleur d'accent par mot-clé).

On garde le chunk de ~5 mots à l'écran, mais le mot en cours passe en couleur d'accent / léger scale.

**Impact ★★★ / Effort ★★** — réécriture de `write_ass_for_montage`, données déjà présentes.

### 2.3 Normalisation loudness + gate QC

Deux ajouts au render loop (`runner.py` + `ffmpeg.py`) :

**Loudnorm.** Le son source varie énormément ; là on ne fait que l'`acrossfade` entre segments. Un filtre vers ~ **-14 LUFS** (cible plateformes) donne un volume constant entre clips :

```
-af loudnorm=I=-14:TP=-1.5:LRA=11
```

**Gate QC après rendu.** Aujourd'hui on ne vérifie **rien** sur le fichier produit : on upload directement (`runner.py`, boucle de render). Un probe rapide éviterait de livrer des clips morts :

- durée rendue dans la tolérance attendue (`abs(probe - attendu) < 0.5 s`) ;
- présence d'au moins un **flux audio** ;
- **volume moyen** > plancher (pas de clip muet) — via `volumedetect` ;
- **frame pas toute noire** (échantillon au milieu, luminance moyenne > seuil).

Si la QC échoue → on log et on saute ce clip (ou on retente sans sous-titres, comme déjà fait pour le burn-in). Évite les « ratés » qui détruisent la confiance.

**Impact ★★★ (QC) / ★★ (loudnorm) / Effort ★** chacun.

### 2.4 Trim des silences / fillers intra-segment

**Constat.** À l'intérieur d'un segment, les blancs et les « euh » restent → rythme mou.

**Technique.** À partir des word timestamps : repérer les trous > ~600 ms et les fillers, raccourcir le segment en micro-coupes (ou via `silenceremove` ffmpeg pour l'audio + coupe vidéo alignée). Attention à garder le retiming des captions cohérent (`captions.py` recalcule déjà les offsets — il faudra propager les micro-coupes).

**Impact ★★ / Effort ★★.**

---

## 3. Explicabilité (comprendre *pourquoi* ce clip)

### 3.1 Persister le `why` par segment

**Constat.** Le LLM justifie **chaque** segment (`ArcSegmentSpec.why`, bien parsé dans `story_arcs.py`), mais `_segments_to_jsonb` (`runner.py:365`) ne sérialise que `role / start / end / transcript_excerpt` → **la justification est jetée**.

**Technique.** Ajouter `why` dans le JSONB des segments stockés. Gratuit, et ça rend chaque morceau du montage explicable côté produit.

**Impact ★★ / Effort ★.**

### 3.2 Variantes titre / hook / hashtags par clip

**Constat.** On stocke `title`, `hook`, `rationale`, mais une seule version.

**Technique.** Un petit appel LLM en fin de pipeline (nouveau `pipeline/metadata.py`) produisant, par clip retenu : 3 variantes de titre, 2-3 hooks, des hashtags et une description prête à coller. Coût négligeable (texte court), très haute valeur perçue — c'est ce que l'utilisateur copie-colle directement.

**Impact ★★ / Effort ★.**

### 3.3 Thumbnail / poster frame par clip

**Constat.** On ne génère aucune vignette par clip.

**Technique.** Choisir la meilleure frame (visage net + énergie haute, signaux qu'on a déjà via deep vision / courbe audio), l'extraire en JPEG, l'uploader à côté du clip. Utile pour l'UI et c'est aussi un signal de compréhension (« voilà le moment fort »).

**Impact ★ / Effort ★★.**

---

## Récapitulatif d'implémentation

| Brique | Fichiers touchés | Nouveau coût LLM/vision ? |
| --- | --- | --- |
| 1. Snapping des bords | `pipeline/boundaries.py` (nouveau), `runner.py` | Non |
| 2. Loudnorm | `pipeline/ffmpeg.py` | Non |
| 3. Gate QC | `pipeline/ffmpeg.py`, `runner.py` | Non |
| 4. Persist `why` | `runner.py` (`_segments_to_jsonb`) | Non |
| 5. Karaoké | `pipeline/captions.py` | Non |
| 6. Recadrage face-aware | `models.py`, `prompts.py`, `pipeline/vision.py`, `ffmpeg.py` | Non (réutilise la deep vision) |
| 7. Énergie audio | `pipeline/ffmpeg.py`, `video_map.py`, `prompts.py` | Non |
| 8. Diversité arcs | `pipeline/score.py` | Non |
| 9. Trim silences | `pipeline/captions.py`, `ffmpeg.py` | Non |
| 10. Variantes méta | `pipeline/metadata.py` (nouveau), `runner.py`, `prompts.py` | Oui (texte court) |
| 11. Thumbnail | `pipeline/ffmpeg.py`, `runner.py` | Non |

À noter : **10 briques sur 11 n'ajoutent aucun coût LLM/vision** — elles réutilisent des données déjà calculées (word timestamps, deep vision, video map). Seules les variantes méta (#10) ajoutent un petit appel texte. La marge par job reste sous contrôle (cf. `docs/pipeline.md` § coût).

---

## Définition de succès

La pipeline est « niveau marché » quand un clip livré :

- démarre et finit sur une **phrase complète** (snapping) ;
- garde le **sujet bien cadré** même s'il est décentré (recadrage) ;
- a des **sous-titres karaoké** avec mot actif surligné ;
- a un **volume constant** (-14 LUFS) et passe la **QC** (pas de clip muet/noir) ;
- est livré avec son **« pourquoi »**, des **variantes de titre/hook** et une **vignette**.

Le tout **sans exploser la marge** : la quasi-totalité des améliorations réutilise des signaux déjà calculés.
