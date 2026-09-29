## Dernière reprise — 12 septembre 2026

Connexion réussie au Chrome normal via MCP. Le sitemap a été relu par Google le **11 septembre** : **18 pages découvertes**, statut **Opération effectuée**.

Nouvelle tentative d'indexation de `/clipping-ia` le 12 septembre : **quota quotidien encore dépassé**, aucune demande acceptée confirmée. La page demeure non indexée dans l'inspection. Aucun contournement ni soumission répétitive supplémentaire n'a été réalisé après ce refus confirmé.

Audit public relancé : **18 pages, aucune erreur**, voir `production-2026-09-12.json`. Le test en ligne de `/clipping-tools` réalisé le 11 septembre avait confirmé **Google a accès à cette URL**, **La page peut être indexée**, et un fil d'Ariane valide. Cela prouve l'accès et l'éligibilité technique de cette page, pas son indexation effective.

Les données de performances citées plus bas restent celles consultées le 11 septembre ; elles n'ont pas été rafraîchies aujourd'hui. La prochaine demande dépend du renouvellement du quota imposé par Google. Aucun suivi automatique programmé.

# ClipFactory — SEO et cohérence UI

État contrôlé le 8 septembre 2026 : **publié en production, 18 pages publiques vérifiées**.

Site : https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app/

Déploiement : `dpl_Eij1NPuT8pPADkb9gGvWexECmtU3`, READY, Production.
Version : https://clipfactory-saas-gn2ozq40n-demeauxa8-1591s-projects.vercel.app/

Le domaine court `https://clipfactory-saas.vercel.app/` sert également cette version. Les canonical restent sur le domaine de la propriété Google validée par Augustin.

## Correction de la cohérence UI

Les anciennes pages marketing affichaient un autre logo, une barre pleine largeur et une hiérarchie typographique différente de la landing Edit Axis. Elles utilisent désormais la marque à trois lames, une navigation flottante et les tokens du projet. Le pied de page est partagé avec la landing.

Les guides ont été recomposés en lignes éditoriales, avec de grands titres et un sommaire latéral sur ordinateur. Sur mobile, le sommaire précède le contenu et le tableau comparatif défile dans son conteneur. Les pages Features, Pricing et les autres pages publiques reprennent la navigation, le pied de page et le style des titres.

Menu mobile vérifié : ouverture, fermeture avec Échap, restitution du focus au bouton, navigation puis fermeture. Captures inspectées à 390 px et 1440 px : guides, article, nouvelles pages, tableau, pied de page, Features et Pricing. Aucun débordement horizontal du document observé sur les surfaces contrôlées. Les derniers titres français et anglais ont aussi été inspectés sur le build Vercel publié.

## Pages et intentions ciblées

| Page | Cible | Contenu |
| --- | --- | --- |
| `/` | AI video clipping tool, clipping vidéo | Titre SEO plus explicite, présentation du produit |
| `/clipping-ia` | clipping IA, outil de clipping vidéo | Page française, définition, méthode, exemple de brief, contrôle des extraits, tarif et limites |
| `/clipping-tools` | AI clipping tools, video clipping tools | Comparaison documentée de ClipFactory, OpusClip, Vizard et Descript, protocole d'évaluation et CSV téléchargeable |
| `/guides` | video clipping guides | Index éditorial et liens vers les contenus ciblés |
| `/guides/youtube-video-to-shorts` | vidéo YouTube vers Shorts | Sélection d'un moment complet, cadrage, sous-titres |
| `/guides/podcast-clips-for-social-media` | podcast clips | Contexte et cohérence d'une série |
| `/guides/video-clipping-campaign-brief` | brief de clipping IA | Public, objectif et exemple adaptable |

La page française possède un contenu et une navigation en français, un conteneur `lang=fr`, un Open Graph `fr_FR` et un schéma `inLanguage: fr`. Le produit et les autres ressources restent en anglais, ce qui est signalé. Aucun lien `hreflang` n'associe artificiellement des pages qui ne sont pas des traductions équivalentes.

La grille `/resources/clipping-tools-worksheet.csv` contient les colonnes d'évaluation à remplir. Aucun résultat de benchmark, avis utilisateur, volume de recherche ou promesse de viralité n'a été inventé. Les descriptions concurrentes renvoient aux pages officielles consultées le 7 septembre 2026.

## Vérification technique

Audit HTTP/HTML après promotion : **18/18 pages valides, 0 erreur sur les contrôles définis**. Vérifications : statuts HTTP, titres et descriptions distincts, canonical, H1, Open Graph, Twitter, JSON-LD, liens internes, ancres, pages privées en noindex, véritables 404 et ressources de partage.

Le fichier `google9773389826078f2e.html` déjà installé par Augustin reste disponible et exact sur les deux domaines. Aucun `X-Robots-Tag: noindex` sur les pages publiques contrôlées. Le sitemap contient 18 URL et est annoncé par `robots.txt`.

Build Vercel et vérification des types réussis. Aucun journal de niveau erreur retourné pour le déploiement dans la fenêtre de 15 minutes contrôlée après publication.

