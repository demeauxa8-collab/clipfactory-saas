"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Check, Link2, LockKeyhole } from "lucide-react";
import {
  PaywallDialog,
  type PaywallReason,
} from "@/components/product/paywall-dialog";
import { ProductStatus } from "@/components/product/product-primitives";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";
import styles from "./source-form.module.css";

type Job = { id: string };

export function SubmitJobForm({
  campaignId,
  campaignName,
  subscriptionStatus,
  availableCredits,
}: {
  campaignId: string;
  campaignName: string;
  subscriptionStatus?: string;
  availableCredits: number;
}) {
  const router = useRouter();
  const draftStorageKey = `clipfactory:source-draft:${campaignId}`;
  const [busy, setBusy] = React.useState(false);
  const [sourceUrl, setSourceUrl] = React.useState("");
  const [clipCount, setClipCount] = React.useState(3);
  const [error, setError] = React.useState<string | null>(null);
  const [paywallReason, setPaywallReason] =
    React.useState<PaywallReason | null>(null);
  const [draftRestored, setDraftRestored] = React.useState(false);
  const provider = getProvider(sourceUrl);
  const isSupported = provider === "YouTube" || provider === "Vimeo";
  const hasActivePlan =
    subscriptionStatus === "active" || subscriptionStatus === "trialing";
  const initialPaywallReason: PaywallReason =
    subscriptionStatus === "past_due" ? "past_due" : "no_subscription";

  React.useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(draftStorageKey);
      if (!stored) return;
      const draft = JSON.parse(stored) as {
        sourceUrl?: unknown;
        clipCount?: unknown;
      };
      if (typeof draft.sourceUrl === "string") setSourceUrl(draft.sourceUrl);
      if (
        typeof draft.clipCount === "number" &&
        [1, 2, 3].includes(draft.clipCount)
      ) {
        setClipCount(draft.clipCount);
      }
    } catch {
      window.sessionStorage.removeItem(draftStorageKey);
    } finally {
      setDraftRestored(true);
    }
  }, [draftStorageKey]);

  React.useEffect(() => {
    if (!draftRestored) return;
    try {
      if (!sourceUrl) {
        window.sessionStorage.removeItem(draftStorageKey);
        return;
      }
      window.sessionStorage.setItem(
        draftStorageKey,
        JSON.stringify({ sourceUrl, clipCount }),
      );
    } catch {
      // Storage can be unavailable in privacy modes; the visible form still works.
    }
  }, [clipCount, draftRestored, draftStorageKey, sourceUrl]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isSupported) {
      setError("Paste a public YouTube or Vimeo URL.");
      return;
    }
    if (!hasActivePlan) {
      setPaywallReason(initialPaywallReason);
      return;
    }

    setBusy(true);
    setError(null);
    setPaywallReason(null);
    void track("job_submit_clicked", {
      campaign_id: campaignId,
      target_clip_count: clipCount,
    });

    try {
      const job = await apiFetch<Job>("/jobs", {
        method: "POST",
        json: {
          campaign_id: campaignId,
          source_url: sourceUrl.trim(),
          target_clip_count: clipCount,
        },
      });
      window.sessionStorage.removeItem(draftStorageKey);
      router.push(`/app/jobs/${job.id}`);
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError) {
        const reason = paywallReasonFromCode(caught.code);
        if (reason) setPaywallReason(reason);
        setError(humanizeJobError(caught.code ?? caught.message));
      } else {
        setError(
          "We could not start this analysis. Your source is still here. Try again.",
        );
      }
      setBusy(false);
    }
  }

  const paywallTrigger = (
    <Button
      type="button"
      size="lg"
      disabled={!isSupported}
      className={styles.primaryAction}
    >
      <LockKeyhole aria-hidden="true" />
      {initialPaywallReason === "past_due"
        ? "Review billing"
        : "Activate Starter to analyze"}
    </Button>
  );

  return (
    <form onSubmit={handleSubmit} className={styles.form} noValidate>
      <div className={styles.thread} aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <div className={styles.urlBlock}>
        <div className={styles.labelRow}>
          <label htmlFor="source_url">Video URL</label>
          <span>YouTube or Vimeo</span>
        </div>
        <div className={styles.urlInput}>
          <Link2 aria-hidden="true" />
          <Input
            id="source_url"
            name="source_url"
            type="url"
            required
            autoComplete="url"
            placeholder="https://www.youtube.com/watch?v=..."
            value={sourceUrl}
            onChange={(event) => {
              setSourceUrl(event.target.value);
              setError(null);
            }}
            aria-describedby="source-help source-state"
          />
        </div>
        <div className={styles.urlState} id="source-state" aria-live="polite">
          {sourceUrl && isSupported ? (
            <ProductStatus tone="success">
              <Check aria-hidden="true" /> {provider} source recognized
            </ProductStatus>
          ) : sourceUrl && provider === "Unsupported" ? (
            <ProductStatus tone="danger">Unsupported host</ProductStatus>
          ) : (
            <span id="source-help">
              Paste a public link. Direct uploads are not available in V1.
            </span>
          )}
        </div>
      </div>

      <fieldset className={styles.clipFieldset}>
        <legend>Requested cuts</legend>
        <p>
          ClipFactory will return up to this number when the campaign evidence
          is strong enough.
        </p>
        <div className={styles.clipPicker}>
          {[1, 2, 3].map((count) => (
            <label key={count} data-selected={clipCount === count}>
              <input
                type="radio"
                name="target_clip_count"
                value={count}
                checked={clipCount === count}
                onChange={() => setClipCount(count)}
              />
              <span>{count}</span>
              <small>{count === 1 ? "cut" : "cuts"}</small>
            </label>
          ))}
        </div>
      </fieldset>

      <div className={styles.summary}>
        <div>
          <span>Campaign</span>
          <strong>{campaignName}</strong>
        </div>
        <div>
          <span>Balance</span>
          <strong>{availableCredits} credits</strong>
        </div>
        <div>
          <span>Credit use</span>
          <strong>Confirmed after reading duration</strong>
        </div>
      </div>

      <div className={styles.actions}>
        {hasActivePlan ? (
          <Button
            type="submit"
            size="lg"
            disabled={busy || !isSupported}
            className={styles.primaryAction}
          >
            {busy
              ? "Starting analysis…"
              : `Analyze source for ${clipCount} ${clipCount === 1 ? "cut" : "cuts"}`}
          </Button>
        ) : (
          <PaywallDialog
            reason={initialPaywallReason}
            trigger={paywallTrigger}
            sourceContext={{
              title: sourceUrl || "Source URL ready",
              detail: `${campaignName} · ${clipCount} requested ${clipCount === 1 ? "cut" : "cuts"} · saved in this browser`,
            }}
            availableCredits={availableCredits}
            checkoutHref="/app/billing"
          />
        )}
        <p>
          The brief is saved to your workspace. This source stays in the current
          browser tab until processing starts.
        </p>
      </div>

      {error ? (
        <div className={styles.error} role="alert">
          <strong>Analysis did not start.</strong>
          <span>{error}</span>
          {paywallReason ? (
            <PaywallDialog
              reason={paywallReason}
              trigger={
                <Button type="button" variant="secondary" size="sm">
                  Resolve and continue
                </Button>
              }
              sourceContext={{ title: sourceUrl, detail: campaignName }}
              availableCredits={availableCredits}
              checkoutHref="/app/billing"
            />
          ) : null}
        </div>
      ) : null}
    </form>
  );
}

