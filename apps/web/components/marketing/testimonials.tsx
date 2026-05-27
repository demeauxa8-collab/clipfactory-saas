import { CheckCircle2 } from "lucide-react";

const POINTS = [
  {
    title: "Easy to understand",
    body:
      "Every clip comes with a simple score and a short reason, so you know why it was selected.",
  },
  {
    title: "Built for full videos",
    body:
      "ClipFactory can connect a setup and a payoff across the whole source video, not only cut one timestamp.",
  },
  {
    title: "Visual checks included",
    body:
      "The product checks what happens on screen so the clip makes sense visually, not only in the transcript.",
  },
];

export function Testimonials() {
  return (
    <section className="border-b border-[var(--color-border)]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Product proof
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            What the AI clip maker has to prove.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            No fake testimonials before launch. The page should explain the product in words
            a creator or agency client can verify quickly.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {POINTS.map((p) => (
            <article
              key={p.title}
              className="flex flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-6"
            >
              <CheckCircle2 className="h-5 w-5 text-[var(--color-brand)]" aria-hidden="true" />
              <h3 className="mt-4 text-lg font-medium">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                {p.body}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
