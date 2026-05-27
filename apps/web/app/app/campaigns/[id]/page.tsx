import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/ui/container";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { SubmitJobForm } from "./submit-job-form";

export const metadata = { title: "Campaign" };

type JobRow = {
  id: string;
  source_url: string;
  status: string;
  target_clip_count: number;
  queued_at: string;
};

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createSupabaseServerClient();

  const { data: campaign } = await supabase
    .from("campaigns")
    .select("id, name, audience, niche, tone, goal, avoid_topics, example_hooks, created_at")
    .eq("id", id)
    .maybeSingle();

  if (!campaign) {
    notFound();
  }

  const { data: jobs } = await supabase
    .from("jobs")
    .select("id, source_url, status, target_clip_count, queued_at")
    .eq("campaign_id", id)
    .order("queued_at", { ascending: false })
    .limit(50);

  return (
    <Container className="py-10">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Campaign</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{campaign.name}</h1>
        </div>
        <Link href="/app" className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">← Back</Link>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <Card title="Audience" value={campaign.audience || "—"} />
        <Card title="Niche" value={campaign.niche || "—"} />
        <Card title="Tone" value={campaign.tone || "—"} />
        <Card title="Clip series goal" value={campaign.goal || "—"} />
        <Card title="Avoid" value={(campaign.avoid_topics || []).join(", ") || "—"} />
        <Card title="Hooks" value={(campaign.example_hooks || []).slice(0, 3).join(" / ") || "—"} />
      </div>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Submit a video</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          Paste a YouTube URL. Each job consumes 1 credit per minute of source.
        </p>
        <div className="pro-panel mt-4 rounded-lg p-5">
          <SubmitJobForm campaignId={String(campaign.id)} />
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Jobs in this campaign</h2>
        <div className="pro-card mt-4 overflow-hidden rounded-lg">
          {(jobs?.length ?? 0) === 0 ? (
            <p className="p-6 text-sm text-[var(--color-muted-foreground)]">No jobs yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {(jobs ?? []).map((j: JobRow) => (
                <li
                  key={j.id}
                  className="flex items-center justify-between gap-4 p-4 transition-colors duration-200 hover:bg-white/[0.035]"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm">{j.source_url}</p>
                    <p className="mt-0.5 text-xs text-[var(--color-muted-foreground)]">
                      <span className="status-pill mr-2">{j.status}</span>
                      {new Date(j.queued_at).toLocaleString()}
                    </p>
                  </div>
                  <a href={`/app/jobs/${j.id}`} className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">
                    Open →
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </Container>
  );
}

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div className="pro-card rounded-lg p-4">
      <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">{title}</p>
      <p className="mt-1 text-sm">{value}</p>
    </div>
  );
}
