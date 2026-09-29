# Plan de test des modèles — par groupes, campagne de A à Z

> Statut : **préparé, pas lancé.** Deux conditions avant de démarrer :
> 1. **Backend fiable** sur le Mac Studio M1 Max (`docs/mac-studio-backend.md` terminé, `doctor.sh` vert, un vrai job réussi depuis le site).
> 2. **Pipeline à sa meilleure version**, figée sous un tag (section suivante). Comparer des modèles sur un moteur incomplet ne dit rien.
> Rédigé le 2026-09-29.

## La méthode (décision d'Augustin)

On ne choisit pas un modèle sur un score d'étape isolée. On compose des **groupes** — une stack complète (transcription + sélection des moments + vision) — et on lance **la même campagne de A à Z** avec chaque groupe, avec le vrai code du pipeline. Puis on **regarde les clips** : quels moments ont été choisis, comment ils sont coupés et montés. Un modèle excellent seul peut donner de mauvais clips une fois enchaîné.

Les bancs par étape servent seulement à **éliminer d'avance** les modèles cassés. C'est déjà fait pour la transcription (29/09, 2 min FR) : deepgram, assemblyai, gpt-transcribe, gpt-4o-mini-transcribe, chirp-3, muse-voice, voxtral-small, qwen3-asr-flash ne renvoient **pas** de timestamps au mot via OpenRouter → exclus.

## Condition 2 : le pipeline à sa meilleure version (tag `pipeline-vtest`)

Tous les groupes tournent sur **exactement le même code**, taggé `pipeline-vtest-AAAA-MM-JJ`. Ce tag n'est posé que quand toutes les cases ci-dessous sont cochées et que les tests sont verts. Le plan de finition détaillé (étapes 0 à 7, critères de sortie, estimations) est dans le document privé « Second Brain, Director et montage multi-segments : inventaire et plan de finition » (`~/data clips/docs-prives/`).

| Brique | Meilleure version visée | État au 29/09 |
|---|---|---|
| Ancrage / bornes / vérif | `boundaries` strict + `verify` par couverture | ✅ PR #8 |
| Moteur de rendu | `clip_render` → EDL V2 (`edl`, `edl_render`, `edl_captions`), QC média | ✅ PR #8 (branché) |
| Crédits / cycle de vie des jobs | réservation atomique, jeton de tentative, séries | ✅ PR #8 |
| Transcription | backend enfichable (API ou MLX local) + correctif durée nulle | ⏳ correctif ✅ PR #8 ; MLX = runbook Mac Studio §6 |
| Fins et ouvertures | sous-ensemble fins/ouvertures de `editorial_reflex_qc` en post-ancrage ; contrôle promesse → payoff | ❌ étape 1 |
| Montage multi-segments | `duration_seconds` juste, `link_reason` / `campaign_fit_reason` persistés, `snap failed` instrumenté | ❌ étape 1 |
| Second Brain de campagne | version légère : raisons de rejet (liste fermée), feedback de campagne relu, exemples bons/mauvais injectés dans la sélection et le juge, règles de craft (contenu des 29 notes) par tags | ❌ étape 2 |
| Juge de clip | `clip_judge` calibré sur 40 clips notés par Augustin, d'abord en observation | ⏳ code ✅ PR #8 (désactivé) ; calibration ❌ étapes 0 et 3 |
| Cadrage | crop piloté par la vision deep (`face_center_x`), zéro bande noire | ❌ étape 4 |
| Opérations de montage | trim des silences, punch-in sur le chiffre ou la chute, profil de sortie par plateforme, texte-hook vérifié, cold open typé — chacune retenue seulement si elle gagne en A/B | ❌ étape 5 |
| Director | passe de réparation bornée (1 passe, 2 variantes max), déclenchée seulement par un échec du QC ou du juge | ❌ étape 6 |

Minimum pour poser le tag : **étapes 0 à 4**. Les étapes 5 et 6 peuvent entrer si elles sont finies ; sinon on teste sans, et elles repassent en A/B plus tard sur le groupe gagnant.

**Règle d'ordre** : on fige le pipeline → on compare les groupes de modèles → on ré-ajuste les prompts pour le groupe gagnant (et seulement lui). On ne mélange jamais un changement de pipeline et un changement de modèle dans la même comparaison.

## Les groupes

