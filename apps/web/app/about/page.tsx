import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Github, Mail, MapPin, ShieldCheck } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "About ClipFactory — AI video clipping for creators",
  description: `Why ${SITE.name} exists, who builds it, and what we promise to creators, podcasters and agencies turning long videos into short clips.`,
  keywords: [
    "ClipFactory founders",
    "AX Studio",
    "independent AI SaaS",
    "EU AI clipping",
    "AI video clipping",
    "AI clip maker",
    "long video to shorts",
  ],
  alternates: { canonical: "/about" },
};

const PROMISES = [
  {
    title: "No watermark, ever.",
    body: "Not on Starter, not on any future plan. Your reputation isn't an upsell.",
  },
  {
    title: "Predictable cost.",
    body: "1 minute of source = 1 credit. No revenue share, no surprise overage.",
  },
  {
    title: "Clear scoring.",
    body: "Every clip explains why it was picked. You can disagree, and that judgment is recorded without silently retraining the system.",
  },
  {
    title: "EU by default.",
    body: "Database and storage are designed around a European path. Subprocessors and processing boundaries belong in the privacy policy, not in an absolute slogan.",
  },
  {
    title: "Honest billing controls.",
    body: "Stripe Checkout activates Starter. Self-service subscription management is still being completed for the pilot.",
  },
  {
    title: "We use what we sell.",
    body: "Illustrative fixtures are labelled as such. Live product results stay separate from designed examples.",
  },
];

const PRINCIPLES = [
  {
    n: "01",
    title: "Fewer random clips.",
    body: "Returning 10 generic clips is easy. Returning 3 useful clips for the right audience is the real job.",
  },
  {
    n: "02",
    title: "Clear beats magical.",
    body: "Scores, timestamps and reasons are visible. If you cannot understand the AI, you cannot improve it.",
  },
  {
    n: "03",
    title: "Cost matters.",
    body: "Vision is used where it changes the clip decision. That keeps pricing stable instead of wasting budget.",
  },
  {
    n: "04",
    title: "The basics must work.",
    body: "Captions, traceable failures, a visible credit ledger and no watermark. Not glamorous, but important.",
  },
];

export default function AboutPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "About", href: "/about" },
        ]}
      />
      <MarketingNav />
      <main id="main-content" className="flex-1">
        {/* Intro */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-3xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              About
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              AI video clipping built for people who post every week.
            </h1>
            <div className="mt-10 space-y-6 text-[var(--color-foreground)]">
              <p>
                {SITE.name} started because many AI clippers give you the same
                thing: a batch of short clips with little context and no clear
                reason. Sometimes it works. Often, the clips are just random.
              </p>
              <p>
                We think clipping should start with the person watching. You
                tell us who you talk to, what you want to show and what to
                avoid. Then ClipFactory picks clips that fit that audience, with
                a simple score and a reason.
              </p>
              <p>
                On long videos, we also look for moments that only make sense
                together: a setup at minute 2, a payoff at minute 12, combined
                into one vertical short. That is where better clip selection
                matters.
              </p>
            </div>
          </Container>
        </section>

        {/* Principles */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              How we build
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Four principles we will not compromise.
            </h2>
            <div className="mt-10 grid gap-6 md:grid-cols-2">
              {PRINCIPLES.map((p) => (
                <article
                  key={p.n}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6"
                >
                  <p className="font-mono text-xs text-[var(--color-brand)]">
                    {p.n}
                  </p>
                  <h3 className="mt-2 text-lg font-medium">{p.title}</h3>
                  <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
                    {p.body}
                  </p>
                </article>
              ))}
            </div>
          </Container>
        </section>

        {/* Promises */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              What we promise
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              The fine print, in plain sight.
            </h2>
            <ul className="mt-10 grid gap-4 md:grid-cols-2">
              {PROMISES.map((p) => (
                <li
                  key={p.title}
                  className="rounded-lg border border-[var(--color-border)] p-5"
                >
                  <p className="font-medium">{p.title}</p>
                  <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
                    {p.body}
                  </p>
                </li>
              ))}
            </ul>
          </Container>
        </section>

        {/* Who builds */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-3xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Who builds this
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              A small team. A simple promise.
            </h2>
            <p className="mt-6 text-[var(--color-foreground)]">
              {SITE.name} is built by {SITE.founder} at AX Studio. The product
              uses an EU-first account and database path and is built as a real
              product, not a wrapper around another clipping website. The
              promise is simple: long videos in, useful short clips out, with
              clear reasons.
            </p>
            <ul className="mt-8 space-y-2 text-sm text-[var(--color-muted-foreground)]">
              <li className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-[var(--color-brand)]" /> EU
                Supabase project for account and product data.
              </li>
              <li className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[var(--color-brand)]" />{" "}
                Deletion requests handled during the pilot while lifecycle
                automation is completed.
              </li>
              <li className="flex items-center gap-2">
                <Github className="h-4 w-4 text-[var(--color-brand)]" />{" "}
                Processing stages and failure states stay visible in the
                product.
              </li>
            </ul>
          </Container>
        </section>

        {/* Contact CTA */}
        <section>
          <Container className="max-w-3xl py-20 text-center">
            <Mail className="mx-auto h-6 w-6 text-[var(--color-brand)]" />
            <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">
              Get in touch.
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-[var(--color-muted-foreground)]">
              Feedback, partnerships, agency volume, press — write to{" "}
              <a className="underline" href={`mailto:${SITE.contactEmail}`}>
                {SITE.contactEmail}
              </a>
              . I read every email myself.
            </p>
            <Link
              href="/login?next=/app/campaigns/new"
              className="mt-8 inline-flex"
            >
              <Button size="lg">
                Try ClipFactory
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
