import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { createPageMetadata } from "@/lib/seo";
import { SITE } from "@/lib/site";

const meta = createPageMetadata(
  "/clipping-ia",
  "Clipping IA : vos vidéos en Shorts, Reels et TikTok",
  "ClipFactory transforme vos vidéos YouTube et Vimeo en clips verticaux sous-titrés. Définissez votre campagne, puis choisissez les extraits qui servent votre message.",
);
export const metadata = {
  ...meta,
  openGraph: { ...meta.openGraph, locale: "fr_FR" },
};
const contents = [
  ["definition", "Comprendre le clipping IA"],
  ["workflow", "De la source au clip"],
  ["example", "Un brief concret"],
  ["review", "Valider un extrait"],
  ["pricing", "Tarif et limites"],
  ["questions", "Questions fréquentes"],
];

export default function AIClippingPage() {
  const data = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: "Clipping IA avec ClipFactory",
    inLanguage: "fr",
    url: `${SITE.url}/clipping-ia`,
    description: meta.description,
    about: {
      "@type": "SoftwareApplication",
      name: "ClipFactory",
      applicationCategory: "MultimediaApplication",
      operatingSystem: "Web",
    },
  };
  return (
    <div lang="fr">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(data).replace(/</g, "\\u003c"),
        }}
      />
      <BreadcrumbJsonLd
        items={[
          { name: "ClipFactory", href: "/" },
          { name: "Clipping IA", href: "/clipping-ia" },
        ]}
      />
      <MarketingNav language="fr" />
      <main id="main-content" className="marketing-page">
        <div className="editorial-wrap">
          <header className="editorial-hero">
            <p className="editorial-eyebrow">Clipping IA · ClipFactory</p>
            <h1>
              Clipping IA.
              <br />
              Gardez le sens de la vidéo.
            </h1>
            <p>
              Transformez vos vidéos YouTube et Vimeo en Shorts, Reels et TikTok
              sous-titrés. Donnez une intention à votre campagne, puis revoyez
              les extraits et la raison de chaque sélection.
            </p>
            <div className="editorial-actions">
              <Link
                className="editorial-action"
                href="/login?next=/app/campaigns/new"
              >
                Créer ma campagne <ArrowUpRight size={16} aria-hidden="true" />
              </Link>
              <a className="editorial-text-link" href="#workflow">
                Voir le fonctionnement
              </a>
            </div>
          </header>
          <div className="editorial-grid">
            <nav className="editorial-toc" aria-label="Dans cette page">
              <p>La source reste au centre.</p>
              {contents.map(([id, label]) => (
                <a key={id} href={`#${id}`}>
                  {label}
                </a>
              ))}
            </nav>
            <div className="editorial-body">
              <section id="definition">
                <h2>Qu’est-ce que le clipping IA ?</h2>
                <p>
                  Le clipping vidéo consiste à extraire des passages d’une vidéo
                  longue pour créer des contenus courts. Le clipping IA ajoute
                  une aide à la sélection et à la préparation du montage :
                  repérer un sujet, proposer une coupe, adapter le format et
                  préparer les sous-titres.
                </p>
                <p>
                  Un extrait utile doit rester compréhensible lorsqu’on découvre
                  la vidéo sans avoir vu le reste. Une phrase marquante perd sa
                  valeur si le spectateur ne sait pas de quoi elle parle. Le
                  travail consiste donc à garder assez de contexte pour que le
                  début, la preuve et la conclusion tiennent ensemble.
                </p>
                <p>
                  ClipFactory organise ce travail autour d’un brief de campagne.
                  Vous choisissez un public et un objectif avant de juger les
                  propositions. Un score de sélection aide à examiner un
                  candidat ; il ne prédit pas le nombre de vues.
                </p>
              </section>
              <section id="workflow">
                <h2>De votre vidéo au clip vertical.</h2>
                <ol>
                  <li>
                    <strong>Définissez la campagne.</strong> Précisez le public,
                    le message à faire passer, le ton et les sujets à éviter.
                    Une campagne de démonstration produit ne cherche pas les
                    mêmes moments qu’un récit de fondateur.
                  </li>
                  <li>
                    <strong>Ajoutez la source.</strong> Utilisez une URL YouTube
                    ou Vimeo accessible et une vidéo que vous êtes autorisé à
                    exploiter. Vérifiez sa durée avant de lancer le traitement.
                  </li>
                  <li>
                    <strong>Examinez les propositions.</strong> Comparez
                    l’extrait à son contexte dans la source. Regardez où
                    commence la coupe, ce que l’image montre et pourquoi le
                    passage convient au brief.
                  </li>
                  <li>
                    <strong>Validez le rendu.</strong> Relisez les sous-titres
                    et regardez la vidéo verticale jusqu’à la fin avant de la
                    publier sur la plateforme choisie.
                  </li>
                </ol>
                <p>
                  Ce parcours convient notamment aux interviews, démonstrations
                  et podcasts vidéo. Pour un épisode qui dépasse la durée
                  acceptée, préparez un segment cohérent dans la limite du
                  pilote au lieu de lancer la totalité de l’enregistrement.
                </p>
              </section>
              <section id="example">
                <h2>Un brief précis change ce qu’on cherche.</h2>
                <p>
                  « Fais des clips viraux » donne peu de critères pour choisir.
                  Un brief concret indique ce que le spectateur doit comprendre
                  et ce que la vidéo doit montrer. Voici un exemple de consigne
                  éditoriale, à adapter à votre propre source :
                </p>
                <div className="editorial-note">
                  <p>
                    <strong>Public :</strong> les responsables de petites
                    équipes de création.
                  </p>
                  <p>
                    <strong>Objectif :</strong> montrer comment un brief évite
                    les allers-retours de montage.
                  </p>
                  <p>
                    <strong>À chercher :</strong> une difficulté précise, une
                    démonstration à l’écran et une conclusion compréhensible
                    seule.
                  </p>
                  <p>
                    <strong>À éviter :</strong> la présentation générale de
                    l’entreprise et les promesses sans preuve dans la vidéo.
                  </p>
                </div>
                <p>
                  On peut ensuite écarter un passage spectaculaire qui ne répond
                  pas à ce besoin. Le bon extrait est celui qui porte le message
                  avec assez de contexte et une image pertinente, même s’il
                  n’est pas le moment le plus bruyant de la source.
                </p>
              </section>
              <section id="review">
                <h2>Avant de publier, vérifiez le sens.</h2>
                <ul>
                  <li>
                    <strong>Le début :</strong> comprend-on le sujet dès les
                    premières phrases, sans un pronom qui renvoie à une scène
                    absente ?
                  </li>
                  <li>
                    <strong>La coupe :</strong> les conditions, réserves et
                    négations du locuteur sont-elles conservées ?
                  </li>
                  <li>
                    <strong>Le cadrage :</strong> le visage, le produit ou la
                    preuve restent-ils visibles en vertical ?
                  </li>
                  <li>
                    <strong>Les sous-titres :</strong> les noms propres, les
                    chiffres et les termes métier correspondent-ils à l’audio ?
                  </li>
                  <li>
                    <strong>La fin :</strong> l’idée se termine-t-elle vraiment,
                    sans une phrase interrompue ou une conclusion ajoutée par le
                    montage ?
                  </li>
                </ul>
                <p>
                  Pour comparer deux propositions, regardez-les sans le reste de
                  la vidéo. Si l’une demande une longue explication avant d’être
                  comprise, reprenez les limites de l’extrait ou choisissez un
                  autre moment.
                </p>
              </section>
              <section id="pricing">
                <h2>Un pilote avec des limites claires.</h2>
                <p>
                  Le forfait Starter est proposé à{" "}
                  <strong>29 € par mois pour 300 crédits</strong>. Un crédit
                  correspond à une minute de vidéo source. Le pilote accepte les
                  sources jusqu’à 30 minutes et jusqu’à 3 clips demandés par
                  traitement, avec sous-titres et sans filigrane.
                </p>
                <p>
                  Par exemple, une source de 20 minutes représente 20 crédits.
                  Trois traitements de cette durée représentent 60 crédits de
                  source. Le nombre de clips exploitables dépend du contenu et
                  des contrôles de qualité ; demander trois clips ne garantit
                  pas trois bons moments.
                </p>
                <p>
                  Consultez les{" "}
                  <Link href="/pricing">conditions du forfait en anglais</Link>{" "}
                  avant de vous abonner. L’interface de création de campagne est
                  actuellement en anglais. Cette page présente le fonctionnement
                  en français.
                </p>
              </section>
              <section id="questions">
                <h2>Questions sur le clipping IA.</h2>
                <h3>Quelle différence avec un logiciel de montage ?</h3>
                <p>
                  Un éditeur classique vous donne une timeline pour construire
                  manuellement le montage. Un outil de clipping IA vous aide à
                  trouver et préparer des extraits à partir d’une source longue.
                  Le choix dépend du travail à automatiser et du contrôle
                  nécessaire sur chaque coupe.
                </p>
                <h3>Le clipping IA garantit-il des vues ?</h3>
                <p>
                  Non. Le sujet, le public, le compte qui publie et la réception
                  réelle du contenu influencent le résultat. Un score éditorial
                  sert à comparer les propositions, pas à garantir la viralité.
                </p>
                <h3>Peut-on utiliser n’importe quelle vidéo YouTube ?</h3>
                <p>
                  La disponibilité d’un lien ne remplace pas l’autorisation
                  d’exploiter son contenu. Utilisez vos propres sources ou
                  celles pour lesquelles vous disposez des autorisations
                  nécessaires. Une vidéo privée ou inaccessible peut également
                  empêcher le traitement.
                </p>
                <h3>Comment choisir un outil de clipping ?</h3>
                <p>
                  Comparez les outils avec la même source et le même objectif.
                  Mesurez les corrections nécessaires, la qualité des
                  sous-titres, le respect du contexte et le coût des minutes
                  traitées. Notre{" "}
                  <Link href="/clipping-tools">
                    guide des clipping tools en anglais
                  </Link>{" "}
                  propose une grille de comparaison et des liens vers les
                  documentations des éditeurs.
                </p>
                <div className="editorial-actions">
                  <Link
                    className="editorial-action"
                    href="/login?next=/app/campaigns/new"
                  >
                    Préparer ma première campagne{" "}
                    <ArrowUpRight size={16} aria-hidden="true" />
                  </Link>
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>
      <MarketingFooter language="fr" />
    </div>
  );
}
