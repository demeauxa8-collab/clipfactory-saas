import Link from "next/link";
import { ArrowUpRight, Mic, Building2, Lightbulb } from "lucide-react";

const CASES = [
  {
    icon: Lightbulb,
    persona: "Solo creators",
    title: "Build your library, week after week.",
    body: "Drop a long-form, get 3 vertical shorts that match the audience you're growing — not the algorithm's favourite chaos.",
    bullets: [
      "1 long-form → 3 campaign-fit clips",
      "Your tone, your hooks, your goals",
      "Honest score so you know what to post",
    ],
    href: "/use-cases/creators",
  },
  {
    icon: Mic,
    persona: "Coaches &amp; podcasters",
    title: "Turn your hour-long episodes into proof.",
    body: "Story arcs find the setup → payoff moments inside a 90-minute conversation. Each clip ships ready for TikTok, Reels and Shorts.",
    bullets: [
      "Multi-segment clips from distant moments",
      "Captions burned in, no manual cleanup",
      "Same picks across platforms — coherent voice",
    ],
    href: "/use-cases/creators",
  },
  {
    icon: Building2,
    persona: "Agencies",
    title: "Serve more clients without losing taste.",
    body: "One campaign brief per client, one queue, scored output you can defend to the brand. No more debating which clip to ship.",
    bullets: [
      "Per-client campaign briefs",
      "Defensible score breakdown for sign-off",
      "Predictable per-minute cost — easy to bill",
    ],
    href: "/use-cases/agencies",
  },
] as const;

export function UseCases() {
  return (
    <section className="border-b border-[var(--color-border)]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Built for these workflows
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Whoever you are, the brief is what matters.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Three workflows, one engine. Tell us who you talk to — the picks adapt.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {CASES.map((c) => (
            <article
              key={c.persona}
              className="group flex flex-col rounded-lg border border-[var(--color-border)] p-6 transition-colors hover:border-[var(--color-brand)]"
            >
              <c.icon className="h-5 w-5 text-[var(--color-brand)]" />
              <p
                className="mt-4 text-xs font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]"
                dangerouslySetInnerHTML={{ __html: c.persona }}
              />
              <h3 className="mt-1 text-lg font-medium">{c.title}</h3>
              <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{c.body}</p>
              <ul className="mt-4 space-y-1.5 text-sm">
                {c.bullets.map((b) => (
                  <li key={b} className="flex gap-2 text-[var(--color-foreground)]/90">
                    <span
                      aria-hidden="true"
                      className="mt-1.5 inline-block h-1 w-1 shrink-0 rounded-full bg-[var(--color-brand)]"
                    />
                    {b}
                  </li>
                ))}
              </ul>
              <Link
                href={c.href as never}
                className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-[var(--color-brand)] hover:underline"
              >
                See the workflow
                <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
