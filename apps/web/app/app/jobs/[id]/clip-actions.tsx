"use client";

import * as React from "react";
import { Download, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";

type DownloadResp = { url: string; expires_in_seconds: number };

export function ClipActions({ clipId }: { clipId: string }) {
  const [busy, setBusy] = React.useState<null | "download" | "good" | "bad">(null);
  const [feedback, setFeedback] = React.useState<"good" | "bad" | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function handleDownload() {
    setBusy("download");
    setError(null);
    try {
      const r = await apiFetch<DownloadResp>(`/clips/${clipId}/download`);
      window.open(r.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof ApiError ? err.code ?? err.message : "error");
    } finally {
      setBusy(null);
    }
  }

  async function handleFeedback(kind: "good" | "bad") {
    setBusy(kind);
    setError(null);
    try {
      await apiFetch(`/clips/${clipId}/feedback`, { method: "POST", json: { kind } });
      setFeedback(kind);
    } catch (err) {
      setError(err instanceof ApiError ? err.code ?? err.message : "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-4 flex items-center gap-2">
      <Button size="sm" onClick={handleDownload} disabled={busy === "download"}>
        <Download className="h-4 w-4" />
        {busy === "download" ? "…" : "Download"}
      </Button>
      <Button
        size="sm"
        variant={feedback === "good" ? "primary" : "secondary"}
        onClick={() => handleFeedback("good")}
        disabled={busy !== null}
      >
        <ThumbsUp className="h-4 w-4" />
      </Button>
      <Button
        size="sm"
        variant={feedback === "bad" ? "primary" : "secondary"}
        onClick={() => handleFeedback("bad")}
        disabled={busy !== null}
      >
        <ThumbsDown className="h-4 w-4" />
      </Button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
