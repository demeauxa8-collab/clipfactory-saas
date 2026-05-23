import type { Metadata } from "next";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd, FaqJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Common questions about ClipFactory: pricing, EU hosting, supported sources, GDPR, cancellation, watermarks.",
  alternates: { canonical: "/faq" },
};

const FAQ: { q: string; a: string }[] = [
  {
    q: "How much does ClipFactory cost?",
    a: "29€/month for Starter: 300 credits, up to 30 min per video, 3 clips per video. 1 credit = 1 minute of source. Bigger plans (Creator, Agency) ship after Starter is stable.",
  },
  {
    q: "Where is my data hosted?",
    a: "EU regions only. Database in Frankfurt (Supabase EU), object storage in Cloudflare R2 EU, workers in Falkenstein (Hetzner Germany). Source videos are deleted after 14 days, rendered clips kept 60 days.",
  },
  {
    q: "Which video sources are supported?",
    a: "YouTube and Vimeo at launch. Direct upload and other platforms come later. URLs are validated to prevent SSRF and other security issues.",
  },
  {
    q: "Do you add a watermark?",
    a: "No watermark. Ever. Even on Starter.",
  },
  {
    q: "Can I cancel any time?",
    a: "Yes. One click in your billing page redirects you to Stripe to cancel. No friction modal cascade. Credits already granted remain usable until the period ends.",
  },
  {
    q: "What happens if a job fails?",
    a: "Credits debited for that job are fully refunded automatically. The job stays visible in your dashboard with the error code so you can retry.",
  },
  {
    q: "How long do my clips stay available?",
    a: "60 days for rendered clips, 14 days for source videos. You can download clips at any time within that window via a presigned URL.",
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
    a: "A 30-minute video typically takes 5 to 10 minutes to fully process. We do not promise instant: transcription + LLM analysis + render takes real compute.",
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
    a: "Every clip has a thumb-up / thumb-down feedback. Your feedback feeds the campaign memory and tunes future picks. We also drop any clip whose transcript excerpt doesn’t match the real transcript (anti-hallucination).",
  },
  {
    q: "Can I see what the AI is doing?",
    a: "Yes. Each clip ships with a score breakdown (hook, emotion, visual, campaign fit, editing) and a visual summary (decor, action, problems detected). No mystery score.",
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
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">Common questions.</h1>

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
