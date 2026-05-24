import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, X } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { ComparisonTable } from "@/components/marketing/comparison-table";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import {
  BreadcrumbJsonLd,
  FaqJsonLd,
} from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "ClipFactory vs OpusClip — campaign-first AI clipping",
  description:
    "Honest comparison: ClipFactory reads your campaign brief, finds story arcs across distant moments, and ships explained scores. OpusClip ranks loud transcript moments and returns one virality number. Same input, different rules.",
  keywords: [
    "OpusClip alternative",
    "ClipFactory vs OpusClip",
    "best OpusClip alternative",
    "OpusClip vs Vizard",
    "AI clipping comparison",
    "campaign-first AI clipping",
    "OpusClip alternative EU",
  ],
  alternates: { canonical: "/vs/opusclip" },
  openGraph: {
    title: "ClipFactory vs OpusClip — campaign-first AI clipping",
    description:
      "Side-by-side: OpusClip ranks transcript moments, ClipFactory reads your brief and finds story arcs. Honest comparison, last updated May 2026.",
    type: "article",
  },
};

const FAQ = [
  {
    q: "Is ClipFactory a direct replacement for OpusClip?",
    a: "For solo creators and agencies who clip long-form into vertical shorts, yes. The workflow is the same: paste a URL, get vertical clips with captions. The difference is upstream — we let you brief the campaign and we explain every score component.",
  },
  {
    q: "Why is ClipFactory more expensive at entry?",
    a: "OpusClip starts at $19/mo with a watermark, ClipFactory starts at 29€/mo without one. We don't sell volume — we sell campaign-fit selection. If you want generic volume, OpusClip is fine.",
  },
  {
    q: "Does ClipFactory have AI B-roll, like OpusClip?",
    a: "Not in V1. We deliberately focus on the selection problem first: getting the right windows of the source. B-roll, transitions and AI sound design come once selection is rock solid.",
  },
  {
    q: "Can I import my OpusClip campaigns?",
    a: "Not yet. Campaign briefs are written from scratch — it's a 2-minute form. Most users find the framing exercise valuable on its own.",
  },
  {
    q: "Where is the data stored?",
    a: "ClipFactory is EU-hosted (Supabase Frankfurt, Cloudflare R2 EU, Hetzner Germany). OpusClip is US-hosted. If GDPR is a procurement constraint for you, that may matter.",
  },
];

const ROWS = [
  {
    cf: "Reads a campaign brief (audience, niche, tone, goal, avoid topics).",
    op: "Ranks loud transcript moments. No campaign awareness.",
  },
  {
    cf: "Maps the whole video, then finds story arcs across distant moments — setup at minute 2, payoff at minute 12.",
    op: "Picks single-window clips inside one segment of the source.",
  },
  {
    cf: "Returns 5 score components per clip: hook, emotion, visual proof, campaign fit, editing difficulty — with reasons.",
    op: "Returns one 'virality' number per clip.",
  },
  {
    cf: "Runs a transcript anti-hallucination check before render. Hallucinated moments are dropped.",
    op: "No published anti-hallucination step.",
  },
  {
    cf: "EU-hosted (Frankfurt / Germany). Source deleted after 14 days, clips after 60.",
    op: "US-hosted.",
  },
  {
    cf: "No watermark on any plan.",
    op: "Watermark on the free plan.",
  },
];

export default function VsOpusClipPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "ClipFactory vs OpusClip", href: "/vs/opusclip" },
        ]}
      />
      <FaqJsonLd items={FAQ} />
      <MarketingNav />
      <main className="flex-1">
        {/* Hero */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Comparison · last updated May 2026
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              ClipFactory vs OpusClip
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-[var(--color-muted-foreground)]">
              If OpusClip ranks loud moments and ships a virality number, ClipFactory reads your
              campaign brief and ships clips with five explained scores. Same workflow, different
              rules.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/login">
                <Button size="lg">
                  Try ClipFactory
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/pricing">
                <Button size="lg" variant="secondary">
                  See pricing
                </Button>
              </Link>
            </div>
            <p className="mt-3 text-xs text-[var(--color-muted-foreground)]">
              No affiliation with OpusClip — comparison built from their public docs.
            </p>
          </Container>
        </section>

        {/* Comparison table — reusable */}
        <ComparisonTable />

        {/* Side-by-side detail */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              In plain words
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Six things we do differently.
            </h2>
            <ol className="mt-12 space-y-6">
              {ROWS.map((r, i) => (
                <li
                  key={i}
                  className="grid gap-4 rounded-lg border border-[var(--color-border)] p-6 md:grid-cols-2"
                >
                  <div className="rounded-md border-l-4 border-[var(--color-brand)] bg-[var(--color-brand-soft)]/30 p-4">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                      <Check className="h-4 w-4" /> ClipFactory
                    </div>
                    <p className="text-sm">{r.cf}</p>
                  </div>
                  <div className="rounded-md border-l-4 border-[var(--color-border)] bg-[var(--color-muted)] p-4">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
                      <X className="h-4 w-4" /> OpusClip
                    </div>
                    <p className="text-sm text-[var(--color-muted-foreground)]">{r.op}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Container>
        </section>

        {/* Output mockup */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <div className="grid items-center gap-12 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                  What you ship
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  Each clip explains itself.
                </h2>
                <p className="mt-4 text-[var(--color-muted-foreground)]">
                  No mystery number. Five components, each with a reason. When you tell a client a
                  clip didn&apos;t make it, you show the breakdown — not a vibe.
                </p>
                <Link href="/features" className="mt-6 inline-flex">
                  <Button variant="secondary">
                    See the full feature list
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
              <ClipMockup
                title="The reframe that doubled their close rate"
                hook="They didn't change the offer. They changed the question."
                total={89}
                segments={[
                  { role: "setup", range: "03:42 → 04:05" },
                  { role: "payoff", range: "16:20 → 16:48" },
                ]}
                scores={[
                  { label: "Hook", value: 92 },
                  { label: "Emotion", value: 85 },
                  { label: "Visual", value: 87 },
                  { label: "Fit", value: 94 },
                  { label: "Editing", value: 80 },
                ]}
              />
            </div>
          </Container>
        </section>

        {/* FAQ */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-3xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              FAQ
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Honest answers about switching.
            </h2>
            <dl className="mt-10 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
              {FAQ.map((item) => (
                <div key={item.q} className="py-6">
                  <dt className="text-base font-medium">{item.q}</dt>
                  <dd className="mt-2 text-sm text-[var(--color-muted-foreground)]">{item.a}</dd>
                </div>
              ))}
            </dl>
          </Container>
        </section>

        {/* CTA */}
        <section>
          <Container className="max-w-3xl py-20 text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Try it on the same video you&apos;d ship to OpusClip.
            </h2>
            <p className="mt-3 text-[var(--color-muted-foreground)]">
              Same URL, same length. Different selection logic. Free to start, 29€/mo once you
              like the picks.
            </p>
            <Link href="/login" className="mt-8 inline-flex">
              <Button size="lg">
                Start clipping
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </Container>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