| Mesure Lighthouse mobile | Environnement | Performance | Accessibilité | Bonnes pratiques | SEO |
| --- | --- | ---: | ---: | ---: | ---: |
| Clipping tools | Site public | 96 | 100 | 100 | 100 |
| Clipping IA | Site public | 99 | 100 | 100 | 100 |

Ces scores sont des mesures de laboratoire, pas des positions Google ni une validation des Core Web Vitals terrain. Les anciens rapports du 6 septembre restent archivés et ne sont pas présentés comme les scores de la version actuelle. Le passage local de la page française a donné 99/100/100/100 ; un premier passage public n'a pas produit de mesure à cause d'un délai d'attente du navigateur, puis a été relancé.

## Search Console et positionnement

Vérification directe le 11 septembre 2026, dans le compte connecté via le MCP Chrome :

- `sitemap.xml` est déjà enregistré depuis le 8 septembre, lu le 9 septembre, statut **Opération effectuée**, **18 pages découvertes**. Aucune nouvelle soumission n'était nécessaire. L'agent ne s'attribue pas la soumission initiale.
- L'accueil, `/clipping-ia` et `/clipping-tools` ont été inspectés : **non indexés**, motif « Google ne reconnaît pas cette URL », aucune exploration renseignée. L'inspection individuelle n'affiche pas encore de sitemap référent, malgré les 18 URL reconnues dans le rapport Sitemaps.
- La demande d'indexation de `/clipping-ia` a été tentée puis **refusée : quota quotidien dépassé**. Google demande de réessayer demain. Aucune demande acceptée n'est revendiquée.
- Le rapport global d'indexation est en cours de traitement.
- Rapport Performances Web, filtre trois mois, données affichées du 5 au 8 septembre : **0 clic et 0 impression**, aucune requête. Aucune position mesurable.

Le navigateur n'est plus le blocage. La prochaine action dépend du renouvellement du quota Google : retenter une demande pour les URL prioritaires, puis vérifier l'indexation effective. Aucun suivi automatique n'a été programmé.

Pour mesurer le résultat : consulter les impressions, clics, requêtes, pays et pages d'entrée dans Search Console sur des périodes comparables. Le mot « clipping » est large et ambigu ; la page française et le comparatif répondent à des intentions plus précises. Une première place ne peut être garantie par des modifications de balises ou un nombre de pages.

Sources : [Google — guide SEO](https://developers.google.com/search/docs/fundamentals/seo-starter-guide), [Google — sites multilingues](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites), [OpusClip](https://www.opus.pro/clipanything), [Vizard](https://vizard.ai/), [Descript](https://www.descript.com/clips).

## Reprise et fichiers

- `docs/seo.md` : configuration, architecture, intentions et commandes.
- `artifacts/seo/production-ui-refresh.json` : audit public final.
- `artifacts/seo/production-ui-deployment.json` : identité du déploiement.
- `artifacts/seo/pages.csv` : inventaire actualisé des 18 URL.
- `artifacts/seo/lighthouse-production-*-refresh.json` : mesures de cette version.
- `artifacts/seo/refresh-*.png` : preuves visuelles.
- `artifacts/seo/ui-refresh-interactions.json` : menu, focus et largeurs.
- `artifacts/seo/seo-changes.patch` : patch incluant les nouveaux fichiers source.
- `scripts/seo-audit.py` : contrôles reproductibles.

Répertoire : `/Users/augustindemeaux/clipfactory-seo`.
Branche : `codex/seo-vercel-2026-09-06`, base `acd9a61` de `origin/redesign/ui-ux-lab`.

**Aucun commit ni push Git effectué.** Le dépôt principal est intact. Le chantier doit être intégré au flux Git autorisé pour survivre aux prochains déploiements automatiques : `main` contient encore une autre version de la landing. Le déploiement actuel est complet ; cette intégration constitue le point de maintenance à préserver.

## Reprise autonome — accès Google

Le 11 septembre, après déverrouillage de la session macOS, la connexion au Chrome normal par `chrome-devtools-mcp --autoConnect` a réussi. Les anciens constats de session inaccessible et de sitemap non vérifié sont remplacés par les observations ci-dessus. Le fichier `search-console-follow-up.json` détaille l'état actuel ; `gsc-home-2026-09-11.txt` et `gsc-clipping-tools-2026-09-11.txt` conservent les inspections.

## Extension GEO — 19 septembre 2026

La couche GEO reste volontairement légère et factuelle. Le JSON-LD de l'accueil décrit maintenant les thèmes réels de l'organisation et les fonctionnalités visibles de l'application. Une route publique `/llms.txt` résume l'identité, le fonctionnement, les limites du pilote, les pages importantes et le contact. Elle répond HTTP 200 sur l'URL canonique longue et sur `clipfactory-saas.vercel.app` après promotion du déploiement `dpl_JC9SzHNJ9ByXYcjp86AW7zzaYUgo`.

L'audit public du 19 septembre couvre toujours 18 pages et retourne zéro erreur : `artifacts/seo/production-2026-09-19.json`. Google indique qu'AI Overviews et AI Mode n'ont pas d'exigence GEO ou de fichier machine-readable spécial : l'indexation, les liens internes, le contenu textuel utile et la concordance entre données structurées et contenu visible restent les signaux prioritaires. `llms.txt` est donc un complément pour les agents qui le lisent, sans garantie de citation ou de classement.
