import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/ui/container";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { ClipActions } from "@/app/app/jobs/[id]/clip-actions";
import { SeriesMonitor, type SeriesJob } from "./series-monitor";

export const metadata = { title: "Clip series" };

type ClipRow = {
  id: string;
  job_id: string;
  title: string | null;
  hook_text: string | null;
  score_total: number | null;
};

export default async function SeriesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createSupabaseServerClient();
  const { data: series } = await supabase
    .from("clip_series").select("id, campaign_id, created_at").eq("id", id).maybeSingle();
  if (!series) notFound();

  const { data: jobs } = await supabase
    .from("jobs")
    .select("id, source_url, status, current_step, error_message, credits_charged, series_position")
    .eq("series_id", id).order("series_position", { ascending: true });
  const sourceJobs = (jobs ?? []) as SeriesJob[];
  const ids = sourceJobs.map((job) => job.id);
  const { data: clips } = ids.length > 0
    ? await supabase.from("clips")
      .select("id, job_id, title, hook_text, score_total")
      .in("job_id", ids).order("score_total", { ascending: false })
    : { data: [] as ClipRow[] };
  const sourceByJob = new Map(sourceJobs.map((job) => [job.id, job]));

  return (
    <Container className="py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Campaign clip series</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Clips from {sourceJobs.length} videos</h1>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
            Sources are processed in order. Every clip links back to its original video.
          </p>
        </div>
        <Link href={`/app/campaigns/${series.campaign_id}`} className="text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]">
          ← Campaign
        </Link>
      </div>

      <SeriesMonitor seriesId={String(series.id)} initialJobs={sourceJobs} />

      <section className="mt-10">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-lg font-semibold">Series clips</h2>
          <span className="text-sm text-[var(--color-muted-foreground)]">{clips?.length ?? 0} ready</span>
        </div>
        {(clips?.length ?? 0) === 0 ? (
          <div className="pro-panel mt-4 rounded-lg p-6 text-sm text-[var(--color-muted-foreground)]">
            Clips will appear here as each video finishes. You can leave this page and return later.
          </div>
        ) : (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {((clips ?? []) as ClipRow[]).map((clip) => {
              const source = sourceByJob.get(clip.job_id);
              return (
                <article key={clip.id} className="pro-card min-w-0 rounded-lg p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-xs text-[var(--color-muted-foreground)]">Video {(source?.series_position ?? 0) + 1}</p>
                      <h3 className="mt-1 text-base font-medium">{clip.title || "Untitled clip"}</h3>
                    </div>
                    <span className="rounded-md border border-[var(--color-border)] px-2 py-1 text-sm font-medium tabular-nums">
                      {clip.score_total ?? "—"}
                    </span>
                  </div>
                  {clip.hook_text && <p className="mt-2 line-clamp-2 text-sm text-[var(--color-muted-foreground)]">{clip.hook_text}</p>}
                  {source && (
                    <Link href={`/app/jobs/${source.id}`} className="mt-3 block truncate text-xs text-[var(--color-brand)] hover:underline" title={source.source_url}>
                      Source: {source.source_url}
                    </Link>
                  )}
                  <ClipActions clipId={clip.id} />
                </article>
              );
            })}
          </div>
        )}
      </section>
    </Container>
  );
}
