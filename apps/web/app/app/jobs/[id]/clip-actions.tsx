"use client";

import * as React from "react";
import { Download, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";
import styles from "./clip-actions.module.css";

type DownloadResponse = { url: string; expires_in_seconds: number };

export function ClipActions({ clipId }: { clipId: string }) {
  const [busy, setBusy] = React.useState<null | "download" | "good" | "bad">(
    null,
  );
  const [feedback, setFeedback] = React.useState<"good" | "bad" | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function handleDownload() {
    setBusy("download");
    setError(null);
    setMessage(null);
    void track("clip_download_clicked", { clip_id: clipId });
    try {
      const response = await apiFetch<DownloadResponse>(
        `/clips/${clipId}/download`,
      );
      window.open(response.url, "_blank", "noopener,noreferrer");
      setMessage("A fresh download link opened in a new tab.");
    } catch (caught) {
      setError(humanizeActionError(caught));
    } finally {
      setBusy(null);
    }
  }

  async function handleFeedback(kind: "good" | "bad") {
    setBusy(kind);
    setError(null);
    setMessage(null);
    void track("clip_feedback_clicked", { clip_id: clipId, kind });
    try {
      await apiFetch(`/clips/${clipId}/feedback`, {
        method: "POST",
        json: { kind },
      });
      setFeedback(kind);
      setMessage(
        kind === "good" ? "Marked as a strong cut." : "Marked as needing work.",
      );
    } catch (caught) {
      setError(humanizeActionError(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.actions}>
        <Button
          size="sm"
          onClick={handleDownload}
          disabled={busy === "download"}
        >
          <Download aria-hidden="true" />
          {busy === "download" ? "Preparing MP4…" : "Download MP4"}
        </Button>
        <Button
          size="sm"
          variant={feedback === "good" ? "primary" : "secondary"}
          onClick={() => handleFeedback("good")}
          disabled={busy !== null}
          aria-pressed={feedback === "good"}
        >
          <ThumbsUp aria-hidden="true" />
          Good cut
        </Button>
        <Button
          size="sm"
          variant={feedback === "bad" ? "primary" : "secondary"}
          onClick={() => handleFeedback("bad")}
          disabled={busy !== null}
          aria-pressed={feedback === "bad"}
        >
          <ThumbsDown aria-hidden="true" />
          Needs work
        </Button>
      </div>
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className={styles.message} role="status">
          {message}
        </p>
      ) : null}
    </div>
  );
}

function humanizeActionError(error: unknown) {
  const code =
    error instanceof ApiError
      ? (error.code ?? error.message)
      : "unexpected_error";
  if (code === "token_expired")
    return "Your session expired. Sign in again before retrying.";
  if (code === "clip_not_found") return "This clip is no longer available.";
  return "That action did not complete. The cut has not changed; try again.";
}
