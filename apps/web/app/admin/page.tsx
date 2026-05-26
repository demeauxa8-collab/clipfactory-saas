import { Container } from "@/components/ui/container";
import { adminFetch } from "@/lib/admin-api";

type Overview = {
  mrr_cents: number;
  active_subscriptions: number;
  users_total: number;
  users_new_30d: number;
  jobs_total: number;
  jobs_running: number;
  jobs_failed_30d: number;
  clips_generated: number;
  fallback_used_30d: number;
  credits_outstanding: number;
};

export default async function AdminOverviewPage() {
  let data: Overview | null = null;
  let error: string | null = null;
  try {
    data = await adminFetch<Overview>("/admin/overview");
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown_error";
  }

  return (
    <Container className="py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
      {error && (
        <div className="mt-4 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-muted)] p-3 text-sm text-[var(--color-foreground)]">
          Failed to load admin overview: <code>{error}</code>
        </div>
      )}
      {data && (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card title="MRR" value={`${(data.mrr_cents / 100).toFixed(0)}€`} hint={`${data.active_subscriptions} active sub${data.active_subscriptions === 1 ? "" : "s"}`} />
            <Card title="Users" value={data.users_total.toString()} hint={`+${data.users_new_30d} last 30d`} />
            <Card title="Jobs running" value={data.jobs_running.toString()} hint={`${data.jobs_total} total`} />
            <Card title="Failed 30d" value={data.jobs_failed_30d.toString()} hint={`${data.fallback_used_30d} used fallback`} />
            <Card title="Clips generated" value={data.clips_generated.toString()} hint="lifetime" />
            <Card title="Credits outstanding" value={data.credits_outstanding.toString()} hint="all users sum" />
          </div>

          <section className="pro-card mt-10 rounded-lg p-6">
            <h2 className="text-sm font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">Quick links</h2>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              <li><a href="/admin/users" className="text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">All users →</a></li>
              <li><a href="/admin/jobs?status=failed" className="text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">Recent failed jobs →</a></li>
              <li><a href="/admin/jobs?status=queued" className="text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">Jobs in queue →</a></li>
              <li><a href="/admin/finance" className="text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">Monthly P&L →</a></li>
            </ul>
          </section>
        </>
      )}
    </Container>
  );
}

function Card({ title, value, hint }: { title: string; value: string; hint: string }) {
  return (
    <div className="pro-card rounded-lg p-5">
      <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">{title}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{hint}</p>
    </div>
  );
}
