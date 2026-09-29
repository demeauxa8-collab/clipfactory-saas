"use client";

import * as React from "react";
import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";

type Created = { id: string };

function messageFromError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = (error.detail as { detail?: { message?: string } } | undefined)?.detail;
    if (detail?.message) return detail.message;
    if (error.status === 401) return "Sign in again, then retry.";
  }
  return "The videos could not be submitted. Please retry.";
}

export function SubmitJobForm({ campaignId, maxSources }: { campaignId: string; maxSources: number }) {
  const router = useRouter();
  const sourceLimit = Math.min(5, Math.max(1, maxSources));
  const [sources, setSources] = React.useState([""]);
  const [clipCount, setClipCount] = React.useState(3);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const urls = sources.map((source) => source.trim());
    if (new Set(urls).size !== urls.length) {
      setError("Each source video must be different.");
      return;
    }
    setBusy(true);
    setError(null);

    void track("job_submit_clicked", {
      campaign_id: campaignId,
      source_count: urls.length,
      target_clip_count: clipCount,
    });
    try {
      if (urls.length === 1) {
        const job = await apiFetch<Created>("/jobs", {
          method: "POST",
          json: { campaign_id: campaignId, source_url: urls[0], target_clip_count: clipCount },
        });
        router.push(`/app/jobs/${job.id}`);
      } else {
        const series = await apiFetch<Created>("/series", {
          method: "POST",
          json: { campaign_id: campaignId, source_urls: urls, target_clip_count: clipCount },
        });
        router.push(`/app/series/${series.id}`);
      }
      router.refresh();
    } catch (err) {
      setError(messageFromError(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5">
      <div className="space-y-3">
        {sources.map((source, index) => (
          <div key={index} className="space-y-1.5">
            <label htmlFor={`source_url_${index}`} className="text-sm font-medium">
              YouTube video {index + 1}
            </label>
            <div className="flex gap-2">
              <Input
                id={`source_url_${index}`}
                type="url"
                required
                value={source}
                onChange={(event) => {
                  setSources((current) => current.map((value, i) => i === index ? event.target.value : value));
                  setError(null);
                }}
                onBlur={(event) => {
                  if (event.target.value && !event.target.validity.valid) {
                    setError(`Video ${index + 1} needs a valid URL.`);
                  }
                }}
                placeholder="https://www.youtube.com/watch?v=..."
              />
              {sources.length > 1 && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  aria-label={`Remove video ${index + 1}`}
                  onClick={() => setSources((current) => current.filter((_, i) => i !== index))}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        ))}
        {sources.length < sourceLimit && (
          <Button type="button" variant="secondary" size="sm" onClick={() => setSources((current) => [...current, ""])}>
            <Plus className="h-4 w-4" /> Add video
          </Button>
        )}
      </div>

      <div className="space-y-1.5">
        <label htmlFor="target_clip_count" className="text-sm font-medium">Clips per video</label>
        <Input
          id="target_clip_count"
          type="number"
          min={1}
          max={3}
          required
          value={clipCount}
          onChange={(event) => setClipCount(Number(event.target.value))}
          className="max-w-32"
        />
      </div>
      <p className="text-sm text-[var(--color-muted-foreground)]">
        {sourceLimit === 1
          ? "Your plan includes single-video jobs. Multi-video series are available on eligible plans."
          : sources.length === 1
          ? "This video is processed as one job."
          : `${sources.length} videos will be processed in order. Each clip keeps its source video.`}
        {" "}Credits are charged for the minutes processed in each video.
      </p>
      {error && <p role="alert" className="text-sm text-[var(--color-danger)]">{error}</p>}
      <Button type="submit" disabled={busy}>
        {busy ? "Starting…" : sources.length === 1 ? "Create clips" : "Create clip series"}
      </Button>
    </form>
  );
}