Chaque groupe = un fichier `models.lock` (mécanisme de la PR #8), chargé par le worker via `MODELS_LOCK_PATH`. Le juge est le même pour tous et ne fait pas partie de la comparaison.

| Groupe | Idée | Transcription | Sélection / arcs / score | Vision détaillée | Vision rapide (video map) |
|---|---|---|---|---|---|
| **G0 Référence** | la prod d'avant (si encore disponible le jour du test) | `whisper-1` | `google/gemini-2.5-flash` (expire le 20/10) | `qwen/qwen3-vl-32b-instruct` (expire le 09/10) | idem |
| **G1 Google** | le lock provisoire actuel | `openai/whisper-large-v3` (OpenRouter) | `google/gemini-3.8-flash` | `google/gemini-3.8-flash` | `qwen/qwen3-vl-30b-a3b-instruct` |
| **G2 Chinois** | meilleurs modèles chinois repérés | `qwen/qwen3-asr-1.7b` + correctif durée nulle | `xiaomi/mimo-v2.6-pro` | `qwen/qwen3.8-flash` | `qwen/qwen3-vl-30b-a3b-instruct` |
| **G3 Éco** | le moins cher qui tienne | `openai/whisper-large-v3-turbo` | `google/gemini-3.1-flash-lite` | `qwen/qwen3-vl-30b-a3b-instruct` | idem |
| **G4 Local M1 Max** | transcription gratuite sur le GPU | `mlx-whisper` large-v3-turbo (local) | `deepseek/deepseek-v4.1-flash` | `qwen/qwen3-vl-30b-a3b-instruct` | idem |

Remplaçant possible si un groupe ne tient pas : `x-ai/grok-stt-1.0` (0 mot de durée nulle au pré-test), `z-ai/glm-5.3-flash`. Vérifier que chaque identifiant existe sur OpenRouter la veille du test.

Juge commun (aide à la lecture, pas arbitre) : `google/gemini-3.8-flash` en vidéo native.

## Les campagnes et les vidéos (figées)

- **2 campagnes** : une FR (podcast business / entrepreneuriat), une EN (créatrice business). Brief réel et complet : audience, niche, ton, objectif, 3 hooks d'exemple.
- **4 vidéos sources figées**, copiées une fois pour toutes dans un dossier « golden » hors repo (jamais re-téléchargées) : 2 FR solo/interview déjà utilisées dans les bancs précédents, 1 FR à 2 voix, 1 EN longue (~30 min). La liste exacte est privée.
- Paramètres identiques pour tous les groupes : même nombre de clips demandés, mêmes durées cibles, même rendu, même style de sous-titres.

## Déroulé le jour J

1. `doctor.sh` vert. Noter le commit déployé.
2. Pour chaque groupe : pointer `MODELS_LOCK_PATH` sur son fichier, redémarrer le worker, lancer les 2 campagnes depuis le site **comme un vrai client** (4 jobs). Un groupe à la fois, jamais deux en parallèle.
3. Le worker écrit pour chaque job un **manifeste** : moments choisis (citations du transcript, début/fin, raison, scores), coût par étape, temps par étape, modèle réellement utilisé (y compris bascule vers un modèle de secours).
4. Contrôle de cohérence : un job qui a basculé sur le modèle de secours est **relancé** ou marqué, sinon la comparaison est faussée.

## La revue (Augustin, ~45 min)

Une page de comparaison générée à partir des manifestes :

- **Par vidéo source**, tous les clips de tous les groupes, **mélangés et anonymisés** (le groupe est caché jusqu'à la fin).
- Pour chaque clip : publiable oui/non + une raison dans une **liste fermée** (accroche faible, coupe en pleine phrase, sans contexte, chute absente, mauvais cadrage, sous-titres, trop long, autre).
- Pour chaque source : « quel lot de clips posterais-tu ? » (classement des groupes).
- Vue « timeline » : sur la vidéo source, quels moments chaque groupe a choisis — pour voir s'ils trouvent les mêmes pépites.

## Règle de décision

1. Le groupe gagnant = **le plus de clips publiables** selon Augustin.
2. À égalité (±1 clip) : le moins cher par vidéo, puis le plus rapide.
3. Le gagnant devient le `models.lock` de prod. On peut ensuite échanger **une seule brique** à la fois avec le 2ᵉ groupe et refaire un mini-test, si un groupe gagne sur la sélection et un autre sur la transcription.
4. Métriques automatiques (recoupement avec la courbe « most replayed » YouTube, fins suspendues, coût) : lues **après** la revue humaine, pour expliquer, pas pour décider.

## Budget

Estimation : 0,05 à 0,20 $ par job selon le groupe → 5 groupes × 4 jobs ≈ **1 à 4 $**. G4 ne paie pas la transcription.

## À préparer avant le jour J (sans rien lancer)

- [ ] Backend fiable sur le M1 Max (`docs/mac-studio-backend.md`).
- [ ] Pipeline à sa meilleure version, tag `pipeline-vtest-…` posé (condition 2).
- [ ] Les 5 fichiers de groupes `ops/model-groups/g0…g4.toml` (format de `models.lock.toml`).
- [ ] Manifeste de job complet (vérifier ce que le runner écrit déjà ; ajouter le modèle réellement utilisé par étape).
- [ ] Le backend ASR local (`mlx_whisper`) pour G4 — prévu dans le runbook Mac Studio.
- [ ] Les 2 briefs de campagne rédigés, les 4 vidéos figées.
- [ ] Le générateur de page de comparaison (lit les manifestes, anonymise, exporte les votes en CSV).
- [ ] Vérification des identifiants OpenRouter et des dates d'expiration la veille.
