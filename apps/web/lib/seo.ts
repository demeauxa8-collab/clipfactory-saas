import type { Metadata } from "next";
import { SITE } from "@/lib/site";

export const PUBLIC_PAGES = {
  "/": {
    title: "AI Video Clipping Tool for Shorts, Reels & TikTok",
    description:
      "Turn YouTube and Vimeo videos into vertical clips with captions. Set your campaign audience and goal, then review each cut and the reason it was selected.",
  },
  "/features": {
    title: "AI Video Clipping, Captions & Campaign Scoring",
    description:
      "Explore ClipFactory's campaign briefs, source context, multi-moment edits and captions. Review the selected timestamps and the reason behind each short clip.",
  },
  "/pricing": {
    title: "AI Video Clipping Pricing — Starter €29/month",
    description:
      "Starter includes 300 source-video credits per month for €29. Sources up to 30 minutes, up to 3 requested clips per job, captions and no watermark.",
  },
  "/faq": {
    title: "AI Clipping FAQ — Sources, Credits & Clip Quality",
    description:
      "Answers about ClipFactory's YouTube and Vimeo sources, pricing, video credits, captions, clip quality, cancellation and current pilot limitations.",
  },
  "/about": {
    title: "About ClipFactory — Campaign-Based Video Clipping",
    description:
      "Meet the independent project behind ClipFactory. Learn why campaign briefs, source timestamps and clear editorial reasons shape our approach to AI video clipping.",
  },
  "/changelog": {
    title: "Changelog — ClipFactory Product Updates",
    description:
      "Follow ClipFactory development: campaign briefs, clip selection, captions and the editing workflow. Read the scope and limitations of each product update.",
  },
  "/use-cases": {
    title: "AI Clipping for Creators, Podcasts & Agencies",
    description:
      "Explore ways to turn interviews, video podcasts and webinars into short clips. Plan each series around an audience, a campaign goal and the source material.",
  },
  "/use-cases/creators": {
    title: "AI Video Clipping for Creators & Podcasters",
    description:
      "Create a focused clip series from a YouTube or Vimeo video. Review captioned vertical cuts, source timestamps and editorial reasons before you publish.",
  },
  "/use-cases/agencies": {
    title: "AI Video Clipping for Agencies & Content Teams",
    description:
      "Organize client videos around a campaign brief. Review short clips with captions, source evidence and explained scores, with source-minute pricing.",
  },
  "/vs/opusclip": {
    title: "ClipFactory vs OpusClip — Compare the Workflows",
    description:
      "Compare ClipFactory's campaign-based review workflow with OpusClip's published clipping and editing tools. See the tradeoffs and a practical evaluation checklist.",
  },
  "/legal/terms": {
    title: "Terms of Service",
    description:
      "Read ClipFactory's terms for the pilot service, accounts, source content, subscriptions and acceptable use before creating a campaign.",
  },
  "/legal/privacy": {
    title: "Privacy Notice",
    description:
      "Read how ClipFactory handles account information, source videos and generated clips, including pilot limitations and requests for access or deletion.",
  },
} as const;

export const NO_INDEX: Metadata["robots"] = {
  index: false,
  follow: false,
  googleBot: { index: false, follow: false },
};

export function createPageMetadata(
  path: string,
  title: string,
  description: string,
  article = false,
): Metadata {
  const fullTitle = title.includes(SITE.name)
    ? title
    : `${title} | ${SITE.name}`;
  const url = new URL(path, SITE.url).href;
  return {
    title: { absolute: fullTitle },
    description,
    alternates: { canonical: url },
    openGraph: {
      type: article ? "article" : "website",
      locale: "en_US",
      url,
      title: fullTitle,
      description,
      siteName: SITE.name,
      images: [
        {
          url: `${SITE.url}/opengraph-image`,
          width: 1200,
          height: 630,
          alt: "ClipFactory — AI clip maker for long videos",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
      images: [`${SITE.url}/opengraph-image`],
    },
  };
}

export function pageMetadata(path: keyof typeof PUBLIC_PAGES): Metadata {
  const page = PUBLIC_PAGES[path];
  return createPageMetadata(path, page.title, page.description);
}
