import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Check,
  Clock3,
  Download,
  Eye,
  Film,
  GitBranch,
  Plus,
  Sparkles,
  Target,
  ThumbsUp,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Dashboard preview - ClipFactory",
  robots: { index: false, follow: false },
};

const campaigns = [
  {
    name: "Founder lessons Q2",
    audience: "Solo SaaS founders",
    goal: "Make 3 clips that push viewers to join the newsletter",
    jobs: 6,
  },
  {
    name: "Podcast launch clips",
    audience: "Creators and operators",
    goal: "Turn one long episode into a weekly clip series",
    jobs: 3,
  },
];

const jobs = [
  {
    url: "youtube.com/watch?v=founder-interview",
    status: "completed",
    clips: 3,
    time: "14 min source",
  },
  {
    url: "youtube.com/watch?v=agency-call",
    status: "rendering",
    clips: 2,
    time: "22 min source",
  },
  {
    url: "vimeo.com/client-workshop",
    status: "analyzing",
    clips: 3,
    time: "31 min source",
  },
];

const clips = [
  {
    title: "He did not change the offer. He changed the frame.",
    hook: "The line that made the whole room go quiet.",
    score: 91,
    segments: ["02:14-02:39 setup", "12:47-13:05 payoff"],
  },
  {
    title: "The hidden reason the first launch failed",
    hook: "Everyone blamed the product. The real issue was the audience.",
    score: 86,
    segments: ["05:08-05:39 single"],
  },
];

