import type { Metadata } from "next";
import Link from "next/link";
import { Check } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "ClipFactory Starter plan: 29€ / month, 300 credits, 30 min per video, 3 clips per video. No watermark, cancel anytime, EU hosted.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return (
    <>
      <BreadcrumbJsonLd items={[{ name: "Home", href: "/" }, { name: "Pricing", href: "/pricing" }]} />
      <MarketingNav />
      <main className="flex-1">
        <Container className="max-w-4xl py-20">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Pricing</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">Pay only for the minutes you process.</h1>
          <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
            One plan to start. Bigger plans unlock once we ship API access and scheduling.
          </p>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            <Card
              name="Starter"
              price="29€"
              tagline="For solo creators."
              cta="Start with Starter"
              ctaHref="/login"
              features={[
                "300 credits / month",
                "30 min max per video",
                "3 clips per video",
                "1 concurrent job",
                "Vertical 1080×1920, captions",
                "Score breakdown per clip",
                "Feedback good/bad",
                "Cancel anytime",
              ]}
              highlighted
            />
            <Card
              name="Creator"
              price="79€"
              tagline="Coming soon."
              cta="Notify me"
              ctaHref={`mailto:hello@clipfactory.app?subject=Creator%20plan%20waitlist`}
              features={[
                "1000 credits / month",
                "60 min max per video",
                "5 clips per video",
                "2 concurrent jobs",
                "Story arcs (multi-segment)",
                "Campaign memory",
              ]}
            />
            <Card
              name="Agency"
              price="199€"
              tagline="Coming soon."
              cta="Get in touch"
              ctaHref={`mailto:hello@clipfactory.app?subject=Agency%20plan`}
              features={[
                "3000 credits / month",
                "120 min max per video",
                "8 clips per video",
                "3 concurrent jobs",
                "API access (V2)",
                "Priority support",
              ]}
            />
          </div>

          <section className="mt-20 rounded-lg border border-[var(--color-border)] p-8">
            <h2 className="text-xl font-semibold">How credits work</h2>
            <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
              1 credit = 1 minute of source video. If you submit a 12-minute video, we deduct 12 credits when the worker probes the duration. If a job fails before processing, you get a full refund.
            </p>
            <ul className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              <li>· Vertical render, captions, score breakdown — included.</li>
              <li>· No watermark on any plan.</li>
              <li>· Renders kept 60 days, source videos deleted after 14 days.</li>
              <li>· Stripe billing — VAT included for EU customers.</li>
            </ul>
          </section>

          <p className="mt-8 text-center text-sm text-[var(--color-muted-foreground)]">
            Got questions? Read the <Link href="/faq" className="underline">FAQ</Link> or write to <a href="mailto:hello@clipfactory.app" className="underline">hello@clipfactory.app</a>.
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}

function Card({
  name,
  price,
  tagline,
  cta,
  ctaHref,
  features,
  highlighted,
}: {
  name: string;
  price: string;
  tagline: string;
  cta: string;
  ctaHref: string;
  features: string[];
  highlighted?: boolean;
}) {
  return (
    <div
      className={
        "rounded-lg border p-6 " +
        (highlighted
          ? "border-[var(--color-foreground)]"
          : "border-[var(--color-border)]")
      }
    >
      <p className="text-sm font-medium text-[var(--color-muted-foreground)]">{name}</p>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-4xl font-semibold tabular-nums">{price}</span>
        <span className="text-[var(--color-muted-foreground)]">/ month</span>
      </div>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{tagline}</p>
      <ul className="mt-6 space-y-2 text-sm">
        {features.map((f) => (
          <li key={f} className="flex gap-3">
            <Check className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <Link href={ctaHref as never} className="mt-6 block">
        <Button className="w-full" variant={highlighted ? "primary" : "secondary"}>
          {cta}
        </Button>
      </Link>
    </div>
  );
}
