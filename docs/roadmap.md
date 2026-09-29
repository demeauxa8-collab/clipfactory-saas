# Feuille de route ClipFactory — du backend au premier client

> Plan de référence à partir du 29/09/2026. Une étape n'est « finie » que si son **critère de sortie** est atteint et **commité**. On ne commence pas une étape tant que la précédente de la même phase n'est pas finie.
> Durées réalistes avec un abonnement Claude à 20 € + un abonnement ChatGPT/Codex à 20 € (quotas compris). Total estimé : **4 à 6 semaines** jusqu'au test des modèles.

---

## Les règles du jeu

1. **Un seul chantier à la fois.** Une étape = une branche = une PR en brouillon. Augustin merge ; aucun agent ne merge.
2. **Critère chiffré ou rien.** Chaque étape a un critère de sortie mesurable. « Ça a l'air mieux » n'en est pas un.
3. **Qui fait quoi :**
   - **Codex** (sur le Mac Studio) : les longs travaux — installation, implémentation, reports de code. Il tourne seul.
   - **Claude** (sur le MacBook) : specs, relecture des PR, tests, vérifications, doc. **Sonnet** par défaut, **Opus** seulement pour les fusions difficiles. Maximum 2 agents en parallèle.
   - **Augustin** : les actions qu'aucun agent ne peut faire (sudo, comptes, clés, merge) et les jugements humains (notation des clips).
4. **Le goulot, ce sont les validations d'Augustin.** Chaque ⏸ ci-dessous attend une action de sa part ; y répondre le jour même tient le calendrier.
5. **Jamais un changement de pipeline et de modèle dans la même comparaison.**
6. **Les agents se parlent par GitHub.** Chaque étape = une PR ; c'est le canal entre Codex et Claude :
   - l'exécutant (souvent Codex) écrit dans la **description de la PR** : ce qui est fait, les tests (commandes + résultats), le critère de sortie atteint ou non, les questions ouvertes ;
   - le relecteur (souvent Claude) répond en **commentaires de revue** sur la PR ; l'exécutant lit les commentaires avant chaque reprise et répond dans le fil ;
   - une question pour Augustin commence par **`@augustin`** dans le fil et bloque l'étape jusqu'à sa réponse ;
   - rien de sensible dans les PR (repo public) : pas de clés, pas de noms de prospects, pas de faille détaillée.

---

## Vue d'ensemble

| Phase | Objectif | Durée | Fin de phase |
|---|---|---|---|
| **A. Backend Mac Studio** | API + Redis + worker + transcription locale + clips servis sans R2, en ligne 24 h/24 | 3 à 5 jours | un vrai job réussi depuis le site |
| **B. Pipeline meilleure version** | ancrage, montage, fins propres, second brain de campagne, juge calibré, cadrage | 3 à 4 semaines | tag `pipeline-vtest-…` posé |
| **C. Test des modèles par groupes** | choisir la stack de modèles sur des clips réels | 2 à 3 jours | `models.lock` de prod décidé |
| **D. Vente** (en parallèle dès B2) | premiers clients payants | continu | 3 clients payants |
| **E. Plus tard** | montage viral avancé, Director, apprentissage, VPS | après D | — |

Ordre des merges : **PR #9** (docs) → **PR #8** (consolidation) → branche backend Mac Studio → une branche par étape B.

---

## Phase A — Backend sur le Mac Studio M1 Max

Doc détaillé : `docs/mac-studio-backend.md`. Exécutant : Codex sur le Studio.

| # | Étape | Qui | Livrable | Critère de sortie | Durée |
|---|---|---|---|---|---|
| A1 | Préparer la machine | ⏸ Augustin (sudo) | veille coupée, redémarrage auto, session auto | `pmset -g` : `sleep 0`, `autorestart 1` | 15 min |
| A2 | Outils + code | Codex | Homebrew, ffmpeg avec libass, deno, yt-dlp, Redis local, `~/clipfactory-prod` sur la branche de la PR #8 | tests api + worker verts sur le Studio | ½ j |
| A3 | Secrets | ⏸ Augustin (AirDrop des `.env`) + Codex | `.env` en place, R2 retiré, `MEDIA_SIGNING_SECRET` généré | aucune variable manquante, rien de suivi par git | 30 min |
| A4 | Transcription locale MLX | Codex | backend `mlx_whisper` enfichable + repli OpenAI | seuils du runbook §6 atteints, sinon `openai` gardé et expliqué | 1 j |
| A5 | Clips sans R2 | Codex | route `/media` signée, Range, anti-traversée, R2 optionnel | tests §6.b verts | 1 j |
| A6 | Services + exposition | Codex + ⏸ Augustin (Tailscale, Vercel) | launchd api/worker, Tailscale Funnel, `NEXT_PUBLIC_API_URL` | `doctor.sh` 100 % vert | ½ j |
| A7 | Test de connexion + vrai job | Claude (test) + ⏸ Augustin (job depuis le site) | rapport de passation | `/health`, TLS, CORS OK ; un job de 5–10 min va jusqu'au téléchargement du clip | ½ j |

**Fin de phase A** : ⏸ Augustin merge la PR backend.

---

## Phase B — Le pipeline à sa meilleure version

