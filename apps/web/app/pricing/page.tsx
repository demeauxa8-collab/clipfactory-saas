import type { Metadata } from "next";
import Link from "next/link";
import { Check, Minus } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import {
  BreadcrumbJsonLd,
  FaqJsonLd,
} from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "Pricing — 29€/month, no watermark, EU hosted",
  description:
    "ClipFactory Starter plan: 29€ / month, 300 credits, 30 min per video, 3 clips per video. No watermark, cancel anytime, EU hosted. Creator and Agency tiers coming soon.",
  keywords: [
    "AI clipping pricing",
    "AI clipper price",
    "OpusClip alternative price",
    "vertical short generator price",
    "YouTube to Shorts pricing",
    "EU hosted AI clipping",
    "no watermark AI clipping",
  ],
  alternates: { canonical: "/pricing" },
};

const PRICING_FAQ = [
  {
    q: "What counts as a 'credit'?",
    a: "1 credit = 1 minute of source video. Submit a 12-minute video and the worker deducts 12 credits at probe time. The number of clips returned does not change the cost.",
  },
  {
    q: "What if a job fails?",
    a: "If the worker fails before producing clips, you get a full credit refund automatically. If it produces fewer clips than expected (anti-hallucination drop, source issue), you only pay for what was processed.",
  },
  {
    q: "Is there a free trial?",
    a: "Not yet. The first paying customers get a personal onboarding call instead. Reach out at hello@clipfactory.app and we'll set you up.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes. Stripe handles billing — cancel from your billing portal and you keep access until the end of the current period.",
  },
  {
    q: "Where is my data stored?",
    a: "Supabase Frankfurt for the database, Cloudflare R2 EU for clips, Hetzner Germany for processing. Source videos auto-delete after 14 days, rendered clips after 60.",
  },
  {
    q: "Do you take a cut of my revenue?",
    a: "No. You pay a flat monthly fee, that's it. We never take a percentage of what your clips earn elsewhere.",
  },
];

type PlanFeature = { label: string; included: boolean };
type Plan = {
  name: string;
  price: string;
  tagline: string;
  cta: string;
  ctaHref: string;
  highlighted?: boolean;
  available: boolean;
  features: PlanFeature[];
};

const PLANS: Plan[] = [
  {
    name: "Starter",
    price: "29€",
    tagline: "For solo creators ready to ship.",
    cta: "Start with Starter",
    ctaHref: "/login",
    highlighted: true,
    available: true,
    features: [
      { label: "300 credits / month", included: true },
      { label: "Up to 30 min per video", included: true },
      { label: "3 clips per video", included: true },
      { label: "1 concurrent job", included: true },
      { label: "Vertical 1080×1920 + burned captions", included: true },
      { label: "Full 5-axis score breakdown", included: true },
      { label: "Story arcs (multi-segment clips)", included: true },
      { label: "Campaign briefs", included: true },
      { label: "Good / bad feedback", included: true },
      { label: "API access", included: false },
      { label: "Priority support", included: false },
    ],
  },
  {
    name: "Creator",
    price: "79€",
    tagline: "Coming soon — join the waitlist.",
    cta: "Notify me",
    ctaHref: "mailto:hello@clipfactory.app?subject=Creator%20plan%20waitlist",
    available: false,
    features: [
      { label: "1 000 credits / month", included: true },
      { label: "Up to 60 min per video", included: true },
      { label: "5 clips per video", included: true },
      { label: "2 concurrent jobs", included: true },
      { label: "Story arcs (multi-segment clips)", included: true },
      { label: "Campaign memory across jobs", included: true },
      { label: "Full 5-axis score breakdown", included: true },
      { label: "Good / bad feedback", included: true },
      { label: "API access", included: false },
      { label: "Priority support", included: true },
    ],
  },
  {
    name: "Agency",
    price: "199€",
    tagline: "Coming soon — for studios.",
    cta: "Get in touch",
    ctaHref: "mailto:hello@clipfactory.app?subject=Agency%20plan",
    available: false,
    features: [
      { label: "3 000 credits / month", included: true },
      { label: "Up to 120 min per video", included: true },
      { label: "8 clips per video", included: true },
      { label: "3 concurrent jobs", included: true },
      { label: "Story arcs (multi-segment clips)", included: true },
      { label: "Campaign memory across jobs", included: true },
      { label: "Full 5-axis score breakdown", included: true },
      { label: "Good / bad feedback", included: true },
      { label: "API access (V2)", included: true },
      { label: "Priority support", included: true },
    ],
  },
];

