# 🏭 Worker parallèle — comment traiter plusieurs vidéos à la fois

> **Brouillon de travail.** Rien n'est branché dans le worker de prod, rien n'est poussé sur GitHub. Branche locale `draft/parallel-workers`.
> Code associé : `apps/worker/app/parallel/` · Migration : `docs/architecture/draft-0005_job_leasing.sql`

---

## 🎯 En 30 secondes

Aujourd'hui le worker traite **une seule vidéo à la fois**, et **si elle plante, le client est bloqué et a perdu son argent**. Ça tient à 7 clients, ça casse à 69.

Ce doc propose de :

1. **Traiter plusieurs vidéos en parallèle** (≈ 6 en même temps par machine).
2. **Mettre un frein sur l'étape lourde** (le montage vidéo) pour ne pas faire planter la machine.
3. **Surveiller chaque job** : s'il meurt, on **rembourse le client et on relance** automatiquement.

Le tout sans ajouter de nouvelle techno : on s'appuie sur la base de données qu'on a déjà.

---

## 🍳 L'analogie : la cuisine d'un restaurant

C'est exactement le problème d'une cuisine. Garde cette image, tout le reste en découle.

| Dans la cuisine | Dans ClipFactory |
| --- | --- |
| 👨‍🍳 Un cuisinier qui peut suivre **plusieurs plats** en même temps | Un *slot* de travail |
| ⏳ La plupart du temps de cuisson = **attendre** (mijoter, mariner) | Attendre les réponses des IA, le téléchargement, l'upload |
| 🔥 Le **four**, en quantité limitée (2 plats max sinon il surchauffe) | Le **montage vidéo** (ffmpeg) — gros consommateur de mémoire |
| 🎟️ Le **rail à commandes** : chacun prend la suivante, jamais la même deux fois | La **file des jobs** |
| 🧑‍💼 Le **chef** qui remarque si un cuisinier s'évanouit et reprend son plat | Le **veilleur** (reaper) |

**Le truc clé :** cuisiner, c'est surtout *attendre*. Un seul cuisinier peut donc surveiller 6 casseroles à la fois sans problème. **Sauf le four** : lui, il faut le limiter, sinon il crame.

C'est pareil pour nous : télécharger, transcrire, demander aux IA, uploader = de l'attente (on peut en faire 6 en parallèle facilement). **Le montage vidéo, lui, mange la mémoire** → on le bride à 2 à la fois.

---

## 🔴 Le problème aujourd'hui

### Ce qui se passe maintenant

```
   File des jobs  ─►  [ Worker ]  ─►  vidéo 1   (du début à la fin)
                                  ─►  puis vidéo 2
                                  ─►  puis vidéo 3 ...
                          ▲
                   un seul à la fois, en file indienne
```

Un seul plat à la fois. Le client n°2 attend que le n°1 soit fini.

### Le scénario qui fait mal 💸

> Le worker est en train de monter une vidéo de 30 min. Le montage est gourmand, la machine manque de mémoire → **le worker est tué net**.
>
> Résultat aujourd'hui :
> - la vidéo est **perdue** (personne ne la reprend),
> - les **crédits débités ne sont jamais rendus**,
> - comme le plan autorise « 1 job à la fois », le système croit que ce job-fantôme tourne encore → **le client est bloqué pour toujours**.
>
> Il a payé 29 €, il ne peut plus rien lancer, et personne n'est prévenu.

C'est **le** problème n°1 à régler avant d'avoir beaucoup de clients.

---

## ✅ La solution en un coup d'œil

```
                      ┌──────────────────── une machine worker ────────────────────┐
                      │                                                             │
  File des jobs   ───►│  ┌─ slot 1 → télécharge → transcrit → analyse → 🔥monte → upload
  (dans Postgres)     │  ├─ slot 2 → télécharge → transcrit → analyse → 🔥monte → upload
        ▲             │  ├─ slot 3 → ...                                            │
        │             │  └─ slot 6   (≈6 vidéos en parallèle)                       │
        │             │                                  │                          │
        │ 💓          │                  🔥 le montage passe par un FREIN :         │
        │ battement   │                     2 montages max en même temps           │
        │ de cœur     │                     (sinon la machine sature)              │
        └─────────────┴─────────────────────────────────────────────────────────┘
                      │
   🧑‍💼 Le veilleur tourne en boucle : un job qui ne donne plus de battement
        de cœur depuis 3 min → on rembourse + on relance.
```

