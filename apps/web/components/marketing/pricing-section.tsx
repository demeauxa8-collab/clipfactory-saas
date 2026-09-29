import Link from "next/link";
import type { Route } from "next";
import { ArrowUpRight, Check } from "lucide-react";
import mobile from "./pricing-mobile.module.css";
import styles from "@/components/prototypes/redesign/edit-axis-story.module.css";

export function PricingSection({ startHref, standalone = false }: { startHref: Route; standalone?: boolean }) {
  const Heading = standalone ? "h1" : "h2";
  return (
    <section
      id="pricing"
      className={`${styles.pricingSection} ${mobile.section}`}
      aria-labelledby="pricing-title-v6"
    >
      <div className={styles.pricingIntro}>
        <div>
          <p>{standalone ? "Pricing" : "One source. Or a whole series."}</p>
          <Heading id="pricing-title-v6">{standalone ? <>One source.<br />Or a whole series.</> : "Give every source a place."}</Heading>
        </div>
        <div>
          <p>
            Start with one video on Starter. Pro brings up to five YouTube videos
            into one series, with a shared campaign brief and results for each source.
          </p>
        </div>
      </div>

      <nav className={mobile.planNav} aria-label="Choose a plan">
        <a href="#starter-plan">Starter <span>€29 / month</span></a>
        <a href="#pro-plan">Pro <span>€79 · Coming soon</span></a>
      </nav>

      <div id="starter-plan" className={`${styles.priceLedger} ${mobile.plan}`}>
        <div className={styles.priceAmount} data-pricing-amount>
          <span>Starter</span>
          <div>
            <strong>€29</strong>
            <small>per month</small>
          </div>
          <p>300 credits each month</p>
          <Link href={startHref}>
            Create your campaign <ArrowUpRight />
          </Link>
        </div>
        <div className={styles.priceRules} data-pricing-rules>
          {[
            [
              "Credits",
              "300 credits each month",
              "Credit use is confirmed after the source duration is read.",
            ],
            [
              "Source",
              "Up to 30 minutes per source",
              "One YouTube or Vimeo video per job. Multi-source series require Pro.",
            ],
            [
              "Cuts",
              "Request up to 3 clips",
              "Quality checks may return fewer distinct cuts.",
            ],
            [
              "Delivery",
              "Finished vertical renders",
              "Burned captions, download and no watermark.",
            ],
            [
              "Capacity",
              "One active analysis at a time",
              "Finished clips remain available while the next source is prepared.",
            ],
          ].map(([label, title, description]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{title}</strong>
              <p>{description}</p>
              <Check />
            </div>
          ))}
        </div>
      </div>

      <div id="pro-plan" className={`${styles.priceLedger} ${mobile.plan}`}>
        <div className={styles.priceAmount} data-pricing-amount>
          <span>Pro · Coming soon</span>
          <div>
            <strong>€79</strong>
            <small>per month</small>
          </div>
          <p>1,000 credits each month</p>
          {standalone ? (
            <a href="mailto:hello@clipfactory.app?subject=Pro%20plan%20waitlist">
              Get notified <ArrowUpRight aria-hidden="true" />
            </a>
          ) : (
            <Link href="/pricing">Explore Pro <ArrowUpRight aria-hidden="true" /></Link>
          )}
          <p>Not open for subscriptions yet.</p>
        </div>
        <div className={styles.priceRules} data-pricing-rules>
          {[
            [
              "Credits",
              "1,000 credits each month",
              "Credit use is confirmed after the source duration is read.",
            ],
            [
              "Source",
              "Up to 5 videos per series",
              "YouTube videos, up to 60 minutes each. One shared campaign brief.",
            ],
            [
              "Cuts",
              "Request up to 3 clips per video",
              "Each clip comes from one source. Footage from different videos is not mixed.",
            ],
            [
              "Delivery",
              "Finished vertical renders",
              "Burned captions, download and no watermark.",
            ],
            [
              "Capacity",
              "One active analysis at a time",
              "Sources run in order. Results stay grouped, even if one source fails.",
            ],
          ].map(([label, title, description]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{title}</strong>
              <p>{description}</p>
              <Check />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

