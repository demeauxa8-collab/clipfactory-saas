import { SITE } from "@/lib/site";

export function OrganizationJsonLd() {
  const data = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE.name,
    url: SITE.url,
    "@id": `${SITE.url}/#organization`,
    logo: `${SITE.url}/icon.svg`,
    founder: { "@type": "Person", name: SITE.founder },
    description: SITE.longDescription,
    knowsAbout: [
      "AI video clipping",
      "short-form video repurposing",
      "YouTube to Shorts",
      "podcast clips",
      "campaign-based editing",
      "captioned vertical video",
    ],
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "customer support",
        email: SITE.contactEmail,
      },
    ],
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}

export function SoftwareApplicationJsonLd() {
  const data = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${SITE.url}/#software`,
    url: SITE.url,
    name: SITE.name,
    applicationCategory: "MultimediaApplication",
    applicationSubCategory: "AI video clipping tool",
    operatingSystem: "Web",
    description: SITE.longDescription,
    featureList: [
      "Campaign brief with audience and objective",
      "AI-assisted selection of moments from long videos",
      "Source timestamps and editorial reasons",
      "Captioned vertical clips for Shorts, Reels and TikTok",
    ],
    creator: { "@id": `${SITE.url}/#organization` },
    offers: {
      "@type": "Offer",
      price: SITE.pricingFromEur.toString(),
      priceCurrency: "EUR",
      url: `${SITE.url}/pricing`,
      description: "Starter monthly subscription: 300 source-video credits.",
    },
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}

export function FaqJsonLd({ items }: { items: { q: string; a: string }[] }) {
  const data = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((i) => ({
      "@type": "Question",
      name: i.q,
      acceptedAnswer: { "@type": "Answer", text: i.a },
    })),
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}

export function BreadcrumbJsonLd({
  items,
}: {
  items: { name: string; href: string }[];
}) {
  const data = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, idx) => ({
      "@type": "ListItem",
      position: idx + 1,
      name: it.name,
      item: `${SITE.url}${it.href}`,
    })),
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}

export function WebsiteJsonLd() {
  const data = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE.url}/#website`,
    url: SITE.url,
    name: SITE.name,
    inLanguage: "en",
    publisher: { "@id": `${SITE.url}/#organization` },
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(data).replace(/</g, "\\u003c"),
      }}
    />
  );
}