**Trois mécanismes, trois bénéfices :**

| Mécanisme | En clair | Ça corrige |
| --- | --- | --- |
| 🍳 **Plusieurs slots** | Plusieurs vidéos avancent en même temps | La file d'attente qui s'allonge |
| 🔥 **Frein sur le montage** | Max 2 montages simultanés par machine | Les crashs mémoire (OOM) |
| 💓 **Battement de cœur + veilleur** | On détecte un job mort, on rembourse + relance | Le client bloqué qui a perdu son argent |

---

## 🧩 Les idées une par une

### 1. Plusieurs vidéos en parallèle — les « slots »

**En clair :** au lieu d'un cuisinier qui finit un plat avant d'attaquer le suivant, on lui laisse suivre ~6 plats en même temps.

**Pourquoi ça marche :** traiter une vidéo, c'est ~90 % d'attente (les IA répondent en quelques secondes, le téléchargement prend du temps…). Pendant qu'on attend pour la vidéo 1, on fait avancer la 2, la 3… Une seule machine suffit à en gérer 6 sans transpirer.

> 💡 Réglage `WORKER_SLOTS` (≈ 6). On le monte doucement en surveillant la machine.

---

### 2. Le frein sur le montage — le « sémaphore »

**En clair :** le four ne peut pas cuire 6 plats à la fois. On pose un videur à l'entrée : **2 montages max en même temps**, les autres font la queue 30 secondes et passent ensuite.

**Pourquoi :** le montage vidéo (ffmpeg) est la seule étape qui mange vraiment la mémoire. C'est elle qui fait planter la machine si on en lance 6 d'un coup. Le frein garantit qu'on profite du parallélisme **sans jamais saturer**.

> 💡 Réglage `RENDER_SLOTS` (≈ 2). C'est le réglage anti-crash.
> *(« Sémaphore » = le nom technique du videur qui ne laisse passer que N personnes. Voir glossaire.)*

---

### 3. Le battement de cœur + le veilleur — la fiabilité

**En clair :** chaque vidéo en cours dit « je suis vivante » toutes les 20 secondes (le **battement de cœur**). Un **veilleur** vérifie en boucle : si une vidéo n'a plus donné signe de vie depuis 3 min, c'est qu'elle est morte → il **rembourse le client** et **relance** la vidéo (jusqu'à 3 tentatives, sinon il marque l'échec proprement et rembourse).

**Pourquoi :** c'est exactement ce qui manque aujourd'hui. Avec ça, le scénario « client payé / job-fantôme / compte bloqué » **disparaît** : au pire le client attend 3 min de plus, mais il n'est jamais bloqué ni lésé.

> 💡 Réglages : `HEARTBEAT_INTERVAL` (20 s), `JOB_LEASE` (180 s avant de déclarer mort), `MAX_ATTEMPTS` (3).
> *(« Reaper » = le veilleur, en jargon. Voir glossaire.)*

---

### 4. La file dans la base de données — pas de techno en plus

**En clair :** aujourd'hui la file des jobs vit dans **Redis** (un système séparé). On propose de la mettre **dans Postgres** (la base de données qu'on a déjà), là où vivent déjà les jobs, les crédits, les abonnements.

**Pourquoi c'est mieux ici :**
- **Une seule source de vérité** au lieu de deux systèmes à synchroniser.
- Quand un worker prend un job, il peut **vérifier la limite du plan du client** (« 1 job à la fois ») **dans le même geste** → impossible de tricher en lançant 10 jobs d'un coup (autre faille de l'audit).
- Le veilleur devient **une simple requête** sur la base.

C'est le seul choix d'architecture vraiment structurant. Détail et alternative juste en dessous.

---

## 🧭 La décision à valider : Postgres ou Redis ?

