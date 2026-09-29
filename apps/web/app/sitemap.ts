import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";
import { PUBLIC_PAGES } from "@/lib/seo";
import { GUIDES } from "@/lib/guides";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    ...Object.keys(PUBLIC_PAGES).map((path) => ({
      url: new URL(path, SITE.url).href,
    })),
    { url: `${SITE.url}/guides` },
    { url: `${SITE.url}/clipping-ia`, lastModified: "2026-09-07" },
    { url: `${SITE.url}/clipping-tools`, lastModified: "2026-09-27" },
    ...GUIDES.map((guide) => ({
      url: `${SITE.url}/guides/${guide.slug}`,
      lastModified: guide.updatedAt,
    })),
  ];
}
