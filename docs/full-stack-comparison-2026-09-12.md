# Run comparatif local — clipping et Director 2.2

Le run produit trois clips de référence et trois choix du Director 2.2, rendus à nouveau avec la même présentation pour comparer leur découpage. Sur cette vidéo, les trois fins incomplètes de la référence deviennent des phrases terminées. Les ouvertures et l’adéquation au brief restent imparfaites. Le Director libre a échoué avant que le contrat soit précisé pour ces passages continus : ce résultat ne valide donc pas encore un montage autonome général.

Artefacts : `/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12`.
Branche locale : `codex/full-stack-benchmark-2026-09-12`, issue de `f17e1295757cfccd59392652bc6c07cb8b32a067`. Travail non committé, sans publication ni déploiement. Le dossier rassemble le travail de qualité antérieur et les modules du prototype local ; les autres worktrees sont conservés.

## Vidéos à comparer

Les colonnes ci-dessous utilisent le même fond flouté, le même moteur de sous-titres et le même style. Le modèle choisit les mots du montage Director ; le banc de comparaison impose ensuite cette présentation commune. Cette adaptation conserve exactement les plages de mots du plan Director compilé, vérifiées avant rendu.

| Extrait | Référence actuelle | Director, présentation identique | Lecture du résultat |
|---|---|---|---|
| Résultat e-commerce | [22,50 s](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/selector/clip_00.mp4) | [13,03 s](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/director_matched/clip_00.mp4) | Fin plus nette, mais le raccourcissement retire l’explication Google et l’accompagnement. Le titre initial promet donc davantage que l’extrait final. |
| Taux de conversion | [12,87 s](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/selector/clip_01.mp4) | [15,03 s](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/director_matched/clip_01.mp4) | Ajoute les dix visites avant la vente ; conserve la réserve sur le petit échantillon ; supprime le « Et » final. Le plus convaincant des trois changements. |
| Connaissances et accompagnement | [22,83 s](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/selector/clip_02.mp4) | [26,87 s](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/director_matched/clip_02.mp4) | Répare « fait cette vidéo » et termine l’appel à candidature. L’ouverture « cette vidéo » reste dépendante du contexte source. |

![Comparaison à présentation identique](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/comparison-matched-contact.png)

Les rendus natifs du Director sont également conservés : [extrait 1](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/director_final/clip_00.mp4), [extrait 2](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/director_final/clip_01.mp4), [extrait 3](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/director_final/clip_02.mp4). Leur cadrage `source_safe` laisse de grandes bandes noires. Il n’est pas présenté comme une amélioration visuelle.

## Ce qui a réellement tourné

