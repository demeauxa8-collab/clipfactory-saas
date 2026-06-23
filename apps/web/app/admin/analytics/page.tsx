import { Container } from "@/components/ui/container";
import { adminFetch } from "@/lib/admin-api";

export const metadata = { title: "Analytics" };

type EventStat = {
  event_name: string;
  source: string;
  events: number;
  users: number;
};

const WINDOWS = [7, 14, 30] as const;

export default async function AdminAnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const params = await searchParams;
  const days = clampDays(params.days);

  let stats: EventStat[] = [];
  let error: string | null = null;
  try {
    stats = await adminFetch<EventStat[]>(`/admin/analytics?days=${days}`);
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown_error";
  }

  const totalEvents = stats.reduce((acc, s) => acc + s.events, 0);
  const eventTypes = new Set(stats.map((s) => s.event_name)).size;
  const bySource = groupBy(stats, (s) => s.source);
  const sources = Object.keys(bySource).sort();
  const maxEvents = stats.reduce((m, s) => Math.max(m, s.events), 0) || 1;

  return (
    <Container className="py-10">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--color-muted-foreground)]">
            Product
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Analytics</h1>
          <p className="mt-2 max-w-2xl text-sm text-[var(--color-muted-foreground)]">
            First-party event volume from <code className="text-xs">analytics_events</code> over the
            last {days} days. Mirrored to PostHog when configured.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-muted)] p-1">
          {WINDOWS.map((w) => (
            <a
              key={w}
              href={`/admin/analytics?days=${w}`}
              className={
                "rounded-full px-3 py-1 text-xs transition-colors " +
                (w === days
                  ? "bg-[var(--color-brand)] text-[var(--color-brand-foreground)]"
                  : "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]")
              }
            >
              {w}d
            </a>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-muted)] p-3 text-sm">
          Failed to load analytics: <code>{error}</code>
        </div>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <StatCard title="Total events" value={fmt(totalEvents)} hint={`last ${days} days`} />
        <StatCard title="Event types" value={eventTypes.toString()} hint="distinct names" />
        <StatCard
          title="Sources"
          value={sources.length.toString()}
          hint={sources.join(" · ") || "none yet"}
        />
      </div>

      {/* Source split */}
      {totalEvents > 0 && (
        <div className="pro-card mt-4 rounded-lg p-5">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">By source</p>
          <div className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-foreground)_8%,transparent)]">
            {sources.map((src) => {
              const n = bySource[src].reduce((a, s) => a + s.events, 0);
              return (
                <div
                  key={src}
                  className="h-full"
                  style={{ width: `${(n / totalEvents) * 100}%`, backgroundColor: sourceColor(src) }}
                  title={`${src}: ${n}`}
                />
              );
            })}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-muted-foreground)]">
            {sources.map((src) => (
              <span key={src} className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: sourceColor(src) }} />
                {src} · {fmt(bySource[src].reduce((a, s) => a + s.events, 0))}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Event table */}
      <div className="pro-card mt-6 overflow-hidden rounded-lg">
        <table className="w-full text-sm">
          <thead className="border-b border-[var(--color-border)] text-left text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
            <tr>
              <th className="px-4 py-3">Event</th>
              <th className="px-4 py-3">Source</th>
              <th className="hidden px-4 py-3 sm:table-cell">Volume</th>
              <th className="px-4 py-3 text-right">Events</th>
              <th className="px-4 py-3 text-right">Users</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {stats.map((s) => (
              <tr key={`${s.event_name}-${s.source}`} className="transition-colors hover:bg-white/[0.035]">
                <td className="px-4 py-3 font-medium">{s.event_name}</td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] px-2 py-0.5 text-xs text-[var(--color-muted-foreground)]"
                  >
                    <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: sourceColor(s.source) }} />
                    {s.source}
                  </span>
                </td>
                <td className="hidden px-4 py-3 sm:table-cell">
                  <div className="h-1.5 w-40 overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-foreground)_8%,transparent)]">
                    <div
                      className="h-full rounded-full bg-[var(--color-brand)]"
                      style={{ width: `${(s.events / maxEvents) * 100}%` }}
                    />
                  </div>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{fmt(s.events)}</td>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-muted-foreground)]">{fmt(s.users)}</td>
              </tr>
            ))}
            {stats.length === 0 && !error && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--color-muted-foreground)]">
                  No events in this window yet. They will appear as users interact with the product.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Container>
  );
}

function StatCard({ title, value, hint }: { title: string; value: string; hint: string }) {
  return (
    <div className="pro-card rounded-lg p-5">
      <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">{title}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 truncate text-xs text-[var(--color-muted-foreground)]">{hint}</p>
    </div>
  );
}

function clampDays(raw?: string): number {
  const n = Number(raw);
  if (n === 7 || n === 14 || n === 30) return n;
  return 14;
}

function groupBy<T>(rows: T[], key: (row: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const row of rows) {
    const k = key(row);
    (out[k] ??= []).push(row);
  }
  return out;
}

function sourceColor(source: string): string {
  if (source === "web") return "var(--color-brand)";
  if (source === "api") return "var(--color-vision)";
  if (source === "worker") return "var(--color-warn)";
  return "var(--color-muted-foreground)";
}

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}
