# Architecture infrastructure — ClipFactory

> Décision d'architecture : séparation **control plane** (VPS) / **worker** (Mac Studio).
> Statut : adopté · Dernière mise à jour : 2026-06

---

## 1. Principe

L'infra est découpée en deux rôles aux natures opposées :

- **Control plane (VPS)** — la « porte d'entrée » qui doit répondre **24/7**.
- **Worker (Mac Studio M2 Ultra)** — le « bras musclé » qui fait le **calcul lourd** mais interruptible.

L'image de référence : **le VPS est la caisse + la porte d'entrée du resto, le Mac est la cuisine.** La caisse et la porte restent ouvertes même si un cuisinier est malade.

---

## 2. Répartition des rôles

### VPS (control plane) — doit toujours être joignable
- API publique + dashboard client
- Base de données (source de vérité : clients, paiements, crédits)
- Queue de jobs
- Webhooks Stripe (un webhook raté = de l'argent perdu)

### Mac Studio (worker) — travail lourd, tolérant aux pannes
- Transcription via l'**API OpenAI** (`gpt-4o-mini-transcribe`, appelée avec une clé API) — **pas** de Whisper local.
- Rendu vidéo (ffmpeg)
- Génération des captions animées

Le Mac **va chercher** les jobs dans la queue (modèle *pull*). Il se connecte vers
l'extérieur — **personne ne se connecte à lui**.

---

## 3. Pourquoi séparer (et ne pas tout mettre sur le Mac)

| Risque si tout sur le Mac | Conséquence |
|---|---|
| Coupure internet / courant à la maison | SaaS **down**, dashboard inaccessible |
| Mise à jour macOS / reboot automatique | Idem, en pleine nuit, sans surveillance |
| Webhook Stripe pendant une indisponibilité | Paiement potentiellement raté |
| Unique copie de la DB sur un disque maison | Disque qui lâche = perte des clients |
| Réseau maison exposé publiquement | Surface d'attaque sur le même réseau que les machines perso |

**Bénéfice du split :** si le Mac tombe une heure, le produit **ne tombe pas**. Les
clients se connectent toujours, uploadent (→ queue), les paiements passent. Seul le
*traitement* prend du retard, et se rattrape tout seul au retour du Mac.

---

## 4. Sécurité : le modèle *pull* (zéro port ouvert)

Comme le Mac interroge la queue au lieu d'attendre une connexion entrante :
- **Aucun port à ouvrir** sur le réseau maison.
- La surface d'attaque publique vit sur un **VPS jetable** (reconstruit en ~10 min si compromis).
- Le réseau perso reste isolé.

---

## 5. Stockage des vidéos

Les gros fichiers vidéo **ne transitent pas par le VPS**. Ils vont dans de l'**object
storage S3-compatible** :
- uploads et clips servis depuis l'object storage,
- bande passante du VPS préservée,
- le pic de charge (« choc d'user ») est absorbé par la **queue**, pas par la puissance du VPS.

> Le facteur qui encaisse réellement un afflux d'utilisateurs, c'est le **débit du Mac**
> (vidéos rendues / heure), pas la taille du VPS.

---

## 6. Stratégie de déploiement par phase

### Phase BUILD / TEST (zéro client payant) — *actuel*
- **Tout sur le Mac Studio** + **Cloudflare Tunnel** (URL publique HTTPS, sans ouvrir de port, IP maison cachée).
- Gratuit, suffisant pour valider le produit.
- **Pas de VPS à ce stade.**

### Phase PROD (dès l'activation de Stripe / premier client payant)
- **Split : petit VPS (control plane) + Mac Studio (worker).**
- Le standard de fiabilité monte → le VPS à 8–15 €/mois devient une évidence
  face au risque de perdre un client.

**Déclencheur du passage en prod : le premier euro encaissé.**

---

## 7. Choix du VPS

Cible : contrôle plane léger, hébergé en **UE (argument GDPR)**, français de préférence.

| Provider | Offre conseillée | Specs | Prix/mois (HT) | Remarque |
|---|---|---|---|---|
| **OVHcloud** | VPS-2 | 2 vCPU / ~4 Go | ~8,49 € | Tout compris (IP + bande passante). Le plus simple à budgéter. |
| **Scaleway** | DEV1-M | 3 vCPU / 4 Go | ~14,74 € (+ IPv4 ~2,9 €) | Pas de frais d'egress, meilleure API/console/Terraform. |

- Prix **HT** → +20 % TVA en France.
- Montée en charge : changement d'instance en quelques minutes (vertical scaling), pas besoin de surdimensionner dès le départ.
- **À éviter : Hetzner** — KYC durci (upload pièce d'identité + selfie obligatoire).
  Scaleway/OVH demandent en général **juste une carte** (pas de pièce d'identité).

---

## 8. Note légale (titulaire des comptes)

Fondateur mineur → impossible de signer un contrat d'hébergement ou de détenir un
compte de paiement en son nom.

- **Un parent est titulaire légal de la couche infra + paiements** (compte cloud, carte, Stripe/KYC).
- Le fondateur **opère** tout (accès, déploiement, code).
- Le parent = nom sur le papier + carte, **pas un cofondateur**, n'intervient pas sur le technique.
- À résoudre **en une seule fois** : ouvrir compte cloud + Stripe dans la même session.

---

## TL;DR

- **Maintenant** : tout sur le Mac + Cloudflare Tunnel. Pas de VPS.
- **Au premier client payant** : split VPS (control plane, ~8–15 €/mois) + Mac (worker).
- Le VPS porte ce qui doit jamais tomber (API, DB, Stripe) ; le Mac porte le calcul lourd.
- Mac en *pull* → zéro port ouvert. Vidéos en object storage. Le pic est absorbé par la queue.
