# Accroche, tension et rétention : doctrine éditoriale locale

**Décision.** ClipFactory doit monter un extrait pour un spectateur qui découvre la vidéo dans un fil : comprendre rapidement le sujet et la valeur, avoir une raison précise de rester, recevoir de nouvelles informations, puis obtenir la réponse promise. C'est une hypothèse de montage à tester, pas une formule de viralité ni un score prédisant la rétention.

## Ce que les sources permettent de dire

| Signal | Source | Portée et limite |
| --- | --- | --- |
| Une lacune d'information identifiable peut susciter la curiosité. | [Loewenstein, revue théorique](https://www.cmu.edu/dietrich/sds/docs/loewenstein/PsychofCuriosity.pdf) ; [Gruber et al., expérience de mémoire](https://pmc.ncbi.nlm.nih.gov/articles/PMC4252494/) | Hypothèse plausible pour structurer un hook. Le rappel de réponses à des questions en laboratoire ne mesure pas la rétention d'un Short. |
| L'anticipation d'une issue significative, avec incertitude ou conflit, peut porter la tension. | [Lehne et Koelsch, modèle théorique](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.00079/full) | Le modèle ne fournit ni durée optimale de teasing ni fréquence de coupe. |
| Les créations TikTok peuvent organiser un hook, un corps et une conclusion, avec de la valeur tôt. | [TikTok for Business, conseils publicitaires](https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads/) | Une observation sur le rappel publicitaire dans les six premières secondes n'est pas un taux de rétention ni une règle pour toutes les vidéos. |
| La mesure distingue le choix de regarder des variations de rétention. Une pointe peut signaler un replay ou une confusion. | [YouTube, Analytics Shorts](https://support.google.com/youtube/answer/12942217?co=YOUTUBE._YTVideoType%3Dshorts&hl=en) ; [YouTube, moments clés de rétention](https://support.google.com/youtube/answer/9314415?hl=en) | Le contexte de diffusion, la durée et le dénominateur comptent. La mesure d'introduction à 30 secondes ne devient pas un seuil universel pour Shorts. |
| L'attention peut survivre à la connaissance de la fin dans une tâche de film narratif. | [Cohen et al., expérience de film](https://onlinelibrary.wiley.com/doi/10.1002/acp.4070) | C'est un indice contre le dogme « ne jamais révéler le résultat », pas une preuve qu'un *result-first* gagne sur les réseaux. |

Le catalogue exhaustif, avec type d'étude et limites, est dans [`editorial-retention-sources-v1.json`](../../apps/worker/app/knowledge/editorial-retention-sources-v1.json). Les notes utilisées par le moteur sont dans [`editorial-retention-v1.json`](../../apps/worker/app/knowledge/editorial-retention-v1.json). Les pages sources restent hors du prompt ; seuls des résumés courts, revus, accompagnés de leur contre-exemple peuvent être récupérés.

## Grille de décision pour un monteur de réseaux

1. **Promesse vérifiable.** Écrire en une phrase la réponse, le résultat ou le mécanisme que le titre et l'ouverture promettent. Repérer dans la transcription les mots et dans l'image les preuves qui permettent de la tenir. Si la source ne les contient pas, réduire la promesse.
2. **Entrée compréhensible à froid.** Dans la première phrase ou le premier plan, nommer le sujet et une raison d'y prêter attention. Couper une introduction dépendante (« d'ailleurs », « ça », « comme je disais ») seulement si le nouveau départ reste grammatical et fidèle. Une surprise sans référent crée de la confusion, pas forcément de la curiosité.
3. **Question ouverte réelle.** Faire émerger une seule question claire : « comment », « pourquoi », « est-ce que ça marche ? » ou « que s'est-il passé ? ». Un résultat montré tôt peut laisser ouverte l'explication. Ne pas cacher artificiellement tout le résultat.
4. **Tension fondée dans la source.** Montrer l'objectif, l'obstacle et les conséquences possibles si la source les établit. Refuser les délais inventés, le danger exagéré et les qualifications supprimées. La musique ne crée pas une preuve.
5. **Progression à chaque passage.** Chaque nouveau bloc doit ajouter une tentative, un indice, une objection, une conséquence ou une preuve. Ne pas empiler « attends la suite » et des effets pour remplir le temps. Une coupe sert un changement de sens ou de preuve.
6. **Preuve lisible et conclusion complète.** Vérifier les unités, pourcentages, tailles d'échantillon et nuances à taille téléphone. Le dernier passage doit répondre à la question et au titre ; un appel à l'action vient après la valeur livrée.

