"use client";

import * as React from "react";
import Link from "next/link";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export type SeriesJob = {
  id: string;
  source_url: string;
  status: string;
  current_step: string | null;
  error_message: string | null;
  credits_charged: number | null;
  series_position: number;
};

type SeriesView = { jobs: SeriesJob[] };
const TERMINAL = new Set(["completed", "failed", "canceled"]);

export function SeriesMonitor({ seriesId, initialJobs }: { seriesId: string; initialJobs: SeriesJob[] }) {
  const router = useRouter();
  const initiallyFinished = initialJobs.every((job) => TERMINAL.has(job.status));
  const { data, error } = useSWR<SeriesView>(
    initiallyFinished ? null : `/series/${seriesId}`,
    (path: string) => apiFetch<SeriesView>(path),
    { refreshInterval: (latest) => latest?.jobs.every((job) => TERMINAL.has(job.status)) ? 0 : 5000, revalidateOnFocus: false }
  );
  const jobs = data?.jobs ?? initialJobs;
  const completed = jobs.filter((job) => job.status === "completed").length;
  const finished = jobs.filter((job) => TERMINAL.has(job.status)).length;
  const lastFinished = React.useRef(initialJobs.filter((job) => TERMINAL.has(job.status)).length);

  React.useEffect(() => {
    if (finished > lastFinished.current) {
      lastFinished.current = finished;
      router.refresh();
    }
  }, [finished, router]);

  return (
    <section className="pro-panel mt-8 rounded-lg p-5" aria-label="Source processing status">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Sources</h2>
        <p className="text-sm text-[var(--color-muted-foreground)]" aria-live="polite">
          {finished} of {jobs.length} finished · {completed} completed
        </p>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">
          Live progress is unavailable. Refresh this page to check the series.
        </p>
      )}
      <ol className="mt-4 divide-y divide-[var(--color-border)]">
        {jobs.map((job, index) => (
          <li key={job.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">Video {index + 1}</p>
              <p className="truncate text-xs text-[var(--color-muted-foreground)]" title={job.source_url}>{job.source_url}</p>
              {job.error_message && <p className="mt-1 text-xs text-[var(--color-danger)]">{job.error_message}</p>}
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className="status-pill text-xs">{job.status === "queued" && index > 0 ? "Waiting" : job.status}</span>
              <Link href={`/app/jobs/${job.id}`} className="text-xs text-[var(--color-brand)] hover:underline">Details</Link>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
