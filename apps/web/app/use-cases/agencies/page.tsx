import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Building2,
  FileText,
  LineChart,
  ShieldCheck,
} from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "AI clipping for agencies and content studios",
  description:
    "Serve more clients without losing taste. Per-client campaign briefs, defensible scored output for sign-off, predictable per-minute cost — built for studios who clip at scale.",
  keywords: [
    "AI clipping for agencies",
    "content agency AI",
    "white-label clipping",
    "agency video editing AI",
    "EU agency AI",
    "per-client campaign briefs",
  ],
  alternates: { canonical: "/use-cases/agencies" },
};

const PROBLEMS = [
  {
    title: "Generic AI picks ten clips. Your client wants three good ones.",
    body: "You spend hours sorting. Worse, you can&apos;t explain to the brand why a clip got picked.",
  },
  {
    title: "Cost is unpredictable.",
    body: "Pay-per-clip pricing breaks margin once you serve five clients. You need per-minute billing you can pass through.",
  },
  {
    title: "Reviews stall on taste.",
    body: "Without a defensible score, every brand call ends in subjective debate. You need numbers to defend a pick.",
  },
];

const SOLUTIONS = [
  {
    icon: FileText,
    title: "One campaign brief per client.",
    body: "Audience, niche, tone, goal, avoid topics, example hooks. Every job inherits the brief — picks stay on-brand at scale.",
  },
  {
    icon: LineChart,
    title: "Score breakdown you can defend.",
    body: "Five components per clip. When a brand asks why this clip and not that one, you don&apos;t guess — you point.",
  },
  {
    icon: ShieldCheck,
    title: "EU hosting, predictable billing.",
    body: "1 minute of source = 1 credit. EU-hosted infrastructure for procurement-friendly contracts. Pass-through pricing that fits agency margin.",
  },
];

export default function AgenciesUseCasePage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Use cases", href: "/use-cases/agencies" },
          { name: "For agencies", href: "/use-cases/agencies" },
        ]}
      />
      <MarketingNav />
      <main className="flex-1">
        {/* Hero */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-3 py-1 text-xs font-medium text-[var(--color-brand)]">
              <Building2 className="h-3.5 w-3.5" />
              For agencies &amp; content studios
            </div>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              Serve more clients without losing taste.
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-[var(--color-muted-foreground)]">
              Per-client campaign briefs, defensible scored output for sign-off, predictable
              per-minute cost. Built so a 4-person studio can serve 20 clients without becoming a
              clip-sorting factory.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="mailto:hello@clipfactory.app?subject=Agency%20pilot">
                <Button size="lg">
                  Book a pilot call
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
              Agency plan launches Q3 — Starter works today.
            </p>
          </Container>
        </section>

        {/* Problems */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                The bottleneck
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                The clipping step kills your margin.
              </h2>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {PROBLEMS.map((p) => (
                <article
                  key={p.title}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6"
                >
                  <h3
                    className="text-lg font-medium"
                    dangerouslySetInnerHTML={{ __html: p.title }}
                  />
                  <p
                    className="mt-2 text-sm text-[var(--color-muted-foreground)]"
                    dangerouslySetInnerHTML={{ __html: p.body }}
                  />
                </article>
              ))}
            </div>
          </Container>
        </section>

        {/* Solutions */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                Three things we changed
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Designed for sign-off, not just selection.
              </h2>
            </div>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {SOLUTIONS.map((s) => (
                <article
                  key={s.title}
                  className="rounded-lg border border-[var(--color-border)] p-6 transition-colors hover:border-[var(--color-brand)]"
                >
                  <s.icon className="h-5 w-5 text-[var(--color-brand)]" />
                  <h3 className="mt-4 text-base font-medium">{s.title}</h3>
                  <p
                    className="mt-2 text-sm text-[var(--color-muted-foreground)]"
                    dangerouslySetInnerHTML={{ __html: s.body }}
                  />
                </article>
              ))}
            </div>
          </Container>
        </section>

        {/* Output preview */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <div className="grid items-center gap-12 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                  Brand-ready output
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  Three clips. Three scored arguments.
                </h2>
                <p className="mt-4 text-[var(--color-muted-foreground)]">
                  Walk into the brand review with the breakdown on screen. Hook, emotion, visual
                  proof, campaign fit, editing. No more taste fights.
                </p>
                <Link href="mailto:hello@clipfactory.app?subject=Agency%20pilot" className="mt-6 inline-flex">
                  <Button>
                    Book a pilot call
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
              <ClipMockup
                title="Why the rebrand actually worked"
                hook="It wasn't the logo. It was the silence around it."
                total={92}
                duration="0:46"
                segments={[
                  { role: "setup", range: "07:22 → 07:48" },
                  { role: "payoff", range: "22:10 → 22:36" },
                ]}
                scores={[
                  { label: "Hook", value: 96 },
                  { label: "Emotion", value: 90 },
                  { label: "Visual", value: 88 },
                  { label: "Fit", value: 95 },
                  { label: "Editing", value: 85 },
                ]}
              />
            </div>
          </Container>
        </section>

        {/* CTA */}
        <section>
          <Container className="max-w-3xl py-20 text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Pilot it on one client this month.
            </h2>
            <p className="mt-3 text-[var(--color-muted-foreground)]">
              Starter handles a first client; the Agency plan opens with API access and team
              workspaces in Q3.
            </p>
            <Link
              href="mailto:hello@clipfactory.app?subject=Agency%20pilot"
              className="mt-8 inline-flex"
            >
              <Button size="lg">
                Book a pilot call
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
