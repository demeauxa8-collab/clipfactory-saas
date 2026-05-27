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
  title: "AI video clipping pricing — 29€/month, no watermark",
  description:
    "ClipFactory pricing starts at 29€ / month for 300 video minutes. Turn long videos into Shorts, Reels and TikToks with captions, no watermark, EU hosting and simple credits.",
  keywords: [
    "AI video clipping pricing",
    "AI clip maker pricing",
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
    a: "1 credit = 1 minute of source video. A 12-minute video uses 12 credits, whether ClipFactory returns one clip or three clips.",
  },
  {
    q: "What if a job fails?",
    a: "If ClipFactory cannot process the video, the credits are refunded. If a video is too broken to make good clips, we do not charge for fake output.",
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
    a: "ClipFactory is designed around EU hosting: database in Frankfurt, storage in Europe and video processing in Germany. Source videos auto-delete after 14 days, rendered clips after 60.",
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
      { label: "300 video minutes / month", included: true },
      { label: "Up to 30 min per video", included: true },
      { label: "3 clips per video", included: true },
      { label: "1 concurrent job", included: true },
      { label: "Vertical 1080×1920 + burned captions", included: true },
      { label: "Simple score for every clip", included: true },
      { label: "Multi-part clips when the story needs it", included: true },
      { label: "Audience brief", included: true },
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
      { label: "1 000 video minutes / month", included: true },
      { label: "Up to 60 min per video", included: true },
      { label: "5 clips per video", included: true },
      { label: "2 concurrent jobs", included: true },
      { label: "Multi-part clips when the story needs it", included: true },
      { label: "Saved audience briefs", included: true },
      { label: "Simple score for every clip", included: true },
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
      { label: "3 000 video minutes / month", included: true },
      { label: "Up to 120 min per video", included: true },
      { label: "8 clips per video", included: true },
      { label: "3 concurrent jobs", included: true },
      { label: "Multi-part clips when the story needs it", included: true },
      { label: "Saved audience briefs", included: true },
      { label: "Simple score for every clip", included: true },
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
              Pricing for turning long videos into short clips.
            </h1>
            <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
              Simple monthly plans for AI video clipping. You pay for video minutes,
              get vertical clips with captions, and keep the clips with no watermark.
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
              How video minutes work
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              1 credit = 1 minute of source video.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              Upload or paste a 12-minute video and it uses 12 credits. The number of
              clips does not change the price, so costs stay easy to understand.
            </p>
            <ul className="mt-8 grid gap-3 text-sm md:grid-cols-2">
              <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                <span className="font-semibold">Vertical clips included.</span>{" "}
                1080×1920, captions, no watermark — on every plan.
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
