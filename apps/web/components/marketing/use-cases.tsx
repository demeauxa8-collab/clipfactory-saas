import Link from "next/link";
import { ArrowUpRight, Mic, Building2, Lightbulb } from "lucide-react";

const CASES = [
  {
    icon: Lightbulb,
    persona: "Solo creators",
    title: "Turn one long video into weekly clips.",
    body: "Paste a long video and get 3 vertical clips for TikTok, Reels and Shorts. The picks match your audience, not just random viral moments.",
    bullets: [
      "1 long video -> 3 short clips",
      "Your tone, hooks and goals",
      "Simple score so you know what to post",
    ],
    href: "/use-cases/creators",
  },
  {
    icon: Mic,
    persona: "Coaches &amp; podcasters",
    title: "Cut strong moments from long episodes.",
    body: "Find the best questions, reactions and before-and-after moments inside a 60 to 90 minute conversation. Each clip is ready for TikTok, Reels and Shorts.",
    bullets: [
      "Multi-part clips when the story needs it",
      "Captions included, no manual cleanup",
      "Same message across every platform",
    ],
    href: "/use-cases/creators",
  },
  {
    icon: Building2,
    persona: "Agencies",
    title: "Make client clips faster.",
    body: "Create a simple brief for each client, process videos in a queue, and show why each clip was selected. Less debating, faster delivery.",
    bullets: [
      "One brief per client",
      "Score and explanation for sign-off",
      "Predictable video-minute cost",
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
            Use cases
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            AI video clipping for creators, podcasts and agencies.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Tell ClipFactory who you talk to. The clip selection changes for that audience.
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
                See this use case
                <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
