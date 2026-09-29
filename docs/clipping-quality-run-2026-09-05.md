# Clipping et fiabilité — run du 5 au 12 septembre 2026

## Résultat livré

Le chemin actif du worker utilise maintenant la compilation EDL pour produire les clips, leurs sous-titres et leurs manifestes. La comparaison sur trois extraits communs passe de **deux frontières au milieu d'un mot à zéro**, par rapport au transcript horodaté conservé. Le replay final produit **sept MP4**, tous validés techniquement, sans rejet au rendu. **500 tests passent** : 484 tests worker et 16 intégrations PostgreSQL/API.

Ce résultat concerne une seule source de 595,220 secondes et des propositions déjà capturées. Il prouve une amélioration locale de découpe, de sous-titrage et des contrats d'exécution. Il ne prouve pas un gain de viralité, une sélection optimale sur tout type de vidéo ou une mise en production.

Le code est local, non committé, dans `/Users/augustindemeaux/clipfactory-clipping-quality`, branche `codex/clipping-quality-2026-09-05`. Aucun push, déploiement ou changement du schéma Supabase en ligne n'a été effectué.

## Inventaire et réutilisation

La base vérifiée après rafraîchissement du remote le 12 septembre reste `origin/main`, commit `f17e1295757cfccd59392652bc6c07cb8b32a067` ; aucun écart de commit entre cette base et HEAD. Les changements du run restent dans le répertoire de travail. Les copies existantes ont été préservées.

L'inventaire référence **1 275 fichiers de source et documentation**, avec taille et SHA-256, dans sept racines. C'est un index du périmètre retrouvé, pas une affirmation de lecture ligne par ligne de tous les fichiers ni de tout le disque personnel.

| Racine locale | Fichiers indexés | Utilisation |
| --- | ---: | --- |
| `clipfactory-saas` | 196 | Référence SaaS, contrats et déploiement |
| `Documents/autre/ChatGPT/clips factory saas pricp` | 258 | Prototype déplacé, modules EDL et éditoriaux |
| `ClipFactory` | 51 | Moteur historique, comparaison et inspiration |
| `clipfactory-beige` | 151 | Variante UI ancienne |
| `clipfactory-redesign` | 154 | Variante UI ancienne |
| `Documents/Codex/2026-08-21/clipfactory-ui-redesign` | 265 | Handoff UI et documentation |
| `clipfactory-saas/.claude/worktrees/free-trial-paywall` | 200 | Essai gratuit et admission, scope distinct |

Le relevé Git contient 18 références locales/distantes, dont les sept branches distantes ci-dessous. Les nombres « fichiers » concernent le diff de chaque branche par rapport à main, pas le nombre de modifications de ce run.

| Branche distante | Commit | Écart à main | Fichiers | Décision |
| --- | --- | --- | ---: | --- |
| `main` | `f17e1295` | 0 | 0 | Base |
| `codex/architecture-backend` | `eac742b4` | +1 | 6 | Reprise ciblée du retry OpenRouter ; documents utilisés comme contexte |
| `codex/ui-premium` | `6e4a5df1` | +1 | 118 | UI préservée, sans fusion globale |
| `redesign/ui-premium` | `7378eabc` | +1 | 68 | Même delta OpenRouter ; scope mixte laissé séparé |
| `redesign/ui-ux-lab` | `acd9a618` | +3 | 123 | UI/docs préservées |
| `vercel/vercel-web-analytics-integrati-rr9e3j` | `d567a4bc` | +1 | 3 | Analytics frontend, séparé du clipping |
| `worktree-free-trial-paywall` | `254de071` | −1 / +5 | 24 | Admission/essai examinés, pas de changement d'offre importé |

La branche locale `draft/parallel-workers` est distante de main de −46 / +1 commits. Son brouillon de concurrence et de reprise n'a pas été activé. Les protections de propriété et de crédits ont été implémentées sur la base actuelle et testées avec des transactions réelles.

Le comparatif worker/docs du prototype contient 55 fichiers identiques, 16 différents et 59 absents de main. Dix fichiers de modules/tests ont été restaurés avec provenance, puis adaptés lorsque nécessaire. EDL et rendu sont branchés au runner ; `editorial_beats`, `editorial_director` et `editorial_reflex_qc` restent des fondations testées. Recherche, graphes, contexte, apprentissage et director ne sont pas présentés comme activés.

## Changements exécutables

### Découpe et rendu

