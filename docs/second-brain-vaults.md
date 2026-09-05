# ClipFactory — Second Brain éditorial navigable

Statut : fondations locales implémentées et testées, sans activation dans
`runner.py`, sans base persistante et sans remplacement du chemin V2 existant.

Architecture commune avec la recherche campagne, la traçabilité des décisions et
l’apprentissage gouverné : [`context-intelligence-architecture.md`](context-intelligence-architecture.md).

## Vision

ClipFactory ne doit pas injecter toute sa connaissance du montage dans un prompt
géant. Il doit disposer d’une mémoire externe inspirée d’Obsidian : notes
atomiques, liens typés, backlinks, provenance, exemples et contre-exemples.

Le LLM navigue dans cette mémoire pour résoudre une question éditoriale précise,
puis produit des décisions structurées et citées. Les timecodes restent sous le
contrôle du transcript et du compilateur EDL ; la mémoire ne peut jamais émettre
directement du FFmpeg.

## Les trois vaults

### 1. Global Editing Vault

Connaissance générale et réutilisable du montage :

- principes : intention de coupe, eye trace, continuité, tension/résolution ;
- techniques : J-cut, L-cut, punch-in, match cut, cut on motion, proof hold ;
- structures : proof-first, question/reveal, claim/proof, before/after ;
- diagnostics : hook faible, pronom orphelin, preuve illisible, payoff coupé ;
- exemples et contre-exemples multimodaux ;
- connaissance par format et plateforme, toujours datée et contextualisée.

### 2. Campaign Vault

Mémoire durable propre à une campagne :

- audience, douleurs, objections et vocabulaire ;
- offre, promesses autorisées, CTA et sujets interdits ;
- preuves disponibles et claims vérifiés ;
- ton et préférences éditoriales ;
- clips déjà produits, décisions et métriques ;
- hypothèses, expériences et apprentissages validés.

### 3. Source Vault

Compréhension d’une vidéo précise :

- transcript avec `word_id` ;
- phrases et moments narratifs ;
- plans, visages, écrans, objets, gestes et zones sûres ;
- silences, emphases, respirations et changements d’énergie ;
- claims, preuves, réactions et payoffs ;
- relations entre moments : `answers`, `proves`, `contrasts`, `causes`, etc.

Le workspace d’un clip combine les trois vaults pour produire l’EDL.

```text
Global Editing Vault
        +
Campaign Vault
        +
Source Vault
        -> Editor Brain -> décisions citées -> EDL -> rendu -> QC
```

## Modèle de note minimal

Les contenus peuvent rester compatibles Markdown/Obsidian, mais les IDs,
relations, permissions, versions et métriques doivent avoir une représentation
structurée en base.

```yaml
id: principle_readable_proof_hold
type: editorial_principle
vault: global
status: curated
confidence: high
tags: [proof, screen, readability]
source_refs: []
created_at: 2026-08-09
updated_at: 2026-08-09
```

```markdown
# Hold visual proof long enough to read

Une preuve visuelle n’a aucune valeur si le spectateur ne peut pas comprendre
ce qu’elle démontre.

## Use when

- [[Problem - Unreadable dashboard]]
- [[Pattern - Claim Proof]]

## Repairs

- [[Technique - Screen focus]]
- [[Technique - Proof crop]]
- [[Technique - Freeze frame]]

## Avoid when

- la preuve n’est pas vérifiée ;
- l’écran ne permet pas une lecture fiable, même après recadrage.
```

Types initiaux recommandés :

- `principle`, `technique`, `pattern`, `problem` ;
- `example`, `counterexample`, `case_study` ;
- `audience`, `objection`, `offer`, `claim`, `proof`, `asset` ;
- `source_moment`, `clip`, `decision` ;
- `observation`, `hypothesis`, `learning`, `policy`.

Statuts de confiance :

```text
raw_source -> observation -> hypothesis -> validated -> curated
                                                   -> deprecated
```

Une hypothèse ne doit jamais devenir automatiquement une policy après un seul
clip performant.

Le premier lot local peut conserver ce statut compact. Dans le stockage durable,
séparer ensuite trois axes évite les ambiguïtés : la nature épistémique
(`observation|hypothesis|learning|policy`), l’état de revue
(`unreviewed|approved|rejected`) et le cycle de vie
(`active|superseded|deprecated`). Les règles de promotion sont détaillées dans
[`context-intelligence-architecture.md`](context-intelligence-architecture.md).

## Relations typées

Ne pas se limiter aux backlinks textuels. Les relations utiles au raisonnement
doivent être explicites :

```text
proves          answers          contradicts      causes
supports        repairs          risks            requires
used_in         derived_from     targets          performs_for
```

Exemple :

```text
[[Proof - Conversion 10%]]
    proves -> [[Claim - Le trafic convertit]]
    answers -> [[Objection - Personne n’achètera]]
    used_in -> [[Clip - Curiosity 002]]
    requires -> [[Principle - Readable proof hold]]
```

## Navigation du LLM

Le LLM ne reçoit pas le vault entier. Il dispose d’outils de lecture bornés :

