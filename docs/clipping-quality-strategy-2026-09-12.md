# Stratégie d'amélioration de la qualité des clips

Date : 12 septembre 2026. Statut : protocole préparé, expériences éditoriales non exécutées. Ce document complète le run technique décrit dans `clipping-quality-run-2026-09-05.md`.

## 1. Ce qui a réellement été utilisé

| Élément | État vérifié | Rôle dans le prochain benchmark |
| --- | --- | --- |
| Compilateur EDL V2, captions, rendu et QC | Branchés au runner local via `clip_render.py` ; utilisés par les sept rendus | Référence stable R0 |
| Sélecteur actuel et scoreur | Toujours le chemin actif ; les propositions du replay étaient déjà capturées | Mesurer séparément découverte, classement et montage |
| Beats et Director 2.1 | Restaurés/testés ; pas d'appel du runner à leur chaîne de décision | Expérience E3 |
| Editorial Reflex QC | Présent/testé ; pas activé dans la boucle de décision du runner | Détecter les défauts fondés sur des preuves explicites |
| Director 2.2 | Dans le prototype déplacé, pas intégré | Expérience E4 après vérification de ses dépendances |
| Context intelligence, recherche, vaults, apprentissage | Fondations locales, pas utilisées par les sept rendus | Introduire une brique à la fois si elle améliore un défaut mesuré |

Le Director 2.2 est un wrapper de citations autour des contrôles 2.1. Ses points d'entrée publics bruts sont volontairement désactivés : le chemin prévu passe par `VerifiedEditorialContext`, qui vérifie notamment contexte, intégrité et périmètre. La stratégie prévoit cette intégration sans contourner ses contrôles. Un numéro de version supérieur ne prouve pas un meilleur montage.

Le replay précédent utilisait une seule source, un transcript et des propositions figés, sans nouvelle sélection payante, avec cadrage `fit_blur` forcé. Les 500 tests et le passage de deux mots tronqués à zéro sont des preuves techniques locales. Ils ne mesurent pas encore le bénéfice du Director ni la qualité éditoriale générale.

## 2. Définir le résultat recherché

Objectif principal : augmenter le nombre de clips que la personne peut publier tels quels pour sa campagne, tout en diminuant les corrections nécessaires.

Un clip publiable doit se comprendre sans avoir vu la longue vidéo, présenter un intérêt identifiable, tenir sa promesse, terminer son idée, respecter le sens de la source et rester lisible/audible sur téléphone. Le style et la longueur peuvent varier selon le public. Une fin ouverte volontaire est acceptable si la question est intentionnelle et comprise ; une amorce accidentelle de phrase suivante ne l'est pas.

Ne pas remplacer cet objectif par le nombre de fichiers encodés, le score de rétention déclaré par le sélecteur ou le nombre d'effets. Ne pas assimiler la fidélité au propos source à la vérité d'une affirmation dans le monde réel.

## 3. Diagnostic initial : mots entiers, phrases parfois incomplètes

Ces observations viennent des extraits de transcript et des planches déjà inspectées. Elles sont des hypothèses documentées à confirmer en regardant et écoutant le clip entier, puis les passages source voisins. Aucune note humaine n'a été inventée.

| Cas | Indice constaté | Expérience prioritaire |
| --- | --- | --- |
| Défi 1 € → 50 € | Des segments finissent par « Aujourd’hui ça », « Ce que j’ai », « Donc c’est vraiment » | Retirer l'amorce de phrase suivante sans supprimer la conclusion |
| Coût des connaissances | Début « fait cette vidéo », fin « Et » | Rétablir une entrée compréhensible et une sortie complète |
| Financer son lancement | Setup terminé par « Et en » | Revoir la jointure sur les mots, puis écouter l'enchaînement |
| Produit à 2 000 € | « Ça c’était » suivi de « c’était », avec chevauchement source | Éviter la répétition accidentelle à la jointure |
| Témoignage | « Dont je vous parlais tout à l’heure » | Vérifier si le contexte utile est expliqué dans le clip |
| Recherche de produit | Preuve à l'écran réduite par le cadrage de comparaison | Mesurer la lisibilité de ce que le spectateur doit voir |
| Validation Google Ads | Titre « 3 étapes », extrait focalisé sur les concurrents, fin « Mais » | Aligner titre et contenu réellement livré, fermer le propos |

