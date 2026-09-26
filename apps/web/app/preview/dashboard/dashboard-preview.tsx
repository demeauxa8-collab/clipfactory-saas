"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  Clapperboard,
  Clock3,
  Download,
  Eye,
  Film,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Plus,
  Search,
  Settings,
  Sparkles,
  Target,
  ThumbsUp,
  Wallet,
} from "lucide-react";
import { Button } from "@/components/ui/button";

/* ── Fake data (preview only — no login, no backend) ─────────────── */

const CREDITS_TOTAL = 300;
const CREDITS_LEFT = 238;

const usage7d = [
  { d: "Mon", v: 8 },
  { d: "Tue", v: 14 },
  { d: "Wed", v: 6 },
  { d: "Thu", v: 19 },
  { d: "Fri", v: 11 },
  { d: "Sat", v: 4 },
  { d: "Sun", v: 0 },
];

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

type JobStatus = "completed" | "rendering" | "analyzing" | "failed";
const jobs: { url: string; status: JobStatus; clips: number; time: string }[] =
  [
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
    {
      url: "youtube.com/watch?v=webinar-q1",
      status: "completed",
      clips: 4,
      time: "47 min source",
    },
    {
      url: "youtube.com/watch?v=broken-link",
      status: "failed",
      clips: 0,
      time: "18 min source",
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
  {
    title: "Stop optimising the thing nobody asked for",
    hook: "Two years of polish on a feature with zero demand.",
    score: 78,
    segments: ["21:02-21:30 single"],
  },
];

const SIDEBAR = [
  { icon: LayoutDashboard, label: "Dashboard", active: true },
  { icon: Target, label: "Campaigns" },
  { icon: Clock3, label: "Jobs" },
  { icon: Clapperboard, label: "Clips" },
  { icon: Wallet, label: "Billing" },
  { icon: Settings, label: "Settings" },
];

const JOB_FILTERS = ["All", "Running", "Completed", "Failed"] as const;
type JobFilter = (typeof JOB_FILTERS)[number];

/* ── Component ────────────────────────────────────────────────────── */

export function DashboardPreview() {
  const [filter, setFilter] = React.useState<JobFilter>("All");
  const [query, setQuery] = React.useState("");
  const [topClipsOnly, setTopClipsOnly] = React.useState(false);

  const filteredJobs = jobs.filter((j) => {
    const matchesQuery = j.url.toLowerCase().includes(query.toLowerCase());
    const matchesFilter =
      filter === "All" ||
      (filter === "Running" &&
        (j.status === "rendering" || j.status === "analyzing")) ||
      (filter === "Completed" && j.status === "completed") ||
      (filter === "Failed" && j.status === "failed");
    return matchesQuery && matchesFilter;
  });

  const shownClips = topClipsOnly ? clips.filter((c) => c.score >= 90) : clips;
  const usedPct = Math.round(
    ((CREDITS_TOTAL - CREDITS_LEFT) / CREDITS_TOTAL) * 100,
  );
  const maxUsage = Math.max(...usage7d.map((u) => u.v), 1);

  return (
    <div className="min-h-dvh bg-[var(--color-background)] text-[var(--color-foreground)] lg:flex">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-foreground)_2.5%,var(--color-background))] lg:flex">
        <div className="flex h-16 items-center gap-2 border-b border-[var(--color-border)] px-5 font-semibold tracking-tight">
          <span className="relative inline-flex h-6 w-6 items-center justify-center rounded-[0.6rem] border border-[var(--color-border)] bg-[var(--color-muted)]">
            <span className="h-3 w-1 rounded-full bg-[var(--color-brand)]" />
          </span>
          ClipFactory
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {SIDEBAR.map((item) => (
            <button
              key={item.label}
              className={
                "flex w-full items-center gap-3 rounded-[0.875rem] px-3 py-2.5 text-sm transition-colors " +
                (item.active
                  ? "bg-[var(--color-brand-soft)] text-[var(--color-brand)]"
                  : "text-[var(--color-muted-foreground)] hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)]")
              }
            >
              <item.icon className="h-[18px] w-[18px]" />
              {item.label}
            </button>
          ))}
        </nav>
        {/* Credit widget */}
        <div className="m-3 rounded-[1.25rem] border border-[var(--color-border)] bg-[var(--color-muted)] p-4">
          <div className="flex items-center justify-between text-xs text-[var(--color-muted-foreground)]">
            <span className="inline-flex items-center gap-1.5">
              <Gauge className="h-3.5 w-3.5" /> Credits
            </span>
            <span className="font-mono tabular-nums text-[var(--color-foreground)]">
              {CREDITS_LEFT}/{CREDITS_TOTAL}
            </span>
          </div>
          <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-foreground)_8%,transparent)]">
            <div
              className="h-full rounded-full bg-[var(--color-brand)]"
              style={{ width: `${100 - usedPct}%` }}
            />
          </div>
          <p className="mt-2 text-[11px] text-[var(--color-muted-foreground)]">
            {usedPct}% used this month
          </p>
        </div>
      </aside>

      {/* Main column */}
      <div className="min-w-0 flex-1">
        {/* Top bar */}
        <header className="sticky top-0 z-40 flex h-16 items-center gap-4 border-b border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-background)_72%,transparent)] px-6 backdrop-blur-xl">
          <div className="flex items-center gap-2 text-sm text-[var(--color-muted-foreground)] lg:hidden">
            <span className="relative inline-flex h-6 w-6 items-center justify-center rounded-[0.6rem] border border-[var(--color-border)] bg-[var(--color-muted)]">
              <span className="h-3 w-1 rounded-full bg-[var(--color-brand)]" />
            </span>
          </div>
          <h1 className="text-sm font-semibold tracking-tight">Dashboard</h1>
          <div className="relative ml-auto hidden md:block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-muted-foreground)]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search jobs, clips…"
              className="h-9 w-56 rounded-full border border-[var(--color-border)] bg-[var(--color-muted)] pl-9 pr-3 text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            />
          </div>
          <Button size="sm" className="ml-auto md:ml-0">
            <Plus className="h-4 w-4" />
            New campaign
          </Button>
          <span className="hidden text-xs text-[var(--color-muted-foreground)] sm:inline">
            Preview · no login
          </span>
          <Link href="/">
            <Button size="sm" variant="secondary">
              Home
            </Button>
          </Link>
        </header>

        <main id="main-content" className="mx-auto max-w-6xl px-6 py-7">
          {/* Header row */}
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--color-muted-foreground)]">
                Workspace
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">
                Your clip factory, at a glance.
              </h2>
            </div>
          </div>

          {/* Metric cards with sparkline */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              icon={Wallet}
              label="Credits left"
              value="238"
              hint="1 credit = 1 source min"
              trend={[6, 9, 7, 12, 8, 14, 10]}
            />
            <Metric
              icon={Target}
              label="Campaigns"
              value="2"
              hint="Active clip series"
              trend={[1, 1, 2, 2, 2, 2, 2]}
            />
            <Metric
              icon={Clock3}
              label="Jobs"
              value="11"
              hint="3 running right now"
              trend={[2, 4, 3, 6, 5, 7, 3]}
            />
            <Metric
              icon={Film}
              label="Clips ready"
              value="27"
              hint="No watermark"
              trend={[3, 5, 8, 9, 14, 21, 27]}
            />
          </div>

          {/* Two-column work area */}
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
            {/* Jobs panel with filter tabs + search */}
            <Panel
              title="Jobs"
              eyebrow="Pipeline"
              right={
                <span className="text-xs text-[var(--color-muted-foreground)]">
                  {filteredJobs.length} shown
                </span>
              }
            >
              <div className="flex flex-wrap items-center gap-2">
                {JOB_FILTERS.map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={
                      "rounded-full px-3 py-1.5 text-xs font-medium transition-colors " +
                      (filter === f
                        ? "bg-[var(--color-foreground)] text-[var(--color-background)]"
                        : "border border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]")
                    }
                  >
                    {f}
                  </button>
                ))}
              </div>

              <div className="mt-4 divide-y divide-[var(--color-border)]">
                {filteredJobs.length === 0 ? (
                  <p className="py-8 text-center text-sm text-[var(--color-muted-foreground)]">
                    No jobs match this filter.
                  </p>
                ) : (
                  filteredJobs.map((job) => (
                    <div
                      key={job.url}
                      className="flex items-center justify-between gap-4 py-3.5 first:pt-0"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm">{job.url}</p>
                        <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                          {job.time} · {job.clips} clip(s)
                        </p>
                      </div>
                      <StatusPill status={job.status} />
                    </div>
                  ))
                )}
              </div>
            </Panel>

            {/* Current job — output review */}
            <Panel title="Current job" eyebrow="Output review">
              <div className="grid gap-5 sm:grid-cols-[150px_1fr]">
                <div className="relative mx-auto aspect-[9/16] w-full max-w-[150px] overflow-hidden rounded-[1.25rem] border border-[var(--color-border)] bg-[linear-gradient(150deg,#26262a,#0a0a0b)]">
                  <div className="absolute inset-x-3 top-3 flex justify-between font-mono text-[10px] text-white/55">
                    <span>02:14</span>
                    <span>13:05</span>
                  </div>
                  <div className="absolute inset-x-4 top-16 h-20 rounded-[0.875rem] border border-white/10 bg-white/[0.06]" />
                  <div className="absolute inset-x-3 bottom-4">
                    <p className="text-sm font-semibold leading-tight text-white">
                      Setup and payoff in one clip.
                    </p>
                    <p className="mt-1.5 font-mono text-[9px] uppercase tracking-wider text-white/50">
                      captions · 1080x1920
                    </p>
                  </div>
                </div>

                <div className="min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">
                      Series clip · 42.6s · 2 segments
                    </p>
                    <span className="shrink-0 rounded-[0.875rem] bg-[var(--color-brand)] px-3 py-1.5 text-center text-[var(--color-brand-foreground)] shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]">
                      <span className="block font-mono text-[9px] uppercase tracking-wider opacity-80">
                        Score
                      </span>
                      <span className="block text-xl font-semibold tabular-nums leading-none">
                        91
                      </span>
                    </span>
                  </div>
                  <h3 className="mt-2 text-base font-semibold leading-snug">
                    He did not change the offer. He changed the frame.
                  </h3>

                  <div className="mt-4 space-y-2.5">
                    {[
                      ["Hook", 95],
                      ["Emotion", 88],
                      ["Visual proof", 92],
                      ["Audience fit", 90],
                    ].map(([label, value]) => (
                      <ScoreRow
                        key={label as string}
                        label={label as string}
                        value={value as number}
                      />
                    ))}
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
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
          </div>

          {/* Usage chart + campaigns */}
          <div className="mt-6 grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
            <Panel
              title="Usage"
              eyebrow="Last 7 days"
              right={
                <span className="text-xs text-[var(--color-muted-foreground)]">
                  62 credits
                </span>
              }
            >
              <div className="flex items-end justify-between gap-2.5 pt-2">
                {usage7d.map((u) => (
                  <div
                    key={u.d}
                    className="flex flex-1 flex-col items-center gap-2"
                  >
                    <div className="flex h-28 w-full items-end">
                      <div
                        className="w-full rounded-t-[0.4rem] bg-[var(--color-brand)]"
                        style={{
                          height: `${Math.max((u.v / maxUsage) * 100, 4)}%`,
                          opacity: u.v === 0 ? 0.25 : 1,
                        }}
                        title={`${u.v} credits`}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-[var(--color-muted-foreground)]">
                      {u.d}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Campaigns" eyebrow="Series goals">
              <div className="space-y-3">
                {campaigns.map((campaign) => (
                  <div
                    key={campaign.name}
                    className="rounded-[1.25rem] border border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-foreground)_3%,transparent)] p-4 transition-colors hover:border-[color-mix(in_srgb,var(--color-border)_45%,var(--color-foreground))]"
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
                    <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted-foreground)]">
                      <span className="text-[var(--color-foreground)]">
                        Goal:{" "}
                      </span>
                      {campaign.goal}
                    </p>
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          {/* Clips gallery with score filter */}
          <section className="liquid-shell mt-6 p-5 md:p-6">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">
                  Library
                </p>
                <h2 className="mt-2 text-xl font-semibold tracking-tight">
                  Recent clips
                </h2>
              </div>
              <button
                onClick={() => setTopClipsOnly((v) => !v)}
                className={
                  "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors " +
                  (topClipsOnly
                    ? "bg-[var(--color-foreground)] text-[var(--color-background)]"
                    : "border border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]")
                }
              >
                <Sparkles className="h-3.5 w-3.5" />
                Top picks (90+)
              </button>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {shownClips.map((clip) => (
                <article
                  key={clip.title}
                  className="rounded-[1.25rem] border border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-foreground)_3%,transparent)] p-5 transition-[border-color,transform] duration-150 ease-out hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--color-border)_45%,var(--color-foreground))]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">
                      Clip
                    </p>
                    <span className="rounded-[0.6rem] bg-[var(--color-brand)] px-2.5 py-1 font-mono text-sm font-semibold tabular-nums text-[var(--color-brand-foreground)]">
                      {clip.score}
                    </span>
                  </div>
                  <h3 className="mt-2.5 line-clamp-2 text-sm font-semibold leading-snug">
                    {clip.title}
                  </h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[var(--color-muted-foreground)]">
                    {clip.hook}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {clip.segments.map((segment) => (
                      <span key={segment} className="status-pill font-mono">
                        {segment}
                      </span>
                    ))}
                  </div>
                  <button className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[var(--color-brand)] transition-opacity duration-150 hover:opacity-75">
                    Review clip <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </article>
              ))}
            </div>
          </section>

          {/* Admin row */}
          <section className="mt-6 rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-muted)] p-6">
            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">
                  Admin preview
                </p>
                <h2 className="mt-2 text-xl font-semibold tracking-tight">
                  The numbers you watch before opening publicly.
                </h2>
              </div>
              <Link
                href="/preview"
                className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
              >
                Back to previews →
              </Link>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Metric
                icon={BarChart3}
                label="MRR"
                value="203 EUR"
                hint="7 active Starter subs"
              />
              <Metric
                icon={Sparkles}
                label="Clips"
                value="184"
                hint="Generated lifetime"
              />
              <Metric
                icon={GitBranch}
                label="Montage"
                value="41%"
                hint="Multi-segment clips"
              />
              <Metric
                icon={Eye}
                label="Vision cost"
                value="11.80 EUR"
                hint="Current month"
              />
              <Metric
                icon={Check}
                label="Margin"
                value="73%"
                hint="Gross estimate"
              />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

/* ── Pieces ───────────────────────────────────────────────────────── */

function Metric({
  icon: Icon,
  label,
  value,
  hint,
  trend,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
  trend?: number[];
}) {
  const max = trend ? Math.max(...trend, 1) : 1;
  return (
    <div className="rounded-[1.25rem] border border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-foreground)_3%,var(--color-background))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
          {label}
        </p>
        <Icon className="h-4 w-4 text-[var(--color-brand)]" />
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p>
      {trend ? (
        <div className="mt-3 flex h-6 items-end gap-0.5">
          {trend.map((t, i) => (
            <div
              key={i}
              className="flex-1 rounded-sm bg-[color-mix(in_srgb,var(--color-brand)_55%,transparent)]"
              style={{ height: `${Math.max((t / max) * 100, 8)}%` }}
            />
          ))}
        </div>
      ) : (
        <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
          {hint}
        </p>
      )}
      {trend ? (
        <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="font-mono text-xs tabular-nums text-[var(--color-muted-foreground)]">
          {value}
        </span>
      </div>
      <div className="mt-1.5 h-1 rounded-full bg-[color-mix(in_srgb,var(--color-foreground)_8%,transparent)]">
        <div
          className="h-full rounded-full bg-[var(--color-brand)]"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: JobStatus }) {
  const map: Record<JobStatus, string> = {
    completed:
      "text-[var(--color-brand)] border-[color-mix(in_srgb,var(--color-brand)_45%,transparent)]",
    rendering: "text-[var(--color-foreground)] border-[var(--color-border)]",
    analyzing: "text-[var(--color-foreground)] border-[var(--color-border)]",
    failed:
      "text-[var(--color-danger)] border-[color-mix(in_srgb,var(--color-danger)_45%,transparent)]",
  };
  return (
    <span
      className={
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs " +
        map[status]
      }
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{
          backgroundColor:
            status === "completed"
              ? "var(--color-brand)"
              : status === "failed"
                ? "var(--color-danger)"
                : "var(--color-muted-foreground)",
        }}
      />
      {status}
    </span>
  );
}

function Panel({
  title,
  eyebrow,
  right,
  children,
}: {
  title: string;
  eyebrow: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="liquid-shell p-5 md:p-6">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[var(--color-brand)]">
            {eyebrow}
          </p>
          <h2 className="mt-1.5 text-lg font-semibold tracking-tight">
            {title}
          </h2>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}
