import { Container } from "@/components/ui/container";
import { NewCampaignForm } from "./new-campaign-form";

export const metadata = { title: "New campaign" };

export default function NewCampaignPage() {
  return (
    <Container className="py-10">
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight">New campaign</h1>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Tell ClipFactory who the clips are for, what the series should achieve,
          and what kind of moments to avoid. Every video in this campaign uses this brief.
        </p>
        <div className="pro-panel mt-8 rounded-lg p-6">
          <NewCampaignForm />
        </div>
      </div>
    </Container>
  );
}
