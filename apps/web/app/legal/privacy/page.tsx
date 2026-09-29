import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <>
      <MarketingNav />
      <main id="main-content" className="flex-1">
        <Container className="prose max-w-3xl py-16 text-[var(--color-foreground)]">
          <h1 className="text-3xl font-semibold tracking-tight">
            Privacy Policy
          </h1>
          <p className="mt-4 text-[var(--color-muted-foreground)]">
            Pilot privacy notice · Last updated 23 August 2026.
          </p>
          <p className="mt-6">
            We store the account and job data needed to operate the service:
            your email, subscription state, campaign briefs, submitted URLs,
            processing records, feedback and delivered clip metadata.
            ClipFactory is not intended as permanent media storage. Automated
            deletion windows are still being completed during the pilot, so
            request deletion instead of relying on an unverified fixed retention
            period.
          </p>
          <p className="mt-4">
            Authentication and the product database are configured through an EU
            Supabase project. Stripe handles checkout. Video storage and AI
            processing providers depend on the active pilot deployment; request
            the current subprocessor and processing-location list before
            submitting sensitive material. ClipFactory does not intentionally
            use submitted content to train a ClipFactory model.
          </p>
          <p className="mt-4">
            You can request a full export or deletion of your account by
            emailing{" "}
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
