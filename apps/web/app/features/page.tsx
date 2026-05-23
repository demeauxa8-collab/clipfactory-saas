import type { Metadata } from "next";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { Brain, Eye, GitBranch, ListChecks, Sparkles, Target } from "lucide-react";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Campaign-first AI clipping: story arcs, candidate vision, explained score, anti-hallucination guard, EU hosting and predictable per-minute pricing.",
  alternates: { canonical: "/features" },
};

const features = [
  {
    icon: Target,
    title: "Campaign-first selection",
    body: "Every job is tied to a campaign brief (audience, niche, tone, goal, hooks). The clip selection prompt includes that brief — so the picks fit the audience you actually talk to, not generic virality.",
  },
  {
    icon: GitBranch,
    title: "Story arcs across the whole video",
    body: "On long videos (≥ 5 min), we build a compact map of the entire video, then detect narrative arcs that connect distant moments (setup → payoff, promise → failure). Clips can stitch up to 3 segments from different parts of the source.",
  },
  {
    icon: Eye,
    title: "Vision on what matters",
    body: "We never run expensive vision on the full video. A cheap visual pass maps the source, then deep visual analysis runs only on the top 5 candidates. The result: real visual context without exploding cost.",
  },
  {
    icon: Brain,
    title: "Score you can argue with",
    body: "Every clip gets a number, and every number is a sum of explicit weights — hook, emotion, visual, campaign fit, editing difficulty. No mystery score. You see why we picked it, and you can disagree.",
  },
  {
    icon: ListChecks,
    title: "Anti-hallucination guard",
    body: "Before rendering, we string-match each clip’s transcript excerpt against the actual transcript. If the AI invented a moment that doesn’t exist, we drop it. We’d rather ship 2 good clips than 3 with one fake.",
  },
  {
    icon: Sparkles,
    title: "Predictable, EU-first",
    body: "1 minute of source = 1 credit. EU hosting, no watermark, vertical 1080x1920, auto captions, cancel anytime. The boring parts done right.",
  },
];

export default function FeaturesPage() {
  return (
    <>
      <BreadcrumbJsonLd items={[{ name: "Home", href: "/" }, { name: "Features", href: "/features" }]} />
      <MarketingNav />
      <main className="flex-1">
        <Container className="max-w-5xl py-20">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Features</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
            What makes ClipFactory different.
          </h1>
          <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
            Six things we do that most AI clippers don&apos;t — listed honestly, with the trade-offs.
          </p>

          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {features.map((f) => (
              <article key={f.title} className="rounded-lg border border-[var(--color-border)] p-6">
                <f.icon className="h-5 w-5" />
                <h2 className="mt-4 text-lg font-medium">{f.title}</h2>
                <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{f.body}</p>
              </article>
            ))}
          </div>

          <section className="mt-20 rounded-lg border border-[var(--color-border)] bg-[var(--color-muted)] p-8">
            <h2 className="text-xl font-semibold">Honest about what we don&apos;t do yet</h2>
            <ul className="mt-4 space-y-2 text-sm text-[var(--color-muted-foreground)]">
              <li>· No scheduling to TikTok / Reels / Shorts (manual download for now).</li>
              <li>· No public API yet (coming after the first paying customers stabilise).</li>
              <li>· No team workspaces (one user per account).</li>
              <li>· No face-tracking reframe — vertical crop is centred for now.</li>
            </ul>
          </section>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