export default function PricingPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Pricing", href: "/pricing" },
        ]}
      />
      <FaqJsonLd items={PRICING_FAQ} />
      <MarketingNav />
      <main className="flex-1">
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Pricing
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              Pay only for the minutes you process.
            </h1>
            <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
              Predictable per-minute billing. No revenue share, no watermark, no surprise overage —
              the price you see is the price you pay.
            </p>

            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {PLANS.map((p) => (
                <PlanCard key={p.name} plan={p} />
              ))}
            </div>
          </Container>
        </section>

        {/* Credits explanation */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-4xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              How credits work
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              1 credit = 1 minute of source. That&apos;s the whole rule.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              Charge happens at probe time, not at upload — so a failed download never burns
              credits. If the pipeline drops clips at the anti-hallucination step, you are only
              billed for the clips you actually get.
            </p>
            <ul className="mt-8 grid gap-3 text-sm md:grid-cols-2">
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                <span className="font-semibold">Vertical render included.</span>{" "}
                1080×1920, burned captions, no watermark — on every plan.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                <span className="font-semibold">Storage retention.</span> Source files deleted
                after 14 days, rendered clips after 60. GDPR-friendly by design.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                <span className="font-semibold">Stripe billing.</span> VAT included for EU
                customers. Billing portal for invoices and cancellation.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                <span className="font-semibold">No revenue share.</span> What your clips earn
                elsewhere is yours, full stop.
              </li>
            </ul>
          </Container>
        </section>

        {/* FAQ */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-3xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Pricing FAQ
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Common questions about billing.
            </h2>
            <dl className="mt-10 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
              {PRICING_FAQ.map((item) => (
                <div key={item.q} className="py-6">
                  <dt className="text-base font-medium">{item.q}</dt>
                  <dd className="mt-2 text-sm text-[var(--color-muted-foreground)]">{item.a}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-8 text-sm text-[var(--color-muted-foreground)]">
              Still unsure? Write to{" "}
              <a href="mailto:hello@clipfactory.app" className="underline">
                hello@clipfactory.app
              </a>{" "}
              or check the <Link href="/faq" className="underline">full FAQ</Link>.
            </p>
          </Container>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}

function PlanCard({ plan }: { plan: Plan }) {
  return (
    <div
      className={
        "flex flex-col rounded-lg border p-6 " +
        (plan.highlighted
          ? "border-2 border-[var(--color-brand)]"
          : "border-[var(--color-border)]")
      }
    >
      <div className="flex items-center gap-2">
        <p
          className={
            "text-sm font-semibold uppercase tracking-wider " +
            (plan.highlighted
              ? "text-[var(--color-brand)]"
              : "text-[var(--color-muted-foreground)]")
          }
        >
          {plan.name}
        </p>
        {!plan.available && (
          <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-muted)] px-2 py-0.5 text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">
            Soon
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-4xl font-semibold tabular-nums">{plan.price}</span>
        <span className="text-[var(--color-muted-foreground)]">/ month</span>
      </div>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{plan.tagline}</p>

      <ul className="mt-6 flex-1 space-y-2 text-sm">
        {plan.features.map((f) => (
          <li
            key={f.label}
            className={
              "flex gap-3 " +
              (f.included ? "" : "text-[var(--color-muted-foreground)] line-through")
            }
          >
            {f.included ? (
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-brand)]" />
            ) : (
              <Minus className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-muted-foreground)]" />
            )}
            <span>{f.label}</span>
          </li>
        ))}
      </ul>

      <Link href={plan.ctaHref as never} className="mt-8 block">
        <Button
          className="w-full"
          variant={plan.highlighted ? "primary" : "secondary"}
        >
          {plan.cta}
        </Button>
      </Link>
      {plan.available && (
        <p className="mt-3 text-center text-xs text-[var(--color-muted-foreground)]">
          Cancel anytime · VAT included
        </p>
      )}
    </div>
  );
}
