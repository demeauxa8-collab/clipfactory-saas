/**
 * Side-by-side: a generic AI clipper's pick vs ClipFactory's pick.
 * The goal isn't to caricature — it's to make the differentiator concrete.
 */
export function BeforeAfter() {
  const items = [
    {
      label: "Generic AI clipper",
      title: "30 seconds, random viral picks",
      bullets: [
        "Picks loud moments by transcript only",
        "No campaign awareness — same output for every audience",
        "Single 'virality' number, no explanation",
        "Vision rarely used, never on candidates",
        "Same single window cut — no story across the video",
      ],
      tone: "muted",
    },
    {
      label: "ClipFactory",
      title: "Campaign-fit clips with explained scores",
      bullets: [
        "Reads your brief: audience, niche, tone, goal, avoid topics",
        "Maps the whole video, finds setup → payoff arcs minutes apart",
        "Scores Hook / Emotion / Visual / Fit / Editing separately — and tells you why",
        "Vision runs on candidate frames only, never on the full video (cost-controlled)",
        "Anti-hallucination check before render — fake moments are dropped",
      ],
      tone: "brand",
    },
  ] as const;

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {items.map((it) => (
        <article
          key={it.label}
          className={
            "rounded-xl border p-6 " +
            (it.tone === "brand"
              ? "border-[var(--color-brand)] bg-[var(--color-brand-soft)]/30"
              : "border-[var(--color-border)] bg-[var(--color-muted)]")
          }
        >
          <p
            className={
              "text-xs font-semibold uppercase tracking-wider " +
              (it.tone === "brand"
                ? "text-[var(--color-brand)]"
                : "text-[var(--color-muted-foreground)]")
            }
          >
            {it.label}
          </p>
          <h3 className="mt-2 text-lg font-semibold">{it.title}</h3>
          <ul className="mt-4 space-y-2 text-sm">
            {it.bullets.map((b) => (
              <li
                key={b}
                className="flex gap-2 text-[var(--color-foreground)]/90"
              >
                <span
                  aria-hidden="true"
                  className={
                    "mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full " +
                    (it.tone === "brand"
                      ? "bg-[var(--color-brand)]"
                      : "bg-[var(--color-muted-foreground)]")
                  }
                />
                {b}
              </li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
