import { Container } from "@/components/ui/container";
import { adminFetch } from "@/lib/admin-api";

type Job = {
  job_id: string;
  user_id: string;
  user_email: string;
  campaign_id: string | null;
  source_url: string;
  status: string;
  current_step: string | null;
  duration_seconds: number | null;
  credits_charged: number | null;
  total_cost_estimate_cents: number | null;
  fallback_used: boolean;
  error_code: string | null;
  queued_at: string;
};

const STATUS_FILTERS = ["all", "queued", "downloading", "transcribing", "analyzing", "rendering", "completed", "failed"];

export default async function AdminJobsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const filter = status && STATUS_FILTERS.includes(status) ? status : "all";

  let jobs: Job[] = [];
  let error: string | null = null;
  try {
    jobs = await adminFetch<Job[]>(`/admin/jobs?limit=200${filter !== "all" ? `&status=${filter}` : ""}`);
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown_error";
  }

  return (
    <Container className="py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Jobs ({jobs.length})</h1>

      <div className="mt-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((s) => (
          <a
            key={s}
            href={s === "all" ? "/admin/jobs" : `/admin/jobs?status=${s}`}
            className={
              "rounded-md border px-3 py-1 text-xs " +
              (filter === s
                ? "border-[var(--color-foreground)] bg-[var(--color-foreground)] text-[var(--color-background)]"
                : "border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]")
            }
          >
            {s}
          </a>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-muted)] p-3 text-sm text-[var(--color-foreground)]">{error}</div>
      )}

      <div className="pro-card mt-6 overflow-x-auto rounded-lg">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
            <tr>
              <th className="px-3 py-3">When</th>
              <th className="px-3 py-3">User</th>
              <th className="px-3 py-3">Source</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3 text-right">Dur</th>
              <th className="px-3 py-3 text-right">Credits</th>
              <th className="px-3 py-3 text-right">Cost</th>
              <th className="px-3 py-3">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {jobs.map((j) => (
              <tr key={j.job_id} className="transition-colors duration-200 hover:bg-white/[0.035]">
                <td className="px-3 py-3 text-xs text-[var(--color-muted-foreground)]">
                  {new Date(j.queued_at).toLocaleString("en-GB")}
                </td>
                <td className="px-3 py-3 font-mono text-xs">{j.user_email}</td>
                <td className="px-3 py-3 max-w-xs truncate text-xs" title={j.source_url}>{j.source_url}</td>
                <td className="px-3 py-3">
                  <span
                    className={
                      "rounded-sm px-1.5 py-0.5 text-[10px] font-semibold uppercase " +
                      (j.status === "completed"
                        ? "border border-[var(--color-border)] bg-[var(--color-foreground)] text-[var(--color-background)]"
                        : j.status === "failed"
                        ? "border border-[var(--color-danger)]/50 bg-[var(--color-muted)] text-[var(--color-danger)]"
                        : "border border-[var(--color-border)] bg-[var(--color-muted)] text-[var(--color-foreground)]")
                    }
                  >
                    {j.status}
                  </span>
                  {j.current_step && j.status !== j.current_step && (
                    <div className="mt-0.5 text-[10px] text-[var(--color-muted-foreground)]">{j.current_step}</div>
                  )}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">{j.duration_seconds ? `${j.duration_seconds}s` : "—"}</td>
                <td className="px-3 py-3 text-right tabular-nums">{j.credits_charged ?? "—"}</td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {j.total_cost_estimate_cents != null ? `${(j.total_cost_estimate_cents / 100).toFixed(2)}€` : "—"}
                </td>
                <td className="px-3 py-3 text-xs">
                  {j.fallback_used && <span className="mr-2 text-[var(--color-brand)]">fallback</span>}
                  {j.error_code && <span className="text-[var(--color-danger)]">{j.error_code}</span>}
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-[var(--color-muted-foreground)]">No jobs match.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Container>
  );
}
