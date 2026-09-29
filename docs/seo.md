# SEO ClipFactory — configuration et exploitation

Mise à jour : 8 septembre 2026.

## État vérifié de la publication

Publié et contrôlé le 8 septembre 2026 : déploiement `dpl_Eij1NPuT8pPADkb9gGvWexECmtU3`, statut READY. Audit HTTP/HTML en ligne : 18/18 pages validées, 0 erreur sur les contrôles définis. Captures inspectées à 390 et 1440 px. Les mesures Lighthouse publiques de la version du 6 septembre restent archivées ; les nouvelles mesures portent le suffixe `-refresh`. Voir le rapport pour les scores de la version actuelle.

Le fichier Google préexistant est conservé. Soumission du sitemap dans le compte Google : non effectuée par l’agent, faute de session Google accessible. Rapport : `artifacts/seo/rapport-seo.md`.

## Adresse de référence

Le SaaS utilise **https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app** : cette adresse correspond à la propriété Search Console validée par Augustin. Le domaine est ajouté aux domaines de production du projet Vercel `clipfactory-saas` (`prj_vYB0eqRzdMemio88Ebc4ojyXdl7e`).

Au début de l'intervention, cette adresse était un alias avec `X-Robots-Tag: noindex`. Le rattachement au projet comme domaine de production a retiré ce blocage. `clipfactory.app` sert une autre landing ; il n'est plus utilisé comme adresse canonique du SaaS. Aucun achat de domaine ni changement DNS Cloudflare n'est nécessaire pour ce SEO.

`NEXT_PUBLIC_SITE_URL` est configurée dans Vercel pour Production et Preview. `apps/web/lib/site.ts` normalise cette valeur en origine HTTPS ; son défaut est l'adresse de production ci-dessus. Une adresse temporaire de déploiement ne doit pas remplacer cette valeur.

Le fichier public `apps/web/public/google9773389826078f2e.html` conserve la validation Google déjà réalisée par Augustin. Il doit rester accessible sans connexion ni redirection vers un autre domaine. Les variables facultatives `GOOGLE_SITE_VERIFICATION` et `BING_SITE_VERIFICATION` permettent également une validation par balise HTML, mais elles ne sont pas nécessaires à la validation actuelle par fichier.

## Périmètre livré

- 12 pages publiques existantes avec titres, descriptions, URL canoniques, Open Graph et cartes Twitter propres à chaque page.
- Un index `/guides` et trois guides complets pré-rendus : YouTube vers Shorts, sélection d'extraits de podcast, rédaction du brief de campagne.
- 18 URL publiques dans `/sitemap.xml`, toutes sur la même origine.
- `robots.txt` annonce ce sitemap ; les pages privées restent protégées par l'authentification et/ou `noindex` selon leur rôle.
- `X-Robots-Tag: noindex, nofollow` sur les routes d'application, d'administration, d'authentification, d'API, de connexion et de démonstration. Les pages de connexion et de démonstration restent explorables pour que Google puisse lire `noindex`.
- Les déploiements Preview ont également une métadonnée `noindex` explicite. Ne pas promouvoir un build Preview en production sans reconstruire avec l'environnement Production.
- Une image de partage 1200 × 630 fonctionnelle, avec l'adresse canonique actuelle.
- Données structurées Organization, WebSite, SoftwareApplication, BreadcrumbList, Article et FAQPage uniquement lorsque le contenu correspondant existe. La FAQ de la landing et son JSON-LD utilisent la même source.
- GEO léger et maintenable : l'entité Organization expose ses thèmes réels et l'application expose une liste de fonctionnalités cohérente avec le contenu visible. La route `/llms.txt` fournit un résumé factuel pour les agents qui choisissent de le lire ; ce n'est ni une exigence Google ni une garantie d'apparition dans une réponse générative.
- Aucun avis, note utilisateur, résultat de campagne ou volume de recherche inventé. Les scores illustratifs du produit ne sont pas des avis clients.
- Le comparatif OpusClip cite les fonctionnalités documentées par OpusClip et explicite les limites du pilote ClipFactory. Il ne constitue pas un benchmark de qualité.
- Liens vers le dépôt GitHub privé et le compte social non vérifié retirés du pied de page public. Hiérarchie des titres et contraste du bouton du pied de page corrigés.

## Intentions de recherche

Les regroupements suivants sont des choix éditoriaux, pas des volumes ou difficultés mesurés avec un outil de mots-clés.