- L'ancrage strict rejette les citations de début/fin/payoff manquantes ou impossibles à résoudre. Il ne fait plus reculer artificiellement une ancre explicite en fin de vidéo.
- La vérification compare une citation aux mots de la fenêtre, avec couverture dans les deux sens. Les courtes citations sont exactes ; nombres et négations non couverts provoquent un rejet. Cela supprime le biais de l'ancien ratio sur toute la fenêtre rembourrée, sans accepter un simple fragment source dans une longue citation inventée.
- L'adaptateur transforme les fenêtres en identifiants de mots requis. Le compilateur valide portée, padding, coordonnées de cadrage, durée, catalogue d'opérations et timeline. Les durées minimales sont revérifiées après chaque ajustement important.
- FFmpeg reçoit le plan compilé. Les métadonnées en base décrivent les fenêtres finales. Le crop centré sur un visage utilise la position correcte dans l'image. Les transitions actives sont des coupes franches.
- La réserve complète déjà évaluée est conservée : un candidat rejeté peut être remplacé par le suivant. La vision approfondie du runner reste plafonnée à cinq arcs ; le replay de sept candidats n'est pas un nouveau quota de production.

### Sous-titres et contrôle qualité

- Les groupes suivent pauses et phrases ASR alignées, avec équilibrage pour limiter les queues d'un seul mot.
- Les longues expressions françaises passent sur deux lignes ; un token impossible à afficher à la taille minimale est rejeté. Les groupes aux mêmes timestamps sont réunis et les événements ASS ne se chevauchent plus.
- L'inspection des rendus de réserve a trouvé un débordement sur « différencier maintenant les ». Le rendu final corrige ce cas. Le replay a ensuite révélé des mots ASR de durée nulle répartis entre deux groupes : le correctif et un test dédié conservent maintenant ce clip.
- Aucun échec ne conduit à publier silencieusement une version sans sous-titres. Les contrôles couvrent les flux audio/vidéo, leur durée, cadence, dimensions, plages noires et silencieuses sur toute la durée. Les seuils exacts sont dans le contrat pipeline.
- Un manifeste lie le MP4 à la source, au transcript, aux sous-titres et au plan par SHA-256. Les sept manifestes finaux ont été revérifiés contre les fichiers conservés.

### Fiabilité des jobs et crédits

- Une revendication atomique du job et un jeton de tentative empêchent les doubles exécutions actives et les publications d'une ancienne tentative.
- L'admission concurrente d'un même utilisateur est sérialisée. La réservation utilise la durée réelle avant analyse payante. `120.01 secondes` exige trois crédits, sans troncature préalable.
- Le remboursement utilise uniquement le débit net réel. Pas de crédit créé avant débit, de double remboursement ou de remboursement d'un job terminal par une livraison dupliquée.
- La finalisation vérifie réservation et propriété dans sa transaction. Les clips intermédiaires sont masqués par l'API et par la nouvelle politique RLS jusqu'à `completed`.
- L'annulation contrôlée atteint le remboursement avant fermeture du pool. Les sous-processus ont un timeout et sont arrêtés/récupérés à l'annulation. Le retry OpenRouter est borné et conserve le budget de sortie lorsqu'un fournisseur refuse le paramètre de raisonnement.
- Transcript, sélection et résultats de rendu sont enregistrés sous des clés par tentative. Ces checkpoints servent au diagnostic/replay, sans reprise automatique.

### Reproductibilité

Deux fichiers `requirements.lock` figent les dépendances testées en préservant les versions runtime du contexte initial. Des environnements Python 3.11 isolés ont été créés. Le workflow `pipeline-quality.yml` prépare lint, tests et PostgreSQL 17 sur GitHub ; il n'a pas encore été exécuté à distance. Le contrat pipeline et le README worker ont été actualisés, et la spécification précédente archivée.

## Comparaison sur médias réels

Entrées inchangées : source de 595,220 s, transcript avec mots/phrases conservés et neuf propositions Gemini capturées le 21 août. Aucun appel payant au sélecteur, à la vision ou à la transcription pour ce replay. Le cadrage `fit_blur` est forcé des deux côtés pour isoler le changement de découpe ; ce test ne valide pas les décisions de cadrage de la vision.

| Extrait commun | Avant (s) | Après (s) | Frontières dans un mot |
| --- | ---: | ---: | ---: |
| Comment j'ai transformé 1€ en 50€ de bénéfice en 24h | 29.140 | 29.033 | 0 → 0 |
| Le vrai coût du succès en e-commerce : pas l'argent, mais les connaissances | 13.000 | 12.833 | 1 → 0 |
| De 1 euro à 100 euros : la méthode pour financer son lancement | 21.333 | 21.233 | 1 → 0 |

