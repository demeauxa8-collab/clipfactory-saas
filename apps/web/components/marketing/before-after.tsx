/**
 * Side-by-side: a generic AI clipper's pick vs ClipFactory's pick.
 * The goal isn't to caricature — it's to make the differentiator concrete.
 */
export function BeforeAfter() {
  const items = [
    {
      label: "Generic AI clipper",
      title: "Random clips from the transcript",
      bullets: [
        "Often picks loud sentences only",
        "Same style of output for every series goal",
        "One score, little explanation",
        "May miss what happens on screen",
        "Usually cuts one continuous timestamp",
      ],
      tone: "muted",
    },
    {
      label: "ClipFactory",
      title: "A series built around your goal",
      bullets: [
        "Uses your audience, niche, tone and series objective",
        "Can connect setup, proof and payoff moments minutes apart",
        "Explains hook, emotion, visual proof, fit and editability",
        "Checks visuals on the best candidate moments",
        "Checks the quote before rendering the clip",
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
            "rounded-[1.25rem] border p-7 " +
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
