import { Container } from "@/components/ui/container";
import { adminFetch } from "@/lib/admin-api";

type FinanceMonth = {
  month: string;
  revenue_cents: number;
  transcription_cost_cents: number;
  video_map_cost_cents: number;
  deep_vision_cost_cents: number;
  text_analysis_cost_cents: number;
  storage_bytes: number;
  jobs_completed: number;
  jobs_failed: number;
};

export default async function AdminFinancePage() {
  let months: FinanceMonth[] = [];
  let error: string | null = null;
  try {
    months = await adminFetch<FinanceMonth[]>("/admin/finance?months=6");
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown_error";
  }

  return (
    <Container className="py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Finance</h1>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
        Monthly P&amp;L estimate. Costs are derived from the worker&apos;s self-reported model — wire to real provider invoices in V2.
      </p>
      {error && (
        <div className="mt-4 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-muted)] p-3 text-sm text-[var(--color-foreground)]">{error}</div>
      )}

      <div className="pro-card mt-6 overflow-x-auto rounded-lg">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
            <tr>
              <th className="px-3 py-3">Month</th>
              <th className="px-3 py-3 text-right">Revenue</th>
              <th className="px-3 py-3 text-right">Transcription</th>
              <th className="px-3 py-3 text-right">Video map</th>
              <th className="px-3 py-3 text-right">Deep vision</th>
              <th className="px-3 py-3 text-right">Text LLM</th>
              <th className="px-3 py-3 text-right">Total cost</th>
              <th className="px-3 py-3 text-right">Margin</th>
              <th className="px-3 py-3 text-right">Storage</th>
              <th className="px-3 py-3 text-right">Done</th>
              <th className="px-3 py-3 text-right">Fail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {months.map((m) => {
              const total =
                m.transcription_cost_cents +
                m.video_map_cost_cents +
                m.deep_vision_cost_cents +
                m.text_analysis_cost_cents;
              const margin = m.revenue_cents - total;
              return (
                <tr key={m.month} className="transition-colors duration-200 hover:bg-white/[0.035]">
                  <td className="px-3 py-3 font-mono">{m.month}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{(m.revenue_cents / 100).toFixed(2)}€</td>
                  <td className="px-3 py-3 text-right tabular-nums">{(m.transcription_cost_cents / 100).toFixed(2)}€</td>
                  <td className="px-3 py-3 text-right tabular-nums">{(m.video_map_cost_cents / 100).toFixed(2)}€</td>
                  <td className="px-3 py-3 text-right tabular-nums">{(m.deep_vision_cost_cents / 100).toFixed(2)}€</td>
                  <td className="px-3 py-3 text-right tabular-nums">{(m.text_analysis_cost_cents / 100).toFixed(2)}€</td>
                  <td className="px-3 py-3 text-right tabular-nums">{(total / 100).toFixed(2)}€</td>
                  <td className={"px-3 py-3 text-right font-medium tabular-nums " + (margin >= 0 ? "text-[var(--color-foreground)]" : "text-[var(--color-danger)]")}>
                    {(margin / 100).toFixed(2)}€
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{(m.storage_bytes / 1024 ** 3).toFixed(1)} GB</td>
                  <td className="px-3 py-3 text-right tabular-nums">{m.jobs_completed}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{m.jobs_failed}</td>
                </tr>
              );
            })}
            {months.length === 0 && (
              <tr>
                <td colSpan={11} className="px-3 py-6 text-center text-[var(--color-muted-foreground)]">No data yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Container>
  );
}