```text
search_notes(query, vaults, types, status, limit)
open_note(note_id)
get_neighbors(note_id, relations, depth, limit)
get_backlinks(note_id, relation, limit)
find_examples(pattern_id, content_type, campaign_id, limit)
compare_patterns(pattern_ids, campaign_goal, available_evidence)
```

Recherche recommandée : plein texte + embeddings + filtres structurés + parcours
du graphe + reranking. Un budget de navigation limite le nombre de notes et de
liens ouverts pour chaque décision.

Boucle de raisonnement :

1. formuler la question éditoriale ;
2. rechercher les notes pertinentes ;
3. ouvrir quelques principes, exemples et contre-exemples ;
4. traverser les relations nécessaires ;
5. produire une décision avec références ;
6. compiler et vérifier la décision de façon déterministe.

## Une mémoire opérationnelle, pas seulement du RAG

Un vector store qui retourne des paragraphes proches ne constitue pas un
Second Brain. ClipFactory a besoin de quatre formes de mémoire complémentaires :

1. **sémantique** — principes, audience, claims et faits versionnés ;
2. **relationnelle** — ce qui prouve, contredit, répare ou exige autre chose ;
3. **épisodique** — une décision précise, son contexte, son rendu et son
   résultat observé ;
4. **procédurale** — les policies revues qui autorisent ou interdisent une
   action déterministe.

La recherche hybride sert uniquement à proposer des candidats. Les relations,
scopes, statuts, versions et autorités décident ensuite ce qui peut réellement
entrer dans un `EditorialContextPack`. Un score d'embedding élevé ne peut donc
jamais contourner une permission, ressusciter une note deprecated ou transformer
une observation web en claim approuvé.

## Admission : comment la mémoire apprend sans se polluer

Chaque écriture passe par une file d'admission explicite :

```text
raw artefact
  -> normalisation + provenance
  -> observation immutable
  -> détection doublon / contradiction / scope
  -> revue ou expérience préenregistrée
  -> learning borné
  -> policy humaine versionnée
```

Les événements source, research, QC, feedback et plateforme restent des
observations séparées. Ils ne réécrivent jamais rétroactivement une décision ou
une note utilisée par un ancien clip. Une nouvelle version supersède l'ancienne,
mais l'audit historique continue de pointer son digest exact.

Une contradiction n'est pas un déchet à supprimer. Elle devient une relation
`contradicts` ou `risks` et doit accompagner le principe récupéré quand elle est
pertinente. C'est ce qui empêche la mémoire de devenir une machine à confirmer
les croyances du Director.

## Retrieval comme compilateur de question

La bonne unité d'entrée n'est pas « fais un bon clip », mais une question
fermée : hook, preuve, objection, payoff, continuité, CTA ou diversité de
variante. La question porte les beats et source moments autorisés. Le retriever :

1. filtre d'abord owner/campaign/source/status/version ;
2. exige une note Source liée aux evidence IDs demandés ;
3. sélectionne les observations Campaign utiles à l'hypothèse ;
4. n'ajoute un principe Global qu'avec son contre-exemple atomique ;
5. rejette les contraintes dures contradictoires ;
6. projette un JSON stable et borné, avec une allowlist exacte de références.

Le Context Pack est donc plus proche d'un artefact compilé que d'un résultat de
recherche : même entrée, même snapshot et même policy produisent les mêmes notes,
le même ordre et le même digest.

## Oubli, fraîcheur et archive

Le Second Brain ne supprime pas l'histoire, mais il distingue clairement :

- **actif** : admissible pour une nouvelle décision ;
- **expiré** : visible pour audit, exclu de la décision ;
- **superseded** : remplacé par une version plus récente ;
- **deprecated** : connu comme faux, dangereux ou obsolète ;
- **archive research** : finding conservée, mais absente de la lignée de
  recherche active de la campagne.

La décroissance n'est pas un simple score temporel. Une préférence de montage
peut vieillir lentement, une note plateforme rapidement, et une preuve source ne
vaut que pour son asset. Les TTL et règles de révision doivent donc dépendre du
type, du scope et de la provenance.

## Contrat d’une décision éditoriale

Une décision doit relier connaissance, source et campagne :

```json
{
  "decision_id": "decision_014",
  "shot_id": "conversion_proof",
  "decision": "use_screen_focus_and_extend_hold",
  "motivation": "proof_reveal",
  "knowledge_refs": [
    "principle_readable_proof_hold",
    "technique_screen_focus"
  ],
  "source_refs": [
    "visual_beat_dashboard_031",
    "claim_conversion_10pct"
  ],
  "campaign_refs": [
    "objection_results_are_not_real",
    "goal_build_credibility"
  ]
}
```

Les références doivent être validées. Une note ne donne aucune autorité sur les
timecodes, chemins de fichiers, assets ou filtres de rendu.

## Connaissance multimodale

Une note d’exemple peut référencer :

- proxy vidéo court ;
- contact sheet ;
- frames autour d’une coupe ;
- waveform et carte audio ;
- transcript synchronisé ;
- EDL et captions ;
- métriques et résultat du QC.

