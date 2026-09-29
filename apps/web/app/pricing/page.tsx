import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { BreadcrumbJsonLd, FaqJsonLd } from "@/components/marketing/json-ld";
import { MobileMenu } from "@/components/marketing/mobile-menu";
import { PricingSection } from "@/components/marketing/pricing-section";
import landing from "@/components/prototypes/redesign/apple-edit-axis.module.css";
import story from "@/components/prototypes/redesign/edit-axis-story.module.css";
import styles from "./pricing.module.css";

export const metadata: Metadata = {
  title: "Plans & pricing — Starter and Pro",
  description: "Starter at €29/month for 300 credits. Explore Pro at €79/month for 1,000 credits and up to five YouTube sources per series. Pro is coming soon.",
  alternates: { canonical: "/pricing" },
};

const FAQ = [
  { q: "Can I use several videos in one series?", a: "Multi-source series are reserved for Pro, with two to five YouTube videos under one campaign brief. Sources are processed in order and results stay grouped. Each exported clip uses one source; footage from different videos is not mixed. Pro subscriptions are not open yet." },
  { q: "How are credits counted?", a: "One credit covers one minute of source video. A 12-minute video uses 12 credits, whether it produces one clip or three. In a multi-source series, the duration of each video counts toward the total." },
  { q: "How many clips will I receive?", a: "You can request up to three clips per video. Quality checks may return fewer distinct cuts when the source does not support three. Every delivered clip includes vertical framing, burned captions and a download without a watermark." },
  { q: "Can I cancel my subscription?", a: "Contact hello@clipfactory.app for billing, invoices or cancellation during the pilot. Pro is not open for subscriptions yet, so joining its notification list does not start a subscription or create a charge." },
  { q: "What happens if processing fails?", a: "The failed source and its status stay visible. In a series, a failed source does not prevent the next source from being processed. Contact support if a credit adjustment needs review." },
];

function BrandMark() {
  return <span className={landing.brandMark} aria-hidden="true"><span /><span /><span /></span>;
}

export default function PricingPage() {
  return (
    <div className={`${landing.page} ${story.rest} ${styles.page}`}>
      <BreadcrumbJsonLd items={[{ name: "Home", href: "/" }, { name: "Pricing", href: "/pricing" }]} />
      <FaqJsonLd items={FAQ} />
      <header className={`${landing.header} ${styles.header}`}>
        <Link href="/" className={landing.brand} aria-label="ClipFactory home"><BrandMark /><span>ClipFactory</span></Link>
        <nav className={landing.primaryNav} aria-label="Primary navigation">
          <Link href="/#story">How it works</Link>
          <Link href="/#campaign-v6">Features</Link>
          <Link href="/pricing" aria-current="page">Pricing</Link>
        </nav>
        <div className={landing.headerActions}>
          <MobileMenu />
          <Link href="/login" className={landing.signIn}>Sign in</Link>
          <Link href="/app/campaigns/new" className={landing.navCta}>Start a campaign <ArrowUpRight aria-hidden="true" /></Link>
        </div>
      </header>
      <main id="main-content">
        <div className={styles.plans}><PricingSection startHref="/app/campaigns/new" standalone /></div>
        <section className={styles.credits} aria-labelledby="credits-title">
          <div><p className={styles.eyebrow}>Count the source, not the cuts</p><h2 id="credits-title">One minute.<br />One credit.</h2></div>
          <div className={styles.creditExample}>
            <div className={styles.equation}><span><strong>12</strong>minutes of source</span><span aria-hidden="true">=</span><span><strong>12</strong>credits used</span></div>
            <p>Request up to three clips from the same video. The number of clips does not change the credit cost.</p>
            <p>For a series, add the duration of every source. Credits are counted separately for each video.</p>
          </div>
        </section>
        <section className={`${story.faqSection} ${styles.faq}`} aria-labelledby="faq-title">
          <div className={story.faqHeading}><p className={styles.eyebrow}>A few details</p><h2 id="faq-title">Before your<br />first cut.</h2><p className={styles.contact}>Need a hand choosing?<br /><a href="mailto:hello@clipfactory.app">Talk to us <ArrowUpRight aria-hidden="true" /></a></p></div>
          <div className={story.faqList}>{FAQ.map((item, index) => <details key={item.q} name="pricing-faq"><summary><span>{String(index + 1).padStart(2, "0")}</span><strong>{item.q}</strong><ChevronDown aria-hidden="true" /></summary><p>{item.a}</p></details>)}</div>
        </section>
      </main>
      <footer className={styles.footer}>
        <Link href="/" className={landing.brand}><BrandMark /><span>ClipFactory</span></Link>
        <p>The whole story, kept in sync.</p>
        <nav aria-label="Footer navigation"><Link href="/legal/terms">Terms</Link><Link href="/legal/privacy">Privacy</Link><a href="mailto:hello@clipfactory.app">Get in touch</a></nav>
        <small>© {new Date().getFullYear()} ClipFactory</small>
      </footer>
    </div>
  );
}
