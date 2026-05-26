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
  title: "ClipFactory vs OpusClip — clip series, context and montage",
  description:
    "Compare ClipFactory with OpusClip for turning long videos into a focused series of Shorts, Reels and TikToks. AI clipping with series goals, visual context, explained picks, montage and EU-first processing.",
  keywords: [
    "OpusClip alternative",
    "ClipFactory vs OpusClip",
    "best OpusClip alternative",
    "OpusClip vs Vizard",
    "AI clipping comparison",
    "AI clip maker comparison",
    "YouTube to Shorts AI",
    "campaign-first AI clipping",
    "OpusClip alternative EU",
  ],
  alternates: { canonical: "/vs/opusclip" },
  openGraph: {
    title: "ClipFactory vs OpusClip — AI clip maker for Shorts and Reels",
    description:
      "Side-by-side positioning: basic AI clipping versus explained clip selection with visual context.",
    type: "article",
  },
};

const FAQ = [
  {
    q: "Is ClipFactory a direct replacement for OpusClip?",
    a: "For the core workflow, yes: paste a URL and get vertical clips. The difference is how clips are selected: ClipFactory uses your series goal, audience, the full video and what happens on screen, then explains each pick.",
  },
  {
    q: "Why choose ClipFactory instead of a basic AI clipper?",
    a: "If you only want lots of generic clips, a basic tool may be enough. ClipFactory is for creators, podcasters and agencies who want a smaller series of clips that fit a clear objective.",
  },
  {
    q: "Does ClipFactory have AI B-roll, like OpusClip?",
    a: "Not in V1. The first job is to find the right moments in the source video. B-roll, transitions and AI sound design can come later.",
  },
  {
    q: "Can I import my OpusClip projects?",
    a: "Not yet. You create a simple brief from scratch. It takes about two minutes: audience, series goal, tone and topics to avoid.",
  },
  {
    q: "Where is the data stored?",
    a: "ClipFactory is designed around EU hosting: database in Frankfurt, storage in Europe and video processing in Germany. If data location matters for client work, verify every vendor's current policy before buying.",
  },
];

const ROWS = [
  {
    cf: "Uses your audience, series goal, tone and topics to avoid.",
    op: "Often focused on fast clip volume first. Context varies by product and plan.",
  },
  {
    cf: "Looks across the whole video, so it can connect a setup at minute 2 with a payoff at minute 12.",
    op: "Most clipping tools are strongest on one continuous timestamp.",
  },
  {
    cf: "Explains the score: hook, emotion, visual proof, audience fit and editing difficulty.",
    op: "Scoring is typically simpler and less tied to your audience.",
  },
  {
    cf: "Checks the quote and moment before rendering. Fake moments are dropped.",
    op: "Check the current vendor docs if verification is important for your workflow.",
  },
  {
    cf: "EU-hosted (Frankfurt / Germany). Source deleted after 14 days, clips after 60.",
    op: "Data region and retention depend on vendor policy. Verify before using client footage.",
  },
  {
    cf: "No watermark on any plan.",
    op: "Watermark rules depend on the current plan and promotion.",
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
              Comparison
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              ClipFactory vs OpusClip
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-[var(--color-muted-foreground)]">
              OpusClip made AI clipping popular. ClipFactory is built for creators who
              want fewer random clips and a better series: clips that understand the
              full video, the screen, and the objective.
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
              No affiliation with OpusClip. Always check each vendor&apos;s current docs before buying.
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
                  Each clip explains why it belongs.
                </h2>
                <p className="mt-4 text-[var(--color-muted-foreground)]">
                  No mystery number. Five components, each with a reason. When you tell
                  a client why this clip fits the series and another one does not, you
                  show the breakdown, not a vibe.
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
              Same URL, same long video. Different clip series. Free to start,
              29€/mo once you like the picks.
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