Le LLM reçoit des proxies ciblés, jamais automatiquement le média 4K complet.

## Stockage SaaS recommandé

- contenu de note en Markdown pour la lisibilité et l’export Obsidian ;
- métadonnées, relations, versions et permissions en Postgres ;
- index plein texte et vectoriel pour la recherche ;
- médias/proxies dans le stockage objet ;
- isolation stricte par `user_id` et `campaign_id` ;
- export/import d’un vault Markdown comme fonctionnalité produit ultérieure.

Le Markdown ne doit pas être l’unique source de vérité des permissions ou des
relations critiques.

## Premier lot local — réalisé

Objectif : prouver la navigation et la traçabilité sans toucher au runner.

1. Définir `KnowledgeNote`, `KnowledgeRelation`, `KnowledgeRef` et leurs
   validations dans un module provider-independent.
2. Créer un petit vault fixture contenant 20 à 30 notes de montage, campagne et
   source, avec relations typées.
3. Implémenter une API de lecture pure : recherche, ouverture, voisins et
   backlinks, avec limites strictes.
4. Construire un `EditorialContextPack` compact à partir d’une question de
   montage et vérifier que toutes les références sont réelles.
5. Étendre ensuite le contrat du Director pour exiger `knowledge_refs`,
   `source_refs` et `campaign_refs` par décision.
6. Réutiliser l’EDL V2 existante pour les timings, la validation et le rendu.

Le lot local couvre maintenant davantage que ce socle :

- vault global/campaign/source immuable, versionné et strictement scoped ;
- recherche, ouverture, voisins et backlinks bornés ;
- matérialisation one-way du brief, des findings web et du BeatGraph ;
- snapshot canonique sans transcript, timecodes, chemins ou URLs de source ;
- enveloppe tenant HMAC liant l'exact vault de base à
  `owner_id/campaign_id/source_id`; toute composition non globale et toute
  émission de contexte la revérifient, puis digèrent ce binding dans le
  snapshot ;
- retrieval déterministe obligatoire par question, qui bloque les contraintes
  campagne explicitement contradictoires ;
- lignée research active explicite : les observations historiques restent
  archivées, mais seules les notes matérialisées depuis le digest de recherche
  courant peuvent être sélectionnées ;
- contexte éditorial unifié reprenant exactement ses sélections, avec quotas et
  contre-exemple global ;
- Director 2.2 cité, abaissé sans modification vers l'EDL 2.1/2.0 ;
- capability HMAC locale obligatoire du couple snapshot/contexte avant tout
  prompt, parse, validation ou compile Director ;
- preuves vision signées par asset/graphe/fenêtre/frames/ROI avant tout
  `screen_focus`, `locked_face` ou claim visuel ;
- claims source/research/opérateur séparés, avec usages signés : les captions et
  paroles restent transcript-owned, la recherche reste rationale-only, et une
  overlay exige une approbation opérateur signée ;
- audit digesté plan/shot, provenance de variante liée au snapshot/issuance,
  puis enveloppe de variante signée liée au render ; expériences et outcomes
  restent liés à cette provenance ;
- gouvernance append-only séparant nature, revue et lifecycle ;
- autorité de promotion courte durée qui recalcule expériences/outcomes avant
  de laisser une policy entrer dans la gouvernance, puis conserve son digest.

Les signatures locales permettent de tester les vraies frontières de
consommation : un objet public, un token Python importé ou un digest isolé ne
suffisent pas. Elles ne remplacent pas encore un service de clés/KMS, une ACL de
base, un journal append-only persistant ou la rotation/révocation d'autorité
multi-tenant en production.

Tests d’acceptation du premier lot :

- aucune fuite entre deux campaign vaults ;
- une relation vers une note inconnue est rejetée ;
- les notes `deprecated` ne sont pas proposées par défaut ;
- une décision sans preuve source ou sans objectif campagne est rejetée lorsque
  la policy l'exige ;
- une note campaign/source ne peut pas être relabellée sous un autre owner avec
  une authority d'un autre scope ;
- une classification web, une ROI, un claim ou une provenance de variante
  auto-déclarés sont rejetés sans leur enveloppe et leur verifier ;
- le context pack respecte son budget et conserve la provenance ;
- le même ensemble d’inputs produit le même pack ordonné ;
- aucun appel réseau, rendu ou modification de `runner.py`.

## Non-objectifs initiaux

- ne pas fine-tuner un modèle par campagne ;
- ne pas injecter tout le vault dans un prompt ;
- ne pas laisser le LLM créer directement du FFmpeg ;
- ne pas apprendre automatiquement une règle depuis une seule performance ;
- ne pas activer ce système en production avant validation locale et revue des
  frontières de confiance.

## Décision produit

Cette architecture transforme ClipFactory d’une pipeline qui appelle un LLM en
un système de montage doté d’une mémoire externe navigable. La différenciation
vient de l’accumulation d’un savoir de montage global, combiné à une mémoire
spécifique à chaque campagne et à une compréhension détaillée de chaque source.
