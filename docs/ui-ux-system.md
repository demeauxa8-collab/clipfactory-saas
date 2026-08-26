# Système UI/UX ClipFactory — direction, parcours et règles de maintenance

> Document canonique pour tout agent qui modifie la landing, le parcours d'activation, le traitement, le paywall ou le workspace web.
>
> Dernière mise à jour : 2026-08-26. État décrit : branche `redesign/ui-ux-lab`, commits UI `2081513` et `4d8b50d`.

## 1. Lire ceci avant de toucher au frontend

ClipFactory n'est pas un dashboard générique d'IA. C'est un SaaS de montage **campaign-first** : l'utilisateur donne une intention de campagne, une source longue, puis reçoit des clips dont les mots, l'image, le timecode et la raison éditoriale restent reliés.

La direction livrée se lit ainsi : **un outil de montage Apple Pro / Final Cut, calme et précis, avec des moments lumineux contrôlés — jamais une landing sombre remplie de cartes SaaS et de gradients violets**.

Ordre de priorité si deux règles se contredisent :

1. instruction explicite d'Augustin ;
2. tokens et décisions déjà présents dans le projet ;
3. skill spécialiste du domaine (`apple-design`, `animate`, `accessibility`, `form-design`, etc.) ;
4. références `uikit` (`craft.md`, `ux.md`, `apple-style.md`) ;
5. goût général ou style d'un composant externe.

Avant une modification UI :

1. lire `AGENTS.md`, puis charger le skill `uikit` ;
2. lire ce document ;
3. lire `apps/web/.21st/design.json` — source machine des contraintes ;
4. inspecter les composants et tokens existants avant toute recherche externe ;
5. identifier si le travail touche le **chrome produit** ou une **surface démonstrative** ;
6. vérifier le résultat par screenshot à 390 px et 1440 px ;
7. ne jamais présenter une surface qui n'a pas été regardée dans le navigateur.

`apps/web/.21st/DESIGN.md` est généré. Modifier les décisions dans `apps/web/.21st/design.json`, puis régénérer le snapshot au lieu d'éditer le Markdown généré à la main.

---

## 2. L'idée directrice : le « Source Thread »

Chaque écran doit rendre visible le même fil de décision :

```text
Campaign brief
      ↓
Source video + transcript
      ↓
Candidate moment + visible proof
      ↓
Vertical frame + exact words
      ↓
Explained clip + delivery
```

Cette continuité est le différenciateur. Un clip ne doit jamais apparaître comme un résultat magique détaché de sa source.

Les relations à maintenir visuellement et dans la copie :

- l'intention de campagne explique **pour qui** et **pour quoi** on coupe ;
- le timecode et le transcript prouvent **où** se trouve le moment ;
- le cadre et l'image prouvent **ce qui est visible** ;
- le score et la rationale expliquent **pourquoi** le moment a été retenu ;
- le résultat garde l'accès à ces preuves au lieu de devenir un simple fichier MP4.

Si une nouvelle page ne renforce pas ce fil, elle est probablement décorative ou mal placée dans l'architecture.

---

## 3. Parcours utilisateur canonique

Le parcours validé est :

```text
Landing
  → account
  → campaign brief
  → source URL
  → first-job processing
  → first clip ready
  → user presses play
  → 3-second teaser + contextual paywall
  → unlocked result
  → workspace
```

Le paywall est une **conséquence contextuelle de la première lecture**, pas une étape numérotée autonome dans la progression.

| Étape visible | Promesse utilisateur | Surface canonique | Condition de sortie |
| --- | --- | --- | --- |
| Sign in | Ouvrir un espace où la source et le brief seront conservés | écran de connexion | session créée ou fixture locale confirmée |
| Campaign | Définir l'intention éditoriale sans remplir sept champs plats | brief en trois chapitres sémantiques | brief valide et explicite |
| Source | Attacher une vidéo au brief | URL YouTube/Vimeo + récapitulatif campagne | source reconnue |
| Build | Voir ce que fait réellement ClipFactory | `SignalTimeline` immersif | premier clip prêt |
| Verrou contextuel | Comprendre ce qui est déjà produit et pourquoi payer | `ClipGate`, teaser de trois secondes | abonnement confirmé ou démo déverrouillée |
| Review | Inspecter les candidats, leur preuve et leur score | viewer + tabs + inspector | clip sélectionné |
| Workspace | Continuer le travail sans perdre le contexte | liste campagnes/jobs/clips + prochaine action | prochaine tâche claire |

