# Pipeline de clipping — contrat d'exécution

Mis à jour le 12 septembre 2026 pour `codex/clipping-quality-2026-09-05`. Ce document décrit le code local, pas un déploiement confirmé. L'ancienne spécification est conservée dans `pipeline-v1-archive-2026-09-05.md`. Les mesures et limites sont dans `clipping-quality-run-2026-09-05.md`.

## Contrat central

Le sélecteur propose des passages et cite le transcript. L'ancrage retrouve les mots cités. Le compilateur EDL dérive ensuite les fenêtres source, les images de sortie et les occurrences de mots. FFmpeg reçoit seulement le plan compilé et validé. Les sous-titres, les segments sauvegardés et le contrôle qualité utilisent ce même plan.

```mermaid
flowchart LR
    A[Source et transcription horodatée] --> B[Sélection et citations]
    B --> C[Ancrage et vérification]
    C --> D[Réserve classée et vision]
    D --> E[Identifiants de mots]
    E --> F[Compilation EDL]
    F --> G[Sous-titres et FFmpeg]
    G --> H[Contrôles du MP4]
    H --> I[Manifeste et publication]
```

Un score élevé ne permet pas de contourner une frontière invalide, un sous-titre impossible à afficher ou un rendu qui échoue au contrôle technique. Un candidat rejeté laisse sa place au suivant dans la réserve déjà analysée.

## Admission, tentative et crédits

1. L'API verrouille le profil pendant la vérification de l'abonnement, de la campagne, du nombre de jobs actifs et du solde. Elle crée un job `queued`, puis l'envoie dans Redis. `credits_estimated=1` est une estimation d'affichage, sans débit à ce stade.
2. Un échec d'enqueue ne peut faire échouer qu'un job encore `queued`. Si le worker l'a déjà pris malgré une réponse Redis perdue, l'API retourne son état courant.
3. Le worker réclame atomiquement `queued → downloading`, avec un UUID de tentative dans `worker_id`. Une livraison dupliquée, terminale ou déjà active est ignorée avant toute modification de fichiers.
4. Après téléchargement et ffprobe, le worker compare la durée réelle à la limite du plan, puis réserve `ceil(durée réelle / 60)` crédits avant l'analyse payante. Exemple : `120.01 s → 3 crédits`. Un solde insuffisant arrête le job.
5. Les transactions de crédits verrouillent toujours profil puis job. La réservation tient compte du débit net réellement inscrit au ledger. L'achèvement vérifie cette réservation dans la même transaction que `completed`.
6. Un échec rembourse au plus le débit net réel, une seule fois, et supprime les clips intermédiaires en base. Un échec avant débit n'invente aucun crédit. Une tentative périmée ne peut ni publier ni rembourser le job.

La machine d'état exécutée est `queued → downloading → transcribing → analyzing → rendering → completed | failed`. L'arrêt contrôlé annule la pipeline, attend son remboursement et ferme ensuite les connexions. Un processus traite un seul job à la fois ; `WORKER_CONCURRENCY` n'active pas de pool parallèle.

## Analyse de la source

Le worker valide l'URL et ses redirections, télécharge la source, mesure sa durée et tente de conserver une copie. Une heatmap d'audience disponible est un signal facultatif ; son absence ne bloque pas le job.

La transcription utilise `OPENAI_TRANSCRIBE_MODEL`, avec `whisper-1` comme valeur par défaut du code. Elle conserve mots horodatés et phrases ASR. Ces timestamps sont la référence temporelle du moteur ; leur exactitude acoustique n'est pas garantie par les contrôles de code.

Deux chemins partagent la suite : sélection de fenêtres sous le seuil configuré, ou carte vidéo et arcs de plusieurs segments au-delà. Le seuil par défaut vaut 300 secondes ; le routage utilise actuellement la durée entière arrondie au supérieur dans le contexte du job. Les modèles restent configurables dans `app/settings.py` ; ce run n'a pas revalidé leur disponibilité commerciale par des appels payants.

L'ancrage strict exige les citations nécessaires au début, à la fin et au payoff lorsqu'il est demandé. Une ancre explicite à la fin de la source ne recule pas artificiellement pour conserver la durée d'une proposition erronée. Les durées sont vérifiées après ancrage et ajustement des frontières.

La vérification textuelle accepte une citation exacte dans sa fenêtre. Pour une citation longue approchée, elle exige au moins 85 % de couverture de la citation et 65 % du passage source apparié. Les courtes citations exigent un appariement exact. Des nombres ou négations manquants dans le passage apparié entraînent le rejet. Ce contrôle vérifie le support textuel ; il ne prouve ni la vérité d'un titre ni l'autonomie narrative du clip.

## Réserve et compilation

Le chemin actif présélectionne au plus cinq arcs diversifiés pour la vision approfondie. Il conserve cette réserve entière après classement, puis rend les candidats jusqu'au nombre demandé ou à son épuisement. Le benchmark hors ligne peut examiner sept propositions sans augmenter ce plafond du worker.

Le garde contre une ouverture noire peut retirer du vide avant la parole. Si cela amputerait la parole, il rejette le candidat. L'adaptateur `clip_render.py` sélectionne ensuite les mots entièrement contenus dans chaque segment et rejette une frontière coupant substantiellement un mot voisin, avec une tolérance ASR de 25 ms.

