import type { Metadata } from "next";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd, FaqJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "AI clip maker FAQ — pricing, YouTube Shorts, Reels and TikToks",
  description: "Common questions about ClipFactory: AI video clipping, pricing, YouTube and Vimeo support, EU hosting, GDPR, cancellation, watermarks and clip quality.",
  alternates: { canonical: "/faq" },
};

const FAQ: { q: string; a: string }[] = [
  {
    q: "How much does ClipFactory cost?",
    a: "Starter costs 29€/month. It includes 300 video minutes, up to 30 minutes per video and 3 clips per video. 1 credit = 1 minute of source video.",
  },
  {
    q: "Where is my data hosted?",
    a: "ClipFactory is designed around EU hosting: database in Frankfurt, storage in Europe and video processing in Germany. Source videos are deleted after 14 days, rendered clips kept 60 days.",
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
    a: "Yes. You can cancel from the billing page. Credits already granted remain usable until the period ends.",
  },
  {
    q: "What happens if a job fails?",
    a: "Credits used for that video are refunded automatically. The job stays visible in your dashboard so you can retry.",
  },
  {
    q: "How long do my clips stay available?",
    a: "Rendered clips stay available for 60 days. Source videos are deleted after 14 days. You can download clips during that window.",
  },
  {
    q: "Do you store my videos forever?",
    a: "No. Source videos are deleted after 14 days, clips after 60 days. We do not train any model on your content.",
  },
  {
    q: "Is ClipFactory GDPR compliant?",
    a: "EU hosted, minimal data collection, full data export and deletion on request via hello@clipfactory.app. Public terms and privacy policy on the site.",
  },
  {
    q: "Can I use ClipFactory clips commercially?",
    a: "Yes — you keep all rights to clips generated from content you own or are licensed to use. You agree not to upload material you do not have the right to process.",
  },
  {
    q: "How fast is the processing?",
    a: "A 30-minute video typically takes 5 to 10 minutes to process. It is not instant because ClipFactory reads the transcript, checks the video and renders the final clips.",
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
    a: "Every clip has a thumbs up or thumbs down. Your feedback helps future picks. ClipFactory also drops clips when the quote or moment cannot be verified in the source.",
  },
  {
    q: "Can I see what the AI is doing?",
    a: "Yes. Each clip includes a simple score, a reason, the selected timestamps and a short visual summary. No mystery score.",
  },
];

export default function FaqPage() {
  return (
    <>
      <BreadcrumbJsonLd items={[{ name: "Home", href: "/" }, { name: "FAQ", href: "/faq" }]} />
      <FaqJsonLd items={FAQ} />
      <MarketingNav />
      <main className="flex-1">
        <Container className="max-w-3xl py-20">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">FAQ</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
            Common questions about AI video clipping.
          </h1>

          <dl className="mt-10 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
            {FAQ.map((item) => (
              <div key={item.q} className="py-6">
                <dt className="text-lg font-medium">{item.q}</dt>
                <dd className="mt-2 text-sm text-[var(--color-muted-foreground)]">{item.a}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-10 text-sm text-[var(--color-muted-foreground)]">
            Still unsure? Email <a href="mailto:hello@clipfactory.app" className="underline">hello@clipfactory.app</a>. I read every message.
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
