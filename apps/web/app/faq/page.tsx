import type { Metadata } from "next";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd, FaqJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "AI clip maker FAQ — pricing, YouTube Shorts, Reels and TikToks",
  description:
    "Common questions about ClipFactory: AI video clipping, pricing, YouTube and Vimeo support, privacy, cancellation, watermarks and clip quality.",
  alternates: { canonical: "/faq" },
};

const FAQ: { q: string; a: string }[] = [
  {
    q: "How much does ClipFactory cost?",
    a: "Starter costs 29€/month. It includes 300 credits, sources up to 30 minutes and up to three requested clips per source. ClipFactory may return fewer clips when the source does not contain enough verified campaign moments. 1 credit = 1 minute of source video.",
  },
  {
    q: "Where is my data hosted?",
    a: "Authentication and the product database are configured on an EU Supabase project. Video storage and processing depend on the active pilot deployment; contact us for the current subprocessor and location list before submitting sensitive material.",
  },
  {
    q: "Which video sources are supported?",
    a: "YouTube and Vimeo at launch. Direct upload and other platforms come later.",
  },
  {
    q: "Do you add a watermark?",
    a: "No watermark. Ever. Even on Starter.",
  },
  {
    q: "Can I cancel any time?",
    a: "During the pilot, contact support to cancel. The billing page shows the current plan and ledger, but self-service subscription management is not live yet.",
  },
  {
    q: "What happens if a job fails?",
    a: "The job stays visible with the failed stage and no delivery is implied. Automatic refunds are not promised during the pilot; support can review the credit ledger when needed.",
  },
  {
    q: "How long do my clips stay available?",
    a: "Availability depends on the active pilot storage configuration. Download delivered clips promptly. You can request source, clip or account deletion at any time through hello@clipfactory.app.",
  },
  {
    q: "Do you store my videos forever?",
    a: "ClipFactory is not designed as permanent media storage. Automated lifecycle deletion is still being completed for the pilot, so contact support for deletion rather than relying on an unverified fixed window. ClipFactory does not intentionally use submitted content to train a ClipFactory model.",
  },
  {
    q: "Is ClipFactory GDPR compliant?",
    a: "ClipFactory minimizes account and job data and accepts access, export and deletion requests at hello@clipfactory.app. The current pilot privacy notice lists the limits of the deployment; it does not replace a customer-specific data processing review.",
  },
  {
    q: "Can I use ClipFactory clips commercially?",
    a: "Yes — you keep all rights to clips generated from content you own or are licensed to use. You agree not to upload material you do not have the right to process.",
  },
  {
    q: "How fast is the processing?",
    a: "Processing time depends on source length and the checks required. ClipFactory shows discrete stages instead of an unconfirmed completion-time estimate.",
  },
  {
    q: "Do you have an API?",
    a: "Not yet. Public API ships after the first paying customers stabilise. You can email hello@clipfactory.app to join the API waitlist.",
  },
  {
    q: "Can I work with my team on the same account?",
    a: "Team workspaces are V2. For now, one user per account. If you are an agency with multiple accounts, write to us — we will help.",
  },
  {
    q: "What if the AI picks bad clips?",
    a: "Every clip has a thumbs up or thumbs down so your judgment is recorded for review. That feedback does not silently retrain the system. ClipFactory also drops clips when the quote or moment cannot be verified in the source.",
  },
  {
    q: "Can I see what the AI is doing?",
    a: "Yes. Each clip includes a simple score, a reason, the selected timestamps and a short visual summary. No mystery score.",
  },
];

export default function FaqPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "FAQ", href: "/faq" },
        ]}
      />
      <FaqJsonLd items={FAQ} />
      <MarketingNav />
      <main id="main-content" className="flex-1">
        <Container className="max-w-3xl py-20">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
            FAQ
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
            Common questions about AI video clipping.
          </h1>

          <dl className="mt-10 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
            {FAQ.map((item) => (
              <div key={item.q} className="py-6">
                <dt className="text-lg font-medium">{item.q}</dt>
                <dd className="mt-2 text-sm text-[var(--color-muted-foreground)]">
                  {item.a}
                </dd>
              </div>
            ))}
          </dl>

          <p className="mt-10 text-sm text-[var(--color-muted-foreground)]">
            Still unsure? Email{" "}
            <a href="mailto:hello@clipfactory.app" className="underline">
              hello@clipfactory.app
            </a>
            . I read every message.
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
