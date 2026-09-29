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
  series_id: string | null;
};

type SeriesRow = { id: string; created_at: string };

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

  const [{ data: jobs }, { data: series }, { data: subscription }] = await Promise.all([
    supabase.from("jobs")
      .select("id, source_url, status, target_clip_count, queued_at, series_id")
      .eq("campaign_id", id).order("queued_at", { ascending: false }).limit(50),
    supabase.from("clip_series")
      .select("id, created_at")
      .eq("campaign_id", id).order("created_at", { ascending: false }).limit(20),
    supabase.from("subscriptions")
      .select("plan_code")
      .in("status", ["active", "trialing"])
      .order("current_period_end", { ascending: false }).limit(1).maybeSingle(),
  ]);
  const { data: plan } = subscription
    ? await supabase.from("plan_definitions")
      .select("max_series_sources").eq("code", subscription.plan_code).maybeSingle()
    : { data: null };
  const maxSeriesSources = Number(plan?.max_series_sources ?? 1);
  const standaloneJobs = ((jobs ?? []) as JobRow[]).filter((job) => !job.series_id);

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
        <h2 className="text-lg font-semibold">Create clips from videos</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
          {maxSeriesSources > 1
            ? `Add up to ${maxSeriesSources} YouTube videos to one series. Each source is processed in order.`
            : "Paste one YouTube URL. Multi-video series are available with Pro."}
        </p>
        <div className="pro-panel mt-4 rounded-lg p-5">
          <SubmitJobForm campaignId={String(campaign.id)} maxSources={maxSeriesSources} />
        </div>
      </section>

      {(series?.length ?? 0) > 0 && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold">Clip series</h2>
          <div className="pro-card mt-4 divide-y divide-[var(--color-border)] overflow-hidden rounded-lg">
            {(series as SeriesRow[]).map((item) => (
              <Link key={item.id} href={`/app/series/${item.id}`} className="flex items-center justify-between gap-4 p-4 text-sm hover:bg-white/[0.035]">
                <span>Series created {new Date(item.created_at).toLocaleString()}</span>
                <span className="text-[var(--color-muted-foreground)]">Open →</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Single-video jobs</h2>
        <div className="pro-card mt-4 overflow-hidden rounded-lg">
          {standaloneJobs.length === 0 ? (
            <p className="p-6 text-sm text-[var(--color-muted-foreground)]">No single-video jobs yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {standaloneJobs.map((j) => (
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
