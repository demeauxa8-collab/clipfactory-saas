import { AnimatedCounter } from "./animated-counter";

const STATS = [
  { value: 5, suffix: " axes", label: "Scored components per clip" },
  { value: 14, suffix: "d", label: "Source retention before auto-delete" },
  { value: 100, suffix: "%", label: "EU-hosted infrastructure" },
  { value: 0, suffix: "%", label: "Revenue share on your clips" },
];

export function StatStrip() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-background)]">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-y-8 px-6 py-12 md:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label} className="text-center md:text-left">
            <AnimatedCounter
              to={s.value}
              suffix={s.suffix}
              className="text-3xl font-semibold tabular-nums text-[var(--color-brand)] md:text-4xl"
            />
            <p className="mt-1 text-xs text-[var(--color-muted-foreground)] md:text-sm">
              {s.label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
