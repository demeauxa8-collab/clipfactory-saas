"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch, ApiError } from "@/lib/api";

type Job = { id: string };

export function SubmitJobForm({ campaignId }: { campaignId: string }) {
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const data = new FormData(event.currentTarget);
    const payload = {
      campaign_id: campaignId,
      source_url: String(data.get("source_url") ?? "").trim(),
      target_clip_count: Number(data.get("target_clip_count") ?? 3),
    };

    try {
      const job = await apiFetch<Job>("/jobs", { method: "POST", json: payload });
      router.push(`/app/jobs/${job.id}`);
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.code ?? err.message);
      } else {
        setError("unexpected_error");
      }
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="flex-1 space-y-1.5">
        <label htmlFor="source_url" className="text-sm font-medium">YouTube URL</label>
        <Input
          id="source_url"
          name="source_url"
          type="url"
          required
          placeholder="https://www.youtube.com/watch?v=..."
        />
      </div>
      <div className="w-32 space-y-1.5">
        <label htmlFor="target_clip_count" className="text-sm font-medium">Clips</label>
        <Input
          id="target_clip_count"
          name="target_clip_count"
          type="number"
          min={1}
          max={3}
          defaultValue={3}
        />
      </div>
      <Button type="submit" disabled={busy}>
        {busy ? "Submitting…" : "Submit"}
      </Button>
      {error && <span className="text-sm text-[var(--color-danger)]">{error}</span>}
    </form>
  );
}
