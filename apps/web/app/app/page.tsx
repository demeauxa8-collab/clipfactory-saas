import Link from "next/link";
import type { Route } from "next";
import {
  AlertTriangle,
  ArrowUpRight,
  Clapperboard,
  Play,
  Plus,
  Target,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ProductEmptyState,
  ProductPageIntro,
  ProductPanel,
  ProductSectionTitle,
  ProductStatus,
} from "@/components/product/product-primitives";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const metadata = { title: "Workspace" };

type CampaignRow = {
  id: string;
  name: string;
  audience: string | null;
  niche: string | null;
  goal: string | null;
  created_at: string;
};

type JobRow = {
  id: string;
  source_url: string;
  status: string;
  target_clip_count: number;
  campaign_id: string | null;
  queued_at: string;
};

const RUNNING = new Set([
  "queued",
  "downloading",
  "transcribing",
  "analyzing",
  "rendering",
]);

export default async function AppHome() {
  const supabase = await createSupabaseServerClient();
  const [campaignResult, jobResult, ledgerResult] = await Promise.all([
    supabase
      .from("campaigns")
      .select("id, name, audience, niche, goal, created_at")
      .order("created_at", { ascending: false })
      .limit(8),
    supabase
      .from("jobs")
      .select(
        "id, source_url, status, target_clip_count, campaign_id, queued_at",
      )
      .order("queued_at", { ascending: false })
      .limit(12),
    supabase.from("credit_ledger").select("delta"),
  ]);

  const campaigns = (campaignResult.data ?? []) as CampaignRow[];
  const jobs = (jobResult.data ?? []) as JobRow[];
  const balance = (ledgerResult.data ?? []).reduce(
    (total, entry) =>
      total + (typeof entry.delta === "number" ? entry.delta : 0),
    0,
  );
  const hasDataError = Boolean(
    campaignResult.error || jobResult.error || ledgerResult.error,
  );
  const activeJob = jobs.find((job) => RUNNING.has(job.status));
  const readyJob = jobs.find((job) => job.status === "completed");
  const latestCampaign = campaigns[0];
  const primary = getPrimaryAction({ activeJob, readyJob, latestCampaign });
  const jobCountByCampaign = new Map<string, number>();
  for (const job of jobs) {
    if (job.campaign_id) {
      jobCountByCampaign.set(
        job.campaign_id,
        (jobCountByCampaign.get(job.campaign_id) ?? 0) + 1,
      );
    }
  }

  return (
    <div className="cf-page">
      <ProductPageIntro
        eyebrow="Workspace"
        title="Continue the edit."
        description="Your brief, source and selected moments stay on one thread. Pick up at the next useful decision."
        actions={
          <Button asChild>
            <Link href="/app/campaigns/new">
              <Plus aria-hidden="true" />
              New campaign
            </Link>
          </Button>
        }
      />

      {hasDataError ? (
        <ProductPanel
          tone="signal"
          className="cf-inline-notice cf-workspace-notice"
        >
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Part of your workspace could not be loaded.</strong>
            <p>
              Nothing has been changed. Refresh before starting a new analysis.
            </p>
          </div>
        </ProductPanel>
      ) : null}

      <ProductPanel className="cf-next-action cf-enter-delay">
        <div className="cf-thread-rail" aria-hidden="true">
          <span />
        </div>
        <div className="cf-next-action__copy">
          <ProductStatus tone={primary.tone} pulse={primary.pulse}>
            {primary.status}
          </ProductStatus>
          <p className="cf-next-action__kicker">Next on your source thread</p>
          <h2>{primary.title}</h2>
          <p>{primary.description}</p>
          <div className="cf-next-action__actions">
            <Button asChild size="lg">
              <Link href={primary.href as Route}>
                {primary.icon === "play" ? (
                  <Play aria-hidden="true" />
                ) : (
                  <ArrowUpRight aria-hidden="true" />
                )}
                {primary.cta}
              </Link>
            </Button>
            <span>{balance} credits available</span>
          </div>
        </div>
        <div className="cf-next-action__visual" aria-hidden="true">
          <div className="cf-source-frame">
            <span>9:16</span>
            <div className="cf-source-frame__subject" />
            <div className="cf-source-frame__caption">
              The proof arrives before the promise.
            </div>
          </div>
          <div className="cf-source-thread-mini">
            <span />
            <span className="is-active" />
            <span />
          </div>
        </div>
      </ProductPanel>

      <div className="cf-workspace-grid">
        <ProductPanel className="cf-list-panel">
          <ProductSectionTitle
            eyebrow="Campaigns"
            title="Briefs in motion"
            description="Every source is evaluated against one campaign lens."
            action={
              <Button asChild variant="secondary" size="sm">
                <Link href="/app/campaigns/new">New brief</Link>
              </Button>
            }
          />
          {campaigns.length === 0 ? (
            <ProductEmptyState
              icon={Target}
              title="Build your first campaign lens"
              description="Tell ClipFactory what the audience should feel and do before adding a source."
              action={
                <Button asChild>
                  <Link href="/app/campaigns/new">Create the brief</Link>
                </Button>
              }
            />
          ) : (
            <ul className="cf-work-list">
              {campaigns.map((campaign) => (
                <li key={campaign.id}>
                  <Link href={`/app/campaigns/${campaign.id}`}>
                    <span className="cf-work-list__icon">
                      <Target aria-hidden="true" />
                    </span>
                    <span className="cf-work-list__main">
                      <strong>{campaign.name}</strong>
                      <span>
                        {campaign.goal ||
                          campaign.audience ||
                          "Campaign brief ready"}
                      </span>
                    </span>
                    <span className="cf-work-list__meta">
                      {jobCountByCampaign.get(campaign.id) ?? 0} sources
                    </span>
                    <ArrowUpRight aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </ProductPanel>

        <ProductPanel className="cf-list-panel">
          <ProductSectionTitle
            eyebrow="Sources"
            title="Recent analyses"
            description="Live work and delivered cuts, without a wall of empty metrics."
          />
          {jobs.length === 0 ? (
            <ProductEmptyState
              icon={Clapperboard}
              title="No source on the thread yet"
              description="Open a campaign when its brief is ready, then paste a public YouTube or Vimeo URL."
            />
          ) : (
            <ul className="cf-work-list">
              {jobs.slice(0, 7).map((job) => (
                <li key={job.id}>
                  <Link href={`/app/jobs/${job.id}`}>
                    <span className="cf-work-list__icon">
                      <Clapperboard aria-hidden="true" />
                    </span>
                    <span className="cf-work-list__main">
                      <strong>{readableSource(job.source_url)}</strong>
                      <span>
                        {job.target_clip_count} requested clips ·{" "}
                        {relativeDate(job.queued_at)}
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
                      pulse={RUNNING.has(job.status)}
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
    </div>
  );
}

function getPrimaryAction({
  activeJob,
  readyJob,
  latestCampaign,
}: {
  activeJob?: JobRow;
  readyJob?: JobRow;
  latestCampaign?: CampaignRow;
}) {
  if (activeJob) {
    return {
      status: readableStatus(activeJob.status),
      tone: "action" as const,
      pulse: true,
      title: "Your source is becoming a cut.",
      description:
        "ClipFactory is keeping the transcript, frames and campaign reasoning locked to the same moments.",
      href: `/app/jobs/${activeJob.id}`,
      cta: "Open live analysis",
      icon: "play" as const,
    };
  }
  if (readyJob) {
    return {
      status: "Cuts ready",
      tone: "success" as const,
      pulse: false,
      title: "Review why these moments made the cut.",
      description:
        "Compare each selected moment against the campaign brief, then download the strongest vertical edit.",
      href: `/app/jobs/${readyJob.id}`,
      cta: "Review delivered cuts",
      icon: "play" as const,
    };
  }
  if (latestCampaign) {
    return {
      status: "Brief ready",
      tone: "success" as const,
      pulse: false,
      title: "Add the first source to your campaign.",
      description: `“${latestCampaign.name}” is ready to evaluate a public YouTube or Vimeo source.`,
      href: `/app/campaigns/${latestCampaign.id}`,
      cta: "Add a source",
      icon: "arrow" as const,
    };
  }
  return {
    status: "Ready to begin",
    tone: "action" as const,
    pulse: false,
    title: "Start with the campaign, not the video.",
    description:
      "Set the promise, audience and boundaries first. Starter is only requested once a source is ready to enter processing.",
    href: "/app/campaigns/new",
    cta: "Create campaign brief",
    icon: "arrow" as const,
  };
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

function readableSource(source: string) {
  try {
    const url = new URL(source);
    return url.hostname.replace("www.", "") + url.pathname.slice(0, 28);
  } catch {
    return source;
  }
}

function relativeDate(value: string) {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.round(elapsed / 60_000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
