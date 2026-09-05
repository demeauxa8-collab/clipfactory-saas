import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowUpRight, Clapperboard, Target } from "lucide-react";
import {
  ProductBackLink,
  ProductEmptyState,
  ProductPageIntro,
  ProductPanel,
  ProductSectionTitle,
  ProductStatus,
} from "@/components/product/product-primitives";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { SubmitJobForm } from "./submit-job-form";
import styles from "./campaign-workspace.module.css";

export const metadata = { title: "Campaign" };

type JobRow = {
  id: string;
  source_url: string;
  status: string;
  target_clip_count: number;
  queued_at: string;
};

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createSupabaseServerClient();

  const [{ data: campaign }, jobsResult, subscriptionResult, ledgerResult] =
    await Promise.all([
      supabase
        .from("campaigns")
        .select(
          "id, name, audience, niche, tone, goal, avoid_topics, example_hooks, created_at",
        )
        .eq("id", id)
        .maybeSingle(),
      supabase
        .from("jobs")
        .select("id, source_url, status, target_clip_count, queued_at")
        .eq("campaign_id", id)
        .order("queued_at", { ascending: false })
        .limit(50),
      supabase
        .from("subscriptions")
        .select("status")
        .order("current_period_end", { ascending: false, nullsFirst: false })
        .limit(1)
        .maybeSingle(),
      supabase.from("credit_ledger").select("delta"),
    ]);

  if (!campaign) notFound();

  const jobs = (jobsResult.data ?? []) as JobRow[];
  const subscriptionStatus = subscriptionResult.data?.status as
    string | undefined;
  const balance = (ledgerResult.data ?? []).reduce(
    (total, entry) =>
      total + (typeof entry.delta === "number" ? entry.delta : 0),
    0,
  );
  const briefDetails = [
    campaign.audience,
    campaign.niche,
    campaign.tone,
  ].filter(Boolean);

  return (
    <div className="cf-page cf-page--narrow">
      <ProductBackLink href="/app">Workspace</ProductBackLink>
      <ProductPageIntro
        className={styles.intro}
        eyebrow="Campaign lens"
        title={campaign.name}
        description={
          campaign.goal ||
          "This campaign is ready for a clearer outcome. Add a goal before the next source if needed."
        }
        actions={
          <ProductStatus
            tone={
              subscriptionStatus === "active" ||
              subscriptionStatus === "trialing"
                ? "success"
                : "warning"
            }
          >
            {subscriptionStatus === "active" ||
            subscriptionStatus === "trialing"
              ? "Ready for source"
              : "Starter required"}
          </ProductStatus>
        }
      />

      <div className={styles.workspace}>
        <div className={styles.mainColumn}>
          <ProductPanel className={styles.briefPanel}>
            <ProductSectionTitle
              eyebrow="Brief"
              title="What the cut must understand"
              description="The goal leads. Audience, tone and boundaries refine the selection."
            />
            <dl className={styles.properties}>
              <BriefProperty label="Goal" value={campaign.goal} wide />
              <BriefProperty label="Audience" value={campaign.audience} />
              <BriefProperty label="Niche" value={campaign.niche} />
              <BriefProperty label="Tone" value={campaign.tone} />
              <BriefProperty
                label="Avoid"
                value={(campaign.avoid_topics || []).join(", ")}
              />
              <BriefProperty
                label="Example hooks"
                value={(campaign.example_hooks || []).slice(0, 3).join(" · ")}
                wide
              />
            </dl>
          </ProductPanel>

          <ProductPanel className={styles.sourcePanel}>
            <ProductSectionTitle
              eyebrow="Source"
              title="Add a public video"
              description="YouTube and Vimeo are supported in V1. ClipFactory reads the duration before confirming credit use."
            />
            <SubmitJobForm
              campaignId={String(campaign.id)}
              campaignName={String(campaign.name)}
              subscriptionStatus={subscriptionStatus}
              availableCredits={balance}
            />
          </ProductPanel>

          <ProductPanel className={styles.jobsPanel}>
            <ProductSectionTitle
              eyebrow="Source thread"
              title="Analyses in this campaign"
              description="Open a live build log or return to a delivered cut."
            />
            {jobs.length === 0 ? (
              <ProductEmptyState
                icon={Clapperboard}
                title="No source analyzed yet"
                description="The campaign brief is preserved. Add a public URL above when you are ready."
              />
            ) : (
              <ul className={styles.jobList}>
                {jobs.map((job) => (
                  <li key={job.id}>
                    <Link href={`/app/jobs/${job.id}`}>
                      <span className={styles.jobMarker} aria-hidden="true" />
                      <span className={styles.jobCopy}>
                        <strong>{readableSource(job.source_url)}</strong>
                        <span>
                          {job.target_clip_count} requested clips ·{" "}
                          {new Date(job.queued_at).toLocaleDateString()}
                        </span>
                      </span>
                      <ProductStatus
                        tone={
                          job.status === "completed"
                            ? "success"
                            : job.status === "failed"
                              ? "danger"
                              : "neutral"
                        }
                        pulse={[
                          "queued",
                          "downloading",
                          "transcribing",
                          "analyzing",
                          "rendering",
                        ].includes(job.status)}
                      >
                        {readableStatus(job.status)}
                      </ProductStatus>
                      <ArrowUpRight aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </ProductPanel>
        </div>

        <aside className={styles.lens}>
          <div className={styles.lensHeader}>
            <span>
              <Target aria-hidden="true" />
            </span>
            <div>
              <p>Campaign Lens</p>
              <strong>Selection context</strong>
            </div>
          </div>
          <p className={styles.lensStatement}>
            {campaign.goal || "Define the outcome this series should create."}
          </p>
          <div className={styles.lensMeta}>
            {briefDetails.length ? (
              briefDetails.map((value: string) => (
                <span key={value}>{value}</span>
              ))
            ) : (
              <span>Broad audience</span>
            )}
          </div>
          <div className={styles.lensThread} aria-hidden="true">
            <span className={styles.done} />
            <span className={styles.active} />
            <span />
          </div>
          <div className={styles.lensFooter}>
            <span>Brief</span>
            <span>Source</span>
            <span>Cut</span>
          </div>
        </aside>
      </div>
    </div>
  );
}

function BriefProperty({
  label,
  value,
  wide = false,
}: {
  label: string;
  value?: string | null;
  wide?: boolean;
}) {
  return (
    <div className={wide ? styles.propertyWide : undefined}>
      <dt>{label}</dt>
      <dd>{value || "Not specified"}</dd>
    </div>
  );
}

function readableStatus(status: string) {
  const labels: Record<string, string> = {
    queued: "Queued",
    downloading: "Reading source",
    transcribing: "Anchoring words",
    analyzing: "Mapping story",
    rendering: "Rendering",
    completed: "Ready",
    failed: "Needs attention",
    canceled: "Canceled",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function readableSource(source: string) {
  try {
    const url = new URL(source);
    return `${url.hostname.replace("www.", "")}${url.pathname.slice(0, 42)}`;
  } catch {
    return source;
  }
}
