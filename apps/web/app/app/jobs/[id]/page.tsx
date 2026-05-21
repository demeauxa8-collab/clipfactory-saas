import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/ui/container";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { JobMonitor } from "./job-monitor";

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
      "id, idx, title, hook_text, rationale, visual_summary, transcript_excerpt, start_seconds, end_seconds, duration_seconds, score_total, score_breakdown"
    )
    .eq("job_id", id)
    .order("idx", { ascending: true });

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
        <div className="mt-6 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          <p className="font-medium">Job failed: {job.error_code}</p>
          <p className="mt-1">{job.error_message ?? "No additional message."}</p>
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
              <ClipCard key={String(c.id)} clip={c as ClipDTO} />
            ))}
          </div>
        )}
      </section>
    </Container>
  );
}

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
  score_total: number | null;
  score_breakdown: Record<string, number> | null;
};

function ClipCard({ clip }: { clip: ClipDTO }) {
  const breakdown = clip.score_breakdown ?? {};
  return (
    <div className="rounded-lg border border-[var(--color-border)] p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
            Clip {clip.idx + 1} · {clip.duration_seconds.toFixed(1)}s
          </p>
          <p className="mt-1 font-medium truncate">{clip.title ?? "Untitled"}</p>
          {clip.hook_text && (
            <p className="mt-1 text-sm text-[var(--color-muted-foreground)] line-clamp-2">{clip.hook_text}</p>
          )}
        </div>
        <div className="text-3xl font-semibold tabular-nums">{clip.score_total ?? "—"}</div>
      </div>

      {clip.rationale && (
        <p className="mt-3 text-sm">
          <span className="text-[var(--color-muted-foreground)]">Why: </span>
          {clip.rationale}
        </p>
      )}
      {clip.visual_summary && (
        <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">{clip.visual_summary}</p>
      )}

      <dl className="mt-4 grid grid-cols-5 gap-2 text-xs">
        {(["hook", "emotion", "visual", "campaign_fit", "editing_difficulty"] as const).map((k) => (
          <div key={k} className="rounded border border-[var(--color-border)] p-2 text-center">
            <dt className="text-[var(--color-muted-foreground)]">{shortLabel(k)}</dt>
            <dd className="mt-0.5 font-medium tabular-nums">{breakdown[k] ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <ClipActions clipId={clip.id} />
    </div>
  );
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
      return "Edit";
    default:
      return k;
  }
}

import { ClipActions } from "./clip-actions";
