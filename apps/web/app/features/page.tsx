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
  title: "AI clip maker features — clip series, montage and video context",
  description:
    "How ClipFactory uses a clip series goal, full-video context, vision checks and multi-part montage to turn long videos into Shorts, Reels and TikToks with captions and simple scores.",
  keywords: [
    "AI clipping features",
    "AI clip maker features",
    "YouTube Shorts generator features",
    "long video to shorts AI",
    "AI montage tool",
    "AI vision video clipping",
    "context-aware AI clipper",
    "story arcs AI clipping",
    "explained AI clip score",
    "vertical shorts generator",
    "EU hosted AI",
  ],
  alternates: { canonical: "/features" },
};

const FEATURES = [
  {
    icon: Target,
    title: "Clips picked for a clear series goal",
    body: "Tell ClipFactory who you want to reach, your tone, what the clip series should achieve and what to avoid. The AI uses that brief before choosing clips.",
  },
  {
    icon: GitBranch,
    title: "Works across the whole video",
    body: "Some good shorts need two moments: a setup early in the video and a payoff later. ClipFactory can connect those moments into one vertical edit.",
  },
  {
    icon: Eye,
    title: "Checks what happens on screen",
    body: "The AI does not rely only on the transcript. It checks faces, products, reactions, action and on-screen proof before scoring the best moments.",
  },
  {
    icon: Brain,
    title: "Simple score, clear reason",
    body: "Each clip shows why it belongs in the series: hook, emotion, visual proof, audience fit and editing difficulty. No mystery number.",
  },
  {
    icon: ListChecks,
    title: "Checks before rendering",
    body: "Before making the final video, ClipFactory checks that the quote and moment really exist in the source. If the AI invents a moment, it is dropped.",
  },
  {
    icon: Sparkles,
    title: "Simple price, EU hosting",
    body: "1 minute of source video = 1 credit. EU hosting, no watermark, vertical 1080×1920 clips, captions included, cancel anytime.",
  },
];

const PIPELINE_DETAIL = [
  {
    step: "1. Read the video",
    body: "ClipFactory reads the audio and transcript so it knows what people say, when they say it and how the story develops.",
    cost: "source minutes",
  },
  {
    step: "2. Check the visuals",
    body: "The AI samples the video to understand faces, action, products, text on screen and scene changes.",
    cost: "controlled vision",
  },
  {
    step: "3. Build the clip series",
    body: "ClipFactory looks for strong hooks, reactions, proof, before-and-after moments and clips that fit the series goal.",
    cost: "AI selection",
  },
  {
    step: "4. Score the candidates",
    body: "The best moments are scored for hook, emotion, visual proof, fit and editing difficulty.",
    cost: "top moments only",
  },
  {
    step: "5. Render the clips",
    body: "The final clips are rendered vertically with captions and no watermark, ready for Shorts, Reels and TikTok.",
    cost: "included",
  },
];

const BETTER_PICK_DETAIL = [
  {
    icon: Brain,
    title: "Context layer",
    body: "ClipFactory builds a compact map of the full video: topics, timestamps, tension, setup, payoff and dead zones. Simple version: it watches enough of the video to know what a moment means.",
  },
  {
    icon: Eye,
    title: "Vision layer",
    body: "The best candidate moments are checked visually: faces, products, on-screen text, reactions, movement and proof. The transcript is not allowed to make the decision alone.",
  },
  {
    icon: GitBranch,
    title: "Montage layer",
    body: "When one timestamp is not enough, ClipFactory can build a multi-part clip: setup, proof, payoff. The goal is a short that feels edited, not sliced out of the source.",
  },
  {
    icon: ListChecks,
    title: "Safety layer",
    body: "Before render, ClipFactory checks the selected transcript and timestamps against the source. If the AI invented a moment or the edit would not hold, the candidate is rejected.",
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
      <main id="main-content" className="flex-1">
        {/* Intro */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Features
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
              Turn one long video into a series of clips that make sense.
            </h1>
            <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
              Simple version: you give a goal, ClipFactory understands the
              video, then returns clips that fit that goal. Technical version:
              it uses full-video context, vision checks, multi-segment montage
              and an explained score.
            </p>

            <div className="mt-12 grid gap-6 md:grid-cols-2">
              {FEATURES.map((f) => (
                <article
                  key={f.title}
                  className="rounded-lg border border-[var(--color-border)] p-6"
                >
                  <f.icon className="h-5 w-5 text-[var(--color-brand)]" />
                  <h2 className="mt-4 text-lg font-medium">{f.title}</h2>
                  <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
                    {f.body}
                  </p>
                </article>
              ))}
            </div>
          </Container>
        </section>

        {/* Why better */}
        <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                Why the picks are better
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Context, vision and montage work together.
              </h2>
              <p className="mt-3 text-[var(--color-muted-foreground)]">
                For a casual user, this simply means better clips. For a
                creator, agency or technical buyer, these are the layers that
                make the selection different.
              </p>
            </div>

            <div className="mt-10 grid gap-4 md:grid-cols-2">
              {BETTER_PICK_DETAIL.map((item) => (
                <article
                  key={item.title}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6"
                >
                  <item.icon className="h-5 w-5 text-[var(--color-brand)]" />
                  <h3 className="mt-4 text-lg font-medium">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                    {item.body}
                  </p>
                </article>
              ))}
            </div>
          </Container>
        </section>

        {/* Pipeline detail */}
        <section className="border-b border-[var(--color-border)]">
          <Container className="max-w-5xl py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                How it works
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                From a long video to a planned clip series.
              </h2>
              <p className="mt-3 text-[var(--color-muted-foreground)]">
                The product keeps the technical work hidden, but the logic is
                simple: understand the video, choose moments that fit the series
                objective, then render the clips.
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
                  Clip score
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  One score, five simple reasons.
                </h2>
                <p className="mt-4 text-[var(--color-muted-foreground)]">
                  Every clip shows its breakdown. You can see why the AI liked
                  it, why it fits the series goal, then keep it, reject it, or
                  improve the next batch.
                </p>
                <ul className="mt-6 space-y-2 text-sm">
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">
                      Hook
                    </span>{" "}
                    — the first 2 seconds matter more than the rest.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">
                      Emotion
                    </span>{" "}
                    — tension, surprise, reaction.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">
                      Visual proof
                    </span>{" "}
                    — face on camera, action, on-screen text.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">
                      Fit
                    </span>{" "}
                    — match with your audience and series goal.
                  </li>
                  <li>
                    <span className="font-mono text-[var(--color-brand)]">
                      Editing
                    </span>{" "}
                    — how clean the cut will be.
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
                vs basic AI clippers
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                Same video. Better clip series.
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
              Honest limits
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Things coming later.
            </h2>
            <ul className="mt-8 grid gap-3 text-sm text-[var(--color-muted-foreground)] md:grid-cols-2">
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Direct scheduling to TikTok, Reels and Shorts. For V1, download
                the clips manually.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Public API. Coming once the first paying customers are stable.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Team workspaces — one user per account at launch.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Face-tracking reframe. Vertical crop is centred for now.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                Direct upload. Only YouTube and Vimeo URLs at launch.
              </li>
              <li className="rounded-lg border border-[var(--color-border)] p-4">
                B-roll insertion and AI sound design. Out of scope for V1.
              </li>
            </ul>
          </Container>
        </section>

        {/* CTA */}
        <section>
          <Container className="max-w-3xl py-20 text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              Try it on your own video.
            </h2>
            <p className="mt-3 text-[var(--color-muted-foreground)]">
              Connect your account, paste a URL, tell ClipFactory what you want,
              and get your first AI clips.
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
