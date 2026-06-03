/* eslint-disable react/no-unknown-property */
import { cn } from "@/lib/utils";

type Score = { label: string; value: number };

/**
 * Visual mockup of a generated clip card. Used in the hero and on /features.
 * Not a real video — just a static styled preview so the user grasps the output
 * in 2 seconds.
 */
export function ClipMockup({
  title = "He lost 50k because of this",
  hook = "It took him three months to admit it.",
  total = 87,
  scores = [
    { label: "Hook", value: 92 },
    { label: "Emotion", value: 80 },
    { label: "Visual", value: 88 },
    { label: "Fit", value: 90 },
    { label: "Editing", value: 75 },
  ],
  duration = "0:34",
  segments,
  className,
}: {
  title?: string;
  hook?: string;
  total?: number;
  scores?: Score[];
  duration?: string;
  segments?: { role: string; range: string }[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-[1.25rem] border border-[var(--color-border)] bg-[var(--color-muted)] p-6 shadow-[0_18px_60px_rgba(0,0,0,0.42),inset_0_1px_0_rgba(255,255,255,0.06)]",
        className
      )}
    >
      <div className="flex items-start gap-5">
        {/* Vertical preview */}
        <div
          className="relative h-56 w-32 shrink-0 overflow-hidden rounded-[0.875rem] bg-gradient-to-br from-zinc-900 to-zinc-700"
          aria-hidden="true"
        >
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute left-2 right-2 bottom-2 text-[11px] font-medium leading-tight text-white">
            &ldquo;{hook}&rdquo;
          </div>
          <div className="absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-mono tabular-nums text-white">
            {duration}
          </div>
          <div className="absolute left-2 top-2 rounded-full bg-[var(--color-brand)] px-2 py-0.5 text-[10px] font-semibold tabular-nums text-[var(--color-brand-foreground)]">
            1080×1920
          </div>
        </div>

        {/* Right column: title + total score */}
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wider tabular-nums text-[var(--color-muted-foreground)]">
            Clip 1 · {duration}
          </p>
          <p className="mt-1 truncate text-base font-semibold">{title}</p>
          <p className="mt-1 line-clamp-2 text-xs text-[var(--color-muted-foreground)]">
            {hook}
          </p>

          {segments && segments.length > 1 && (
            <ol className="mt-3 flex flex-wrap gap-1.5">
              {segments.map((s, i) => (
                <li
                  key={i}
                  className="rounded-full border border-[var(--color-border)] px-2.5 py-0.5 text-[10px] font-mono tabular-nums"
                >
                  <span className="font-semibold uppercase">{s.role}</span> {s.range}
                </li>
              ))}
            </ol>
          )}

          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1">
              <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                <span>Virality score</span>
                <span className="font-mono tabular-nums text-[var(--color-foreground)]">{total}/100</span>
              </div>
              <div className="mt-1.5 h-px w-full bg-[var(--color-border)]" aria-hidden="true">
                <div
                  className="h-px rounded-full bg-[var(--color-brand)]"
                  style={{ width: `${total}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-5 gap-2 border-t border-[var(--color-border)] pt-4 text-xs">
        {scores.map((s) => (
          <div key={s.label}>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">
              {s.label}
            </dt>
            <dd className="mt-1 flex items-center gap-1.5">
              <span className="font-mono font-semibold tabular-nums">{s.value}</span>
              <span aria-hidden="true" className="h-px flex-1">
                <span
                  className="block h-px rounded-full bg-[var(--color-brand)]"
                  style={{ width: `${s.value}%` }}
                />
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