Dans `clip_render.py`, la liste de pronoms faibles du contrôle éditorial générique est volontairement neutralisée : un pronom seul n'établit pas un manque de contexte. La solution est d'identifier son référent et la structure du propos, pas de bannir toutes les phrases commençant par « il » ou « ce ».

## 4. Corpus et protocole de jugement

### Démarrer avec les fichiers existants

Les sept cas sont préparés dans `evaluation/clipping-quality-2026-09-12/pilot-cases.jsonl`, avec source, MP4, manifeste, segments et hypothèses. Le fichier `reviews.template.jsonl` contient des fiches non notées. Le brief de campagne doit être explicite avant de noter la pertinence ; il n'a pas été inventé pour le pilote.

Pour chaque clip :

1. Regarder et écouter le MP4 seul, avec uniquement le public et le but de la campagne. Noter le sujet compris, la promesse et les points de confusion avant de voir la source.
2. Lire/écouter le contexte autour de chaque fenêtre source, au moins la phrase précédente et suivante, davantage si nécessaire. Vérifier les référents, les négations, les preuves et l'ordre causal.
3. Comparer A/B à l'aveugle, ordre aléatoire, même téléphone/taille de lecture et même niveau sonore. Répondre A, B, équivalent ou aucun acceptable, avec raison et timestamp.

Cible : deux évaluateurs indépendants ; conserver leurs désaccords puis arbitrer les cas critiques. Avec un seul évaluateur, conserver ce statut et éviter de présenter ses préférences comme consensuelles. Les évaluateurs ne doivent pas connaître le nom du moteur ni son score automatique.

### Étendre avant de généraliser

Cible de pilote élargi : 20 vidéos, réparties entre explication solo, entretien à plusieurs, démonstration à l'écran, récit/vlog et live/source difficile. Quatre vidéos par catégorie ; dix sources de développement, dix sources de validation. Les créateurs, sources proches et extraits d'une même vidéo restent dans un seul groupe. Si le regroupement par créateur empêche les quotas exacts, privilégier l'absence de fuite entre groupes.

Inclure différentes durées, débits, accents, changements de locuteur, silences utiles et preuves visuelles. Priorité au français et aux cas correspondant aux campagnes visées. La source actuelle reste dans le développement. Les 19 autres sources ne sont pas encore réunies et aucun droit d'usage n'est supposé acquis.

Annoter les moments utiles sur les vidéos complètes, avant de regarder uniquement ce que le système a retenu. Pour chacun : sujet, public, raison de le garder, contexte minimal, conclusion, preuve et intervalles de mots acceptables. Conserver aussi des zones à éviter. Plusieurs montages peuvent être bons : la référence est un ensemble de moments/contraintes, pas un unique timecode parfait.

La validation tenue à l'écart n'est consultée qu'après gel de l'expérience. Si elle sert ensuite à modifier le système, elle devient du développement et doit être remplacée pour la prochaine décision indépendante. Vingt vidéos constituent un pilote, pas une preuve universelle.

## 5. Mesures et grille

### Mesures principales

- **Rendement publiable** : clips jugés « publier tels quels » / emplacements demandés. Si trois clips sont demandés et un seul est livré/publiable, le résultat vaut 1/3. Un rejet ne disparaît pas du dénominateur.
- **Défauts critiques** : sens changé, contexte essentiel manquant, titre non soutenu par l'extrait, preuve indispensable illisible, parole tronquée ou sous-titres requis absents. Mesurer les défauts par clip et par source.
- **Préférence A/B** : votes avec égalités et « aucun » conservés. Agréger d'abord par source ; sept clips d'une même vidéo ne constituent pas sept sources indépendantes.
- **Temps de correction** : temps observé pour rendre publiable le lot demandé. Signaler séparément les rejets et les slots manquants ; ne pas leur attribuer artificiellement zéro minute.
- **Diversité utile** : nombre de sujets/angles distincts utilisables dans les trois sorties, sans récompense pour une simple reformulation du même passage.

