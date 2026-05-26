import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  Check,
  Eye,
  GitBranch,
  ShieldCheck,
  Sparkles,
  Target,
  TimerReset,
} from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { ClipMockup } from "@/components/marketing/clip-mockup";
import { BeforeAfter } from "@/components/marketing/before-after";
import { ExampleArc } from "@/components/marketing/example-arc";
import { TrustBar } from "@/components/marketing/trust-bar";
import { StatStrip } from "@/components/marketing/stat-strip";
import { UseCases } from "@/components/marketing/use-cases";
import { ComparisonTable } from "@/components/marketing/comparison-table";
import {
  FaqJsonLd,
  OrganizationJsonLd,
  SoftwareApplicationJsonLd,
} from "@/components/marketing/json-ld";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: `AI clip maker for clip series, Shorts, Reels and TikToks — ${SITE.name}`,
  description:
    "Turn long videos, podcasts, webinars and interviews into a focused series of vertical clips for YouTube Shorts, Instagram Reels and TikTok. AI clipping with full-video context, vision, montage, captions and simple scores.",
  alternates: { canonical: "/" },
  openGraph: {
    title: `${SITE.name} — AI clip maker for Shorts, Reels and TikToks`,
    description: SITE.longDescription,
    url: SITE.url,
    siteName: SITE.name,
    type: "website",
  },
};

const HOME_FAQ: { q: string; a: string }[] = [
  {
    q: "Can I turn a long YouTube video into Shorts with AI?",
    a: "Yes. Paste a YouTube or Vimeo link, tell ClipFactory who the clips are for, and it returns vertical clips with captions for YouTube Shorts, TikTok and Instagram Reels.",
  },
  {
    q: "What makes ClipFactory different from a basic AI clipper?",
    a: "A basic clipper often picks loud sentences. ClipFactory also looks at the full video, what is visible on screen, and the goal of the clip series, then explains why each clip was selected.",
  },
  {
    q: "Does ClipFactory understand what happens on screen?",
    a: "Yes. It checks visual context such as products, faces, actions, reactions and proof on screen. That helps avoid clips that sound good in the transcript but do not work visually.",
  },
  {
    q: "What sources are supported at launch?",
    a: "YouTube and Vimeo URLs. Direct upload comes later, once the first paid workflows are stable.",
  },
  {
    q: "How much does it cost?",
    a: "Starter is 29€/month: 300 credits, up to 30 minutes per video and 3 clips per video. 1 credit = 1 minute of source video. No watermark, EU hosted, cancel anytime.",
  },
  {
    q: "Where is the data processed?",
    a: "ClipFactory is designed around EU hosting: database in Frankfurt, storage in Europe and video processing in Germany. Source videos are deleted after 14 days and rendered clips after 60 days.",
  },
];

const serif = {
  fontFamily: "var(--font-serif), 'Iowan Old Style', Georgia, serif",
} as const;

export default function HomePage() {
  return (
    <>
      <OrganizationJsonLd />
      <SoftwareApplicationJsonLd />
      <FaqJsonLd items={HOME_FAQ} />
      <MarketingNav />
      <main className="flex-1">
        <Hero />
        <TrustBar />
        <SimpleProof />
        <Positioning />
        <Pipeline />
        <Example />
        <ScoreExplained />
        <StatStrip />
        <UseCases />
        <Differentiator />
        <ComparisonTable />
        <PricingTeaser />
        <Faq />
        <FinalCta />
      </main>
      <MarketingFooter />
    </>
  );
}