| Élément | État pendant ce run |
|---|---|
| Vidéo source | Vidéo locale réelle de 595,220 s, SHA-256 `ea12a4869887ce814629ea29ec22b053a70826ddbe2c7deb2d15bf2ef2902bbe`. |
| Transcription | Transcription et phrases ASR existantes partagées entre les deux versions. Pas de nouvelle transcription ni de téléchargement. |
| Brief | Brief existant de la campagne, objectif d’achat de formation e-commerce ; pas de changement du brief entre les versions. |
| Analyse audio | Analyse locale FFmpeg des silences et de la dynamique, intégrée au graphe. |
| Vision globale | Nouvelle analyse de 80 images avec `qwen/qwen3-vl-32b-instruct`. |
| Sélection éditoriale | Nouvel appel `google/gemini-2.5-flash` : 9 arcs proposés. |
| Ancrage et filtrage | Ancrage strict dans les mots, vérification, ajustement des bornes et limites de durée : 7 arcs après ancrage, 5 après durée, 3 retenus pour la vision approfondie. |
| Vision des candidats | Nouveaux appels sur les trois candidats ; observations utilisées dans leur classement. |
| Recherche | Coordinateur, plan de requêtes, collecte HTTP réelle, normalisation, synthèse et validation d’extraits exécutés. Adaptateur de recherche alimenté par des URL présélectionnées lors de la recherche de l’agent, pas par un moteur autonome exécutant chaque requête du coordinateur. |
| Résultat de recherche | Partiel : 1 source exploitable sur 4 URL, 1 hypothèse documentée. France Num ; une erreur HTTP et deux limites de taille ont empêché les autres collectes. Aucun résultat de marché complet revendiqué. |
| Contexte éditorial | Matérialisation campagne/source/recherche, sélection des notes, autorité de tenant et contexte signé puis vérifié pendant le run. Signataires locaux éphémères. |
| Director 2.2 | Vrais appels modèles, parsing strict, compilation par identifiants de mots, QC éditorial et réflexe, citations et journal de provenance des décisions. |
| Rendu | FFmpeg, sous-titres issus des occurrences compilées, contrôles du fichier final et manifestes avec empreintes. |
| Cadrage avancé | Pas d’autorité de vision candidate signée pour autoriser un recadrage visage ou une région d’écran. Les images approfondies servent au classement ; les sorties finales conservent le cadre source. |
| Musique, SFX, effets, variation de vitesse | Non exercés dans les rendus de cette comparaison. Aucun catalogue audio autorisé n’est fourni. |
| Apprentissage et résultats d’audience | Contrats couverts par les tests, pas de boucle d’apprentissage sur des résultats réels. Aucune rétention, conversion ou règle gagnante inventée. La note globale isolée n’a pas été sélectionnée comme conseil sans contre-exemple lié ; les consignes du test viennent du prompt explicite. |
| API, Redis, facturation, stockage distant | Non sollicités : exécution locale des composants de traitement média. Ce n’est pas un job SaaS de bout en bout et ce n’est pas une preuve de production. |

## Résultats et limites de la mesure

| Mesure | Référence | Director, présentation commune |
|---|---:|---:|
| Clips livrés | 3/3 | 3/3 |
| Contrôle technique final | 3/3 | 3/3 |
| Bornes coupant partiellement un mot selon les timestamps ASR, tolérance 25 ms | 0 | 0 |
| Fins suspendues observées dans le texte sélectionné | 3/3 | 0/3 |
| Sous-titres présents et empreintes vérifiées | 3/3 | 3/3 |
| Format | 1080 × 1920, 30 fps | 1080 × 1920, 30 fps |

La référence était déjà protégée contre les mots coupés. Le gain observé concerne les unités de sens, surtout les fins. Il ne faut pas transformer « zéro mot coupé selon les timestamps » en une mesure de synchronisation humaine ou en un score de qualité éditoriale.

Exemples vérifiables dans les mots sélectionnés :

- Extrait 1 : la référence finit par « c’est garanti sous contrat Et » ; le Director finit par « presque 2000€ en une journée de bénéfice ». Mais « ce site justement » reste sans référent dans son ouverture, et la coupe retire le passage qui expliquait Google.
- Extrait 2 : la référence finit par « un très très bon taux de conversion Et » ; le Director s’arrête à « conversion » et garde « c’est sur un petit segment de client ».
- Extrait 3 : la référence commence à « fait cette vidéo » et finit à « J’ai un accompagnement Donc » ; le Director commence à « Donc en fait cette vidéo » et termine à « Si ton profil est intéressant ».

Le texte ASR partagé omet certains symboles de pourcentage dans les mots. Ce défaut d’affichage est visible dans les sous-titres des deux versions ; ce run n’a pas régénéré ni corrigé l’ASR. Le téléphone utilisé comme preuve reste petit dans le cadre conservé. Ces deux points méritent une correction séparée.

La revue repose sur le texte réellement compilé, les mesures techniques et les vignettes extraites inspectées. Il ne s’agit ni d’une écoute humaine complète, ni d’un test aveugle, ni d’une mesure de rétention. Les trois extraits proviennent d’une seule vidéo ; ils ont servi à corriger l’intégration, donc ils ne constituent pas un jeu de validation indépendant.

## Échecs conservés et corrections

Le Director initial n’a livré aucun des trois clips : champ `effect` au lieu de `effects`, `shot_id` absent et champs au mauvais niveau. Le prompt décrivait incomplètement le schéma. Le prompt du module a été précisé sans assouplir le parseur.

