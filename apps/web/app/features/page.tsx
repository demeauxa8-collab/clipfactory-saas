import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { PipelineDiagram } from "@/components/marketing/pipeline-diagram";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import { BeforeAfter } from "@/components/marketing/before-after";
import {
  ArrowRight,
  Brain,
  Eye,
  GitBranch,
  ListChecks,
  Sparkles,
  Target,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Features — campaign-first AI clipping",
  description:
    "Story arcs across the whole video, vision on candidates only, explained scores, anti-hallucination guard, EU hosting and predictable per-minute pricing.",
  keywords: [
    "AI clipping features",
    "story arcs AI clipping",
    "explained AI score",
    "campaign clipping",
    "vertical shorts generator",
    "EU hosted AI",
    "anti-hallucination AI",
    "narrative AI clipper",
  ],
  alternates: { canonical: "/features" },
};

const FEATURES = [
  {
    icon: Target,
    title: "Campaign-first selection",
    body: "Every job inherits your campaign brief — audience, niche, tone, goal, topics to avoid, example hooks. The clip-selection prompt reads that brief, so picks fit the audience you actually talk to, not random virality.",
  },
  {
    icon: GitBranch,
    title: "Story arcs across the whole video",
    body: "On long videos (≥ 5 min), we build a compact map of the entire source, then detect narrative arcs that connect distant moments — setup at minute 2, payoff at minute 12. Multi-segment clips stitch up to 3 windows with a clean 150 ms audio crossfade.",
  },
  {
    icon: Eye,
    title: "Vision where it actually pays off",
    body: "Vision never runs on the full video — that's how generic tools blow budget. A cheap pass maps the source, then deep multimodal vision runs only on the top 5 candidate windows. Real visual context, controlled cost.",
  },
  {
    icon: Brain,
    title: "A score you can argue with",
    body: "Each clip ships with five explicit numbers: hook strength, emotion, visual proof, campaign fit, editing difficulty. No mystery score. You see exactly why we picked it, and your feedback tunes the next pick.",
  },
  {
    icon: ListChecks,
    title: "Anti-hallucination guard",
    body: "Before rendering, every transcript excerpt is string-matched against the real transcript (SequenceMatcher ratio ≥ 0.65). If the AI invented a moment that does not exist in the source, the clip is dropped. We'd rather ship 2 honest clips than 3 with a fake.",
  },
  {
    icon: Sparkles,
    title: "Predictable, EU-first",
    body: "1 minute of source = 1 credit. EU hosting (Supabase Frankfurt, Cloudflare R2 EU, Hetzner Germany), no watermark, 1080×1920 vertical, burned captions, cancel anytime. The boring parts done right.",
  },
];

const PIPELINE_DETAIL = [
  {
    step: "1. Download &amp; transcribe",
    body: "yt-dlp pulls the audio track only. Whisper API transcribes with word-level timestamps. We store the transcript, not the source file beyond 14 days.",
    cost: "~0.006€ / min",
  },
  {
    step: "2. Map the source",
    body: "Cheap visual pass (Qwen3-VL Flash via OpenRouter) sampled every ~30 s + transcript chunked. Output: a compressed map the LLM can reason on.",
    cost: "~0.01€ / 10 min source",
  },
  {
    step: "3. Find story arcs",
    body: "DeepSeek V3.2 reads the map + your campaign brief, returns 5 candidate windows with score components and rationale.",
    cost: "~0.005€ / video",
  },
  {
    step: "4. Deep vision on candidates",
    body: "Gemini 2.5 Flash runs on the top 5 windows only — face presence, action, on-screen text. Adjusts scores with visual evidence.",
    cost: "~0.02€ / candidate",
  },
  {
    step: "5. Verify &amp; render",
    body: "Anti-hallucination check, then FFmpeg crops to 1080×1920 and burns captions. Multi-segment clips get a 150 ms audio crossfade.",
    cost: "Fixed — your VPS",
  },
];

