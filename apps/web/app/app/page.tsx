import Link from "next/link";
import { ArrowRight, Plus } from "lucide-react";
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

  return (
    <Container className="py-10">
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

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <StatCard label="Credits left" value={balance.toString()} hint="1 credit = 1 minute of source" />
        <StatCard label="Campaigns" value={(campaigns?.length ?? 0).toString()} hint="Active briefs" />
        <StatCard label="Jobs" value={(jobs?.length ?? 0).toString()} hint="Recent activity" />
      </div>

      <div className="mt-10 grid gap-8 md:grid-cols-2">
        <section>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Campaigns</h2>
            <Link href="/app/campaigns/new">
              <Button size="sm">
                <Plus className="h-4 w-4" />
                New
              </Button>
            </Link>
          </div>
          <div className="pro-card mt-4 overflow-hidden rounded-lg">
            {(campaigns?.length ?? 0) === 0 ? (
              <div className="p-6 text-sm text-[var(--color-muted-foreground)]">
                No campaigns yet. Create one to start submitting videos.
              </div>
            ) : (
              <ul className="divide-y divide-[var(--color-border)]">
                {(campaigns ?? []).map((c: CampaignRow) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between gap-4 p-4 transition-colors duration-200 hover:bg-white/[0.035]"
                  >
                    <div>
                      <p className="font-medium">{c.name}</p>
                      <p className="text-xs text-[var(--color-muted-foreground)]">{c.audience || "no audience set"}</p>
                    </div>
                    <Link
                      href={{ pathname: "/app/campaigns/[id]", query: {}, hash: "" } as never}
                      as={`/app/campaigns/${c.id}` as never}
                      className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
                    >
                      Open <ArrowRight className="inline h-3.5 w-3.5" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold">Recent jobs</h2>
          <div className="pro-card mt-4 overflow-hidden rounded-lg">
            {(jobs?.length ?? 0) === 0 ? (
              <div className="p-6 text-sm text-[var(--color-muted-foreground)]">
                No jobs yet. Open a campaign and submit a video URL.
              </div>
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
                        {j.target_clip_count} clip(s)
                      </p>
                    </div>
                    <a
                      href={`/app/jobs/${j.id}`}
                      className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
                    >
                      Open <ArrowRight className="inline h-3.5 w-3.5" />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </Container>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="pro-card rounded-lg p-5">
      <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{hint}</p>
    </div>
  );
}