Le contexte réel dépassait ensuite la limite de 4 800 caractères malgré le respect des quotas par rôle. La sélection réduit maintenant les observations redondantes avant les autres éléments facultatifs, conserve les contraintes, l’objectif de campagne et les moments source sélectionnés, et retire un conseil global avec son contre-exemple de façon atomique. Une régression vérifie la taille, la conservation des éléments nécessaires et le déterminisme.

Les plans multi-shot proposés à partir d’un unique beat continu étaient incompatibles avec les règles du graphe. La dernière configuration impose donc un seul plan pour ces trois passages continus, tout en laissant au modèle le choix des mots de début et de fin. Elle expose explicitement les contrôles permis. Le troisième clip a encore nécessité une réparation après le rejet d’une entrée en milieu de pensée par le QC réflexe. Aucun plan rejeté n’a été forcé au rendu.

Les premières erreurs de raccordement du banc — enum de question, gestion de la recherche indisponible et sérialisation de la provenance immuable — ont également été corrigées. Les réponses modèles, rejets intermédiaires et rendus de diagnostic restent conservés. La robustesse du Director libre et les montages à plusieurs moments restent à valider sur d’autres vidéos.

## Coût, validation et fichiers

31 requêtes HTTP modèles conservées : 7 appels vision Qwen et 24 appels texte Gemini, y compris sélection, synthèse, essais rejetés et réparations. Coût déclaré dans les réponses fournisseur : **0,217425632 USD**. Réservation conservatrice cumulée : **0,934318548 USD**, sous le plafond local de 1 USD. Cela exclut l’ASR et le téléchargement réutilisés, le calcul local et l’usage de l’agent ; ce n’est pas le coût complet futur d’un job SaaS.

**795 tests worker réussis**, lint des fichiers de ce run réussi, `git diff --check` réussi. Les six fichiers de comparaison ont aussi été validés après rendu ; leurs empreintes vidéo et sous-titres correspondent aux manifestes. Le rendu de présentation commune vérifie que les mots choisis par le Director n’ont pas changé.

- [Mesures et budget](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/metrics.json)
- [Vérification des six fichiers](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/verification.json)
- [Rapport de sélection](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/selection-audit.json)
- [Comparaison finale native](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/comparison.json)
- [Contrôle de présentation commune](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/matched-presentation.json)
- [Journal des appels](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/calls.json)
- [Recherche partielle et citations](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/research/pack.json)
- [Empreintes du code du run](/Users/augustindemeaux/clipfactory-data/full-stack-run-2026-09-12/run-code-manifest.json)

Les scripts de benchmark sont spécifiques à cette fixture et reprennent les artefacts de ce dossier. Pour un nouvel échantillon, employer un nouveau dossier de sortie et reconstituer les entrées ; ne pas réutiliser ces caches pour une autre vidéo. Le runtime Python utilisé se trouve dans l’environnement worker du worktree `clipfactory-clipping-quality`.

## Décisions pour la suite

1. Garder les validations par mots et appliquer systématiquement le QC réflexe après toute modification du découpage. Une fin naturelle ne doit pas dépendre uniquement d’une consigne au modèle.
2. Évaluer la promesse du titre contre le contenu **après** montage. L’extrait 1 illustre une régression possible : plus court et mieux terminé, mais moins fidèle à la promesse Google et au but de campagne.
3. Construire des beats adaptés aux unités de sens avant d’évaluer le montage multi-shot. Ne pas donner à un seul beat « hook » des plans de preuve et de conclusion que son contrat ne peut pas accepter.
4. Relier la vision candidate vérifiée au cadrage et mesurer la lisibilité des preuves à taille téléphone. Corriger l’affichage des unités et pourcentages avec une source ASR vérifiable.
5. Geler cette configuration et la tester sur de nouvelles vidéos : face caméra, écran, conversation et récit avec moments distants. Conserver les rejets et faire une revue aveugle à présentation identique avant de conclure à une amélioration générale.
