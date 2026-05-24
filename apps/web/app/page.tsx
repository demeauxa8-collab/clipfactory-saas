import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  Check,
  Eye,
  GitBranch,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { PublicStats } from "@/components/marketing/public-stats";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import { PipelineDiagram } from "@/components/marketing/pipeline-diagram";
import { BeforeAfter } from "@/components/marketing/before-after";
import { ExampleArc } from "@/components/marketing/example-arc";
import {
  FaqJsonLd,
  OrganizationJsonLd,
  SoftwareApplicationJsonLd,
} from "@/components/marketing/json-ld";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: `AI clipping that fits your campaign — ${SITE.name}`,
  description:
    "Turn long videos into vertical shorts that match your audience — not random viral picks. Story arcs across the whole video, scores you can argue with, EU hosted.",
  alternates: { canonical: "/" },
  openGraph: {
    title: `${SITE.name} — Campaign-first AI clipping`,
    description: SITE.longDescription,
    url: SITE.url,
    siteName: SITE.name,
    type: "website",
  },
};

const HOME_FAQ: { q: string; a: string }[] = [
  {
    q: "How is ClipFactory different from other AI clippers?",
    a: "Most tools return 10 generic viral clips and a black-box score. ClipFactory reads your campaign brief, finds narrative arcs across the whole video (setup → payoff minutes apart), and explains each clip with five scores you can argue with.",
  },
  {
    q: "Which sources are supported?",
    a: "YouTube and Vimeo URLs at launch. Direct upload comes after the first paying users. We deliberately keep the input surface tight to ship a reliable pipeline.",
  },
  {
    q: "How much does it cost?",
    a: "29€/month for the Starter plan: 300 credits, up to 30 minutes per video, 3 clips per video. 1 credit = 1 minute of source. No watermark, EU hosted.",
  },
  {
    q: "Where is my data stored?",
    a: "Everything stays in EU regions: Supabase Frankfurt for the database, Cloudflare R2 EU for clips, Hetzner Germany for processing. Source videos are deleted after 14 days, clips after 60.",
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
        <PublicStats />
        <Problem />
        <Solution />
        <ScoreExplained />
        <Example />
        <Differentiator />
        <PricingTeaser />
        <Faq />
        <FinalCta />
      </main>
      <MarketingFooter />
    </>
  );
}

/* ============================================================
   Hero — narrative tagline + concrete clip mockup
   ============================================================ */
function Hero() {
  return (
    <section className="border-b border-[var(--color-border)]">
      <Container className="grid items-center gap-12 py-20 md:grid-cols-2 md:py-28">
        <div className="fade-up">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-muted)] px-3 py-1 text-xs text-[var(--color-muted-foreground)]">
            <Sparkles className="h-3.5 w-3.5 text-[var(--color-brand)]" />
            For creators &amp; agencies tired of random viral picks
          </div>
          <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">
            Less random virals.
            <br />
            <span className="text-[var(--color-brand)]">More clips that fit your campaign.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-[var(--color-muted-foreground)] md:text-xl">
            ClipFactory reads your campaign brief, maps the whole video, finds narrative arcs across distant moments, and ships publish-ready vertical shorts — each one with a score you can argue with.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/login">
              <Button size="lg">
                Start clipping
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="#how-it-works">
              <Button size="lg" variant="secondary">See how it works</Button>
            </Link>
          </div>
          <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
            No watermark · Cancel anytime · EU hosted · 29€/month
          </p>
        </div>

        <div className="fade-up-2">
          <ClipMockup />
          <p className="mt-3 text-center text-xs text-[var(--color-muted-foreground)]">
            Example output. Every clip ships with this score breakdown.
          </p>
        </div>
      </Container>
    </section>
  );
}

/* ============================================================
   Problem
   ============================================================ */
