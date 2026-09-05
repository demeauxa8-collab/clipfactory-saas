import type { Metadata } from "next";

import {
  FaqJsonLd,
  OrganizationJsonLd,
  SoftwareApplicationJsonLd,
} from "@/components/marketing/json-ld";
import { AppleEditAxis } from "@/components/prototypes/redesign/apple-edit-axis";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: `AI clip maker for clip series, Shorts, Reels and TikToks — ${SITE.name}`,
  description:
    "Turn long videos, podcasts, webinars and interviews into campaign-shaped vertical clips with transcript-grounded evidence, visual context and clear editorial reasoning.",
  alternates: { canonical: "/" },
  openGraph: {
    title: `${SITE.name} — Find the cut the story was hiding`,
    description: SITE.longDescription,
    url: SITE.url,
    siteName: SITE.name,
    type: "website",
  },
};

const HOME_FAQ = [
  {
    q: "Can I turn a long YouTube video into Shorts with AI?",
    a: "Yes. Paste a YouTube or Vimeo link, define the campaign audience and goal, and ClipFactory returns vertical clips with captions and an editorial rationale.",
  },
  {
    q: "What makes ClipFactory different from a basic AI clipper?",
    a: "ClipFactory maps the whole source, checks what is visible, anchors the selected words to transcript timestamps and ranks each moment against your campaign brief.",
  },
  {
    q: "What sources are supported at launch?",
    a: "Public or accessible YouTube and Vimeo URLs. Direct file upload is not part of the current offer.",
  },
  {
    q: "How much does it cost?",
    a: "Starter is 29 euros per month and includes 300 credits, sources up to 30 minutes and up to three requested clips per source.",
  },
];

export default function HomePage() {
  return (
    <>
      <OrganizationJsonLd />
      <SoftwareApplicationJsonLd />
      <FaqJsonLd items={HOME_FAQ} />
      <AppleEditAxis />
    </>
  );
}