function Hero() {
  return (
    <section className="liquid-hero relative overflow-hidden border-b border-[var(--color-border)] bg-[var(--color-background)]">
      <Container className="relative py-12 text-center md:py-14 lg:py-16">
        <div className="fade-up mx-auto max-w-5xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-muted)]/60 px-4 py-2 text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-muted-foreground)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-brand)]" aria-hidden />
            AI clip maker for long videos
          </div>
          <h1
            style={serif}
            className="mx-auto mt-5 max-w-5xl text-[clamp(3.15rem,8vw,6.75rem)] font-light leading-[0.91] tracking-tight"
          >
            Turn long videos
            <br />
            into <span className="italic text-[var(--color-brand)]">Shorts</span>,
            <br />
            Reels and TikToks.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-[var(--color-muted-foreground)] md:text-xl">
            Paste a YouTube or Vimeo link, set the goal for your clip series, and
            ClipFactory watches the whole video to find moments that belong together.
            It can join setup, proof and payoff into ready-to-post vertical clips.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2 text-xs text-[var(--color-muted-foreground)]">
            {["Series goal", "Whole-video context", "Multi-moment montage"].map((item) => (
              <span
                key={item}
                className="rounded-full border border-[var(--color-border)] bg-black/20 px-3 py-2 transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-brand)] hover:text-[var(--color-foreground)]"
              >
                {item}
              </span>
            ))}
          </div>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Link href="/login">
              <Button size="lg">
                Start clipping
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="#why-better">
              <Button size="lg" variant="secondary">
                Why it works
              </Button>
            </Link>
          </div>
          <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
            29€/month · 300 video minutes · no watermark · EU hosted
          </p>
        </div>

        <div className="fade-up-2 mx-auto mt-9 w-full max-w-5xl">
          <HeroProductStage />
        </div>
      </Container>
    </section>
  );
}

