import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { GUIDES } from "@/lib/guides";
import { createPageMetadata } from "@/lib/seo";
import type { Route } from "next";

export const metadata = createPageMetadata(
  "/guides",
  "Video Clipping Guides for Creators & Agencies",
  "Practical guides to turning YouTube videos and podcasts into short clips. Choose complete moments, review captions and write a useful campaign brief.",
);

export default function GuidesPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Clipping guides", href: "/guides" },
        ]}
      />
      <MarketingNav />
      <main id="main-content" className="marketing-page">
        <div className="editorial-wrap">
          <header className="editorial-hero">
            <p className="editorial-eyebrow">The editing notebook</p>
            <h1>
              Good clips start
              <br />
              before the cut.
            </h1>
            <p>
              Practical video clipping guides. Find the complete thought, keep
              the source in view, and give every short a reason to exist.
            </p>
          </header>
          <div className="editorial-rows">
            {GUIDES.map((guide, index) => (
              <Link
                key={guide.slug}
                href={`/guides/${guide.slug}` as Route}
                className="editorial-row"
              >
                <span className="editorial-row-label">
                  0{index + 1} / {guide.category}
                </span>
                <div>
                  <h2>{guide.title}</h2>
                  <p>{guide.description}</p>
                </div>
                <ArrowUpRight size={20} aria-hidden="true" />
              </Link>
            ))}
          </div>
          <div className="editorial-actions">
            <Link className="editorial-action" href="/clipping-tools">
              Choose a clipping tool{" "}
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
            <Link className="editorial-text-link" href="/clipping-ia" lang="fr">
              Découvrir le clipping IA en français
            </Link>
          </div>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
