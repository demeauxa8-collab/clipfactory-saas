import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  const pages = [
    { url: "/", priority: 1.0, changeFrequency: "weekly" as const },
    { url: "/features", priority: 0.9, changeFrequency: "monthly" as const },
    { url: "/pricing", priority: 0.9, changeFrequency: "monthly" as const },
    { url: "/vs/opusclip", priority: 0.9, changeFrequency: "monthly" as const },
    { url: "/use-cases", priority: 0.8, changeFrequency: "monthly" as const },
    { url: "/use-cases/creators", priority: 0.8, changeFrequency: "monthly" as const },
    { url: "/use-cases/agencies", priority: 0.8, changeFrequency: "monthly" as const },
    { url: "/faq", priority: 0.7, changeFrequency: "monthly" as const },
    { url: "/about", priority: 0.6, changeFrequency: "monthly" as const },
    { url: "/changelog", priority: 0.5, changeFrequency: "weekly" as const },
    { url: "/legal/terms", priority: 0.3, changeFrequency: "yearly" as const },
    { url: "/legal/privacy", priority: 0.3, changeFrequency: "yearly" as const },
  ];
  return pages.map((p) => ({
    url: `${SITE.url}${p.url}`,
    lastModified,
    changeFrequency: p.changeFrequency,
    priority: p.priority,
  }));
}