### Notes explicatives, pas un score magique

Noter séparément hook, autonomie, conclusion, fidélité source, lisibilité de la preuve, sous-titres, rythme et adéquation campagne. Échelle commune : 0 inutilisable, 1 correction majeure, 2 correction visible nécessaire, 3 publiable, 4 très convaincant. Une donnée non observable reste inconnue. Un défaut critique ne peut pas être compensé par une moyenne élevée.

### Diagnostic par étage

| Question | Mesure | Interprétation |
| --- | --- | --- |
| Le système trouve-t-il les bons moments ? | Couverture du pool sur les moments annotés de la source entière | Faible couverture : revoir découverte/segmentation/contexte |
| Choisit-il les bons parmi ceux trouvés ? | Pertinence du top 3 et diversité, avec pool identique | Pool bon, top 3 faible : revoir classement |
| Le montage améliore-t-il un même moment ? | A/B avec mêmes moments autorisés | Défauts aux jointures : frontières/Director |
| Le spectateur voit-il la preuve ? | Lecture sur téléphone, même timeline, cadrages différents | Revoir ROI, durée d'affichage et zone des captions |
| Le gain vaut-il son coût ? | Coût par clip publiable et latence p50/p95 | Conserver les compromis mesurés, pas seulement le plus gros modèle |

Les juges LLM peuvent préparer un tri de défauts et citer leurs preuves, mais leurs notes restent séparées des votes humains. Les biais de position, de longueur et d'auto-préférence sont documentés dans [Zheng et al., 2023](https://arxiv.org/abs/2306.05685). Cette étude concerne des assistants textuels : elle justifie une précaution méthodologique, pas une performance garantie pour la vidéo. Calibrer le juge sur nos annotations, inverser A/B, masquer le moteur et examiner ses désaccords. Un juge recevant seulement le transcript doit répondre « non observable » sur l'image et le son.

## 6. Expériences dans l'ordre

Chaque expérience a une hypothèse, une modification isolée, des entrées et des budgets figés. Les sorties rejetées et erreurs sont enregistrées. Ne pas sélectionner rétrospectivement le meilleur résultat d'un nombre d'essais différent selon le moteur.

| ID | Hypothèse | Modification | Ce qui reste fixe |
| --- | --- | --- | --- |
| E1 | Des frontières sémantiques complètes et un titre fidèle améliorent fortement la publication sans retouche | Réparation bornée des entrées, sorties et jointures ; titre vérifié sur le montage final | Source, transcript, pool, modèles, cadrage |
| E2 | Le score actuel laisse remonter des clips incomplets et des doublons | Classement fondé sur contexte/conclusion/preuve et diversité explicite | Pool, renderer et politique E1 |
| E3 | Les décisions motivées améliorent le montage d'un même pool | Graphe validé → Director 2.1 → EDL → Reflex QC | Pool, campagne, renderer, effets désactivés et cadrage contrôlé |
| E4 | Le contexte cité améliore l'adéquation campagne et la fidélité | Director 2.2 via VerifiedEditorialContext, comparé à 2.1 | Pool, graphe et budget de calcul comparable |
| E5 | Un cadrage qui privilégie la preuve améliore la compréhension | Visage/écran/objet, durée lisible et placement des captions | Mots, ordre, audio et timeline |
| E6 | Un autre sélecteur trouve des moments utiles absents du pool actuel | Prompt ou modèle de découverte, un seul changement à la fois | Source, transcript, pipeline aval et budget |

Si l'annotation de la source révèle une faible couverture du pool, avancer E6 avant E2/E3 : aucun Director ne récupère un moment qui ne lui est pas fourni. Si le pool contient déjà les bons passages, commencer par E1/E2, dont les défauts sont directement observables aujourd'hui.

### Contrat de réparation E1

Le réparateur peut proposer des identifiants de mots pour retirer une amorce de phrase voisine, ajouter le contexte nécessaire dans le périmètre autorisé, conserver la conclusion ou refuser le candidat. Il doit expliquer entrée, sortie et jointure par des citations. Il ne doit pas inventer de phrase pour remplacer un contexte absent, élargir les droits de montage ou supprimer une négation pour rendre le hook plus fort.

