import Link from "next/link";
import { notFound } from "next/navigation";
import type { Route } from "next";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { GUIDES } from "@/lib/guides";
import { SITE } from "@/lib/site";
import { createPageMetadata } from "@/lib/seo";

export const dynamicParams = false;
export function generateStaticParams() {
  return GUIDES.map(({ slug }) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const guide = GUIDES.find((item) => item.slug === slug);
  if (!guide) notFound();
  return createPageMetadata(
    `/guides/${guide.slug}`,
    guide.title,
    guide.description,
    true,
  );
}

export default async function GuidePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const guide = GUIDES.find((item) => item.slug === slug);
  if (!guide) notFound();
  const url = `${SITE.url}/guides/${guide.slug}`;
  const data = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: guide.title,
    description: guide.description,
    mainEntityOfPage: url,
    datePublished: guide.updatedAt,
    dateModified: guide.updatedAt,
    inLanguage: "en",
    author: {
      "@type": "Organization",
      name: "ClipFactory",
      url: `${SITE.url}/about`,
    },
    publisher: { "@type": "Organization", name: SITE.name, url: SITE.url },
  };
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(data).replace(/</g, "\\u003c"),
        }}
      />
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Clipping guides", href: "/guides" },
          { name: guide.title, href: `/guides/${guide.slug}` },
        ]}
      />
      <MarketingNav />
      <main id="main-content" className="marketing-page flex-1">
        <div className="editorial-wrap">
          <nav
            aria-label="Breadcrumb"
            className="text-sm text-[var(--color-muted-foreground)]"
          >
            <Link href="/guides" className="underline underline-offset-4">
              Clipping guides
            </Link>
            <span aria-hidden="true"> / </span>
            {guide.category}
          </nav>
          <article>
            <header className="editorial-hero mt-8">
              <h1 className="text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
                {guide.title}
              </h1>
              <p className="!text-sm text-[var(--color-muted-foreground)]">
                By{" "}
                <Link className="underline underline-offset-4" href="/about">
                  ClipFactory
                </Link>{" "}
                · Updated{" "}
                <time dateTime={guide.updatedAt}>6 September 2026</time>
              </p>
              <p className="mt-8 text-lg leading-relaxed">{guide.intro}</p>
            </header>
            <div className="editorial-grid">
              <nav aria-label="In this guide" className="editorial-toc">
                <p className="text-sm font-semibold">In this guide</p>
                <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm text-[var(--color-muted-foreground)]">
                  {guide.sections.map((section, index) => (
                    <li key={section.title}>
                      <a
                        className="underline underline-offset-4 hover:text-[var(--color-foreground)]"
                        href={`#section-${index + 1}`}
                      >
                        {section.title}
                      </a>
                    </li>
                  ))}
                </ol>
              </nav>
              <div className="editorial-body">
                {guide.sections.map((section, index) => (
                  <section
                    key={section.title}
                    id={`section-${index + 1}`}
                    className="scroll-mt-24"
                  >
                    <h2 className="text-2xl font-semibold leading-tight">
                      {section.title}
                    </h2>
                    {section.paragraphs.map((paragraph) => (
                      <p
                        key={paragraph}
                        className="mt-5 leading-relaxed text-[var(--color-muted-foreground)]"
                      >
                        {paragraph}
                      </p>
                    ))}
                    {section.checklist && (
                      <ul className="mt-6 list-disc space-y-3 pl-5 leading-relaxed">
                        {section.checklist.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    )}
                  </section>
                ))}
              </div>
            </div>
          </article>
          <aside
            aria-label="Related guides and product information"
            className="mt-12 border-t border-[var(--color-border)] pt-8"
          >
            <h2 className="text-xl font-semibold">Continue with your source</h2>
            <ul className="mt-5 space-y-3">
              {guide.related.map((link) => (
                <li key={link.href}>
                  <Link
                    className="underline underline-offset-4"
                    href={link.href as Route}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
