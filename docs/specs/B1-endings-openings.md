# B1 — Fins, ouvertures et bugs du montage

> Spec pour **Codex**. Étape B1 de `docs/roadmap.md`. Prérequis : B0 mergé (harnais golden, métriques, rendement de départ connu).
> Branche : `feat/b1-endings` (part de `feat/b0-golden` ; à rebaser sur `main` après le merge de B0). PR en brouillon. **Tu ne merges pas, tu ne déploies pas.**

## Le problème, constaté en prod

- Job du 30/09 (podcast 23 min) : **3 clips sur 3 finissent au milieu d'une phrase** (« …tu voyais tous les trucs **que** », « …n'importe quel business **Si** », « …ça fait trop **longtemps** »). Le premier segment du montage finit sur « …100 par mois **Et** ».
- Job du 02/10 : un clip **déborde** sur l'échange suivant (« …Félicitations les gars Magnifique **Comment ça va frérot** »).

## La cause (à confirmer sur le golden avant de coder)

`boundaries.build_phrase_index` découpe les phrases avec `Transcript.sentences`, qui sont les **segments** Whisper. Un segment Whisper est un bloc délimité par des pauses, pas une phrase : il peut finir sur « Et » ou contenir la fin d'une phrase et le début de la suivante. Les **mots** Whisper n'ont pas de ponctuation, alors que le **texte des segments** en a. On a donc une ponctuation disponible mais jamais reportée sur les mots ; les fins « de phrase » utilisées par le snap et l'extension sont fausses.

Étape 0 obligatoire : sur les sources golden, mesurer pour chaque clip le dernier mot, sa ponctuation dans le texte du segment, la distance à la vraie fin de phrase, et pourquoi le snap ou l'extension n'a pas atteint cette fin (`MAX_*`, `END_EXTENSION_MAX_DURATION`, échec de snap). Mettre ce diagnostic dans la PR **avant** le correctif.

## Ce qu'il faut construire

### 1. Ponctuation au niveau du mot
Dans `transcribe.py` (fonction partagée par tous les backends ASR) : aligner le texte ponctué de chaque segment sur ses mots (`difflib` sur les formes normalisées, déjà utilisé ailleurs) et attacher à chaque `TranscriptWord` la ponctuation qui le suit (`.`, `?`, `!`, `…`, `,`, `:`). Les vraies fins de phrase deviennent les mots suivis de `. ? ! …`. Repli : si l'alignement échoue sur un segment, garder le comportement actuel pour ce segment et le compter dans les métriques.

### 2. Index de phrases sur les vraies fins
`build_phrase_index` utilise ces fins de phrase mot à mot en priorité, puis les segments, puis les silences. Les phrases trop longues restent coupées à leur plus grand silence interne, comme aujourd'hui.

### 3. Règles de fin (après ancrage, avant rendu)
Pour chaque clip **et chaque segment d'un montage** :
- la fin doit tomber sur une **vraie fin de phrase** ;
- le dernier mot ne doit pas appartenir à la **liste fermée des mots qui appellent une suite** (la même que la métrique B0 : et, mais, donc, si, que, parce, alors, car, ou, because, and, but, so, if, that, or…) ;
- sinon, dans l'ordre : **prolonger** jusqu'à la fin de phrase suivante si la durée reste dans la cible ; sinon **raccourcir** jusqu'à la fin de phrase précédente si le payoff reste dans le clip ; sinon **écarter le candidat** et prendre le suivant du classement (log `boundaries.candidate_dropped_ending`).
- ne jamais prolonger dans **la prise de parole suivante** (changement de locuteur ou silence long) : c'est le cas « Comment ça va frérot ».

### 4. Règles d'ouverture
- le premier mot ne doit pas être un connecteur ou un pronom sans référent (liste fermée de la métrique B0) ;
- sinon reculer jusqu'au début de la phrase (dans la limite de durée), sinon avancer jusqu'à la phrase suivante, sinon écarter.

### 5. Promesse → chute
Le `payoff_line` de l'arc doit être présent dans les mots du dernier segment, et le titre ne doit rien promettre qui ne soit pas dit dans le clip (vérification par mots-clés, sans appel LLM). Sinon : réparer la fin (règle 3) ou écarter. S'inspirer de `_mid_thought_findings` de `editorial_reflex_qc.py` (branche `codex/full-stack-benchmark-2026-09-12`) : reprendre **seulement** la logique fins/ouvertures, pas le reste du module.

### 6. Bugs connus du montage
- `clips.duration_seconds` faux pour les montages (fin − début global au lieu de la **somme des segments**) ; `rendered_duration_seconds` est juste, aligner les deux.
- `link_reason` et `campaign_fit_reason` sont parsés mais jamais enregistrés : les écrire dans `clips.segments` (jsonb, **sans migration**) et dans le manifeste golden.
- Échecs de snap : compter par motif dans l'artefact du job et dans le rapport golden.

## Ce qu'on ne fait pas dans B1
Pas de changement de modèle, de prompt de sélection, de cadrage, de sous-titres ni d'effet de montage. Seulement les bornes, plus les bugs listés. (Règle : un seul changement de pipeline à la fois, jamais en même temps qu'un changement de modèle.)

## Tests
- Alignement de ponctuation : FR avec élisions (« J'ai », « c'est »), nombres, segment sans ponctuation, segment mal aligné (repli).
- Règles de fin et d'ouverture : les 4 cas réels ci-dessus en fixtures (transcript minimal), prolongation, raccourcissement, abandon, frontière de locuteur.
- Montage : chaque segment respecte les règles ; `duration_seconds` = somme des segments.
- Aucun appel payant dans les tests.

## Critères de sortie (sur le golden B0, mêmes sources, mêmes modèles)
| Métrique | Seuil |
|---|---|
| Fins suspendues (clip et segments) | **0** |
| Ouvertures dépendantes | ≤ 10 % |
| Coupes dans un mot | 0 |
| Rendement publiable (juge en observation + contrôle humain sur 10 clips) | ≥ B0 |
| Recoupement « most replayed » | pas de baisse > 5 points vs B0 |
| Coût et durée d'un job | pas de hausse > 10 % |
| Candidats écartés | rapportés ; si > 30 %, le signaler avant de merger |

Rapport dans la PR : tableau B0 vs B1 sur les mêmes sources, diagnostic de l'étape 0, et 5 exemples avant/après (fin du clip en texte).
