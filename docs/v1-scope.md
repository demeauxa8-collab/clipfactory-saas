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
| Pipeline | Story-first (≥ 5 min) + simple (< 5 min), **montage multi-segments 1-3 moments** (`link_reason` obligatoire), transitions par joint (cut sec / dip-to-white 0,10 s selon continuité), crossfade audio 150 ms, cadrage face-crop par segment, captions FR karaoké, anti-hallucination verify |
| Vision | Vision cheap globale + vision deep top 5 arcs (gemini-2.5-flash via OpenRouter, `reasoning` désactivé), renvoie `face_center_x` + `burned_captions` par segment |
| Score expliqué | Story (montage-v2) : visual 28 / hook 20 / payoff 18 / fit 12 / continuity 12 / retention 10 ; campaign_fit = 0.5 auto-éval LLM + 0.5 mots-clés flous ; simple : hook 35 / emotion 20 / visual 25 / fit 15 / editing 5 |
| Mémoire campagne | Feedback good/bad stocké, pas encore d'apprentissage auto |
| Logging coût/marge | Colonnes obligatoires sur jobs (estimations OK), split video_map_cost_cents / deep_vision_cost_cents |
| Dashboard | Crédits, campagnes, jobs, clips téléchargeables, badge MONTAGE sur clips multi-segments |

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

## Décisions techniques (statut au 2026-07-08)

Tranchées :
- ~~Choix providers LLM~~ → OpenRouter primary. **Config validée en réel (2026-07)** : `google/gemini-2.5-flash` sur les 3 rôles (texte, vision cheap, vision deep) avec `reasoning:{max_tokens:0}`. Le mix économique DeepSeek texte + Qwen vision cheap reste une optimisation à re-benchmarker. Fallback Anthropic Haiku 4.5 configuré mais désactivé (pas de clé). Transcription : OpenAI `whisper-1` (word timestamps obligatoires).
- ~~Stratégie fallback~~ → switch automatique sur parse error / timeout / 5xx quand activé. Défaut code `ENABLE_FALLBACK=true`, mais **`false` en local actuellement** (pas de clé Anthropic).
- ~~Seuil routing pipeline simple vs story~~ → 5 min (`STORY_PIPELINE_THRESHOLD_SECONDS=300`).
- ~~Politique montage~~ → montage-v2 (2026-07-08) : 1-3 segments, `link_reason` obligatoire en multi, transitions par joint (cut sec / dip-to-white selon continuité vision), cadrage par segment. L'interdiction single-segment du 2026-07-06 est annulée.
- ~~Format clips~~ → `segments jsonb` (liste ordonnée). Migration 0003.
- ~~Anti-hallucination~~ → string match transcript_excerpt vs transcript réel, SequenceMatcher ratio ≥ 0.65 → drop arc complet.
- ~~Crossfade entre segments~~ → audio 150 ms (`acrossfade`) ; image : cut sec si même scène, dip-to-white 0,10 s si changement de scène (montage-v2).

À mesurer V1 (post-déploiement) :
- Marge réelle LLM par job (estimée ~12 EUR/mois pour 7 users, à vérifier sur vrais coûts).
- Taux de fallback réel (`jobs.fallback_used = true`) → si > 20 %, ajuster provider primary.
- Quand activer `EVAL_SAMPLE_RATE > 0` pour benchmarker primary vs secondary.

---

## Définition de succès (résumé exécutif)

> Un utilisateur payant peut envoyer une vidéo, la pipeline la traite, 3 clips sont générés, les crédits sont débités, les fichiers sont stockés, et le dashboard affiche les résultats avec leur score expliqué.

Ne pas passer trop de temps sur marketing / design avant que ce flow marche.