export default function FeaturesPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Features", href: "/features" },
        ]}
      />
      <MarketingNav />
      <main className="flex-1">
        {/* Intro */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Features
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              Built for clipping that actually matches your campaign.
            </h1>
            <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
              Six engineering choices that separate ClipFactory from generic AI clippers. Listed
              honestly, with the trade-offs.
            </p>

            <div className="mt-12 grid gap-6 md:grid-cols-2">
              {FEATURES.map((f) => (
                <article
                  key={f.title}
                  className="rounded-lg border border-[var(--color-border)] p-6"
                >
                  <f.icon className="h-5 w-5 text-[var(--color-brand)]" />
                  <h2 className="mt-4 text-lg font-medium">{f.title}</h2>
                  <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">{f.body}</p>
                </article>
              ))}
            </div>
          </Container>
        </section>

        {/* Pipeline detail */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                The pipeline, no black box
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Each step, what it does, what it costs.
              </h2>
              <p className="mt-3 text-[var(--color-muted-foreground)]">
                We publish per-step cost because we believe operators should know what they sell.
              </p>
            </div>

            <div className="mt-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6 md:p-10">
              <PipelineDiagram />
            </div>

            <ol className="mt-10 space-y-4">
              {PIPELINE_DETAIL.map((p, i) => (
                <li
                  key={i}
                  className="flex flex-col gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-5 md:flex-row md:items-center md:justify-between"
                >
                  <div className="min-w-0">
                    <p
                      className="text-sm font-semibold"
                      dangerouslySetInnerHTML={{ __html: p.step }}
                    />
                    <p
                      className="mt-1 text-sm text-[var(--color-muted-foreground)]"
                      dangerouslySetInnerHTML={{ __html: p.body }}
                    />
                  </div>
                  <span className="shrink-0 self-start rounded-full border border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-3 py-1 font-mono text-xs text-[var(--color-brand)] md:self-center">
                    {p.cost}
                  </span>
                </li>
              ))}
            </ol>
          </Container>
        </section>

        {/* Score breakdown — visual */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="grid items-center gap-12 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                  Anatomy of a clip
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  Five components. One number. Zero mystery.
                </h2>
                <p className="mt-4 text-[var(--color-muted-foreground)]">
                  Every clip you see in the dashboard exposes its full breakdown. Hover a number,
                  read the reason, decide whether to keep it. No more guessing why the AI loved
                  that clip.
                </p>
                <ul className="mt-6 space-y-2 text-sm">
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">Hook</span> — the first
                    2 seconds matter more than the rest.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">Emotion</span> —
                    tension, surprise, reaction.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">Visual proof</span> —
                    face on camera, action, on-screen text.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">Campaign fit</span> —
                    match with your brief.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">Editing</span> — how
                    clean the cut will be.
                  </li>
                </ul>
              </div>
              <ClipMockup
                title="The moment he realised the deal was off"
                hook="And the silence that followed says it all."
                total={88}
                duration="0:42"
                segments={[
                  { role: "setup", range: "02:14 → 02:34" },
                  { role: "payoff", range: "11:08 → 11:30" },
                ]}
                scores={[
                  { label: "Hook", value: 90 },
                  { label: "Emotion", value: 92 },
                  { label: "Visual", value: 81 },
                  { label: "Fit", value: 89 },
                  { label: "Editing", value: 88 },
                ]}
              />
            </div>
          </Container>
        </section>

        {/* Differentiator */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                vs generic AI clippers
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Same input. Different output.
              </h2>
            </div>
            <div className="mt-10">
              <BeforeAfter />
            </div>
          </Container>
        </section>

        {/* Honest limits */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Honest about what we don&apos;t do yet
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Things on the roadmap, not in V1.
            </h2>
            <ul className="mt-8 grid gap-3 text-sm text-[var(--color-muted-foreground)] md:grid-cols-2">
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Direct scheduling to TikTok / Reels / Shorts — manual download for V1.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Public API — coming once the first paying customers stabilise.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Team workspaces — one user per account at launch.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Face-tracking reframe — vertical crop is centred for now.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Direct upload — only YouTube / Vimeo URLs at launch.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                B-roll insertion / AI sound design — out of scope for V1.
              </li>
            </ul>
          </Container>
        </section>

        {/* CTA */}
        <section>
          <Container className="max-w-3xl py-20 text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              See it on your own footage.
            </h2>
            <p className="mt-3 text-[var(--color-muted-foreground)]">
              Connect your account, paste a URL, brief your campaign. First clips in under 10
              minutes.
            </p>
            <Link href="/login" className="mt-8 inline-flex">
              <Button size="lg">
                Start clipping
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </Container>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
