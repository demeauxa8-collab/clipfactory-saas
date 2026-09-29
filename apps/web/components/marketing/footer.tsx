import Link from "next/link";
import type { Route } from "next";
import { MarketingBrand } from "./brand";
import { SITE } from "@/lib/site";

export function MarketingFooter({
  language = "en",
}: {
  language?: "en" | "fr";
}) {
  const fr = language === "fr";
  const groups = fr
    ? [
        {
          title: "Clipping IA",
          links: [
            ["/clipping-ia#workflow", "Fonctionnement"],
            ["/clipping-ia#pricing", "Tarif et limites"],
            ["/clipping-ia#questions", "Questions fréquentes"],
          ],
        },
        {
          title: "Ressources en anglais",
          links: [
            ["/guides", "Guides de clipping"],
            ["/clipping-tools", "Comparer les outils"],
            ["/vs/opusclip", "ClipFactory et OpusClip"],
          ],
        },
        {
          title: "ClipFactory",
          links: [
            ["/about", "À propos (EN)"],
            ["/legal/terms", "Conditions (EN)"],
            ["/legal/privacy", "Confidentialité (EN)"],
          ],
        },
      ]
    : [
        {
          title: "Product",
          links: [
            ["/features", "Features"],
            ["/pricing", "Pricing"],
            ["/use-cases", "Use cases"],
            ["/faq", "FAQ"],
          ],
        },
        {
          title: "Learn",
          links: [
            ["/guides", "Clipping guides"],
            ["/clipping-tools", "Clipping tools"],
            ["/vs/opusclip", "Compare OpusClip"],
            ["/clipping-ia", "Clipping IA · Français"],
          ],
        },
        {
          title: "Company",
          links: [
            ["/about", "About"],
            ["/changelog", "Changelog"],
            ["/legal/terms", "Terms"],
            ["/legal/privacy", "Privacy"],
          ],
        },
      ];
  return (
    <footer className="marketing-footer" lang={language}>
      <div className="marketing-footer-inner">
        <div>
          <MarketingBrand />
          <p>
            {fr
              ? "La source, le brief et chaque coupe.\nToute l’histoire reste liée."
              : "The source. The brief. Every cut.\nThe whole story, kept in sync."}
          </p>
          <a href={`mailto:${SITE.contactEmail}`}>
            {fr ? "Nous contacter" : "Get in touch"}
          </a>
        </div>
        <nav
          aria-label={fr ? "Pied de page" : "Footer navigation"}
          className="marketing-footer-links"
        >
          {groups.map((group) => (
            <div key={group.title}>
              <h2>{group.title}</h2>
              {group.links.map(([href, label]) => (
                <Link key={href} href={href as Route}>
                  {label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
      </div>
      <div className="marketing-footer-bottom">
        <span>© {new Date().getFullYear()} ClipFactory</span>
        <span>{fr ? "Conçu en France." : "Made in France."}</span>
      </div>
    </footer>
  );
}
