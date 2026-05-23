import type { Metadata } from "next";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "About",
  description: `Why ${SITE.name} exists, who builds it, and what we promise to creators and agencies.`,
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <>
      <BreadcrumbJsonLd items={[{ name: "Home", href: "/" }, { name: "About", href: "/about" }]} />
      <MarketingNav />
      <main className="flex-1">
        <Container className="max-w-3xl py-20">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">About</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
            We build clipping for people who actually run campaigns.
          </h1>

          <div className="mt-10 space-y-6 text-[var(--color-foreground)]">
            <p>
              {SITE.name} started because every AI clipper on the market gives you the same thing: 10 clips, no context, no campaign awareness, no explanation. You get random viral moments — sometimes that works, often it doesn&apos;t.
            </p>
            <p>
              We think clipping should be <strong>campaign-first</strong>. You tell us who you talk to, what you sell, and what to avoid. Then we pick the clips that fit. Every clip ships with a score you can argue with — hook, emotion, visual, campaign fit, editing difficulty. No black box.
            </p>
            <p>
              On long videos, we go further. We map the whole video first, then look for narrative arcs that connect distant moments — a promise made at minute 2 and the payoff at minute 12, cut into a single short. That&apos;s where the algorithm earns its name.
            </p>
          </div>

          <h2 className="mt-16 text-2xl font-semibold tracking-tight">Who builds this</h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            {SITE.name} is built by {SITE.founder}, a designer and product strategist. The product is hosted in the EU and runs on a small, deliberate stack — no third-party black-box clipping API behind the curtain.
          </p>

          <h2 className="mt-16 text-2xl font-semibold tracking-tight">What we promise</h2>
          <ul className="mt-4 space-y-3 text-[var(--color-foreground)]">
            <li>
              <strong>No watermark</strong> on your clips — ever, even on the entry plan.
            </li>
            <li>
              <strong>Predictable cost</strong>: 1 minute of source = 1 credit. No surprises.
            </li>
            <li>
              <strong>Honest scoring</strong>: every clip has a breakdown. You can disagree with us.
            </li>
            <li>
              <strong>EU hosted</strong>: your data stays in EU regions. No transfer to the US.
            </li>
            <li>
              <strong>Cancel anytime</strong>: one click, no friction, no &ldquo;are you sure&rdquo; modal cascade.
            </li>
          </ul>

          <h2 className="mt-16 text-2xl font-semibold tracking-tight">Get in touch</h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Feedback, partnerships, agency volume — write to <a className="underline" href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a>. I read every email myself.
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
