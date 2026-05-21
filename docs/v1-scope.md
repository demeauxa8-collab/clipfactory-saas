# V1 scope — ClipFactory SaaS

Source de vérité du périmètre V1. Ce doc est cité par `plan.md` et `handoff-codex.md`.

---

## Règle produit

ClipFactory ne vend pas "AI clipping".
ClipFactory vend :

> Des clips choisis pour une campagne précise, avec un score expliqué par le texte, le visuel et le fit audience.

Chaque clip rendu doit afficher :
- hook score
- emotion score
- visual score
- campaign fit
- total score
- raison du choix
- hook / caption proposé
- preview + download

---

## Définition de "V1 complète"

V1 est terminée quand un utilisateur payant peut :

1. se connecter,
2. payer Starter (29€),
3. créer une campagne (audience / niche / ton / objectif / sujets à éviter / hooks d'exemple),
4. envoyer une vidéo,
5. recevoir 3 clips verticaux,
6. comprendre pourquoi ces clips ont été choisis (score breakdown + rationale),
7. télécharger les clips,
8. donner un feedback good/bad sur chaque clip,
9. et que le système a débité les crédits + loggé le coût/marge estimé du job.

Tout le reste est V2.

---

## Priorité absolue

Le plus important n'est PAS la landing, ni le polish UI, ni le design.

Le plus important est :

1. backend solide
2. pipeline qui marche de bout en bout
3. crédits / billing fiables
4. worker qui génère vraiment des clips
5. stockage R2 + DB cohérents
6. coûts / marges loggés

Si choix entre "belle UI" et "pipeline fiable" : **toujours pipeline fiable**.

UI V1 doit juste permettre de tester le produit :
- login
- payer
- créer campagne
- lancer job
- voir progression
- télécharger clips

---

## V1 — IN

| Domaine | V1 |
| --- | --- |
| Auth | Supabase magic-link |
| Plan unique | Starter 29€ / 300 credits / 30 min / 3 clips / 1 concurrent |
| Billing | Stripe Checkout + webhook + credit grant idempotent |
| Campagnes | Tables + form simple, attachée à chaque job |
| Pipeline | Download yt-dlp + Whisper API + Claude texte + vision sur candidats + render FFmpeg + R2 |
| Score expliqué | hook 35% + emotion 20% + visual 25% + campaign fit 15% + editing 5% |
| Vision | Sur 2-3 frames par moment candidat, jamais full video |
| Mémoire campagne | Feedback good/bad stocké, pas encore d'apprentissage auto |
| Logging coût/marge | Colonnes obligatoires sur jobs (estimations OK) |
| Dashboard | Crédits, campagnes, jobs, clips téléchargeables |

## V1 — OUT (V2)

| Domaine | Raison |
| --- | --- |
| Scheduling TikTok / Reels / Shorts | Workflow complet pas critique pour 200€ MRR |
| API publique | Vend après preuve de traction |
| MCP / agents | V2 après API publique |
| Team workspace | V2 |
| Brand templates | V2 |
| Multi-langue UI | V2 |
| Editor avancé / B-roll | V2 |
| Apprentissage auto sur feedback | V2 (V1 collecte la donnée seulement) |
| Multi-plans (Creator / Agency) | V2 — un seul plan visible V1 pour mesurer marge |

---

## Contraintes hard

- Ne pas modifier `/Users/augustindemeaux/ClipFactory` — lecture / inspiration uniquement.
- Ne pas copier les workers Mac tels quels (Codex CLI, MLX, chemins locaux interdits en SaaS).
- Code en anglais. Docs / chat en français.
- Pas de secret commité. `.env.example` seulement.
- À chaque étape finie : mettre à jour `handoff-codex.md`.
- Ne pas partir sur "refactor parfait" — V1 qui tourne d'abord.

---

## Définition de succès (résumé exécutif)

> Un utilisateur payant peut envoyer une vidéo, la pipeline la traite, 3 clips sont générés, les crédits sont débités, les fichiers sont stockés, et le dashboard affiche les résultats avec leur score expliqué.

Ne pas passer trop de temps sur marketing / design avant que ce flow marche.