export default function DashboardPreviewPage() {
  return (
    <main className="min-h-dvh bg-[var(--color-background)] text-[var(--color-foreground)]">
      <PreviewNav />

      <section className="relative overflow-hidden border-b border-[var(--color-border)]">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(120deg,rgba(216,195,163,0.08),transparent_38%),repeating-linear-gradient(90deg,rgba(245,245,247,0.026)_0,rgba(245,245,247,0.026)_1px,transparent_1px,transparent_112px)]" />
        <div className="relative mx-auto max-w-7xl px-6 py-10">
          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--color-muted-foreground)]">
                Dashboard preview
              </p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-5xl">
                Your clip factory, at a glance.
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[var(--color-muted-foreground)] md:text-base">
                Campaign goals, jobs, clips, scores and admin numbers in one
                quiet workspace. This page uses fake data so you can review the
                DA without logging in.
              </p>
            </div>
            <Button>
              <Plus className="h-4 w-4" />
              New campaign
            </Button>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-4">
            <Metric icon={Wallet} label="Credits left" value="238" hint="1 credit = 1 source min" />
            <Metric icon={Target} label="Campaigns" value="2" hint="Active clip series" />
            <Metric icon={Clock3} label="Jobs" value="11" hint="3 running right now" />
            <Metric icon={Film} label="Clips ready" value="27" hint="No watermark" />
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <Panel title="Campaigns" eyebrow="Series goals">
            <div className="space-y-3">
              {campaigns.map((campaign) => (
                <div
                  key={campaign.name}
                  className="rounded-[1.5rem] border border-[var(--color-border)] bg-black/20 p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="font-semibold">{campaign.name}</h3>
                      <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
                        {campaign.audience}
                      </p>
                    </div>
                    <span className="status-pill">{campaign.jobs} jobs</span>
                  </div>
                  <p className="mt-4 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                    <span className="text-[var(--color-foreground)]">Goal: </span>
                    {campaign.goal}
                  </p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Recent jobs" eyebrow="Pipeline">
            <div className="divide-y divide-[var(--color-border)]">
              {jobs.map((job) => (
                <div
                  key={job.url}
                  className="flex items-center justify-between gap-4 py-4 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm">{job.url}</p>
                    <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                      {job.time} · {job.clips} clip(s)
                    </p>
                  </div>
                  <span className="status-pill">{job.status}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Current job" eyebrow="Output review">
            <div className="grid gap-5 xl:grid-cols-[180px_1fr]">
              <div className="relative mx-auto aspect-[9/16] w-full max-w-[180px] overflow-hidden rounded-[1.5rem] border border-[var(--color-border)] bg-[linear-gradient(145deg,#2a2a2d,#090909)]">
                <div className="absolute inset-x-4 top-4 flex justify-between font-mono text-[10px] text-white/55">
                  <span>02:14</span>
                  <span>13:05</span>
                </div>
                <div className="absolute inset-x-5 top-20 h-24 rounded-xl border border-white/10 bg-white/[0.06]" />
                <div className="absolute inset-x-4 bottom-5">
                  <p className="text-lg font-semibold leading-tight text-white">
                    Setup and payoff in one clip.
                  </p>
                  <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-white/50">
                    captions · 1080x1920
                  </p>
                </div>
              </div>

              <div>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-muted-foreground)]">
                      Series clip · 42.6s · 2 segments
                    </p>
                    <h3 className="mt-2 text-xl font-semibold">
                      He did not change the offer. He changed the frame.
                    </h3>
                  </div>
                  <div className="rounded-xl bg-[var(--color-foreground)] px-4 py-3 text-right text-[var(--color-background)]">
                    <p className="font-mono text-[10px] uppercase tracking-wider">Score</p>
                    <p className="text-3xl font-semibold tabular-nums">91</p>
                  </div>
                </div>

                <div className="mt-6 grid gap-3">
                  {[
                    ["Hook", 95],
                    ["Emotion", 88],
                    ["Visual proof", 92],
                    ["Audience fit", 90],
                  ].map(([label, value]) => (
                    <div key={label as string}>
                      <div className="flex items-center justify-between text-sm">
                        <span>{label}</span>
                        <span className="font-mono text-xs text-[var(--color-muted-foreground)]">
                          {value}
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-[var(--color-brand)]"
                          style={{ width: `${value}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 flex flex-wrap gap-2">
                  <Button size="sm">
                    <Download className="h-4 w-4" />
                    Download
                  </Button>
                  <Button size="sm" variant="secondary">
                    <ThumbsUp className="h-4 w-4" />
                  </Button>
                  <Button size="sm" variant="secondary">
                    Open job
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </Panel>

          <div className="grid gap-6 md:grid-cols-2">
            {clips.map((clip) => (
              <div key={clip.title} className="pro-card rounded-[1.75rem] p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-muted-foreground)]">
                      Clip
                    </p>
                    <h3 className="mt-2 line-clamp-2 font-semibold">{clip.title}</h3>
                  </div>
                  <span className="rounded-lg bg-[var(--color-foreground)] px-2 py-1 font-mono text-sm font-semibold text-[var(--color-background)]">
                    {clip.score}
                  </span>
                </div>
                <p className="mt-3 line-clamp-2 text-sm text-[var(--color-muted-foreground)]">
                  {clip.hook}
                </p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {clip.segments.map((segment) => (
                    <span key={segment} className="status-pill font-mono">
                      {segment}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-[var(--color-border)] bg-[var(--color-muted)]">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">
                Admin preview
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                The numbers you watch before opening publicly.
              </h2>
            </div>
            <Link href="/preview" className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">
              Back to previews →
            </Link>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-5">
            <Metric icon={BarChart3} label="MRR" value="203 EUR" hint="7 active Starter subs" />
            <Metric icon={Sparkles} label="Clips" value="184" hint="Generated lifetime" />
            <Metric icon={GitBranch} label="Montage" value="41%" hint="Multi-segment clips" />
            <Metric icon={Eye} label="Vision cost" value="11.80 EUR" hint="Current month" />
            <Metric icon={Check} label="Margin" value="73%" hint="Gross estimate" />
          </div>
        </div>
      </section>
    </main>
  );
}

function PreviewNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-background)]/78 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link href="/preview" className="flex items-center gap-2 font-semibold tracking-tight">
          <span
            className="relative inline-flex h-5 w-5 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]"
            aria-hidden
          >
            <span className="h-2.5 w-1 rounded-sm bg-[var(--color-brand)]" />
          </span>
          ClipFactory
        </Link>
        <div className="flex items-center gap-2">
          <span className="hidden text-xs text-[var(--color-muted-foreground)] md:inline">
            Preview · no login
          </span>
          <Link href="/">
            <Button size="sm" variant="secondary">
              Home
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="pro-card rounded-[1.5rem] p-5">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
          {label}
        </p>
        <Icon className="h-4 w-4 text-[var(--color-brand)]" />
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{hint}</p>
    </div>
  );
}

function Panel({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow: string;
  children: React.ReactNode;
}) {
  return (
    <section className="liquid-shell p-5 md:p-6">
      <div className="mb-5">
        <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">
          {eyebrow}
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">{title}</h2>
      </div>
      {children}
    </section>
  );
}