### Règle de vérité commerciale

Le parcours `/preview/journey` simule une première génération offerte afin de tester la désirabilité. La production ne doit placer le paywall après le traitement que si le backend implémente réellement :

- un essai borné au premier job ;
- des sorties verrouillées ;
- aucune fuite du fichier complet avant paiement ;
- une reprise fiable après confirmation Stripe.

Tant que ce contrat n'est pas actif, garder le contrôle de crédits avant le calcul via `components/product/paywall-dialog.tsx`. Ne pas mentir dans l'UI avec une génération « gratuite » que le produit ne supporte pas.

### Ce qui n'est pas canonique

- `screen=paywall` existe seulement comme fixture/lab historique ; hors `lab=1`, la route le remappe sur `processing`.
- Les contrôles « Reset », sélecteurs d'états et rails de fixtures ne doivent jamais apparaître dans l'app client.
- La preview n'envoie aucune donnée, ne crée aucun compte, paiement, upload, job ou export.

---

## 4. Direction artistique

### 4.1 Références et traduction dans ClipFactory

- [Apple Final Cut Pro](https://www.apple.com/final-cut-pro/) : structure navigateur / viewer / timeline / inspector, densité d'outil pro, montage comme métaphore principale.
- Pages Apple Pro : grandes idées éditoriales, contraste précis, rythme généreux, transitions physiques, matériaux utilisés avec parcimonie.
- [Linear](https://linear.app/) : hiérarchie produit calme et états nets.
- [Stripe](https://stripe.com/) : pédagogie progressive d'une mécanique complexe.
- [Vercel](https://vercel.com/) : retenue typographique et interface qui privilégie le contenu.

Ce ne sont pas des styles à copier pixel par pixel. La traduction propre à ClipFactory est le **Source Thread** : une ligne de temps, un axe optique et des preuves éditoriales qui restent synchronisées.

### 4.2 Palette

La palette est monochrome graphite avec **un seul bleu d'action**.

| Token | Valeur | Usage |
| --- | --- | --- |
| `--color-background` | `#0b0b0d` | fond principal |
| `--color-foreground` | `#f5f5f7` | texte principal |
| `--color-muted` | `#161618` | surfaces discrètes |
| `--color-muted-foreground` | `#a1a1a6` | texte secondaire |
| `--color-border` | `rgba(255, 255, 255, 0.09)` | séparateurs et contours |
| `--color-accent` | `#0071e3` | CTA, focus, source active, playhead |
| `--color-brand-soft` | `#0a2a4a` | mélange local du bleu, jamais une deuxième teinte concurrente |
| `--color-success` | `#5dd38b` | succès réellement vérifié uniquement |
| `--color-warn` | `#f59e0b` | avertissement opérationnel uniquement |
| `--color-danger` | `#ef4444` | erreur/destruction uniquement |

Règles :

- ne pas réintroduire l'orange comme couleur de marque ;
- ne pas créer plusieurs bleus arbitraires dans les modules CSS ; utiliser `var(--color-accent)` ou les alias `--cf-action`, `--cf-signal`, `--jt-action` ;
- ne pas utiliser le vert pour « faire joli » : il signifie qu'une preuve ou une action est effectivement validée ;
- les moments lumineux sont des halos neutres ou bleus très localisés autour d'une action, d'un focus ou d'une sélection — jamais un mesh décoratif permanent ;
- pas de gradient violet-bleu sur fond sombre.

La source de vérité des couleurs reste `apps/web/app/globals.css`. Les alias de l'app vivent dans `apps/web/app/product.css` ; la journey doit conserver `--jt-action: var(--color-accent)`.

### 4.3 Typographie

- pile Apple native : `-apple-system`, `BlinkMacSystemFont`, `SF Pro Text`, puis Inter/Helvetica/Arial ;
- titres : même famille avec `SF Pro Display`, pas de vraie serif ;
- titres serrés : tracking global `-0.022em`, grands titres jusqu'à environ `-0.058em` quand le module le définit ;
- corps : hiérarchie par poids, contraste et espace, pas par accumulation de tailles ;
- monospace uniquement pour timecodes, données de source et labels techniques.

Ne pas remplacer la pile par Inter partout. Sur Apple, la présence réelle de SF Pro fait partie de la direction.

### 4.4 Formes, surfaces et profondeur

Rayons canoniques :

- `8px` : inputs ;
- `14px` : petits badges ;
- `20px` : cartes internes ;
- `32px` : panneaux externes ;
- `999px` : vrais pills, contrôles segmentés et boutons qui le justifient.

Les coins imbriqués doivent être concentriques : le rayon intérieur est plus petit que le rayon extérieur en tenant compte du padding. Le glass est limité au chrome sticky, au paywall et à quelques surfaces transitoires ; il ne devient pas le matériau de toutes les cartes.

Les ombres sont larges, douces et peu opaques. Une lueur ne remplace jamais un niveau d'élévation.

---

## 5. Construction de la landing

### 5.1 Entrée et direction canonique

`apps/web/app/page.tsx` rend `AppleEditAxis`. C'est la landing canonique. Les anciennes directions restent dans le lab, mais ne doivent pas être remontées sur `/` sans une nouvelle décision explicite.

Le hero suit une composition d'outil de montage :

- message et CTA à gauche ;
- aperture 9:16 et sujet sélectionné au centre/droite ;
- rationale de campagne attachée à la sélection ;
- timeline source en bas ;
- un même playhead relie l'image, le timecode, les mots et le moment actif.

L'idée forte est : **l'utilisateur déplace la source sous un axe de décision stable**. Ne pas ajouter un deuxième gimmick visuel au hero.

### 5.2 Synchronisation visuelle

`apple-edit-axis.tsx` conserve une seule `MotionValue` de progression. Cette valeur pilote :

- le strip de frames ;
- le timecode ;
- le frame actif ;
- le moment éditorial le plus proche ;
- la fenêtre verticale ;
- le contenu de l'inspector ;
- la géométrie transmise au shader.

Ne pas dupliquer la progression dans plusieurs `useState`. Toute nouvelle couche visuelle qui représente le même instant doit dériver de la même valeur.

### 5.3 Shader de campagne

`campaign-lens-shader.tsx` est un composant custom, car aucun composant de catalogue ne pouvait exprimer correctement la géométrie partagée entre l'aperture HTML, le crop 9:16 et l'image de fond.

Le shader :

- garde la couleur et le contraste utiles dans la lentille ;
- désature et assombrit le contexte extérieur ;
- travaille en coordonnées CSS partagées avec l'interface ;
- écoute `webglcontextlost` et `webglcontextrestored` ;
- conserve une image sémantique `next/image` comme fallback WebGL/CORS/context loss ;
- ne contient pas de boucle décorative dépendante du temps ;
- marque l'image héroïque comme prioritaire afin de protéger le LCP.

Si le crop visuel et l'overlay HTML dérivent, corriger la transformation commune. Ne pas « réaligner » les deux côtés avec des offsets magiques indépendants.

### 5.4 Récit sous le hero

`edit-axis-story.tsx` prolonge une idée par section :

1. `#story` — plusieurs moments deviennent un arc, pas une suite de timestamps ;
2. `#campaign-v6` — une même source produit un choix différent selon le brief ;
3. preuve transcript/timecode — le résultat reste défendable ;
4. `#workflow` — source vers clip expliqué ;
5. `#reliability` — états et garanties ;
6. `#pricing` — une seule offre Starter ;
7. `#faq-v6` — objections sans labyrinthe juridique ;
8. `#closing-v6` — conclusion et CTA.

Éviter les trois cartes de fonctionnalités identiques. Le contenu et la mécanique de chaque section doivent changer, tout en gardant la même grammaire graphique.

---

## 6. Construction du produit et de la journey

### 6.1 Primitives communes

Les primitives visuelles partagées vivent dans :

- `apps/web/components/product/product-primitives.tsx` ;
- `apps/web/app/product.css` ;
- `apps/web/components/ui/`.

Réutiliser en priorité `ProductMark`, `Brand`, `PageIntro`, `Panel`, `SectionTitle`, `Status`, `BackLink`, `EmptyState` et `CheckList`. Ne pas recréer un logo, un panel, un status pill ou une empty state dans chaque page.

### 6.2 Formulaires

- un label visible reste associé à chaque champ ; un placeholder ne remplace jamais le label ;
- organiser le brief en chapitres sémantiques, pas en longue fiche plate ;
- valider au blur et expliquer comment corriger ;
- ne pas désactiver silencieusement le submit : accepter l'action, puis remonter les erreurs utiles ;
- conserver les valeurs déjà saisies après une erreur réseau, auth ou billing ;
- une action principale par étape.

### 6.3 Processing : `SignalTimeline`

`apps/web/components/prototypes/processing/signal-timeline.tsx` est la direction canonique. `SourceCut` et `ProofManuscript` sont des références de lab seulement.

La séquence visible vient de `processing-sequence.ts` :

1. Source secured ;
2. Words anchored ;
3. Campaign moments found ;
4. The proof selected ;
5. Subject reframed ;
6. Exact words composed ;
7. First clip ready.

Les délais de démonstration sont `760 / 920 / 1120 / 980 / 1040 / 1160 ms`. En production, les événements doivent venir de vraies étapes du job plutôt que de timers.

Règles de waiting UX :

- pas de faux pourcentage ;
- pas d'ETA inventée ;
- afficher ce qui vient d'être acquis et ce qui arrive ensuite ;
- conserver la campagne et la source à l'écran ;
- fournir un état `loading`, `processing`, `empty`, `error`, `success` et `long` ;
- après 10 secondes, donner une explication utile plutôt qu'une animation plus intense.

### 6.4 Paywall

Deux composants répondent à deux contrats différents :

- `components/prototypes/processing/clip-gate.tsx` : désirabilité après le premier clip, teaser 3 s, contexte conservé, utilisé dans la journey ;
- `components/product/paywall-dialog.tsx` : garde de production pour `no_subscription`, `insufficient_credits` et `past_due`.

Les dialogs utilisent Radix UI. Ne pas remplacer par un overlay maison : focus initial, fermeture, portail, clavier et annonces sémantiques sont déjà gérés.

Le paywall doit répondre immédiatement à quatre questions :

1. qu'est-ce qui est déjà prêt ?
2. qu'est-ce que le paiement déverrouille ?
3. combien cela coûte et quelles limites s'appliquent ?
4. qu'est-ce qui reste sauvegardé si je ferme ?

### 6.5 Review et workspace

Le review garde une logique d'éditeur : browser de clips, viewer, timeline et inspector. Les tabs de clips utilisent Radix. Le player de production dans `app/app/jobs/[id]/rendered-clip-player.tsx` utilise `components/ui/video-player.tsx`.

Le workspace doit conduire vers la prochaine action — nouvelle source, campagne à reprendre, clip à télécharger ou paiement à résoudre — et non ouvrir par une grille de métriques avant la première valeur reçue.

---

## 7. Composants externes et provenance

La mécanique externe est adaptée aux tokens et à l'accessibilité ClipFactory ; le style de démo n'est jamais copié tel quel.

| Bloc | Source | Statut | Règle |
| --- | --- | --- | --- |
| Dialog / focus | Radix UI Dialog | production | primitive obligatoire pour les modales |
| Tabs | Radix UI Tabs | production | review et sélection de clips |
| Motion | `motion` | production | transitions guidées et valeurs synchronisées |
| Video player | [21st.dev / preetsuthar17](https://21st.dev/@preetsuthar17/components/video-player) | production, adapté | mécanique clavier/focus/fullscreen, tokens ClipFactory |
| Magnetic carousel | [Originkit](https://www.originkit.dev/components/magneticcarousel) | lab `SourceCut` | listbox accessible et clavier conservés ; pas canonique |
| `DitherReveal` | Originkit/WebGL adaptation | lab `LivingEditSpace` | ne pas activer sur la landing sans décision |
| `CursorRingField` | shader/Three.js porté en raw WebGL | lab `KineticBroadcast` | boucle décorative incompatible avec la direction actuelle |
| Campaign lens | custom ClipFactory WebGL | production | justifié par la synchronisation source/crop/HTML |

Pour un nouveau bloc : code existant → Originkit → 21st → Magic UI → React Bits → KokonutUI → Origin UI/HeroUI → Uiverse → custom. Comparer deux ou trois candidats, puis n'en intégrer qu'un. Documenter la source dans le composant.

---

## 8. Langage d'animation

L'animation sert trois fonctions : causalité, continuité spatiale et attente. Elle ne sert pas à maintenir l'écran artificiellement en mouvement.

### Valeurs et comportements

- interactions directes : environ `140–180 ms` ;
- changement d'écran journey : spring `0.38 s`, `bounce: 0` ;
- indicateur partagé : spring `0.4 s`, `bounce: 0` ;
- easing principal : `cubic-bezier(0.23, 1, 0.32, 1)` ;
- drawer/sheet : `cubic-bezier(0.32, 0.72, 0, 1)` ;
- privilégier `transform`, `opacity` et `clip-path` contrôlé ;
- ne pas utiliser `transition: all` ;
- pas d'entrée animée automatique sur chaque carte ;
- pas de boucle infinie purement décorative.

### Moments dopaminergiques autorisés

La montée d'énergie doit correspondre à une acquisition réelle :

- transcript verrouillé ;
- candidat sélectionné ;
- passage 16:9 vers 9:16 ;
- mots composés ;
- premier clip prêt ;
- déverrouillage confirmé.

Chaque beat peut intensifier lumière, son visuel, échelle ou vitesse, puis revenir au calme. Éviter de tout animer simultanément : un changement dominant par beat.

### Préférences système

Toute nouvelle animation doit définir un comportement pour :

- `prefers-reduced-motion: reduce` ;
- `prefers-reduced-transparency: reduce` quand glass/shader est impliqué ;
- `prefers-contrast: more` sur les surfaces à faible contraste.

Reduced motion ne veut pas dire retirer l'information. Remplacer le mouvement par un changement d'état immédiat ou une transition courte en opacité.

---

## 9. Accessibilité et états obligatoires

Chaque surface interactive doit être vérifiée avec :

- navigation clavier complète ;
- focus visible avec le bleu canonique ;
- ordre de tab logique ;
- labels et titres de dialog annoncés ;
- zones live uniquement pour les changements utiles ;
- contrôles d'au moins 44 px sur mobile quand ils sont isolés ;
- contenu long sans débordement ;
- état par défaut, loading, empty, error et success ;
- viewport 390 px ;
- contraste renforcé et reduced motion.

Une erreur doit dire ce qui s'est passé, ce qui a été conservé et l'action suivante. Une empty state doit expliquer pourquoi elle est vide et proposer une action pertinente.

---

## 10. Routes de preview et matrice QA

Toutes les previews sont `noindex`.

| URL | Rôle |
| --- | --- |
| `/preview/redesign?v=6&clean=1` | dernière direction landing dans le lab historique |
| `/preview/processing?v=3` | `SignalTimeline`, direction processing retenue |
| `/preview/processing?v=3&state=loading` | état loading |
| `/preview/processing?v=3&state=error` | état erreur |
| `/preview/processing?v=3&state=long` | attente longue |
| `/preview/journey` | parcours A à Z guidé, sans API ni paiement |
| `/preview/journey?screen=result` | accès direct à un écran canonique |
| `/preview/journey?screen=brief&state=error` | combinaison écran/fixture |
| `/preview/journey?lab=1` | rail complet et sélecteur d'états pour QA |

Écrans acceptés : `login`, `brief`, `source`, `processing`, `result`, `workspace`. `paywall` est réservé au lab et remappé vers `processing` dans le parcours client.

États journey acceptés : `default`, `loading`, `empty`, `error`, `success`.

États processing acceptés : `auto`, `loading`, `processing`, `empty`, `error`, `success`, `long`.

Checklist avant publication d'une modification UI :

1. `npm run typecheck` ;
2. `npm run build` ;
3. parcours clavier ;
4. screenshot landing et surface touchée à 390 px et 1440 px ;
5. reduced motion ;
6. états error/empty/loading ;
7. vérification qu'aucun bleu local ne concurrence `#0071e3` ;
8. vérification qu'aucun CTA de preview ne prétend créer un vrai job ou paiement ;
9. Lighthouse sur `/` pour une modification de hero ou d'asset ;
10. `git diff --check` et staging ciblé — jamais `git add -A` dans un worktree sale.

---

## 11. Performance

Baseline mesurée sur la production Vercel le 2026-08-26 :

| Route | Performance | Accessibility | Best Practices | SEO | LCP | TBT | CLS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | 95 | 100 | 100 | 100 | 2.884 s | 18 ms | 0.000141 |
| `/preview/journey` | 97 | 100 | 100 | 66 | 2.551 s | 32 ms | 0 |

Le SEO de la journey est volontairement bas : la route est `noindex`.

Garde-fous :

- conserver l'image hero en `priority`/`fetchPriority="high"` ;
- garder les frames secondaires en priorité basse ;
- ne pas charger les shaders de lab sur `/` ;
- arrêter les boucles `requestAnimationFrame` hors écran ou à la perte de contexte ;
- préserver le fallback image si WebGL échoue ;
- éviter les animations qui déclenchent layout/paint à chaque frame ;
- mesurer le LCP après toute modification du hero, de l'image principale ou du shader.

---

## 12. Carte des fichiers

| Responsabilité | Fichiers |
| --- | --- |
| tokens globaux | `apps/web/app/globals.css` |
| tokens/chrome produit | `apps/web/app/product.css` |
| landing canonique | `apps/web/app/page.tsx` |
| hero Edit Axis | `apps/web/components/prototypes/redesign/apple-edit-axis.tsx` + `.module.css` |
| shader campagne | `apps/web/components/prototypes/redesign/campaign-lens-shader.tsx` |
| récit landing | `apps/web/components/prototypes/redesign/edit-axis-story.tsx` + `.module.css` |
| parcours A à Z | `apps/web/app/preview/journey/journey-preview.tsx` + `.module.css` |
| processing canonique | `apps/web/components/prototypes/processing/signal-timeline.tsx` + `.module.css` |
| séquence processing | `apps/web/components/prototypes/processing/processing-sequence.ts` |
| paywall désirabilité | `apps/web/components/prototypes/processing/clip-gate.tsx` + `.module.css` |
| paywall production | `apps/web/components/product/paywall-dialog.tsx` + `.module.css` |
| primitives produit | `apps/web/components/product/product-primitives.tsx` |
| primitives accessibles | `apps/web/components/ui/` |
| contraintes machine | `apps/web/.21st/design.json` |
| assets canoniques | `apps/web/public/prototypes/*.webp` et `first-cut-teaser-v1.mp4` |

Les PNG source présents localement servent à la génération/inspection. Les assets web canoniques sont les `.webp` optimisés ; ne pas ajouter les PNG lourds au commit par réflexe.

---

## 13. Workflow recommandé pour le prochain agent

1. Reformuler en une phrase la page, l'audience et la direction visée.
2. Rejouer le parcours canonique avant de modifier un écran isolé.
3. Faire un screenshot de l'état actuel aux viewports concernés.
4. Localiser les tokens et primitives déjà utilisés.
5. Pour un nouveau bloc, suivre l'ordre de recherche du kit et comparer plusieurs candidats avant d'en récupérer un.
6. Adapter la mécanique retenue aux tokens ClipFactory ; supprimer le styling de démonstration.
7. Implémenter aussi les états non heureux et le mobile 390 px.
8. Vérifier visuellement, au clavier, puis par typecheck/build.
9. Mettre à jour ce document et `apps/web/.21st/design.json` si une décision canonique change.
10. Mettre à jour `docs/handoff-codex.md` avec l'état Git, le déploiement et les décisions réellement prises.

---

## 14. Anti-checklist UI

- Ne pas réintroduire l'ancienne DA orange/champagne.
- Ne pas inventer un nouveau bleu dans un module CSS.
- Ne pas transformer le hero en titre centré sur mesh gradient.
- Ne pas mettre trois cartes de features égales pour remplir l'espace.
- Ne pas utiliser le glass sur toutes les surfaces.
- Ne pas montrer un dashboard de métriques avant la première valeur utilisateur.
- Ne pas détacher le clip de son brief, de son timecode et de sa preuve.
- Ne pas faire du paywall une étape numérotée séparée.
- Ne pas afficher un faux pourcentage ou une fausse ETA pendant le traitement.
- Ne pas fabriquer un dialog, des tabs ou un player sans d'abord réutiliser les primitives accessibles existantes.
- Ne pas activer `DitherReveal`, `CursorRingField`, `SourceCut` ou `ProofManuscript` sur la surface canonique sous prétexte qu'ils existent dans le repo.
- Ne pas animer chaque élément au montage ni laisser tourner une boucle décorative infinie.
- Ne pas supprimer les fallbacks WebGL, reduced motion, reduced transparency ou high contrast.
- Ne pas modifier le design sans screenshot 390/1440 et sans avoir parcouru l'écran dans le navigateur.

---

## 15. État de publication au 2026-08-26

- Landing Vercel : `https://clipfactory-saas.vercel.app/`
- Journey QA : `https://clipfactory-saas.vercel.app/preview/journey`
- Déploiement UI publié depuis `redesign/ui-ux-lab` au commit `4d8b50d`.
- `origin/main` reste à `f17e129` : le redesign n'est pas encore mergé dans `main`.
- `clipfactory.app` est encore intercepté par une configuration Cloudflare historique qui sert l'ancienne landing orange. Voir `docs/deploy.md` avant toute modification de domaine.
- Augustin a autorisé le commit et le push ciblés de cette documentation le 2026-08-26. Les fichiers locaux hors périmètre restent exclus.