| | Redis (système actuel) | **Postgres (recommandé)** | Redis Streams (plus tard) |
| --- | --- | --- | --- |
| Vidéo perdue si crash ? | ❌ oui | ✅ non | ✅ non |
| Détecter les jobs morts | ❌ à coder à part | ✅ une requête | ⚠️ complexe |
| Empêcher de tricher sur la limite | ❌ impossible | ✅ inclus | ❌ besoin de Postgres en plus |
| Nombre de systèmes | 2 | **1** | 2 |
| Adapté à notre volume | — | ✅ largement | surdimensionné |

> **Recommandation : Postgres.** À notre échelle (des vidéos qui prennent plusieurs minutes, quelques dizaines de jobs par jour — pas des milliers par seconde), c'est plus simple, plus fiable, et ça corrige deux failles d'un coup. Redis reste utile pour autre chose (limiter les abus d'API), mais sort de la gestion des jobs.
>
> Si un jour le volume explose vraiment, on documente le passage à « Redis Streams » (§ Annexe). On n'y sera pas à 2000 € MRR.

**C'est le point sur lequel je veux ton aval avant d'aller plus loin.**

---

## 📖 Glossaire (les mots techniques, en clair)

| Terme | Traduction simple |
| --- | --- |
| **Slot** | Une « place » de travail : 6 slots = 6 vidéos en parallèle. |
| **Sémaphore** | Le videur qui ne laisse passer que N choses à la fois (ici : 2 montages). |
| **Heartbeat** (battement de cœur) | Signal « je suis vivant » envoyé régulièrement par un job en cours. |
| **Reaper** (veilleur) | La tâche qui repère les jobs morts et les rembourse/relance. |
| **Claim** | Le geste par lequel un worker « prend » un job dans la file. |
| **SKIP LOCKED** | Une astuce de la base : deux workers ne prennent jamais le même job. |
| **Advisory lock** | Un « jeton » qui fait que les workers prennent les jobs chacun leur tour, pour compter juste. |
| **OOM** (Out Of Memory) | La machine n'a plus de mémoire → elle tue le programme. La cause du bug n°1. |

---

## ⚙️ Réglages de départ (à affiner en vrai)

| Réglage | Départ | À quoi ça sert |
| --- | --- | --- |
| `WORKER_SLOTS` | 6 | Vidéos en parallèle par machine |
| `RENDER_SLOTS` | 2 | Montages simultanés max (anti-crash mémoire) |
| `HEARTBEAT_INTERVAL` | 20 s | Fréquence du « je suis vivant » |
| `JOB_LEASE` | 180 s | Délai avant de déclarer un job mort |
| `MAX_ATTEMPTS` | 3 | Relances avant abandon + remboursement |

À surveiller en prod : la mémoire pendant les montages (ajuster `RENDER_SLOTS`), la longueur de la file, et le taux de relances par le veilleur (s'il est élevé → la machine sature, à régler).

---

## 🚀 Déploiement : progressif et réversible

On n'allume pas tout d'un coup. Chaque étape est sûre et revient en arrière facilement.

1. **Migration** (ajoute des colonnes, sans risque).
2. **Veilleur seul**, avec 1 seule vidéo à la fois → on gagne **déjà** la fiabilité (fin des comptes bloqués) sans rien changer d'autre.
3. On **monte les slots** doucement : 2 → 4 → 6, en regardant la machine.
4. On **règle le frein** du montage selon les pics de mémoire.
5. Quand une machine sature : on en **ajoute une deuxième** (zéro changement de code).

> Revenir à « 1 vidéo à la fois » = le comportement d'aujourd'hui, mais fiable. Filet de sécurité permanent.

---

---

# 🔧 Annexe technique (pour l'implémentation)

> Cette partie est pour le dev / Codex. Le reste du doc suffit à comprendre la proposition.

### Le claim atomique (cœur du système)

Une transaction qui : (1) prend un advisory lock global pour compter juste, (2) sélectionne le plus vieux job `queued` dont le client est sous sa limite de plan, (3) le verrouille avec `SKIP LOCKED` et le passe `running`.

```sql
select pg_advisory_xact_lock(816072);          -- sérialise les claims (clé fixe)

with claimable as (
  select j.id
    from jobs j
    join subscriptions s on s.user_id = j.user_id and s.status in ('trialing','active')
    join plan_definitions p on p.code = s.plan_code
   where j.status = 'queued'
     and ( select count(*) from jobs r
            where r.user_id = j.user_id
              and r.status in ('downloading','transcribing','analyzing','rendering')
         ) < p.max_concurrent_jobs              -- compteur exact (claims sérialisés)
   order by j.queued_at
   for update of j skip locked
   limit 1
)
update jobs set status='downloading', current_step='claimed',
       worker_id=$1, claimed_at=now(), heartbeat_at=now(),
       started_at=coalesce(started_at, now()), attempts=attempts+1, updated_at=now()
 where id in (select id from claimable)
returning id;
```

Si le débit de claims devenait un point chaud (improbable ici), sharder l'advisory lock par `hashtext(user_id)` au lieu d'une clé globale.

### Profil I/O vs CPU

Étapes I/O-bound (parallélisme libre, jusqu'à `WORKER_SLOTS`) : `download` (yt-dlp), `transcribe` (Whisper), `analyze` (LLM/vision), `upload` (R2).
Étape CPU/RAM-bound (bridée par `Semaphore(RENDER_SLOTS)`) : `render` (ffmpeg) + extraction de frames.

### Idempotence au re-run (prérequis du veilleur)

`run_job` se relance de zéro sur requeue → blinder deux points :
- `clips` a `unique (job_id, idx)` → supprimer les clips du job **avant** de retraiter (et idéalement les objets R2).
- Le débit initial est ré-inséré à chaque tentative → **recommandation : ne débiter qu'au settle final** (supprime le risque et simplifie le ledger).

### Fichiers brouillon

| Fichier | Rôle |
| --- | --- |
| `apps/worker/app/parallel/claim.py` | Claim atomique + heartbeat (SQL ci-dessus) |
| `apps/worker/app/parallel/reaper.py` | Veilleur : requeue / fail + refund |
| `apps/worker/app/parallel/supervisor.py` | Pool asyncio : boucle de claim, slots, sémaphore, shutdown |
| `docs/architecture/draft-0005_job_leasing.sql` | Migration (colonnes `claimed_at`, `heartbeat_at`, `attempts`) |

### À modifier au moment de promouvoir le brouillon

- `apps/worker/app/main.py` : remplacer la boucle `BLPOP` par `Supervisor.run()`.
- `apps/worker/app/pipeline/runner.py` : accepter `render_sem` + un hook heartbeat ; entourer le bloc rendu de `async with render_sem:` ; nettoyer les clips au début.
- `apps/worker/app/db.py` : `max_size` ≥ `WORKER_SLOTS + 2` (sinon les connexions DB se bloquent). Vérifier la limite du pooler Supabase.
- `apps/api/app/services/jobs.py` : l'INSERT du job suffit (retirer l'enqueue Redis) ; garder le check de concurrence au submit pour l'UX.
- `settings.py` : ajouter `worker_slots`, `render_slots`, `job_lease_seconds`, `heartbeat_interval_seconds`, `reaper_interval_seconds`, `max_attempts` ; supprimer `worker_concurrency` (mort).

### Scaling horizontal

Workers stateless : on ajoute des machines pointant sur le même Postgres, `SKIP LOCKED` + advisory lock garantissent zéro double-claim. La concurrence de rendu est par-machine (`RENDER_SLOTS × nb_machines`) ; pour un plafond global, prévoir un token DB ou un sémaphore Redis (pas nécessaire au début).

### Alternative Redis Streams (si le volume explose un jour)

`XADD` / `XREADGROUP` / `XACK` + `XAUTOCLAIM` pour récupérer les messages des workers morts. Gain : très haut débit. Coût : 2 systèmes à raisonner, et il faut **quand même** Postgres pour le gate de concurrence par user. À garder pour > ~50 claims/s soutenus — hors de portée à 2000 € MRR.