| Invariant | Valeur / règle |
| --- | --- |
| Clip final | 12 à 60 secondes après compilation |
| Segment final | Au moins 3 secondes |
| Fenêtres | Finies, ordonnées dans chaque segment, dans la source |
| Contenu requis | Tous les mots sélectionnés de chaque segment |
| Padding | Dans le périmètre autorisé, sans mot voisin tronqué |
| Timeline | Nombre entier d'images, 30 fps par défaut |
| Sortie active | 1080 × 1920, H.264, audio stéréo 48 kHz |
| Jointures actives | Coupes franches |

Le cadrage est choisi par segment : visage centré selon la vision, ou source complète avec fond flouté. Le calcul du crop tient compte du centre réel de l'image. Le suivi continu d'un visage ou d'un locuteur n'est pas implémenté dans ce chemin.

## Sous-titres et contrôle du rendu

Les sous-titres reprennent les occurrences de mots sur la timeline compilée, y compris les replays expérimentaux. Le regroupement suit les phrases ASR lorsqu'elles s'alignent correctement, les pauses et l'équilibrage des groupes. Il évite les queues isolées lorsque les contraintes le permettent.

Les lignes longues sont réparties sur deux lignes avec le budget de largeur existant du projet ; la police peut diminuer jusqu'au minimum lisible existant. Un mot qui dépasse encore ce budget est rejeté. Les groupes commençant au même instant sont réunis pour préserver les mots ASR de durée nulle. Les événements ASS sont bornés par le groupe suivant pour éviter les lignes superposées. Aucun échec ne déclenche une tentative sans sous-titres.

Le MP4 doit avoir des flux mesurables et cohérents avec la durée compilée. La tolérance de synchronisation audio/vidéo est d'une image plus 12 ms. Les dimensions, la cadence et le format audio sont contrôlés. Une analyse de toute la durée recherche les plages noires et silencieuses : bords noirs supérieurs à 250 ms, bords silencieux supérieurs à 800 ms, ou plus de 15 % de noir échouent au contrôle. L'intensité audio et la luminance au milieu sont aussi mesurées. Les pauses intérieures sont consignées, sans suppression automatique.

Ces seuils sont des heuristiques techniques. Ils ne mesurent pas la lisibilité de chaque preuve visuelle, le naturel de toutes les jointures, la factualité ou la rétention d'audience.

## Artefacts, publication et reprise

Chaque tentative dispose d'un répertoire et de clés de stockage distincts :

```text
sources/{user_id}/{job_id}/{attempt_id}.mp4
jobs/{user_id}/{job_id}/{attempt_id}/transcript.json
jobs/{user_id}/{job_id}/{attempt_id}/selection.json
jobs/{user_id}/{job_id}/{attempt_id}/render_outcomes.json
clips/{user_id}/{job_id}/{attempt_id}/{index}.mp4
clips/{user_id}/{job_id}/{attempt_id}/{index}.manifest.json
```

La source et les checkpoints sont conservés au mieux ; un échec est journalisé. Le MP4 et son manifeste sont obligatoires pour publier un clip. Le manifeste contient les empreintes SHA-256 de la source, du transcript, des sous-titres et du MP4, l'EDL, les occurrences et les résultats de contrôle. Les segments sauvegardés en base correspondent aux fenêtres compilées.

L'API et la politique RLS de lecture des clips exigent un job `completed`. Si la réserve produit moins de clips que demandé mais au moins un valide, le job peut terminer avec ce nombre réel ; la facturation reste fondée sur la durée source. Zéro clip valide fait échouer le job et rembourse la réservation.

Les checkpoints servent à l'audit et au replay, pas à une reprise automatique à mi-parcours. Redis utilise toujours `BLPOP` : un arrêt brutal après le pop peut perdre une livraison, et une tentative active abandonnée n'a pas encore de lease/reaper. Les objets de stockage orphelins après échec ne sont pas collectés automatiquement.

## Permissions et déploiement

La migration `20260907150016_restrict_client_job_and_profile_writes.sql` réserve les mutations de jobs au backend, limite l'édition du profil client à `full_name`, applique les droits de l'appelant à `credit_balances` et masque les clips intermédiaires. Elle est testée localement ; son application en production reste distincte du changement de code.

Les opérations de crédits sont protégées contre les accès concurrents du worker et de l'API. Cela ne remplace pas une revue de tous les autres producteurs du ledger ni un test complet Stripe. Toute nouvelle écriture de crédits doit respecter le même ordre de verrouillage.

Les appels OpenRouter ont au plus trois tentatives, avec temporisation bornée et échec immédiat des erreurs permanentes. Un rejet explicite du paramètre de raisonnement autorise un essai sans ce paramètre, en gardant le budget de sortie. Les sous-processus ont un délai maximal configurable, 900 secondes par défaut ; annulation et timeout arrêtent puis récupèrent leur groupe de processus.

Les modules `editorial_beats.py`, `editorial_director.py` et `editorial_reflex_qc.py` sont des fondations restaurées et testées, pas un directeur activé dans `run_job`. Recherche externe, apprentissage, musique, SFX, inserts et suivi dynamique ne font pas partie du chemin actif validé ici.

## Vérification

Les dépendances sont figées dans les deux fichiers `requirements.lock`. La procédure locale est dans `apps/worker/README.md`. Le workflow `pipeline-quality.yml` exécute lint, tests worker et intégrations sur PostgreSQL 17 sous Python 3.11. Sa présence dans le dépôt n'est pas la preuve de son exécution sur GitHub.