function Problem() {
  const pains = [
    {
      title: "Your AI clipper doesn't know your audience.",
      body: "It picks loud moments by transcript alone. Same output whether you sell SaaS or train athletes. Generic clips, generic engagement.",
    },
    {
      title: "The 'virality score' is a black box.",
      body: "One number, no breakdown. You can't argue, you can't iterate, you can't learn what worked and why.",
    },
    {
      title: "It misses the stories already in your video.",
      body: "Setup at minute 2, payoff at minute 12 — the connection is gone. You get isolated clips that float without context.",
    },
  ];

  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            The problem
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Most AI clippers ship the same 10 clips to everyone.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            That works for impressions. It does not work for campaigns. Not when you have a specific audience, a clear angle, and a reputation to protect.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {pains.map((p) => (
            <article
              key={p.title}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6"
            >
              <h3 className="text-lg font-medium">{p.title}</h3>
              <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{p.body}</p>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}

/* ============================================================
   Solution — pipeline diagram + four-step explanation
   ============================================================ */
function Solution() {
  const steps = [
    {
      icon: Target,
      title: "1. Brief the campaign",
      body: "Audience, niche, tone, goal, topics to avoid, example hooks. Two minutes of writing, every job inherits the brief.",
    },
    {
      icon: Eye,
      title: "2. We map the whole video",
      body: "Compressed visual + transcript map of every minute. Cheap globally, deep only where it counts — vision never runs on the full source.",
    },
    {
      icon: GitBranch,
      title: "3. We find story arcs",
      body: "Setup → payoff, promise → failure, before → after. Multi-segment clips stitch distant moments with a clean audio crossfade.",
    },
    {
      icon: Brain,
      title: "4. You get explained clips",
      body: "Five scores per clip: hook, emotion, visual proof, campaign fit, editing difficulty. With reasons. Keep, refine, or kill.",
    },
  ];

  return (
    <section id="how-it-works" className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            How it works
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            One brief in, publish-ready shorts out.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            A predictable pipeline, designed to protect your margin and your taste.
          </p>
        </div>

        <div className="mt-12 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted)] p-6 md:p-10">
          <PipelineDiagram />
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((s) => (
            <article
              key={s.title}
              className="rounded-lg border border-[var(--color-border)] p-6"
            >
              <s.icon className="h-5 w-5 text-[var(--color-brand)]" />
              <h3 className="mt-4 text-base font-medium">{s.title}</h3>
              <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{s.body}</p>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}

/* ============================================================
   Score explained — mockup on the right + reasons on the left
   ============================================================ */
function ScoreExplained() {
  const scores = [
    { label: "Hook", body: "Strength of the first 2 seconds — what makes the viewer stop scrolling." },
    { label: "Emotion", body: "Tension, surprise, reaction — anything that anchors the moment." },
    { label: "Visual proof", body: "Face on camera, action, visible objects — context the eye can hold." },
    { label: "Campaign fit", body: "Match with the audience, niche and goal you described in your brief." },
    { label: "Editing difficulty", body: "How clean the cut will be — penalises dark frames, missing faces, bad slides." },
  ];

  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-20">
        <div className="grid items-center gap-12 md:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              A score you can argue with
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Five numbers. Five reasons. No black box.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              Every clip carries its full breakdown. If a clip lands an 87, you see exactly why — and where the remaining 13 points went. Disagree, and your feedback tunes the next pick.
            </p>

            <dl className="mt-8 space-y-4">
              {scores.map((s) => (
                <div key={s.label} className="border-l-2 border-[var(--color-brand)] pl-4">
                  <dt className="text-sm font-semibold">{s.label}</dt>
                  <dd className="text-sm text-[var(--color-muted-foreground)]">{s.body}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div>
            <ClipMockup
              title="It cost him $50k to learn that one lesson"
              hook="And he says it with a smile, that's the wild part."
              total={91}
              scores={[
                { label: "Hook", value: 95 },
                { label: "Emotion", value: 88 },
                { label: "Visual", value: 92 },
                { label: "Fit", value: 90 },
                { label: "Editing", value: 84 },
              ]}
            />
          </div>
        </div>
      </Container>
    </section>
  );
}

/* ============================================================
   Real example — story arcs across distant moments
   ============================================================ */
function Example() {
  return (
    <section className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Real example
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            One vlog. Two moments ten minutes apart. One clip.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Other tools would clip these separately and the magic would be lost. ClipFactory stitches them.
          </p>
        </div>
        <div className="mt-10">
          <ExampleArc />
        </div>
      </Container>
    </section>
  );
}

/* ============================================================
   Before / after — generic AI clipper vs ClipFactory
   ============================================================ */
function Differentiator() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            What you get vs what you used to get
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Same input. Different output.
          </h2>
        </div>
        <div className="mt-10">
          <BeforeAfter />
        </div>
      </Container>
    </section>
  );
}

/* ============================================================
   Pricing teaser
   ============================================================ */
function PricingTeaser() {
  const features = [
    "300 credits per month (1 credit = 1 minute of source)",
    "Up to 30 min per video, 3 clips per video",
    "Vertical 1080×1920 with burned-in captions",
    "Full score breakdown on every clip",
    "EU hosted, no watermark, cancel anytime",
  ];
  return (
    <section id="pricing" className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Pricing
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            One plan to start. The price you see is the price you pay.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Creator and Agency plans unlock once API access and scheduling ship.
          </p>
        </div>

        <div className="mx-auto mt-12 max-w-md rounded-lg border-2 border-[var(--color-brand)] p-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Starter
          </p>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-5xl font-semibold tabular-nums">29€</span>
            <span className="text-[var(--color-muted-foreground)]">/ month</span>
          </div>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
            For solo creators getting serious about campaign-driven clipping.
          </p>
          <ul className="mt-6 space-y-3 text-sm">
            {features.map((f) => (
              <li key={f} className="flex gap-3">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-brand)]" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
          <Link href="/login" className="mt-8 block">
            <Button size="lg" className="w-full">Start with Starter</Button>
          </Link>
          <p className="mt-3 text-center text-xs text-[var(--color-muted-foreground)]">
            Cancel anytime · VAT included for EU customers
          </p>
        </div>
        <p className="mt-8 text-center text-sm text-[var(--color-muted-foreground)]">
          See the full plan comparison on the <Link href="/pricing" className="underline">pricing page</Link>.
        </p>
      </Container>
    </section>
  );
}

/* ============================================================
   FAQ inline
   ============================================================ */
function Faq() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="max-w-3xl py-20">
        <div className="mb-10">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Quick answers
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Common questions
          </h2>
        </div>
        <dl className="divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
          {HOME_FAQ.map((item) => (
            <div key={item.q} className="py-6">
              <dt className="text-base font-medium">{item.q}</dt>
              <dd className="mt-2 text-sm text-[var(--color-muted-foreground)]">{item.a}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-8 text-sm text-[var(--color-muted-foreground)]">
          More answers on the <Link href="/faq" className="underline">full FAQ</Link>.
        </p>
      </Container>
    </section>
  );
}

/* ============================================================
   Final CTA
   ============================================================ */
function FinalCta() {
  return (
    <section>
      <Container className="py-24 text-center">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-3 py-1 text-xs font-medium text-[var(--color-brand)]">
          <ShieldCheck className="h-3.5 w-3.5" />
          EU hosted · GDPR aware · no watermark
        </div>
        <h2 className="mt-6 text-3xl font-semibold tracking-tight md:text-5xl">
          Try it on your next long-form.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-[var(--color-muted-foreground)]">
          If the picks do not match your campaign, we want to hear it. Feedback feeds the next clip.
        </p>
        <Link href="/login" className="mt-8 inline-flex">
          <Button size="lg">
            Start clipping
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
        <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
          29€/month · Cancel any time
        </p>
      </Container>
    </section>
  );
}
