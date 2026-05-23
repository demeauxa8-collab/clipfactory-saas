import type { Metadata } from "next";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "Changelog",
  description: "What's new in ClipFactory.",
  alternates: { canonical: "/changelog" },
};

const ENTRIES: { date: string; title: string; body: string[] }[] = [
  {
    date: "2026-05-22",
    title: "Story-first pipeline",
    body: [
      "Long videos (≥ 5 min) now build a compact video map and detect narrative arcs across distant moments.",
      "Clips can be multi-segment montages (setup → payoff) when the source has a story.",
      "Vision runs in two passes: cheap on the whole video, deep only on the top 5 candidates.",
      "Anti-hallucination guard verifies each transcript excerpt against the actual transcript.",
    ],
  },
  {
    date: "2026-05-21",
    title: "Public beta launch",
    body: [
      "Starter plan at 29€ / month, 300 credits.",
      "Campaign briefs: each job ties to an audience, niche, tone, goal.",
      "Per-clip score with explicit breakdown.",
      "EU hosting end to end.",
    ],
  },
];

export default function ChangelogPage() {
  return (
    <>
      <BreadcrumbJsonLd items={[{ name: "Home", href: "/" }, { name: "Changelog", href: "/changelog" }]} />
      <MarketingNav />
      <main className="flex-1">
        <Container className="max-w-3xl py-20">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Changelog</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">What&apos;s new.</h1>

          <ul className="mt-12 space-y-12">
            {ENTRIES.map((e) => (
              <li key={e.date} className="border-l-2 border-[var(--color-border)] pl-6">
                <time className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
                  {e.date}
                </time>
                <h2 className="mt-1 text-xl font-semibold">{e.title}</h2>
                <ul className="mt-3 space-y-2 text-sm text-[var(--color-muted-foreground)]">
                  {e.body.map((b, i) => (
                    <li key={i}>· {b}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