Exemples d'ouvertures à essayer **seulement si elles sont prononcées ou démontrables dans la source** : résultat puis « comment » ; contradiction entre attente et résultat suivie de sa résolution ; objection concrète puis preuve ; tentative avec obstacle et enjeu. Le Director choisit les mots de la transcription ; les horodatages de l'ASR restent l'autorité de coupe.

### Cas local à surveiller

Dans le comparatif réel, un titre promettait le mécanisme « avec Google Ads ». Une version plus courte pouvait conserver le bénéfice annoncé tout en perdant ce mécanisme. La fin était techniquement complète, mais la promesse éditoriale du titre devenait fragile. Le couple `promise_payoff` / `promise_mismatch` demande donc de contrôler **titre → ouverture → preuve → conclusion** avant de classer ce clip comme réussi. Un autre risque observé était une preuve sur petit écran : le chiffre peut attirer l'attention sans être lisible ou correctement qualifié.

## Mesurer sans confondre les effets

| Étape | Question | Mesures utiles | Interprétation prudente |
| --- | --- | --- | --- |
| Arrêt du défilement | Les personnes exposées choisissent-elles de regarder ? | Vu vs balayé quand la plateforme le fournit ; taux de démarrage avec dénominateur explicite. | Dépend aussi de l'audience, de la première image, du titre et de la distribution. |
| Tenue | Restent-elles après avoir compris l'ouverture ? | Courbe de rétention, abandon au moment précis, complétion parmi les démarrages, par classes de durée. | Un clip plus court peut mécaniquement mieux compléter ; une pointe peut être un replay de confusion. |
| Valeur | La promesse est-elle comprise et satisfaite ? | Lecture humaine à froid, rappel du mécanisme, commentaires qualitatifs, actions cohérentes avec l'objectif. | Le watch time seul ne prouve pas la satisfaction ; [YouTube décrit plusieurs signaux de valeur](https://blog.youtube/inside-youtube/on-youtubes-recommendation-system/), sans livrer une formule actuelle du classement. |

Pour apprendre réellement : figer la source, le corps, le style de sous-titres, le format et la promesse, puis comparer deux ou trois ouvertures compatibles avec les mêmes preuves. Consigner la plateforme, la durée, la fenêtre de publication, le volume et la composition de l'audience. Inspecter séparément le choix de regarder, la courbe conditionnelle, la compréhension et l'action utile. Sans trafic comparable ni revue humaine aveugle, conserver le résultat comme observation locale, pas comme règle globale.

## Intégration dans le moteur local

[`editorial_knowledge.py`](../../apps/worker/app/pipeline/editorial_knowledge.py) charge les notes, contrôle leurs références et refuse un conseil sans principe et risque appariés. [`compare_full_stack.py`](../../apps/worker/scripts/compare_full_stack.py) remet ce vault à `prepare_editorial_context` avec une autorité de tenant ; la recherche lexicale choisit une paire adaptée à la question. Le [prompt du Director](../../apps/worker/app/pipeline/editorial_director.py) traduit la doctrine en décisions sur l'entrée, la progression, la preuve et la conclusion, sans changer les contrats de mots, de graphe et d'EDL.

L'[audit de récupération sur un vrai candidat](retrieval-audit-2026-09-25.json) conserve les empreintes des fichiers utilisés, les trois questions, les paires retenues et la taille du contexte. Un test vérifie aussi que le prompt Director émis par une autorité signée contient bien la paire et exclut les adresses des sources.

**Limite de déploiement :** cette intégration et sa vérification concernent le moteur expérimental local. Le runner SaaS actif ne bascule pas automatiquement sur ce Director ou ce vault. Aucun gain de rétention en production n'est encore mesuré.