Plan détaillé (inventaire, preuves, estimations) : document privé « Second Brain, Director et montage multi-segments : inventaire et plan de finition ». Le socle est la PR #8 (ancrage strict, rendu EDL branché, crédits atomiques, `models.lock`).
Pour chaque étape : **Claude écrit la spec courte** (fichiers, tests, critère) → **Codex implémente** sur une branche → **Claude relit et teste** → ⏸ **Augustin merge**.

| # | Étape | Livrable | Critère de sortie | Durée |
|---|---|---|---|---|
| **B0** | Référence mesurée | harnais « golden » (sources figées, métriques, rapport) ; juge de clip en observation seule ; page de notation | ⏸ **Augustin note 40 clips** (~3 h) ; accord juge ↔ Augustin mesuré ; rendement publiable de départ connu | 2 j + 3 h |
| **B1** | Fins, ouvertures, bugs du montage | contrôle fins/ouvertures après ancrage ; promesse → chute vérifiée ; `duration_seconds` juste ; raisons persistées ; échecs de snap instrumentés | 0 fin suspendue ; ouvertures dépendantes ≤ 10 % sur le golden | 3 j |
| **B2** | Second brain de campagne (léger) | liste fermée de raisons de rejet ; feedback lu par le worker ; exemples bons/mauvais de la campagne injectés dans la sélection et le juge ; règles de craft par tags ; ⏸ migration validée par Augustin | sur 3 campagnes test avec 5 feedbacks : moins de clips « hors brief » ou « accroche faible » qu'en B1 | 3 j |
| **B3** | Juge = filtre + reclassement | le juge écarte les clips non publiables et reclasse les candidats | seulement si accord κ ≥ 0,6 et rappel ≥ 0,8 (mesurés en B0) ; rendement publiable +10 points vs B1 | 1 j |
| **B4** | Cadrage sans bandes noires | recadrage piloté par la vision (position du visage), plein cadre par défaut | 0 bande noire sur le golden ; rendement publiable ≥ B3 | 4 j |

**Fin de phase B** : tests verts, golden au niveau de B4, ⏸ Augustin valide → tag **`pipeline-vtest-AAAA-MM-JJ`**.
Optionnel si prêt à temps (sinon après C, en A/B sur le groupe gagnant) : B5 opérations de montage (silences, punch-in, texte d'accroche, profils par plateforme), B6 Director en réparation bornée.

---

## Phase C — Test des modèles par groupes

Doc détaillé : `docs/model-test-plan.md`.

| # | Étape | Qui | Critère de sortie | Durée |
|---|---|---|---|---|
| C1 | Préparer : 5 fichiers de groupes (G0 à G4), 2 briefs, 4 vidéos figées, page de comparaison, vérif des modèles la veille | Claude | tout prêt, rien lancé | ½ j |
| C2 | Lancer la même campagne avec chaque groupe (un groupe à la fois, depuis le site) | ⏸ Augustin lance, Codex/Claude surveillent | 5 groupes × 4 jobs terminés, aucun job passé en secours sans être marqué | 1 j |
| C3 | Revue à l'aveugle des clips | ⏸ Augustin (~45 min) | chaque clip noté publiable oui/non + raison ; classement par source | 45 min |
| C4 | Décision | Claude propose, ⏸ Augustin tranche | groupe gagnant = `models.lock` de prod ; prompts ré-ajustés pour ce groupe seulement | ½ j |

---

## Phase D — Vente (démarre en parallèle dès la fin de B2)

| # | Étape | Qui | Critère |
|---|---|---|---|
| D1 | Relances des prospects déjà contactés, avec un clip réel tiré de leur épisode | ⏸ Augustin envoie, Claude prépare les clips | chaque relance porte un clip |
| D2 | 5 nouveaux prospects par jour, chacun avec un clip prêt | Claude prépare, ⏸ Augustin envoie | 50 contacts ; si 0 réponse, on change de cible (clippeurs pro) |
| D3 | Stripe Starter en production | ⏸ un adulte titulaire du compte Stripe + Claude (config) | un paiement test réel remboursé de bout en bout |
| D4 | Premier client | — | 1, puis 3 clients payants |

---

## Phase E — Plus tard (après les premiers clients)

- B5 / B6 si non faits ; apprentissage léger à partir des vues réelles des clips publiés.
- VPS pour l'API (control plane) quand un client paie : `docs/deploy.md` §5.A ; stockage objet à ce moment-là si besoin, sans changer le contrat de l'API.
- Domaine à soi + tunnel Cloudflare à la place de Tailscale Funnel.
- Nouveaux modèles : uniquement via un nouveau test par groupes.

---

## Calendrier indicatif

| Semaine | Travail |
|---|---|
| S1 | Phase A complète · B0 démarré (harnais + page de notation) · ⏸ notation des 40 clips |
| S2 | B1 · B2 |
| S3 | B2 fin · B3 · démarrage D1/D2 |
| S4 | B4 · tag `pipeline-vtest` |
| S5 | Phase C · décision des modèles · D continue |
| S6 | marge (quotas, retours, corrections) |

## Moments où Augustin doit agir (⏸)

A1 sudo · A3 AirDrop des `.env` · A6 Tailscale + Vercel · A7 lancer un job · merge de chaque PR · B0 noter 40 clips · B2 valider la migration · fin B valider le tag · C2 lancer les jobs · C3 revue 45 min · C4 trancher · D envoyer les messages · D3 Stripe (titulaire adulte).
