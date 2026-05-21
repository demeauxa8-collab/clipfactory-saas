import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";

export const metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <>
      <MarketingNav />
      <main className="flex-1">
        <Container className="prose max-w-3xl py-16 text-[var(--color-foreground)]">
          <h1 className="text-3xl font-semibold tracking-tight">Privacy Policy</h1>
          <p className="mt-4 text-[var(--color-muted-foreground)]">
            Draft policy. Final version will be published before public launch.
          </p>
          <p className="mt-6">
            We store the bare minimum: your email, your subscription state, the URLs you submit, and the clips we produce for you. Source videos are deleted within 14 days. Rendered clips are kept 60 days unless your plan says otherwise.
          </p>
          <p className="mt-4">
            We use Supabase (EU region) for authentication and database, Cloudflare R2 for storage, Stripe for billing, OpenAI for transcription, and Anthropic for analysis. Each provider processes the minimum data required for the job.
          </p>
          <p className="mt-4">
            You can request a full export or deletion of your account by emailing <a className="underline" href="mailto:hello@clipfactory.app">hello@clipfactory.app</a>.
          </p>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