Les deux défauts corrigés concernaient « en » au début du deuxième extrait et « transpirant » au début d'un segment du troisième. Le compteur utilise une tolérance de 25 ms par rapport aux timestamps du transcript ; il ne remplace pas une mesure acoustique indépendante.

L'ancien chemin classait cinq propositions ; le nouveau en classe sept. Trois citations longues précédemment rejetées sont récupérées par le contrôle de couverture, tandis qu'un candidat supplémentaire est correctement écarté sous les 12 secondes après ajustement. Les trois ratios de citations récupérées passent de 0,57/0,64/0,63 à 0,98/0,88/0,99 ; ces scores sont ceux de deux métriques différentes et ne sont pas des probabilités. Le fichier de comparaison conserve citations et fenêtres pour examen.

| # | Rendu final | Durée | Preuve |
| --- | --- | ---: | --- |
| 1 | [Comment j'ai transformé 1€ en 50€ de bénéfice en 24h](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_00.mp4>) | 29.033 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_00.manifest.json>) |
| 2 | [Le vrai coût du succès en e-commerce : pas l'argent, mais les connaissances](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_01.mp4>) | 12.833 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_01.manifest.json>) |
| 3 | [De 1 euro à 100 euros : la méthode pour financer son lancement](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_02.mp4>) | 21.233 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_02.manifest.json>) |
| 4 | [Le produit miracle qui m'a fait gagner 2000€ en une journée](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_03.mp4>) | 14.367 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_03.manifest.json>) |
| 5 | [Témoignage d'élève : comment mon coaching a changé sa vie](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_04.mp4>) | 15.267 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_04.manifest.json>) |
| 6 | [Comment trouver un produit qui marche en dropshipping (méthode Gaspar)](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_05.mp4>) | 20.833 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_05.manifest.json>) |
| 7 | [Comment j'ai validé mon produit en 3 étapes (Google Ads)](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_06.mp4>) | 14.933 s | [Manifeste](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/clip_06.manifest.json>) |

Tous les MP4 ci-dessus passent le contrôle technique et n'ont aucune frontière détectée au milieu d'un mot. Les planches de quatre images de chacun ont été inspectées, dont les cas de sous-titres longs et de timestamps identiques. Il n'y a pas eu d'écoute humaine intégrale ni de panel éditorial aveugle.

Les dossiers `compiled`, `final`, `reserve` et `delivery` gardent les itérations intermédiaires. **La livraison retenue est exclusivement `delivery-verified`**. L'itération `delivery` contient notamment le rejet intermédiaire du clip à timestamps identiques, corrigé ensuite. Les durées de calcul sont conservées mais aucun gain de vitesse n'est annoncé : certaines exécutions initiales partageaient les ressources de la machine.

## Tests et portée

| Suite | Résultat | Preuve conservée |
| --- | ---: | --- |
| Worker | 484 réussis | `worker-tests.xml` |
| Intégration worker/PostgreSQL | 12 réussis | `worker-integration.xml` |
| Intégration API/PostgreSQL | 4 réussis | `api-integration.xml` |
| Lint worker et fichiers API modifiés | Réussi | Commandes du workflow exécutées localement |
| Contrôle du diff | Réussi | `git diff --check` |

La base worker initiale comportait 340 tests réussis. Les nouveaux cas couvrent notamment les frontières/NaN, la couverture des citations, la compilation et les sous-titres, de vrais encodages FFmpeg avec noir/silence, l'arrêt des processus, les collisions entre cinq revendications, les réservations simultanées, les remboursements, l'admission et la publication différée.

Les intégrations utilisent un **vrai PostgreSQL 16.2 local**, avec bases jetables et verrous/RLS réels. Le runtime macOS ne fournit pas les extensions contrib : `CLIPFACTORY_TEST_BUILTIN_UUID=1` remplace uniquement la génération UUID initiale par `gen_random_uuid()` et omet l'extension pgcrypto inutilisée dans ces tests. La nouvelle migration est appliquée telle quelle. Le PostgreSQL 17 du workflow utilisera les migrations complètes, mais cette exécution distante reste à faire.

Les tests de cycle complet du runner utilisent PostgreSQL réel, avec médias/providers/stockage simulés. Ils prouvent la gestion de rejet puis remplacement, du débit et de l'annulation, pas une chaîne hébergée OpenAI → R2 → application. Les commandes reproductibles sont dans le README worker ; la fixture interdit une base distante.

## État en ligne vérifié le 12 septembre

| Surface | Observation | Conclusion autorisée |
| --- | --- | --- |
| `clipfactory-saas.vercel.app` | HTTP 200, 08:14 UTC | Frontend joignable |
| `api.clipfactory.app` | DNS non résolu, curl code 6 | API publique non validée |
| `clipfactory.app` | HTTP 200 | Autre surface répondante ; ne prouve pas le backend SaaS |
| Historique de déploiements GitHub | Dernier enregistrement Production consulté : succès du 25 août, `4d8b50d9cf237cd666cf2bde1e429a8063b6922d` | Historique frontend, pas preuve de l'alias actuel ni de la révision worker |
| Supabase, 08:37 UTC | `authenticated` peut encore UPDATE `profiles.is_admin` et INSERT `jobs` ; options de `credit_balances` absentes | Corrections locales de permissions non appliquées en ligne |

La migration locale retire les mutations client de jobs, limite la modification du profil à `full_name`, place la vue de soldes en `security_invoker` et limite la lecture des clips aux jobs terminés. La documentation officielle Supabase sur les permissions par colonne et les RLS a été utilisée ; le changelog a été consulté pour tenir compte des évolutions des grants par défaut.

Aucun job de production ni débit client n'a été lancé. Aucune preuve actuelle de worker, queue et stockage formant une chaîne fonctionnelle n'est déduite du HTTP 200 du frontend.

## Limites et suite technique justifiée

1. **Qualité éditoriale.** Le corpus comprend une seule vidéo. Plusieurs extraits commencent encore avec un référent qui dépend du contexte, et certains titres promettent plus que le passage seul ne montre. Exemple : le titre « 3 étapes » accompagne un passage focalisé sur la concurrence. Les contrôles actuels ne prouvent pas ces promesses. Étendre le corpus, annoter débuts/fins et preuves, puis évaluer un directeur avant de l'activer reste nécessaire pour établir un gain éditorial général.
2. **Reprise après crash.** `BLPOP` et l'absence de lease/reaper laissent une fenêtre de perte après pop et des tentatives actives abandonnées après arrêt brutal. La protection contre doublons et l'arrêt contrôlé sont acquis ; reprise durable, checkpoint exécutable et nettoyage des objets R2 orphelins restent ouverts.
3. **Cadrage et source.** Le suivi continu du locuteur n'est pas activé. `fit_blur` conserve tout le cadre mais réduit les captures d'écran. Les sous-titres déjà incrustés dans la source ne sont pas retirés. L'inspection par planches ne garantit pas la lisibilité à chaque image.
4. **Modèles et coûts.** Pas de nouvelle évaluation payante de transcription/sélection/vision. Les coûts restent estimés et ne représentent pas tous les échecs facturables d'une facture fournisseur.
5. **Mise en service.** Avant de présenter ces changements comme disponibles aux utilisateurs : revue du patch, exécution CI, migration sur environnement de validation, déploiement coordonné API/worker, vérification DNS puis job témoin avec ledger et fichiers réels. La modification de profil peut affecter un ancien client qui écrit d'autres colonnes directement ; ce chemin doit être vérifié lors de l'intégration.

Ces limites sont distinguées des correctifs déjà testés. Elles n'ont pas été masquées par l'activation globale de modules expérimentaux ou une fusion de branches mêlant UI, billing et moteur.

## Artefacts consultables

- [Synthèse machine et vérification des empreintes](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/verification-summary.json>)
- [Rapport détaillé des rendus finaux](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/delivery-verified/report.json>)
- [Rapport de référence legacy](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/legacy/report.json>)
- [Inventaire des références Git](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/branches.json>)
- [Inventaire des fichiers locaux](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/local-sources.json>)
- [Comparatif du prototype](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/prototype-vs-main.json>)
- [Provenance des modules restaurés](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/restored-modules.json>)
- [Comparatif des citations](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/quote-verification-comparison.json>)
- [Relevé HTTP et DNS](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/public-endpoints-final.json>)
- [Historique des déploiements GitHub](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/github-deployments-final.json>)
- [Lecture des permissions Supabase](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/supabase-permissions-final.json>)
- [Tests worker](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/worker-tests.xml>)
- [Tests intégration worker](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/worker-integration.xml>)
- [Tests intégration API](</Users/augustindemeaux/clipfactory-data/quality-run-2026-09-05/api-integration.xml>)

Sources techniques : [permissions par colonne Supabase](https://supabase.com/docs/guides/database/postgres/column-level-security), [RLS Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security), [sécurisation de l’API Supabase](https://supabase.com/docs/guides/api/securing-your-api), [filtres FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#blackdetect).
