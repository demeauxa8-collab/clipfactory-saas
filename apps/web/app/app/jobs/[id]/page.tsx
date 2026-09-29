import Link from "next/link";
import type { Route } from "next";
import { notFound } from "next/navigation";
import { AlertTriangle, Clapperboard, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ProductBackLink,
  ProductEmptyState,
  ProductPageIntro,
  ProductPanel,
  ProductSectionTitle,
  ProductStatus,
} from "@/components/product/product-primitives";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { ClipReview, type ClipReviewData } from "./clip-review";
import { JobMonitor } from "./job-monitor";
import styles from "./job-page.module.css";

export const metadata = { title: "Analysis" };

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createSupabaseServerClient();
  const { data: job } = await supabase
    .from("jobs")
    .select(
      "id, source_url, status, current_step, target_clip_count, duration_seconds, credits_charged, error_code, error_message, queued_at, finished_at, campaign_id",
    )
    .eq("id", id)
    .maybeSingle();

  if (!job) notFound();

  const { data: clips } = await supabase
    .from("clips")
    .select(
      "id, idx, title, hook_text, rationale, visual_summary, transcript_excerpt, start_seconds, end_seconds, duration_seconds, rendered_duration_seconds, segments, score_total, score_breakdown",
    )
    .eq("job_id", id)
    .order("idx", { ascending: true });

  const clipList = (clips ?? []) as ClipReviewData[];
  const backHref = (
    job.campaign_id ? `/app/campaigns/${job.campaign_id}` : "/app"
  ) as Route;
  const isRunning = [
    "queued",
    "downloading",
    "transcribing",
    "analyzing",
    "rendering",
  ].includes(job.status);

  return (
    <div className="cf-page">
      <ProductBackLink href={backHref}>
        {job.campaign_id ? "Campaign" : "Workspace"}
      </ProductBackLink>
      <ProductPageIntro
        className={styles.intro}
        eyebrow="Source analysis"
        title={readableSource(job.source_url)}
        description="The frame, transcript-grounded words and campaign reason stay attached to the same source moments."
        actions={
          <ProductStatus
            tone={
              job.status === "completed"
                ? "success"
                : job.status === "failed"
                  ? "danger"
                  : "action"
            }
            pulse={isRunning}
          >
            {readableStatus(job.status)}
          </ProductStatus>
        }
      />

      <JobMonitor
        jobId={String(job.id)}
        initialStatus={String(job.status)}
        initialStep={job.current_step as string | null}
      />

      {job.error_code ? (
        <ProductPanel tone="signal" className={styles.errorPanel}>
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>{humanizeJobError(job.error_code).title}</strong>
            <p>{humanizeJobError(job.error_code).description}</p>
            <Button asChild variant="secondary" size="sm">
              <Link href={backHref}>
                <RotateCcw aria-hidden="true" /> Return to campaign
              </Link>
            </Button>
          </div>
        </ProductPanel>
      ) : null}

      <section className={styles.results}>
        <ProductSectionTitle
          eyebrow="Delivered cuts"
          title={
            clipList.length
              ? `${clipList.length} ${clipList.length === 1 ? "cut" : "cuts"}, each with a reason.`
              : "The result will land here."
          }
          description={
            clipList.length
              ? "Select a cut, inspect its source thread, then download or teach ClipFactory what worked."
              : "ClipFactory only returns moments that survive transcript anchoring, campaign fit and render checks."
          }
        />

        {clipList.length ? (
          <ClipReview clips={clipList} />
        ) : (
          <ProductPanel className={styles.emptyPanel}>
            <ProductEmptyState
              icon={Clapperboard}
              title={
                job.status === "completed"
                  ? "No cut met this campaign brief"
                  : job.status === "failed"
                    ? "No cut was delivered"
                    : "Cuts are still being built"
              }
              description={
                job.status === "completed"
                  ? "The source completed without a verified candidate. Return to the campaign and try another public source."
                  : job.status === "failed"
                    ? "This analysis stopped before a verified render was delivered. The campaign and source history remain available."
                    : "You can leave this page. The analysis log above keeps the last confirmed processing state."
              }
              action={
                job.status === "completed" || job.status === "failed" ? (
                  <Button asChild>
                    <Link href={backHref}>Try another source</Link>
                  </Button>
                ) : undefined
              }
            />
          </ProductPanel>
        )}
      </section>
    </div>
  );
}

function readableSource(source: string) {
  try {
    const url = new URL(source);
    return `${url.hostname.replace("www.", "")}${url.pathname.slice(0, 48)}`;
  } catch {
    return source;
  }
}

function readableStatus(status: string) {
  const labels: Record<string, string> = {
    queued: "Queued",
    downloading: "Reading source",
    transcribing: "Anchoring words",
    analyzing: "Mapping story",
    rendering: "Rendering cuts",
    completed: "Ready",
    failed: "Needs attention",
    canceled: "Canceled",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function humanizeJobError(code: string) {
  const messages: Record<string, { title: string; description: string }> = {
    invalid_url: {
      title: "This source is not supported.",
      description:
        "Use a public YouTube or Vimeo URL when you submit another source.",
    },
    video_too_long: {
      title: "This source exceeds the current duration limit.",
      description: "Starter supports sources up to 30 minutes in V1.",
    },
    insufficient_credits: {
      title: "The source needs more credits.",
      description:
        "Return to the campaign; the source history and brief are preserved.",
    },
    render_failed: {
      title: "The render did not complete.",
      description:
        "No verified MP4 was delivered. Return to the campaign to submit another source.",
    },
    no_verified_arcs: {
      title: "No source moment passed verification.",
      description:
        "ClipFactory did not manufacture a weak cut. Try a source with clearer campaign evidence.",
    },
  };
  return (
    messages[code] ?? {
      title: "This analysis stopped before delivery.",
      description:
        "The campaign and source history are preserved. Return to the campaign to continue.",
    }
  );
}
