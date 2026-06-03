import Link from "next/link";
import { ArrowRight, Clock3, Film, Plus, Target, Wallet } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const metadata = { title: "Dashboard" };

type CampaignRow = {
  id: string;
  name: string;
  audience: string;
  created_at: string;
};

type JobRow = {
  id: string;
  source_url: string;
  status: string;
  target_clip_count: number;
  campaign_id: string | null;
  queued_at: string;
};

const RUNNING = new Set(["queued", "downloading", "transcribing", "analyzing", "rendering"]);

export default async function AppHome() {
  const supabase = await createSupabaseServerClient();
  const [{ data: campaigns }, { data: jobs }, { data: ledger }] = await Promise.all([
    supabase
      .from("campaigns")
      .select("id, name, audience, created_at")
      .order("created_at", { ascending: false })
      .limit(10),
    supabase
      .from("jobs")
      .select("id, source_url, status, target_clip_count, campaign_id, queued_at")
      .order("queued_at", { ascending: false })
      .limit(10),
    supabase.from("credit_ledger").select("delta"),
  ]);

  const balance = (ledger ?? []).reduce(
    (acc, row) => acc + (typeof row.delta === "number" ? row.delta : 0),
    0
  );
  const jobList = (jobs ?? []) as JobRow[];
  const runningCount = jobList.filter((j) => RUNNING.has(j.status)).length;
  const clipsReady = jobList
    .filter((j) => j.status === "completed")
    .reduce((acc, j) => acc + (j.target_clip_count || 0), 0);

  return (
    <Container className="py-10">
      {/* Header */}
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--color-muted-foreground)]">
            Workspace
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Dashboard
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--color-muted-foreground)]">
            Create a campaign, submit a long video, then review the generated clips,
            scores and downloads in one place.
          </p>
        </div>
        <Link href="/app/campaigns/new" className="inline-flex">
          <Button>
            <Plus className="h-4 w-4" />
            New campaign
          </Button>
        </Link>
      </div>

      {/* Metrics */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={Wallet} label="Credits left" value={balance.toString()} hint="1 credit = 1 minute of source" />
        <Metric icon={Target} label="Campaigns" value={(campaigns?.length ?? 0).toString()} hint="Active briefs" />
        <Metric icon={Clock3} label="Jobs running" value={runningCount.toString()} hint={`${jobList.length} recent`} />
        <Metric icon={Film} label="Clips ready" value={clipsReady.toString()} hint="No watermark" />
      </div>

      {/* Work area */}
      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        <section className="liquid-shell p-5 md:p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">Series goals</p>
              <h2 className="mt-1.5 text-lg font-semibold tracking-tight">Campaigns</h2>
            </div>
            <Link href="/app/campaigns/new">
              <Button size="sm">
                <Plus className="h-4 w-4" />
                New
              </Button>
            </Link>
          </div>
          {(campaigns?.length ?? 0) === 0 ? (
            <div className="rounded-[1.25rem] border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted-foreground)]">
              No campaigns yet. Create one to start submitting videos.
            </div>
          ) : (
            <div className="divide-y divide-[var(--color-border)]">
              {(campaigns ?? []).map((c: CampaignRow) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between gap-4 py-3.5 first:pt-0"
                >
                  <div className="min-w-0">
                    <p className="font-medium">{c.name}</p>
                    <p className="text-xs text-[var(--color-muted-foreground)]">{c.audience || "no audience set"}</p>
                  </div>
                  <Link
                    href={{ pathname: "/app/campaigns/[id]", query: {}, hash: "" } as never}
                    as={`/app/campaigns/${c.id}` as never}
                    className="inline-flex items-center gap-1 text-sm text-[var(--color-muted-foreground)] transition-colors hover:text-[var(--color-foreground)]"
                  >
                    Open <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="liquid-shell p-5 md:p-6">
          <div className="mb-4">
            <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">Pipeline</p>
            <h2 className="mt-1.5 text-lg font-semibold tracking-tight">Recent jobs</h2>
          </div>
          {(jobList.length ?? 0) === 0 ? (
            <div className="rounded-[1.25rem] border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted-foreground)]">
              No jobs yet. Open a campaign and submit a video URL.
            </div>
          ) : (
            <div className="divide-y divide-[var(--color-border)]">
              {jobList.map((j) => (
                <div
                  key={j.id}
                  className="flex items-center justify-between gap-4 py-3.5 first:pt-0"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm">{j.source_url}</p>
                    <p className="mt-0.5 text-xs text-[var(--color-muted-foreground)]">
                      {j.target_clip_count} clip(s)
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusPill status={j.status} />
                    <a
                      href={`/app/jobs/${j.id}`}
                      className="inline-flex items-center gap-1 text-sm text-[var(--color-muted-foreground)] transition-colors hover:text-[var(--color-foreground)]"
                    >
                      Open <ArrowRight className="h-3.5 w-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </Container>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[1.25rem] border border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-foreground)_3%,var(--color-background))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">{label}</p>
        <Icon className="h-4 w-4 text-[var(--color-brand)]" />
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{hint}</p>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone = status === "completed"
    ? "text-[var(--color-brand)] border-[color-mix(in_srgb,var(--color-brand)_45%,transparent)]"
    : status === "failed" || status === "canceled"
    ? "text-[var(--color-danger)] border-[color-mix(in_srgb,var(--color-danger)_45%,transparent)]"
    : "text-[var(--color-foreground)] border-[var(--color-border)]";
  const dot = status === "completed"
    ? "var(--color-brand)"
    : status === "failed" || status === "canceled"
    ? "var(--color-danger)"
    : "var(--color-muted-foreground)";
  return (
    <span className={"inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs " + tone}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: dot }} />
      {status}
    </span>
  );
}
