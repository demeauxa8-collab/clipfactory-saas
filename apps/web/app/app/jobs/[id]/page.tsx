import Link from "next/link";
import { notFound } from "next/navigation";
import { Lock } from "lucide-react";
import { Container } from "@/components/ui/container";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { clipIsLocked, planFromCode } from "@/lib/plan";
import { ClipActions } from "./clip-actions";
import { JobMonitor } from "./job-monitor";
import { UpgradeWall } from "./upgrade-wall";

export const metadata = { title: "Job" };

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createSupabaseServerClient();

  const { data: job } = await supabase
    .from("jobs")
    .select(
      "id, source_url, status, current_step, target_clip_count, duration_seconds, credits_charged, error_code, error_message, queued_at, finished_at, campaign_id"
    )
    .eq("id", id)
    .maybeSingle();

  if (!job) notFound();

  const { data: clips } = await supabase
    .from("clips")
    .select(
      "id, idx, title, hook_text, rationale, visual_summary, transcript_excerpt, start_seconds, end_seconds, duration_seconds, rendered_duration_seconds, segments, score_total, score_breakdown"
    )
    .eq("job_id", id)
    .order("idx", { ascending: true });

  // Which plan is paying for this account right now. A paid subscription has a
  // current_period_end and therefore outranks the trial, whose end is null.
  const { data: sub } = await supabase
    .from("subscriptions")
    .select("plan_code, current_period_end")
    .in("status", ["trialing", "active"])
    .order("current_period_end", { ascending: false, nullsFirst: false })
    .limit(1)
    .maybeSingle();

  const plan = planFromCode(sub?.plan_code as string | undefined);
  const lockedCount = (clips ?? []).filter((c) => clipIsLocked(plan, Number(c.idx))).length;

  return (
    <Container className="py-10">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Job</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight break-all">{job.source_url}</h1>
        </div>
        <Link href={job.campaign_id ? `/app/campaigns/${job.campaign_id}` : "/app"} className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">← Back</Link>
      </div>

      <JobMonitor
        jobId={String(job.id)}
        initialStatus={String(job.status)}
        initialStep={job.current_step as string | null}
      />

      {job.error_code && (
        <div className="mt-6 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-muted)] p-4 text-sm text-[var(--color-foreground)]">
          <p className="font-medium">Job failed: {job.error_code}</p>
          <p className="mt-1 text-[var(--color-muted-foreground)]">{job.error_message ?? "No additional message."}</p>
        </div>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Clips</h2>
        {(clips?.length ?? 0) === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
            No clips yet. They appear once the job reaches the rendering stage.
          </p>
        ) : (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {(clips ?? []).map((c) => (
              <ClipCard
                key={String(c.id)}
                clip={c as ClipDTO}
                locked={clipIsLocked(plan, Number(c.idx))}
              />
            ))}
          </div>
        )}

        {lockedCount > 0 && (
          <UpgradeWall lockedCount={lockedCount} totalCount={clips?.length ?? 0} />
        )}
      </section>
    </Container>
  );
}

type Segment = {
  role: "setup" | "transition" | "payoff" | "single";
  start: number;
  end: number;
  transcript_excerpt?: string;
};

type ClipDTO = {
  id: string;
  idx: number;
  title: string | null;
  hook_text: string | null;
  rationale: string | null;
  visual_summary: string | null;
  transcript_excerpt: string | null;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  rendered_duration_seconds: number | null;
  segments: Segment[] | null;
  score_total: number | null;
  score_breakdown: Record<string, number> | null;
};

