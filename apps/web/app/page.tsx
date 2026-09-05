import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  Check,
  Eye,
  GitBranch,
  ShieldCheck,
  Target,
  TimerReset,
} from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { Hero } from "@/components/sections/hero";
import { LogoBand } from "@/components/sections/logo-band";
import { ProductShowcase } from "@/components/sections/product-showcase";
import { Pipeline } from "@/components/sections/pipeline";
import { FeatureBento } from "@/components/sections/feature-bento";
import { ScoreOrbit } from "@/components/sections/score-orbit";
import { Comparison } from "@/components/sections/comparison";
import { Pricing } from "@/components/sections/pricing";
import { Faq } from "@/components/sections/faq";
import { FinalCta } from "@/components/sections/final-cta";
import { StickyCta } from "@/components/sections/sticky-cta";
import { MarketingFooter } from "@/components/marketing/footer";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import { BeforeAfter } from "@/components/marketing/before-after";
import { ExampleArc } from "@/components/marketing/example-arc";
import { TrustBar } from "@/components/marketing/trust-bar";
import { StatStrip } from "@/components/marketing/stat-strip";
import { UseCases } from "@/components/marketing/use-cases";
import {
  FaqJsonLd,
  OrganizationJsonLd,
  SoftwareApplicationJsonLd,
} from "@/components/marketing/json-ld";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: `AI clip maker for clip series, Shorts, Reels and TikToks — ${SITE.name}`,
  description:
    "Turn long videos, podcasts, webinars and interviews into a focused series of vertical clips for YouTube Shorts, Instagram Reels and TikTok. AI clipping with full-video context, vision, montage, captions and simple scores.",
  alternates: { canonical: "/" },
  openGraph: {
    title: `${SITE.name} — AI clip maker for Shorts, Reels and TikToks`,
    description: SITE.longDescription,
    url: SITE.url,
    siteName: SITE.name,
    type: "website",
  },
};

const HOME_FAQ: { q: string; a: string }[] = [
  {
    q: "Can I turn a long YouTube video into Shorts with AI?",
    a: "Yes. Paste a YouTube or Vimeo link, tell ClipFactory who the clips are for, and it returns vertical clips with captions for YouTube Shorts, TikTok and Instagram Reels.",
  },
  {
    q: "What makes ClipFactory different from a basic AI clipper?",
    a: "A basic clipper often picks loud sentences. ClipFactory also looks at the full video, what is visible on screen, and the goal of the clip series, then explains why each clip was selected.",
  },
  {
    q: "Does ClipFactory understand what happens on screen?",
    a: "Yes. It checks visual context such as products, faces, actions, reactions and proof on screen. That helps avoid clips that sound good in the transcript but do not work visually.",
  },
  {
    q: "What sources are supported at launch?",
    a: "YouTube and Vimeo URLs. Direct upload comes later, once the first paid workflows are stable.",
  },
  {
    q: "How much does it cost?",
    a: "Starter is 29€/month: 300 credits, up to 30 minutes per video and 3 clips per video. 1 credit = 1 minute of source video. No watermark, EU hosted, cancel anytime.",
  },
  {
    q: "Where is the data processed?",
    a: "ClipFactory is designed around EU hosting: database in Frankfurt, storage in Europe and video processing in Germany. Source videos are deleted after 14 days and rendered clips after 60 days.",
  },
];

export default function HomePage() {
  return (
    <>
      <OrganizationJsonLd />
      <SoftwareApplicationJsonLd />
      <FaqJsonLd items={HOME_FAQ} />
      <MarketingNav />
      <main className="flex-1">
        <Hero />
        <LogoBand />
        <ProductShowcase />
        <Pipeline />
        <FeatureBento />
        <ScoreOrbit />
        <Comparison />
        <Pricing />
        <Faq items={HOME_FAQ} />
        <FinalCta />
      </main>
      <MarketingFooter />
      <StickyCta />
    </>
  );
}
