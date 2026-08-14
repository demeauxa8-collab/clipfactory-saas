"use client";

import * as React from "react";
import { Download, Lock, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";

type DownloadResp = { url: string; expires_in_seconds: number };

export function ClipActions({ clipId, locked = false }: { clipId: string; locked?: boolean }) {
  const [busy, setBusy] = React.useState<null | "download" | "good" | "bad">(null);
  const [feedback, setFeedback] = React.useState<"good" | "bad" | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function handleDownload() {
    setBusy("download");
    setError(null);
    void track("clip_download_clicked", { clip_id: clipId });
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
    void track("clip_feedback_clicked", { clip_id: clipId, kind });
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
      {locked ? (
        // Scrolls to the paywall below instead of firing a request the API
        // would answer with 402 anyway.
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            void track("locked_clip_clicked", { clip_id: clipId });
            document
              .getElementById("upgrade-wall")
              ?.scrollIntoView({ behavior: "smooth", block: "center" });
          }}
        >
          <Lock className="h-4 w-4" />
          Unlock
        </Button>
      ) : (
        <Button size="sm" onClick={handleDownload} disabled={busy === "download"}>
          <Download className="h-4 w-4" />
          {busy === "download" ? "…" : "Download"}
        </Button>
      )}
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
      {error && <span className="text-xs text-[var(--color-danger)]">{error}</span>}
    </div>
  );
}
