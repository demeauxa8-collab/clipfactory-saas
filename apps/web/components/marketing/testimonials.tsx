import { Quote } from "lucide-react";

const QUOTES = [
  {
    quote:
      "I stopped exporting one giant clip per podcast and started shipping three campaign-fit ones. My audience finally sees the line through them.",
    author: "Solo coach, productivity niche",
    detail: "Beta user, May 2026",
  },
  {
    quote:
      "The scored output is the part I didn't know I needed. When I tell a client a clip didn't make it, I show them the numbers.",
    author: "Founder, French content agency",
    detail: "Beta user, May 2026",
  },
  {
    quote:
      "Story arcs are real. The Lambo example you put on the homepage? That's exactly what we found in two of my last vlogs.",
    author: "YouTuber, vlogs &amp; deep-dives",
    detail: "Beta user, May 2026",
  },
];

export function Testimonials() {
  return (
    <section className="border-b border-[var(--color-border)]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Early voices
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            From the first creators who run the pipeline.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            We launched in beta. These quotes come from the operators who tested it on their real
            footage — names public on request.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {QUOTES.map((q, i) => (
            <figure
              key={i}
              className="flex flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-6"
            >
              <Quote className="h-5 w-5 text-[var(--color-brand)]" aria-hidden="true" />
              <blockquote className="mt-4 flex-1 text-sm leading-relaxed text-[var(--color-foreground)]/95">
                &ldquo;{q.quote}&rdquo;
              </blockquote>
              <figcaption className="mt-6 border-t border-[var(--color-border)] pt-4">
                <p
                  className="text-sm font-medium"
                  dangerouslySetInnerHTML={{ __html: q.author }}
                />
                <p className="text-xs text-[var(--color-muted-foreground)]">{q.detail}</p>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