Budget initial proposé : un passage de réparation et au plus deux variantes par candidat. Toute modification repasse par la compilation, les contraintes de durée, les sous-titres et le QC. Une alternative jugée meilleure ne doit pas faire disparaître le résultat de référence. L'alignement du titre est jugé séparément de la vérité externe de l'affirmation.

### Intégration du Director

Pour E3, compléter la construction du graphe à partir des observations réellement disponibles. Marquer une preuve inconnue comme inconnue. Un contrôle réflexe ne peut garantir que ce que ses preuves contiennent. Commencer par des décisions de structure avec cuts simples ; introduire ensuite cadrage puis effets pour en mesurer l'effet propre.

Pour E4, inventorier et porter la fermeture des dépendances contexte/autorité/tenant/attestations avec tests, puis utiliser la capacité vérifiée. Ne pas appeler les fonctions privées « unverified » pour faire fonctionner artificiellement le prototype. Tester la validité et la pertinence des citations : un plan bien signé peut encore être éditorialement mauvais.

Recherche de tendances et apprentissage arrivent après une amélioration observée. Le contexte externe peut guider un angle ou un vocabulaire, mais ne doit jamais inventer une preuve dans la vidéo. Les retours d'évaluation peuvent alimenter un jeu d'entraînement seulement en préservant la séparation avec la validation.

## 7. Règles de décision proposées

À figer avant de voir les comparaisons ; ce sont des objectifs de travail, pas des standards scientifiques ni des résultats acquis :

1. Tous les clips livrés passent les contrôles techniques existants ; aucun nouveau défaut critique sur les cas gelés.
2. Viser +15 points de rendement publiable et au moins 60 % de préférence pour la variante, en publiant séparément égalités, rejets, nombre de sources et désaccords.
3. Calculer l'incertitude par source/créateur, pas par frame ni par clip considéré indépendant. Si le gain reste incertain, poursuivre l'évaluation et ne pas annoncer de supériorité générale.
4. Ne pas masquer une régression d'un type de contenu derrière la moyenne globale. Décider par catégorie si les compromis diffèrent.
5. Documenter latence et coût par clip publiable. Accepter une hausse seulement si le gain éditorial la justifie pour le produit.

Le premier lot de sept clips sert à repérer et réparer les défauts, pas à valider statistiquement ces seuils.

## 8. Boucle de travail et livrables

**D'abord** : compléter le brief du pilote, noter les sept clips et leurs jointures, annoter la source puis geler R0. **Ensuite** : produire E1 sur les mêmes candidats et comparer à l'aveugle. **Puis** : choisir E2/E6 selon couverture du pool, tester le Director et le cadrage. **Enfin** : confirmer sur les sources gardées à l'écart.

Chaque résultat conserve source/transcript/propositions, modèle et version de prompt, paramètres, budget et nombre d'essais, état Git et hash du code, manifestes, coûts/temps, erreurs/rejets et avis avec preuves. Les fichiers de ce protocole sont sous `docs/evaluation/clipping-quality-2026-09-12/` ; les futurs médias volumineux restent sous `clipfactory-data`.

Une phase d'audience réelle pourra suivre la validation hors ligne : analyser rétention, complétion, partages et objectif campagne par plateforme et durée, en tenant compte des différences d'exposition, d'audience et d'horaire. Un simple avant/après organique n'établit pas une causalité. Aucun post, appel payant ou déploiement n'est lancé par cette préparation de stratégie.

## Livré maintenant

- `protocol.json` : corpus cible, métriques, expériences et règles provisoires.
- `pilot-cases.jsonl` : sept cas existants avec chemins et hypothèses vérifiables.
- `reviews.template.jsonl` : sept fiches sans notes inventées, prêtes à dupliquer par évaluateur.
- `inspected-code.json` : provenance des modules inspectés, y compris Director 2.2 et son autorité.

La suite logique prioritaire est l'expérience E1 sur les entrées/sorties et les promesses des titres. Les cas observés donnent déjà une raison concrète de la tester avant d'ajouter des effets de montage.