function ClipCard({ clip, locked = false }: { clip: ClipDTO; locked?: boolean }) {
  const breakdown = clip.score_breakdown ?? {};
  const segments = clip.segments ?? [];
  const isMontage = segments.length > 1;
  const renderedDuration = clip.rendered_duration_seconds ?? clip.duration_seconds;

  return (
    <div className="pro-card rounded-lg p-5">
      <div className="grid gap-5 sm:grid-cols-[128px_1fr]">
        <div className="relative mx-auto aspect-[9/16] w-full max-w-[8rem] overflow-hidden rounded-md border border-[var(--color-border)] bg-[linear-gradient(145deg,#2a2a2d,#090909)]">
          <div className="absolute inset-x-3 top-3 flex justify-between font-mono text-[10px] text-white/55">
            <span>{formatTimestamp(clip.start_seconds)}</span>
            <span>{formatTimestamp(clip.end_seconds)}</span>
          </div>
          <div className="absolute inset-x-4 top-16 h-20 rounded-md border border-white/10 bg-white/[0.06]" />
          <div className="absolute inset-x-3 bottom-4">
            <p className="line-clamp-3 text-sm font-semibold leading-tight text-white">
              {clip.hook_text ?? clip.title ?? "Generated clip"}
            </p>
          </div>
          {/* The clip exists and is rendered — only the file is behind the plan. */}
          {locked && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/55 backdrop-blur-[3px]">
              <Lock className="h-5 w-5 text-white/85" />
            </div>
          )}
        </div>

        <div className="min-w-0">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
                Clip {clip.idx + 1} · {renderedDuration.toFixed(1)}s
                {isMontage && (
                  <span className="ml-2 rounded-sm border border-[var(--color-border)] bg-[var(--color-muted)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-foreground)]">
                    MONTAGE · {segments.length} SEGMENTS
                  </span>
                )}
              </p>
              <p className="mt-1 truncate font-medium">{clip.title ?? "Untitled"}</p>
              {clip.hook_text && (
                <p className="mt-1 line-clamp-2 text-sm text-[var(--color-muted-foreground)]">{clip.hook_text}</p>
              )}
            </div>
            <div className="rounded-md bg-[var(--color-foreground)] px-3 py-2 text-right text-[var(--color-background)]">
              <p className="font-mono text-[10px] uppercase tracking-wider">Score</p>
              <p className="text-2xl font-semibold tabular-nums">{clip.score_total ?? "—"}</p>
            </div>
          </div>

          {isMontage && (
            <ol className="mt-3 flex flex-wrap gap-1.5 text-xs">
              {segments.map((s, i) => (
                <li
                  key={i}
                  className="rounded border border-[var(--color-border)] bg-[var(--color-muted)] px-2 py-1 font-mono"
                  title={s.transcript_excerpt}
                >
                  <span className="font-semibold uppercase">{s.role}</span>{" "}
                  {formatTimestamp(s.start)}-{formatTimestamp(s.end)}
                </li>
              ))}
            </ol>
          )}

          {clip.rationale && (
            <p className="mt-3 text-sm leading-relaxed">
              <span className="text-[var(--color-muted-foreground)]">Why: </span>
              {clip.rationale}
            </p>
          )}
          {clip.visual_summary && (
            <p className="mt-2 text-xs leading-relaxed text-[var(--color-muted-foreground)]">{clip.visual_summary}</p>
          )}

          {Object.keys(breakdown).length > 0 && (
            <dl className="mt-4 grid grid-cols-3 gap-2 text-xs sm:grid-cols-5">
              {Object.entries(breakdown).map(([k, v]) => (
                <div key={k} className="rounded border border-[var(--color-border)] bg-black/20 p-2 text-center">
                  <dt className="text-[var(--color-muted-foreground)]">{shortLabel(k)}</dt>
                  <dd className="mt-0.5 font-medium tabular-nums">{v ?? "—"}</dd>
                </div>
              ))}
            </dl>
          )}

          <ClipActions clipId={clip.id} locked={locked} />
        </div>
      </div>
    </div>
  );
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function shortLabel(k: string): string {
  switch (k) {
    case "hook":
      return "Hook";
    case "emotion":
      return "Emo";
    case "visual":
      return "Vis";
    case "campaign_fit":
      return "Fit";
    case "editing_difficulty":
    case "editing_continuity":
      return "Edit";
    case "payoff_strength":
      return "Payoff";
    case "setup_clarity":
      return "Setup";
    case "visual_proof":
      return "Vis";
    case "retention":
      return "Retn";
    default:
      return k.length > 6 ? k.slice(0, 6) : k;
  }
}