| Page | Intention principale | Rôle |
| --- | --- | --- |
| `/` | AI video clipping tool, AI clip maker, long video to shorts | Présentation du produit et du brief de campagne |
| `/features` | AI video clipping features, captions, campaign scoring | Explication de la sélection et de la revue des clips |
| `/pricing` | AI clipping pricing, source-video credits | Offre Starter et limites |
| `/use-cases` | AI clipping use cases | Orientation vers les usages |
| `/use-cases/creators` | AI clipping for creators and podcasters | Usage créateur |
| `/use-cases/agencies` | AI clipping for agencies | Brief et revue pour les clients |
| `/vs/opusclip` | ClipFactory vs OpusClip, OpusClip alternative | Comparaison documentée des workflows |
| `/faq` | sources, crédits, annulation, qualité des clips | Réponses aux questions produit |
| `/about` | ClipFactory, projet, équipe | Identité du projet |
| `/changelog` | ClipFactory updates | Historique produit, sans promesse de gain SEO dû à la fraîcheur |
| `/legal/terms` | ClipFactory terms | Conditions existantes |
| `/legal/privacy` | ClipFactory privacy | Notice existante |
| `/clipping-ia` | clipping IA, outil de clipping vidéo, découpage vidéo IA | Page française complète : définition, méthode, brief et limites du pilote |
| `/clipping-tools` | AI clipping tools, video clipping tools comparison | Comparaison documentée de quatre workflows et grille CSV téléchargeable |
| `/guides` | video clipping guides | Point d'entrée éditorial |
| `/guides/youtube-video-to-shorts` | how to turn a YouTube video into Shorts | Méthode de sélection, cadrage et revue des sous-titres |
| `/guides/podcast-clips-for-social-media` | how to choose podcast clips for social media | Idées complètes, contexte et série de clips |
| `/guides/video-clipping-campaign-brief` | AI video clipping brief | Objectif, audience et exemple de brief adaptable |

La page `/clipping-ia` possède un contenu, une navigation et un pied de page en français, un conteneur `lang=fr`, une métadonnée Open Graph `fr_FR` et un schéma `inLanguage: fr`. Le document racine et le produit restent en anglais ; les liens vers les ressources anglaises sont signalés. Cette page n'est pas une traduction équivalente de l'accueil ou du comparatif : aucun `hreflang` fictif ne les associe. Une future traduction complète de pages équivalentes devra ajouter les liens réciproques appropriés. Google détermine la langue à partir du contenu visible, selon sa documentation sur les sites multilingues.

## Cohérence visuelle des pages publiques

Le chrome reprend la landing canonique Edit Axis : marque à trois lames, navigation flottante, typographie système et actions bleues. `components/marketing/nav.tsx` et `footer.tsx` remplacent les anciens composants ; le pied de page est aussi utilisé par la landing. Le menu mobile se ferme au choix d'un lien ou avec Échap, qui rend le focus au bouton.

`app/marketing.css` applique les tokens du projet aux pages publiques. Les guides et nouvelles pages utilisent une largeur éditoriale, un sommaire latéral sur ordinateur et des lignes de lecture ; aucune dépendance visuelle externe n'a été ajoutée. Les contrôles sont effectués à 390 px et 1440 px. Le tableau comparatif défile horizontalement dans sa propre région accessible au clavier.

## Travail de positionnement et limites

La cible large « clipping » mélange des intentions (vidéo sociale, capture gaming, autres usages). La landing précise désormais « AI video clipping tool » dans son titre SEO. Les pages `/clipping-ia` et `/clipping-tools` traitent deux besoins distincts avec un contenu substantiel. Les trois guides approfondissent les sources et la revue éditoriale. Le pied de page et l'index des guides relient cet ensemble.

Aucun classement, volume de recherche, trafic, backlink ou gain de conversion n'a été inventé. Les comparaisons reflètent les pages officielles d'OpusClip, Vizard et Descript consultées le 7 septembre 2026 ; il ne s'agit pas de tests comparatifs de qualité. La grille CSV disponible sur `/resources/clipping-tools-worksheet.csv` fournit les colonnes à remplir avec ses propres observations.

La documentation Google indique qu'il n'existe pas d'exigence technique ou de balisage GEO spécial pour les AI Overviews et AI Mode : les fondamentaux SEO, le contenu utile visible, l'indexation et la concordance entre données structurées et contenu restent prioritaires. La route `llms.txt` est donc un complément expérimental pour les agents, pas un substitut au sitemap, aux liens internes ou à l'indexation. Elle a été publiée et vérifiée en HTTP 200 sur les deux alias publics le 19 septembre 2026.

La suite se mesure dans Search Console : indexation des pages ciblées, impressions, requêtes, clics, pays et pages d'entrée, en comparant des périodes équivalentes. Un site techniquement accessible ne prouve ni son indexation effective ni sa position. Les démonstrations réelles du produit et les références externes pertinentes pourront ensuite renforcer sa visibilité ; aucun message externe ni achat de lien n'a été effectué.