function HeroProductStage() {
  const insights = [
    {
      icon: Brain,
      label: "Context",
      title: "Setup found",
      body: "The first moment explains why the payoff matters.",
      color: "var(--color-brand)",
      soft: "var(--color-brand-soft)",
    },
    {
      icon: Eye,
      label: "Vision",
      title: "Screen proof",
      body: "The object, reaction and action are visible in frame.",
      color: "var(--color-vision)",
      soft: "var(--color-vision-soft)",
    },
    {
      icon: GitBranch,
      label: "Edit",
      title: "Two-part cut",
      body: "Setup and payoff are joined into one short story.",
      color: "var(--color-edit)",
      soft: "var(--color-edit-soft)",
    },
  ];

  const scores = [
    { label: "Hook", value: 95, color: "var(--color-brand)" },
    { label: "Emotion", value: 88, color: "var(--color-edit)" },
    { label: "Visual proof", value: 92, color: "var(--color-vision)" },
    { label: "Audience fit", value: 90, color: "var(--color-brand)" },
  ];

  return (
    <div className="relative">
      <div className="absolute -inset-3 rounded-[1.25rem] border border-white/8" aria-hidden />
      <div className="film-surface soft-sheen stage-float relative overflow-hidden rounded-lg border border-[var(--color-border)] shadow-[0_24px_90px_-46px_rgba(245,245,247,0.26)]">
        <div className="frame-notch h-4 opacity-30" aria-hidden />
        <div className="flex items-center justify-between gap-4 border-b border-[var(--color-border)] px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex gap-1.5" aria-hidden>
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-brand)]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-vision)]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-edit)]" />
            </div>
            <p className="truncate font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-muted-foreground)]">
              ClipFactory review
            </p>
          </div>
          <p className="font-mono text-xs tabular-nums text-[var(--color-foreground)]">
            12:47:08
          </p>
        </div>

        <div className="grid lg:grid-cols-[1fr_176px]">
          <div className="p-4">
            <div className="grid gap-4 sm:grid-cols-[170px_1fr]">
              <div className="relative mx-auto aspect-[9/16] w-full max-w-[170px] overflow-hidden rounded-md border border-white/10 bg-[linear-gradient(145deg,#2a2a2d_0%,#141416_42%,#050505_100%)]">
                <span
                  aria-hidden="true"
                  className="scan-sweep absolute inset-x-0 top-0 z-10 h-16 blur-md"
                  style={{ backgroundColor: "rgba(245, 245, 247, 0.16)" }}
                />
                <div className="absolute inset-x-0 top-0 h-10 bg-gradient-to-b from-black/70 to-transparent" />
                <div className="absolute left-3 top-3 rounded-sm bg-black/65 px-2 py-1 font-mono text-[10px] text-white/75">
                  02:14 → 12:47
                </div>
                <div className="absolute right-3 top-3 rounded-sm bg-[var(--color-brand)] px-2 py-1 font-mono text-[10px] font-semibold text-[var(--color-brand-foreground)]">
                  91
                </div>
                <div className="absolute inset-x-5 top-20 h-24 rounded-md border border-white/12 bg-white/8" />
                <div className="absolute left-6 top-24 h-11 w-11 rounded-full border border-[var(--color-vision)]/70 bg-[var(--color-vision-soft)]" />
                <div className="absolute right-7 top-32 h-14 w-14 rounded-sm border border-[var(--color-edit)]/70 bg-[var(--color-edit-soft)]" />
                <div className="absolute inset-x-4 bottom-5">
                  <p className="text-lg font-semibold leading-tight text-white">
                    Setup and payoff in one clip.
                  </p>
                  <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-white/55">
                    captions · 1080x1920
                  </p>
                </div>
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-muted-foreground)]">
                      Output clip
                    </p>
                    <p className="mt-1 text-lg font-semibold">Series clip · 42.6s · 2 segments</p>
                  </div>
                  <div className="rounded-md bg-[var(--color-brand)] px-3 py-2 text-right text-[var(--color-brand-foreground)]">
                    <p className="font-mono text-[10px] uppercase tracking-wider">Score</p>
                    <p className="text-2xl font-semibold tabular-nums">91</p>
                  </div>
                </div>

                <div className="mt-5 grid gap-2">
                  {scores.map((score, scoreIndex) => (
                    <div key={score.label}>
                      <div className="flex items-center justify-between text-sm">
                        <span>{score.label}</span>
                        <span className="font-mono text-xs text-[var(--color-muted-foreground)]">
                          {score.value}
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 rounded-full bg-white/10">
                        <div
                          className="score-fill h-full rounded-full"
                          style={{
                            width: `${score.value}%`,
                            backgroundColor: score.color,
                            animationDelay: `${0.12 * (scoreIndex + 1)}s`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="edit-grid mt-5 rounded-md border border-[var(--color-border)] bg-black/25 p-3">
              <div className="mb-3 flex justify-between font-mono text-[10px] text-[var(--color-muted-foreground)]">
                <span>00:00</span>
                <span>02:14</span>
                <span>12:47</span>
                <span>14:08</span>
              </div>
              <div className="relative space-y-2">
                <span
                  aria-hidden="true"
                  className="timeline-playhead absolute -top-1 bottom-0 z-10 w-px bg-[var(--color-foreground)]/80 shadow-[0_0_18px_rgba(246,240,229,0.55)]"
                >
                  <span className="absolute -left-1 top-0 h-2 w-2 rounded-full bg-[var(--color-foreground)]" />
                </span>
                {[
                  {
                    label: "source",
                    left: "0%",
                    width: "100%",
                    color: "rgba(246,240,229,0.16)",
                  },
                  {
                    label: "setup",
                    left: "16%",
                    width: "18%",
                    color: "var(--color-brand)",
                  },
                  {
                    label: "payoff",
                    left: "78%",
                    width: "14%",
                    color: "var(--color-edit)",
                  },
                  {
                    label: "vision check",
                    left: "74%",
                    width: "20%",
                    color: "var(--color-vision)",
                  },
                ].map((track, trackIndex) => (
                  <div key={track.label} className="grid grid-cols-[78px_1fr] items-center gap-3">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">
                      {track.label}
                    </span>
                    <span className="relative h-4 overflow-hidden rounded-sm bg-black/30">
                      <span
                        className="score-fill absolute inset-y-0 rounded-sm"
                        style={{
                          left: track.left,
                          width: track.width,
                          backgroundColor: track.color,
                          animationDelay: `${0.1 * (trackIndex + 1)}s`,
                        }}
                      />
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <aside className="border-t border-[var(--color-border)] bg-black/18 p-4 lg:border-l lg:border-t-0">
            <div className="flex items-center gap-2 text-[var(--color-brand)]">
              <Sparkles className="h-4 w-4" />
              <p className="font-mono text-[10px] uppercase tracking-[0.2em]">
                Why this works
              </p>
            </div>
            <div className="mt-4 space-y-3">
              {insights.map((item, itemIndex) => (
                <div
                  key={item.label}
                  className="insight-card rounded-md border p-3 transition-transform duration-300 hover:-translate-y-0.5"
                  style={{
                    borderColor: item.color,
                    backgroundColor: item.soft,
                    animationDelay: `${0.18 * (itemIndex + 1)}s`,
                  }}
                >
                  <div className="flex items-center gap-2" style={{ color: item.color }}>
                    <item.icon className="h-4 w-4" />
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em]">
                      {item.label}
                    </p>
                  </div>
                  <p className="mt-2 text-sm font-semibold">{item.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-muted-foreground)]">
                    {item.body}
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function SimpleProof() {
  const points = [
    {
      icon: Brain,
      eyebrow: "Context",
      title: "It understands the story before it cuts.",
      body: "A strong clip is not always the loudest sentence. Sometimes the important part happened five minutes earlier. ClipFactory maps the whole video before choosing.",
      color: "var(--color-brand)",
      soft: "var(--color-brand-soft)",
    },
    {
      icon: Eye,
      eyebrow: "Vision",
      title: "It watches the screen, not just the transcript.",
      body: "Products, faces, reactions, movement and proof on screen change whether a clip works. If the words sound good but the image says nothing, the score goes down.",
      color: "var(--color-vision)",
      soft: "var(--color-vision-soft)",
    },
    {
      icon: GitBranch,
      eyebrow: "Editing",
      title: "It can build a clip from more than one moment.",
      body: "Setup, proof, payoff, reaction. ClipFactory can join moments that are far apart, so each short feels like a real edit inside a planned clip series.",
      color: "var(--color-edit)",
      soft: "var(--color-edit-soft)",
    },
  ];

  return (
    <section id="why-better" className="wave-band">
      <Container className="relative py-24 md:py-28">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Why it is better
          </p>
          <h2
            style={serif}
            className="mt-3 text-4xl font-light leading-tight tracking-tight md:text-6xl"
          >
            A basic clipper hears the video.
            <br />
            ClipFactory understands it.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-[var(--color-muted-foreground)]">
            Good short clips need four things: the series goal, the full-video story,
            what is visible on screen, and how the final moment is edited.
          </p>
        </div>

        <div className="liquid-shell mt-16 p-4 md:p-8">
          <div className="grid gap-4 md:grid-cols-[0.92fr_1.16fr_0.92fr] md:items-center">
          {points.map((p, pointIndex) => (
            <article
              key={p.title}
              className={
                "curve-card insight-card overflow-hidden p-7 pt-14 transition-all duration-500 hover:-translate-y-1 hover:border-[var(--color-foreground)]/30 " +
                (pointIndex === 1 ? "md:min-h-[20rem]" : "md:min-h-[16rem]")
              }
              style={{
                animationDelay: `${0.12 * (pointIndex + 1)}s`,
                color: p.color,
              }}
            >
              <div
                className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                style={{ borderColor: p.color, backgroundColor: p.soft, color: p.color }}
              >
                <p.icon className="h-5 w-5" />
              </div>
              <p
                className="mt-5 text-[11px] font-semibold uppercase tracking-[0.22em]"
                style={{ color: p.color }}
              >
                {p.eyebrow}
              </p>
              <h3 className="mt-2 text-xl font-semibold leading-tight text-[var(--color-foreground)]">
                {p.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                {p.body}
              </p>
            </article>
          ))}
          </div>
        </div>
      </Container>
    </section>
  );
}

function Positioning() {
  const points = [
    {
      icon: Target,
      title: "Tell it the goal of the clip series",
      body: "Give a simple brief: audience, niche, tone, series goal and topics to avoid. The same video can produce a different series for a different objective.",
    },
    {
      icon: Eye,
      title: "It looks at the video, not only the words",
      body: "Products, faces, reactions, action and proof on screen matter. Transcript-only clipping misses why a clip works.",
    },
    {
      icon: GitBranch,
      title: "It can connect moments far apart",
      body: "The best short can start with a setup at minute 2 and end with a payoff at minute 12. ClipFactory is built for those multi-moment edits.",
    },
  ];

  return (
    <section className="relative overflow-hidden border-b border-[var(--color-border)] bg-[var(--color-background)]">
      <Container className="py-24">
        <div className="grid gap-10 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
          <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Why it works
          </p>
          <h2 style={serif} className="mt-2 text-4xl font-light leading-tight tracking-tight md:text-6xl">
            The edit follows the objective.
          </h2>
          <p className="mt-5 text-[var(--color-muted-foreground)]">
            A transcript can tell what was said. A series brief tells what should
            be posted. ClipFactory uses both, then checks the screen before cutting.
          </p>
          </div>

          <div className="liquid-shell p-4 md:p-5">
            <div className="grid gap-3">
          {points.map((p, pointIndex) => (
            <article
              key={p.title}
                  className="insight-card grid gap-4 rounded-[1.5rem] border border-[var(--color-border)] bg-black/25 p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-foreground)]/25 md:grid-cols-[auto_1fr]"
              style={{ animationDelay: `${0.1 * (pointIndex + 1)}s` }}
            >
                  <div className="flex h-12 w-12 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-muted)]">
                    <p.icon className="h-5 w-5 text-[var(--color-brand)]" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">{p.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                      {p.body}
                    </p>
                  </div>
            </article>
          ))}
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}

function Pipeline() {
  const steps = [
    {
      icon: Target,
      title: "Brief",
      body: "Tell ClipFactory who you want to reach and what the whole clip series should achieve.",
    },
    {
      icon: Eye,
      title: "Scan",
      body: "It reads the transcript and checks the video so it understands what happens before, during and after each moment.",
    },
    {
      icon: GitBranch,
      title: "Find",
      body: "It finds strong moments that fit the series goal, including before-and-after clips that happen minutes apart.",
    },
    {
      icon: ShieldCheck,
      title: "Check",
      body: "It checks that the quote and moment really exist before rendering the clip.",
    },
    {
      icon: Brain,
      title: "Score",
      body: "You get vertical clips with captions, a simple score and the reason each one belongs in the series.",
    },
  ];

  return (
    <section id="pipeline" className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-24">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              The simple flow
            </p>
            <h2 style={serif} className="mt-2 text-4xl font-light tracking-tight md:text-5xl">
              From one long video to a clip series you can post.
            </h2>
          </div>
          <Link href="/features" className="inline-flex">
            <Button variant="secondary">
              See all features
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>

        <ol className="liquid-shell mt-12 grid gap-2 p-3 md:grid-cols-5 md:p-4">
          {steps.map((s, i) => (
            <li
              key={s.title}
              className={
                "insight-card relative min-h-52 rounded-[1.6rem] border border-[var(--color-border)] bg-[var(--color-background)] p-5 transition-all duration-500 hover:-translate-y-1 hover:border-[var(--color-brand)]/60 " +
                (i % 2 === 1 ? "md:mt-10" : "")
              }
              style={{ animationDelay: `${0.08 * (i + 1)}s` }}
            >
              <div className="flex items-center justify-between">
                <span className="flex h-11 w-11 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-muted)]">
                  <s.icon className="h-5 w-5 text-[var(--color-brand)]" />
                </span>
                <span className="font-mono text-xs text-[var(--color-brand)]">
                  0{i + 1}
                </span>
              </div>
              <h3 className="mt-5 text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                {s.body}
              </p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}

function Example() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-20">
        <div className="grid items-start gap-10 lg:grid-cols-[0.78fr_1.22fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Real example
            </p>
            <h2 style={serif} className="mt-2 text-4xl font-light tracking-tight md:text-5xl">
              The best clip is often two moments, not one.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              If someone buys a Lamborghini and crashes it ten minutes later, the short
              needs both moments. A simple timestamp picker will miss the story, and it
              will not know if that clip fits the goal of the series.
            </p>
          </div>
          <ExampleArc />
        </div>
      </Container>
    </section>
  );
}

function ScoreExplained() {
  const bullets = [
    "Hook: will the first seconds make people stop scrolling?",
    "Emotion: is there tension, surprise, reaction or stakes?",
    "Visual proof: can the viewer see why this moment matters?",
    "Fit: does it match the audience and the goal of the clip series?",
    "Editing: can the clip be cut cleanly?",
  ];

  return (
    <section className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <div className="grid items-center gap-12 md:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Simple score
            </p>
            <h2 style={serif} className="mt-2 text-4xl font-light tracking-tight md:text-5xl">
              You see why each clip belongs in the series.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              No mystery number. Every clip comes with a short explanation, so you can
              keep it, reject it, or improve the next series.
            </p>
            <ul className="mt-7 space-y-3 text-sm">
              {bullets.map((b) => (
                <li key={b} className="flex gap-3 text-[var(--color-muted-foreground)]">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-brand)]" />
                  {b}
                </li>
              ))}
            </ul>
          </div>

          <ClipMockup
            title="He did not change the offer. He changed the frame."
            hook="The line that made the whole room go quiet."
            total={91}
            segments={[
              { role: "setup", range: "02:14 → 02:39" },
              { role: "payoff", range: "12:47 → 13:05" },
            ]}
            scores={[
              { label: "Hook", value: 95 },
              { label: "Emotion", value: 88 },
              { label: "Visual", value: 92 },
              { label: "Fit", value: 90 },
              { label: "Editing", value: 84 },
            ]}
          />
        </div>
      </Container>
    </section>
  );
}

function Differentiator() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Better picks
          </p>
          <h2 style={serif} className="mt-2 text-4xl font-light tracking-tight md:text-5xl">
            Same video. A smarter series of clips.
          </h2>
        </div>
        <div className="mt-10">
          <BeforeAfter />
        </div>
      </Container>
    </section>
  );
}

function PricingTeaser() {
  const features = [
    "300 video minutes per month",
    "1 credit = 1 minute of source video",
    "Up to 30 min per video, 3 clips per job",
    "Captions, montage picks and score included",
    "EU hosted, no watermark, cancel anytime",
  ];

  return (
    <section id="pricing" className="border-b border-[var(--color-border)]">
      <Container className="py-20">
        <div className="grid items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
              Pricing
            </p>
            <h2 style={serif} className="mt-2 text-4xl font-light tracking-tight md:text-5xl">
              Simple pricing for your first clip series.
            </h2>
            <p className="mt-4 text-[var(--color-muted-foreground)]">
              You pay for the length of the source video, not for confusing add-ons.
              1 credit = 1 minute of video.
            </p>
          </div>

          <div className="pro-panel rounded-lg border-2 border-[var(--color-brand)] p-7">
            <div className="flex items-start justify-between gap-6">
              <div>
                <p className="text-sm font-semibold uppercase tracking-wider text-[var(--color-brand)]">
                  Starter
                </p>
                <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
                  For creators, podcasters and small teams posting weekly clips.
                </p>
              </div>
              <div className="text-right">
                <span className="text-5xl font-semibold tabular-nums">29€</span>
                <span className="block text-sm text-[var(--color-muted-foreground)]">
                  / month
                </span>
              </div>
            </div>
            <ul className="mt-7 grid gap-3 text-sm md:grid-cols-2">
              {features.map((f) => (
                <li key={f} className="flex gap-3">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-brand)]" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Link href="/login" className="mt-8 block">
              <Button size="lg" className="w-full">
                Start with Starter
              </Button>
            </Link>
            <p className="mt-3 text-center text-xs text-[var(--color-muted-foreground)]">
              VAT included for EU customers · no revenue share
            </p>
          </div>
        </div>
      </Container>
    </section>
  );
}

function Faq() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <Container className="max-w-3xl py-20">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
          FAQ
        </p>
        <h2 style={serif} className="mt-2 text-4xl font-light tracking-tight md:text-5xl">
          Questions people ask before trying an AI clip maker.
        </h2>
        <dl className="mt-10 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
          {HOME_FAQ.map((item) => (
            <div key={item.q} className="py-6">
              <dt className="text-base font-medium">{item.q}</dt>
              <dd className="mt-2 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                {item.a}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-8 text-sm text-[var(--color-muted-foreground)]">
          More answers on the{" "}
          <Link href="/faq" className="underline">
            full FAQ
          </Link>
          .
        </p>
      </Container>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(640px 360px at 50% 0%, rgba(216,195,163,0.14), transparent 70%)",
        }}
      />
      <Container className="relative py-24 text-center">
        <TimerReset className="mx-auto h-6 w-6 text-[var(--color-brand)]" />
        <h2
          style={serif}
          className="mx-auto mt-4 max-w-3xl text-4xl font-light tracking-tight md:text-6xl"
        >
          Try it on a video you already want to turn into shorts.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-[var(--color-muted-foreground)]">
          Paste a YouTube or Vimeo URL, set a clear series goal, and see if
          the AI can find the moments that belong together.
        </p>
        <Link href="/login" className="mt-8 inline-flex">
          <Button size="lg">
            Start clipping
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </Container>
    </section>
  );
}
