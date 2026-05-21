"use client";

import * as React from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const STEPS = [
  "queued",
  "downloading",
  "transcribing",
  "analyzing",
  "rendering",
  "completed",
];

type JobView = {
  job: {
    id: string;
    status: string;
    current_step: string | null;
    error_code: string | null;
    error_message: string | null;
  };
};

const POLL_INTERVAL_MS = 5000;

export function JobMonitor({
  jobId,
  initialStatus,
  initialStep,
}: {
  jobId: string;
  initialStatus: string;
  initialStep: string | null;
}) {
  const router = useRouter();
  const isTerminal = (s: string) => s === "completed" || s === "failed" || s === "canceled";

  const { data } = useSWR<JobView>(
    isTerminal(initialStatus) ? null : `/jobs/${jobId}`,
    (path: string) => apiFetch<JobView>(path),
    { refreshInterval: POLL_INTERVAL_MS, revalidateOnFocus: false }
  );

  const status = data?.job.status ?? initialStatus;
  const step = data?.job.current_step ?? initialStep;

  // When job becomes terminal, refresh the server component once to pull clips
  const wasTerminal = React.useRef(isTerminal(initialStatus));
  React.useEffect(() => {
    if (!wasTerminal.current && isTerminal(status)) {
      wasTerminal.current = true;
      router.refresh();
    }
  }, [status, router]);

  const activeIndex = Math.max(
    0,
    STEPS.indexOf(status === "failed" ? step ?? "queued" : status)
  );

  return (
    <div className="mt-6 rounded-lg border border-[var(--color-border)] p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Pipeline</p>
        <p className="text-xs text-[var(--color-muted-foreground)]">
          {status} {step && status !== step ? `· ${step}` : ""}
        </p>
      </div>
      <ol className="mt-4 flex flex-wrap gap-2 text-xs">
        {STEPS.map((s, i) => {
          const done = i < activeIndex || status === "completed";
          const current = i === activeIndex && status !== "completed";
          return (
            <li
              key={s}
              className={
                "rounded-md border px-2 py-1 " +
                (done
                  ? "border-[var(--color-foreground)] bg-[var(--color-foreground)] text-[var(--color-background)]"
                  : current
                  ? "border-[var(--color-foreground)]"
                  : "border-[var(--color-border)] text-[var(--color-muted-foreground)]")
              }
            >
              {s}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
