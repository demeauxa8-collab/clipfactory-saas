import Link from "next/link";
import { ArrowRight, Brain, Check, Sparkles, Target } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";

export default function HomePage() {
  return (
    <>
      <MarketingNav />
      <main className="flex-1">
        <Hero />
        <SocialProofGap />
        <HowItWorks />
        <ScoreExplained />
        <Pricing />
        <FinalCta />
      </main>
      <MarketingFooter />
    </>
  );
}

function Hero() {
  return (
    <section className="border-b border-[var(--color-border)]">
      <Container className="py-20 md:py-28">
        <div className="max-w-3xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-muted)] px-3 py-1 text-xs text-[var(--color-muted-foreground)]">
            <Sparkles className="h-3.5 w-3.5" />
            Built for creators and agencies tired of random viral picks
          </div>
          <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">
            Less random virals.
            <br />
            More clips that fit your campaign.
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-[var(--color-muted-foreground)] md:text-xl">
            ClipFactory picks shorts based on your campaign, your audience and your past performance — not just whichever moment looks loud. Every clip ships with a score you can argue with.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/login">
              <Button size="lg">
                Start clipping
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="#how">
              <Button size="lg" variant="secondary">See how it works</Button>
            </Link>
          </div>
          <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
            No watermark. Cancel any time. EU hosted.
          </p>
        </div>
      </Container>
    </section>
  );
}

function SocialProofGap() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-10">
        <p className="text-sm text-[var(--color-muted-foreground)]">
          We are not a generic AI clipper. We do not promise &ldquo;10 viral clips from one video&rdquo;. We pick the clips that match the campaign you actually run.
        </p>
      </Container>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      icon: Target,
      title: "Tell us your campaign",
      body: "Name your campaign, attach a brief, and let ClipFactory understand the audience you target before any clip is rendered.",
    },
    {
      icon: Brain,
      title: "We score moments, not just transcripts",
      body: "We combine hook strength, emotion, visual context and fit-with-campaign. You get a number per clip — and a reason.",
    },
    {
      icon: Sparkles,
      title: "Get 3 publish-ready shorts",
      body: "Vertical 1080x1920, captions, hook ready. Download or push to your editor. Costs are predictable: 1 minute of source = 1 credit.",
    },
  ];
  return (
    <section id="how" className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">How it works</h2>
        <p className="mt-3 max-w-2xl text-[var(--color-muted-foreground)]">
          Three steps. Predictable cost. Every decision is explained.
        </p>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {steps.map((s, i) => (
            <div
              key={s.title}
              className="rounded-lg border border-[var(--color-border)] p-6"
            >
              <div className="mb-4 flex items-center justify-between">
                <s.icon className="h-5 w-5" />
                <span className="text-xs text-[var(--color-muted-foreground)]">0{i + 1}</span>
              </div>
              <h3 className="text-lg font-medium">{s.title}</h3>
              <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{s.body}</p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}

function ScoreExplained() {
  const scores = [
    { label: "Hook score", body: "Strength of the first 2-3 seconds." },
    { label: "Emotion score", body: "Tension, surprise, reaction in the moment." },
    { label: "Visual score", body: "Face on camera, energy, visible proof." },
    { label: "Campaign fit", body: "Match with the campaign you told us about." },
    { label: "Editing difficulty", body: "How clean the cut will be." },
    { label: "Predicted retention", body: "Likelihood viewers stay until the end." },
  ];
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-20">
        <div className="grid gap-12 md:grid-cols-2">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              A score you can argue with.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              Every clip ships with its full breakdown — not a single mysterious &ldquo;virality&rdquo; number. You see why it was picked, and you can disagree.
            </p>
          </div>
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-4">
              <div>
                <p className="text-sm text-[var(--color-muted-foreground)]">Clip 1</p>
                <p className="font-medium">&ldquo;He lost 50k because of this&rdquo;</p>
              </div>
              <div className="text-3xl font-semibold tabular-nums">87</div>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              {scores.map((s) => (
                <div key={s.label} className="flex flex-col">
                  <dt className="text-[var(--color-muted-foreground)]">{s.label}</dt>
                  <dd className="font-medium">{s.body}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </Container>
    </section>
  );
}

function Pricing() {
  const features = [
    "300 credits / month (1 credit = 1 minute of source)",
    "Up to 30 min per video",
    "3 clips per video, 1080x1920 vertical",
    "Auto captions",
    "Score breakdown for every clip",
    "EU hosted, no watermark",
  ];
  return (
    <section id="pricing" className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Simple pricing</h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            One plan to start. Bigger plans unlock once we ship API access and scheduling.
          </p>
        </div>
        <div className="mx-auto mt-12 max-w-md rounded-lg border border-[var(--color-border)] p-8">
          <p className="text-sm font-medium text-[var(--color-muted-foreground)]">Starter</p>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-5xl font-semibold tabular-nums">29€</span>
            <span className="text-[var(--color-muted-foreground)]">/ month</span>
          </div>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
            For solo creators getting started with campaign-driven clipping.
          </p>
          <ul className="mt-6 space-y-3 text-sm">
            {features.map((f) => (
              <li key={f} className="flex gap-3">
                <Check className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
          <Link href="/login" className="mt-8 block">
            <Button size="lg" className="w-full">Start with Starter</Button>
          </Link>
          <p className="mt-3 text-center text-xs text-[var(--color-muted-foreground)]">
            Cancel anytime. VAT included for EU customers.
          </p>
        </div>
      </Container>
    </section>
  );
}

function FinalCta() {
  return (
    <section>
      <Container className="py-24 text-center">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
          Stop shipping random clips.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-[var(--color-muted-foreground)]">
          Try ClipFactory on your next long-form. If the picks do not fit your campaign, we want to know.
        </p>
        <Link href="/login" className="mt-8 inline-flex">
          <Button size="lg">
            Start clipping
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </Container>
    </section>
  );
}
