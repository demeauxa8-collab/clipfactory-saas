import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Lightbulb,
  ListChecks,
  Mic,
  Sparkles,
  Timer,
} from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import { ExampleArc } from "@/components/marketing/example-arc";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "AI clipping for creators and podcasters — turn episodes into Shorts",
  description:
    "Turn long YouTube videos, podcasts, interviews and webinars into Shorts, Reels and TikToks with AI clipping, captions, simple scores and no watermark.",
  keywords: [
    "AI clipping for creators",
    "AI clipping for podcasters",
    "YouTube to Shorts AI",
    "podcast to TikTok AI",
    "long video to vertical shorts",
    "EU AI clipping",
  ],
  alternates: { canonical: "/use-cases/creators" },
};

const STORY = [
  {
    icon: Timer,
    title: "Monday: your long video goes live",
    body: "Your podcast, interview or vlog is on YouTube. It is too long to clip by hand every week.",
  },
  {
    icon: ListChecks,
    title: "Same Monday: you give a simple brief",
    body: "Tell ClipFactory your audience, tone, goal and topics to avoid. It takes about two minutes.",
  },
  {
    icon: Sparkles,
    title: "Tuesday morning: 3 clips to review",
    body: "You get vertical clips with captions, timestamps, a score and a short reason for each pick.",
  },
];

const WHY = [
  "Solo creators do not have time to sort ten generic clips.",
  "Audiences smell a generic clip from a mile away.",
  "Your hook has more weight than your length — clipping is the new headline.",
  "If you cannot understand why the AI picked a clip, you cannot improve the next batch.",
];

export default function CreatorsUseCasePage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Use cases", href: "/use-cases/creators" },
          { name: "For creators", href: "/use-cases/creators" },
        ]}
      />
      <MarketingNav />
      <main id="main-content" className="flex-1">
        {/* Hero */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-3 py-1 text-xs font-medium text-[var(--color-brand)]">
              <Lightbulb className="h-3.5 w-3.5" />
              For solo creators &amp; podcasters
            </div>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              Turn long videos and podcasts into Shorts, Reels and TikToks.
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-[var(--color-muted-foreground)]">
              Paste a YouTube or Vimeo link. ClipFactory finds strong moments,
              adds captions, and explains why each short was selected.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/login">
                <Button size="lg">
                  Try it on your last episode
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/pricing">
                <Button size="lg" variant="secondary">
                  See pricing
                </Button>
              </Link>
            </div>
          </Container>
        </section>

        {/* Story timeline */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              How it fits your week
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              From upload to publish in 24 hours.
            </h2>
            <ol className="mt-12 grid gap-6 md:grid-cols-3">
              {STORY.map((s, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6"
                >
                  <s.icon className="h-5 w-5 text-[var(--color-brand)]" />
                  <h3 className="mt-4 text-base font-medium">{s.title}</h3>
                  <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
                    {s.body}
                  </p>
                </li>
              ))}
            </ol>
          </Container>
        </section>

        {/* Example */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                A clip most basic tools miss
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Setup at minute 2. Payoff at minute 12.
              </h2>
            </div>
            <div className="mt-10">
              <ExampleArc />
            </div>
          </Container>
        </section>

        {/* Why */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-3xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Why solo creators choose this
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Four reasons we hear most.
            </h2>
            <ul className="mt-8 space-y-4">
              {WHY.map((w, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-5 text-sm"
                  dangerouslySetInnerHTML={{ __html: w }}
                />
              ))}
            </ul>
          </Container>
        </section>

        {/* Output preview */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="grid items-center gap-12 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                  What you publish
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  A clip your audience recognises as yours.
                </h2>
                <p className="mt-4 text-[var(--color-muted-foreground)]">
                  Vertical 1080×1920, captions included, no watermark. The score
                  tells you whether the clip fits your audience and goal.
                </p>
                <Link href="/login" className="mt-6 inline-flex">
                  <Button>
                    Start clipping
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
              <ClipMockup
                title="The morning routine that actually changed my life"
                hook="And it has nothing to do with cold showers."
                total={90}
                duration="0:38"
                scores={[
                  { label: "Hook", value: 94 },
                  { label: "Emotion", value: 86 },
                  { label: "Visual", value: 90 },
                  { label: "Fit", value: 92 },
                  { label: "Editing", value: 82 },
                ]}
              />
            </div>
          </Container>
        </section>

        {/* CTA */}
        <section>
          <Container className="max-w-3xl py-20 text-center">
            <Mic className="mx-auto h-6 w-6 text-[var(--color-brand)]" />
            <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">
              Built for your next episode.
            </h2>
            <p className="mt-3 text-[var(--color-muted-foreground)]">
              Paste your latest long video, give a simple brief, and see what
              ClipFactory finds.
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
