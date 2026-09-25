import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Clapperboard,
  Clock3,
  Download,
  Film,
  Gauge,
  MessageSquare,
  Plus,
  Rocket,
  Sparkles,
  Target,
  ThumbsUp,
  Wallet,
} from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const metadata = { title: "Dashboard" };

type CampaignRow = {
  id: string;
  name: string;
  audience: string | null;
  niche: string | null;
  created_at: string;
};

type JobRow = {
  id: string;
  source_url: string;
  status: string;
  target_clip_count: number;
  campaign_id: string | null;
  queued_at: string;
  duration_seconds: number | null;
};

type SubRow = {
  plan_code: string;
  status: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean | null;
};

type PlanRow = { code: string; name: string; credits_per_period: number };

type EventRow = {
  event_name: string;
  source: string;
  created_at: string;
  properties: Record<string, unknown> | null;
};

const RUNNING = new Set(["queued", "downloading", "transcribing", "analyzing", "rendering"]);
const STARTER_CREDITS = 300;

export default async function AppHome() {
  const supabase = await createSupabaseServerClient();

  const [
    { data: campaigns },
    { data: jobs },
    { data: ledger },
    { count: clipsCount },
    { data: sub },
    { data: plans },
    { data: events },
  ] = await Promise.all([
    supabase
      .from("campaigns")
      .select("id, name, audience, niche, created_at")
      .order("created_at", { ascending: false })
      .limit(8),
    supabase
      .from("jobs")
      .select("id, source_url, status, target_clip_count, campaign_id, queued_at, duration_seconds")
      .order("queued_at", { ascending: false })
      .limit(60),
    supabase.from("credit_ledger").select("delta"),
    supabase.from("clips").select("id", { count: "exact", head: true }),
    supabase
      .from("subscriptions")
      .select("plan_code, status, current_period_end, cancel_at_period_end")
      .order("current_period_end", { ascending: false, nullsFirst: false })
      .limit(1)
      .maybeSingle(),
    supabase.from("plan_definitions").select("code, name, credits_per_period"),
    supabase
      .from("analytics_events")
      .select("event_name, source, created_at, properties")
      .order("created_at", { ascending: false })
      .limit(40),
  ]);

  const balance = (ledger ?? []).reduce(
    (acc, row) => acc + (typeof row.delta === "number" ? row.delta : 0),
    0
  );
  const jobList = (jobs ?? []) as JobRow[];
  const subscription = (sub ?? null) as SubRow | null;
  const planList = (plans ?? []) as PlanRow[];

  const activeSub = subscription && ["active", "trialing", "past_due"].includes(subscription.status);
  const plan = planList.find((p) => p.code === subscription?.plan_code);
  const planCredits = plan?.credits_per_period ?? STARTER_CREDITS;
  const usedThisPeriod = Math.max(0, planCredits - balance);
  const usedPct = Math.min(100, Math.round((usedThisPeriod / planCredits) * 100));

  const completed = jobList.filter((j) => j.status === "completed");
  const failed = jobList.filter((j) => j.status === "failed" || j.status === "canceled");
  const running = jobList.filter((j) => RUNNING.has(j.status));
  const finishedTotal = completed.length + failed.length;
  const successRate = finishedTotal > 0 ? Math.round((completed.length / finishedTotal) * 100) : null;
  const minutesProcessed = Math.round(
    completed.reduce((acc, j) => acc + (j.duration_seconds ?? 0), 0) / 60
  );
  const clipsGenerated = clipsCount ?? 0;

  const campaignList = (campaigns ?? []) as CampaignRow[];
  const jobCountByCampaign = new Map<string, number>();
  for (const j of jobList) {
    if (j.campaign_id) jobCountByCampaign.set(j.campaign_id, (jobCountByCampaign.get(j.campaign_id) ?? 0) + 1);
  }

  const activity = ((events ?? []) as EventRow[])
    .filter((e) => !HIDDEN_EVENTS.has(e.event_name))
    .slice(0, 8);

  return (
    <Container className="py-10">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="fade-up flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight md:text-[2.5rem]">Dashboard</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--color-muted-foreground)]">
            Create a campaign, submit one or more videos, then review the generated clips, scores and
            downloads in one place.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PlanChip activeSub={!!activeSub} planName={plan?.name} sub={subscription} />
          <Link href="/app/campaigns/new" className="inline-flex">
            <Button>
              <Plus className="h-4 w-4" />
              New campaign
            </Button>
          </Link>
        </div>
      </div>

      {/* ── Credits hero + metrics ─────────────────────────────── */}
      <div className="fade-up-2 mt-8 grid gap-4 lg:grid-cols-3">
        <div className="liquid-shell relative overflow-hidden p-6 lg:row-span-1">
          <div className="flex items-center justify-between">
            <p className="text-[0.8125rem] text-[var(--color-muted-foreground)]">Credits</p>
            <Wallet className="h-4 w-4 text-[var(--color-brand)]" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-5xl font-semibold tabular-nums">{balance}</span>
            <span className="text-sm text-[var(--color-muted-foreground)]">
              / {planCredits} per month
            </span>
          </div>
          <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-foreground)_8%,transparent)]">
            <div
              className="score-fill h-full rounded-full bg-[var(--color-brand)]"
              style={{ width: `${100 - usedPct}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-[var(--color-muted-foreground)]">
            <span>{usedThisPeriod} used this period</span>
            <span>1 credit = 1 min of source</span>
          </div>
          {!activeSub && (
            <Link
              href="/app/billing"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-[var(--color-brand)] transition-opacity hover:opacity-80"
            >
              <Rocket className="h-3.5 w-3.5" /> Activate Starter to get {planCredits} credits
            </Link>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          <Metric icon={Film} label="Clips generated" value={clipsGenerated.toString()} hint="lifetime, no watermark" />
          <Metric
            icon={CheckCircle2}
            label="Jobs completed"
            value={completed.length.toString()}
            hint={successRate === null ? "no finished jobs yet" : `${successRate}% success rate`}
            accent={successRate !== null && successRate >= 80}
          />
          <Metric icon={Clock3} label="Jobs running" value={running.length.toString()} hint={`${jobList.length} recent total`} pulse={running.length > 0} />
          <Metric icon={Gauge} label="Minutes processed" value={minutesProcessed.toString()} hint="source minutes, completed" />
        </div>
      </div>

      {/* ── Work area ──────────────────────────────────────────── */}
      <div className="fade-up-3 mt-10 grid gap-6 lg:grid-cols-2">
        {/* Campaigns */}
        <section className="liquid-shell p-5 md:p-6">
          <SectionHead title="Campaigns" icon={Target}>
            <Link href="/app/campaigns/new">
              <Button size="sm">
                <Plus className="h-4 w-4" />
                New
              </Button>
            </Link>
          </SectionHead>
          {campaignList.length === 0 ? (
            <EmptyState>No campaigns yet. Create one to start submitting videos.</EmptyState>
          ) : (
            <div className="-mx-2 mt-1">
              {campaignList.map((c) => (
                <a
                  key={c.id}
                  href={`/app/campaigns/${c.id}`}
                  className="group flex items-center justify-between gap-4 rounded-2xl px-2 py-3 transition-colors hover:bg-[color-mix(in_srgb,var(--color-foreground)_4%,transparent)]"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] text-[var(--color-brand)]">
                      <Target className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{c.name}</p>
                      <p className="truncate text-xs text-[var(--color-muted-foreground)]">
                        {[c.niche, c.audience].filter(Boolean).join(" · ") || "no audience set"}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="hidden text-xs text-[var(--color-muted-foreground)] sm:inline">
                      {jobCountByCampaign.get(c.id) ?? 0} job(s)
                    </span>
                    <ArrowRight className="h-4 w-4 text-[var(--color-muted-foreground)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--color-foreground)]" />
                  </div>
                </a>
              ))}
            </div>
          )}
        </section>

        {/* Recent jobs */}
        <section className="liquid-shell p-5 md:p-6">
          <SectionHead title="Recent jobs" icon={Clapperboard} />
          {jobList.length > 0 && (
            <StatusBar completed={completed.length} running={running.length} failed={failed.length} />
          )}
          {jobList.length === 0 ? (
            <EmptyState>No jobs yet. Open a campaign and submit a video URL.</EmptyState>
          ) : (
            <div className="-mx-2 mt-3">
              {jobList.slice(0, 7).map((j) => (
                <a
                  key={j.id}
                  href={`/app/jobs/${j.id}`}
                  className="group flex items-center justify-between gap-4 rounded-2xl px-2 py-3 transition-colors hover:bg-[color-mix(in_srgb,var(--color-foreground)_4%,transparent)]"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm">{prettyUrl(j.source_url)}</p>
                    <p className="mt-0.5 text-xs text-[var(--color-muted-foreground)]">
                      {j.target_clip_count} clip(s) · {relativeTime(j.queued_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusPill status={j.status} />
                    <ArrowRight className="h-4 w-4 text-[var(--color-muted-foreground)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--color-foreground)]" />
                  </div>
                </a>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* ── Activity feed ──────────────────────────────────────── */}
      <section className="fade-up-3 liquid-shell mt-6 p-5 md:p-6">
        <SectionHead title="Activity" icon={Sparkles} />
        {activity.length === 0 ? (
          <EmptyState>Activity from your account will show up here as you use ClipFactory.</EmptyState>
        ) : (
          <ol className="mt-1">
            {activity.map((e, i) => {
              const meta = describeEvent(e);
              return (
                <li key={`${e.created_at}-${i}`} className="flex items-center gap-3 py-2.5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-background)] text-[var(--color-muted-foreground)]">
                    <meta.icon className="h-3.5 w-3.5" />
                  </span>
                  <p className="min-w-0 flex-1 truncate text-sm">{meta.label}</p>
                  <span className="shrink-0 text-xs tabular-nums text-[var(--color-muted-foreground)]">
                    {relativeTime(e.created_at)}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </Container>
  );
}

/* ── Components ────────────────────────────────────────────────── */

function PlanChip({
  activeSub,
  planName,
  sub,
}: {
  activeSub: boolean;
  planName?: string;
  sub: SubRow | null;
}) {
  if (!activeSub) {
    return (
      <Link
        href="/app/billing"
        className="status-pill gap-1.5 transition-colors hover:text-[var(--color-foreground)]"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-muted-foreground)]" />
        Free plan
      </Link>
    );
  }
  const renews = sub?.current_period_end ? shortDate(sub.current_period_end) : null;
  return (
    <span className="status-pill gap-1.5 text-[var(--color-foreground)]">
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-brand)]" />
      {planName ?? "Starter"}
      {renews && (
        <span className="text-[var(--color-muted-foreground)]">
          · {sub?.cancel_at_period_end ? "ends" : "renews"} {renews}
        </span>
      )}
    </span>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  hint,
  accent = false,
  pulse = false,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
  accent?: boolean;
  pulse?: boolean;
}) {
  return (
    <div className="group rounded-[1.25rem] border border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-foreground)_3%,var(--color-background))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition-all duration-300 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--color-foreground)_18%,transparent)]">
      <div className="flex items-center justify-between gap-4">
        <p className="text-[0.8125rem] text-[var(--color-muted-foreground)]">{label}</p>
        <span className={pulse ? "brand-pulse rounded-full" : ""}>
          <Icon className={"h-4 w-4 " + (accent ? "text-[var(--color-brand)]" : "text-[var(--color-muted-foreground)] group-hover:text-[var(--color-brand)] transition-colors")} />
        </span>
      </div>
      <p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{hint}</p>
    </div>
  );
}

function SectionHead({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] text-[var(--color-brand)]">
          <Icon className="h-4 w-4" />
        </span>
        <h2 className="text-lg font-semibold leading-tight tracking-tight">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function StatusBar({ completed, running, failed }: { completed: number; running: number; failed: number }) {
  const total = completed + running + failed;
  if (total === 0) return null;
  const seg = (n: number) => `${(n / total) * 100}%`;
  return (
    <div className="mt-1">
      <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-foreground)_8%,transparent)]">
        <div className="h-full bg-[var(--color-brand)]" style={{ width: seg(completed) }} />
        <div className="h-full bg-[var(--color-muted-foreground)]" style={{ width: seg(running) }} />
        <div className="h-full bg-[var(--color-danger)]" style={{ width: seg(failed) }} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-muted-foreground)]">
        <Legend color="var(--color-brand)" label={`${completed} done`} />
        <Legend color="var(--color-muted-foreground)" label={`${running} running`} />
        <Legend color="var(--color-danger)" label={`${failed} failed`} />
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2 rounded-[1.25rem] border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted-foreground)]">
      {children}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "completed"
      ? "text-[var(--color-brand)] border-[color-mix(in_srgb,var(--color-brand)_45%,transparent)]"
      : status === "failed" || status === "canceled"
        ? "text-[var(--color-danger)] border-[color-mix(in_srgb,var(--color-danger)_45%,transparent)]"
        : "text-[var(--color-foreground)] border-[var(--color-border)]";
  const dot =
    status === "completed"
      ? "var(--color-brand)"
      : status === "failed" || status === "canceled"
        ? "var(--color-danger)"
        : "var(--color-muted-foreground)";
  const animate = RUNNING.has(status);
  return (
    <span className={"inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs " + tone}>
      <span
        className={"h-1.5 w-1.5 rounded-full " + (animate ? "animate-pulse" : "")}
        style={{ backgroundColor: dot }}
      />
      {status}
    </span>
  );
}

/* ── Helpers ───────────────────────────────────────────────────── */

const HIDDEN_EVENTS = new Set(["pageview", "api_request"]);

const EVENT_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  job_created: { label: "Job submitted", icon: Clapperboard },
  job_started: { label: "Pipeline started", icon: Rocket },
  job_completed: { label: "Clips ready", icon: CheckCircle2 },
  job_failed: { label: "Job failed", icon: Clock3 },
  campaign_created: { label: "Campaign created", icon: Target },
  checkout_started: { label: "Checkout started", icon: Wallet },
  upgrade_clicked: { label: "Viewed upgrade", icon: Rocket },
  clip_download: { label: "Clip downloaded", icon: Download },
  clip_download_clicked: { label: "Clip downloaded", icon: Download },
  clip_feedback: { label: "Clip feedback", icon: ThumbsUp },
  clip_feedback_clicked: { label: "Clip feedback", icon: ThumbsUp },
  login_attempt: { label: "Signed in", icon: MessageSquare },
};

function describeEvent(e: EventRow): { label: string; icon: React.ComponentType<{ className?: string }> } {
  const meta = EVENT_META[e.event_name];
  if (meta) return meta;
  return { label: e.event_name.replace(/_/g, " "), icon: Sparkles };
}

function prettyUrl(url: string): string {
  try {
    const u = new URL(url);
    return `${u.hostname.replace(/^www\./, "")}${u.pathname}${u.search}`.slice(0, 64);
  } catch {
    return url.slice(0, 64);
  }
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return shortDate(iso);
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
