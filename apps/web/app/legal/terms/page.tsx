import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata = { title: "Terms" };

export default function TermsPage() {
  return (
    <>
      <MarketingNav />
      <main id="main-content" className="flex-1">
        <Container className="prose max-w-3xl py-16 text-[var(--color-foreground)]">
          <h1 className="text-3xl font-semibold tracking-tight">
            Terms of Service
          </h1>
          <p className="mt-4 text-[var(--color-muted-foreground)]">
            Pilot terms · Last updated 23 August 2026.
          </p>
          <p className="mt-6">
            ClipFactory provides an AI-assisted video clipping service. By
            creating an account, you agree to use the service only with content
            you have the right to process, and not to upload material protected
            by copyright that you do not own or license.
          </p>
          <p className="mt-4">
            Billing is monthly through Stripe Checkout. Credits unused at the
            end of a billing cycle do not roll over. During the pilot,
            cancellation and invoice questions are handled through support
            rather than a self-service billing portal.
          </p>
          <p className="mt-4">
            Clip selection, scores and processing times are editorial
            assistance, not guaranteed performance results. ClipFactory may
            return fewer requested clips when a source does not contain enough
            verified moments or cannot be processed safely.
          </p>
          <p className="mt-4">
            For any question, write to{" "}
            <a className="underline" href="mailto:hello@clipfactory.app">
              hello@clipfactory.app
            </a>
            .
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
