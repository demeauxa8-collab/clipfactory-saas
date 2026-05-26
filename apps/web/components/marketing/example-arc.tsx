/**
 * The "Lamborghini" example makes multi-part clips concrete.
 * Shown on the landing and on /features.
 */
export function ExampleArc() {
  const segments = [
    { time: "02:00", role: "Setup", text: "He just bought a Lamborghini." },
    { time: "12:30", role: "Payoff", text: "He crashes it leaving the parking lot." },
  ];

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-semibold">
          Example: a 25-minute vlog → one viral 40-second clip
        </h3>
        <span className="rounded bg-[var(--color-brand)] px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-[var(--color-brand-foreground)]">
          2-part clip
        </span>
      </div>
      <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
        The setup and payoff are 10 minutes apart in the source video. ClipFactory
        finds the connection, combines both moments, and explains why this short works.
      </p>

      <ol className="mt-6 space-y-3">
        {segments.map((s) => (
          <li
            key={s.role}
            className="flex items-center gap-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted)] p-4"
          >
            <span className="rounded bg-[var(--color-foreground)] px-2 py-1 font-mono text-xs text-[var(--color-background)]">
              {s.time}
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              {s.role}
            </span>
            <span className="text-sm">{s.text}</span>
          </li>
        ))}
      </ol>

      <div className="mt-6 flex items-center justify-between rounded-lg border border-[var(--color-brand)] bg-[var(--color-brand-soft)]/40 p-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Final montage
          </p>
          <p className="mt-1 text-sm font-medium">
            40 s vertical clip · captions burned · score 91/100
          </p>
        </div>
        <div className="font-mono text-2xl font-bold tabular-nums text-[var(--color-brand)]">
          91
        </div>
      </div>
    </div>
  );
}