function getProvider(value: string) {
  if (!value.trim()) return null;
  try {
    const host = new URL(value.trim()).hostname.toLowerCase();
    if (
      ["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"].includes(
        host,
      )
    )
      return "YouTube";
    if (host === "vimeo.com" || host.endsWith(".vimeo.com")) return "Vimeo";
    return "Unsupported";
  } catch {
    return "Invalid";
  }
}

function paywallReasonFromCode(code?: string | null): PaywallReason | null {
  if (code === "no_active_subscription") return "no_subscription";
  if (code === "insufficient_credits") return "insufficient_credits";
  if (code === "subscription_past_due") return "past_due";
  return null;
}

function humanizeJobError(code: string) {
  const messages: Record<string, string> = {
    no_active_subscription:
      "Starter is required before a source can be analyzed.",
    insufficient_credits:
      "Your current balance cannot cover this source. The URL and brief are preserved.",
    concurrent_jobs_exceeded:
      "Another source is already processing. Open it from the workspace before starting a new one.",
    clip_count_exceeded:
      "This plan supports up to three requested clips per source.",
    invalid_url: "This URL is not a supported public YouTube or Vimeo source.",
    video_too_long: "This source exceeds the current 30-minute limit.",
    rate_limit_exceeded:
      "Too many attempts were made. Wait a moment, then try again.",
    campaign_not_found:
      "This campaign is no longer available. Return to the workspace.",
    token_expired:
      "Your session expired. Sign in again; the source URL remains in this form for now.",
  };
  return (
    messages[code] ??
    "We could not start this analysis. Your source is still here. Try again."
  );
}