Sources : [Google — sites multilingues](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites), [Google — guide de démarrage SEO](https://developers.google.com/search/docs/fundamentals/seo-starter-guide), [OpusClip](https://www.opus.pro/clipanything), [Vizard](https://vizard.ai/), [Descript](https://www.descript.com/clips).

## Vérification reproductible

Depuis la racine du dépôt :

```bash
npm ci --prefix apps/web
npm run build --prefix apps/web
npm run start --prefix apps/web -- --hostname 127.0.0.1 --port 3107
```

Puis, dans un autre terminal :

```bash
python3 scripts/seo-audit.py http://127.0.0.1:3107 \
  --canonical-origin https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app \
  --out artifacts/seo/local.json
```

Pour le site public :

```bash
SSL_CERT_FILE=/etc/ssl/cert.pem python3 scripts/seo-audit.py \
  https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app \
  --canonical-origin https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app \
  --out artifacts/seo/production.json
```

`SSL_CERT_FILE` désigne le magasin de certificats système sur ce Mac ; la vérification TLS reste active. Sur un autre système, utiliser son magasin de certificats habituel.

Le script contrôle les codes HTTP, sitemap, canonical, titres/descriptions uniques, H1, langue, balises robots, Open Graph/Twitter, JSON-LD, concordance FAQ/HTML, liens internes, ancres, routes privées/de démonstration, vraies 404, fichier Google et ressources de partage. Il ne prouve ni l'indexation Google, ni le fonctionnement de la chaîne vidéo ou du paiement.

Les captures à 390 px et 1440 px et les rapports Lighthouse sont conservés dans `artifacts/seo`. Les mesures Lighthouse sont des tests de laboratoire ; elles ne remplacent pas les données utilisateurs réelles de Search Console/CrUX.

## Mise en ligne sans perdre la configuration

Le chantier SEO part du code réellement publié de `redesign/ui-ux-lab` : commit UI `4d8b50d`, puis commit documentaire `acd9a61`. Le code de `main` contient une autre version de la landing. Répertoire de travail : `/Users/augustindemeaux/clipfactory-seo`, branche `codex/seo-vercel-2026-09-06`.

Le déploiement CLI se fait depuis la racine, avec le projet Vercel configuré sur `apps/web`. `.vercelignore` exclut les rapports, documents, autres services et variables locales de l'envoi.

```bash
vercel deploy --prod --skip-domain --yes
# Inspecter et contrôler le déploiement préparé avant la promotion.
vercel promote <deployment-url> --yes
```

La promotion doit utiliser un build créé avec `--prod` : il contient la configuration d'indexation de production. Garder le fichier Google dans tout futur déploiement. Les modifications SEO doivent être intégrées au flux Git autorisé avant qu'un déploiement automatique de `main` ne remplace le travail ; aucun commit ou push n'est implicite dans la publication CLI.

## Search Console : après la publication

Propriété : `https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app/`.

1. Dans **Sitemaps**, soumettre `sitemap.xml` et vérifier son statut. La simple présence d'un sitemap dans le site ne signifie pas qu'il a déjà été soumis depuis le compte Google.
2. Dans **Inspection de l'URL**, tester l'accueil en direct et demander son indexation, puis les trois guides. Il n'est pas nécessaire de répéter la demande chaque jour.
3. Lire les exclusions réelles dans **Indexation des pages**. Les pages privées et de démonstration exclues par `noindex` sont attendues ; les pages publiques ne doivent pas l'être.
4. Utiliser **Performances** pour distinguer marque et requêtes génériques, puis comparer impressions, clics, pages d'entrée et inscriptions réellement attribuables à ces visites.

L'accès à la propriété Google dépend de la session du propriétaire. Une URL de console partagée ne donne pas accès au compte dans le navigateur de l'agent. Ne pas déclarer le sitemap soumis ou les pages indexées sans résultat observé dans Search Console.

## Entretien éditorial

Mettre à jour une page lorsqu'une fonctionnalité, une limite ou son explication change. Les dates `lastModified` des guides correspondent à leurs changements éditoriaux ; les pages sans date fiable n'en inventent pas à chaque build. Google ignore les champs de sitemap `priority` et `changefreq`.

Prioriser ensuite les questions issues des utilisateurs et des requêtes observées : problèmes de cadrage, erreurs de sous-titres, utilisation du brief et exemples de clips issus de sources autorisées. Toute étude de cas doit préciser la source, la méthode et les mesures réellement observées. Éviter les séries de pages presque identiques, les promesses de viralité et les faux comparatifs.

## Références

- [Conditions techniques Google](https://developers.google.com/search/docs/essentials/technical)
- [Sitemaps et dates de modification](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Règles des données structurées](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
- [Restrictions des résultats enrichis FAQ](https://developers.google.com/search/blog/2023/08/howto-faq-changes) : le balisage FAQ ne promet pas un résultat enrichi pour un SaaS.
- [Métadonnées Next.js](https://nextjs.org/docs/app/api-reference/functions/generate-metadata)
- [Gestion des versions Vercel et du contenu dupliqué](https://vercel.com/kb/guide/avoiding-duplicate-content-with-vercel-app-urls)
- [OpusClip ClipAnything](https://www.opus.pro/clipanything), [prompts](https://help.opus.pro/docs/article/select-keywords), [éditeur](https://www.opus.pro/ai-video-editor)
