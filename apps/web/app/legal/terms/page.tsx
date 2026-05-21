import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata = { title: "Terms" };

export default function TermsPage() {
  return (
    <>
      <MarketingNav />
      <main className="flex-1">
        <Container className="prose max-w-3xl py-16 text-[var(--color-foreground)]">
          <h1 className="text-3xl font-semibold tracking-tight">Terms of Service</h1>
          <p className="mt-4 text-[var(--color-muted-foreground)]">
            Draft terms. Final version will be published before public launch.
          </p>
          <p className="mt-6">
            ClipFactory provides an AI-assisted video clipping service. By creating an account, you agree to use the service only with content you have the right to process, and not to upload material protected by copyright that you do not own or license.
          </p>
          <p className="mt-4">
            Billing is monthly via Stripe. Credits unused at the end of a billing cycle do not roll over. You can cancel at any time from your account.
          </p>
          <p className="mt-4">
            For any question, write to <a className="underline" href="mailto:hello@clipfactory.app">hello@clipfactory.app</a>.
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
