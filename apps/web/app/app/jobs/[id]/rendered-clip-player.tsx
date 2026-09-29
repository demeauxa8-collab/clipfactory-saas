"use client";

import * as React from "react";
import {
  AlertTriangle,
  CirclePlay,
  Clapperboard,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { VideoPlayer } from "@/components/ui/video-player";
import { apiFetch, ApiError } from "@/lib/api";
import styles from "./rendered-clip-player.module.css";

type DownloadResponse = {
  url: string;
  expires_in_seconds: number;
};

type PlayerState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; url: string }
  | { status: "error"; message: string };

export function RenderedClipPlayer({
  clipId,
  title,
}: {
  clipId: string;
  title: string;
}) {
  const [state, setState] = React.useState<PlayerState>({ status: "idle" });
  const controllerRef = React.useRef<AbortController | null>(null);
  const requestIdRef = React.useRef(0);

  React.useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  async function loadClip() {
    controllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = requestIdRef.current + 1;
    controllerRef.current = controller;
    requestIdRef.current = requestId;
    setState({ status: "loading" });

    try {
      const response = await apiFetch<DownloadResponse>(
        `/clips/${clipId}/download`,
        {
          method: "GET",
          signal: controller.signal,
        },
      );
      if (!response.url) throw new Error("missing_download_url");
      if (requestIdRef.current === requestId)
        setState({ status: "ready", url: response.url });
    } catch (error) {
      if (controller.signal.aborted || requestIdRef.current !== requestId)
        return;
      setState({ status: "error", message: humanizePreviewError(error) });
    }
  }

  if (state.status === "ready") {
    return (
      <div className={styles.shell}>
        <VideoPlayer
          className={styles.player}
          src={state.url}
          title={title}
          onPlaybackError={() => {
            setState({
              status: "error",
              message:
                "This playback link could not be used. Request a fresh preview and try again.",
            });
          }}
        />
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className={styles.shell}>
        <div
          className={styles.state}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <div className={styles.stateIcon}>
            <LoaderCircle className={styles.loadingIcon} aria-hidden="true" />
          </div>
          <span className={styles.kicker}>Rendered MP4</span>
          <h3>Preparing the preview…</h3>
          <p>
            ClipFactory is requesting a fresh playback link for this delivered
            cut.
          </p>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className={styles.shell}>
        <div className={styles.state} data-tone="error" role="alert">
          <div className={styles.stateIcon}>
            <AlertTriangle aria-hidden="true" />
          </div>
          <span className={styles.kicker}>Preview unavailable</span>
          <h3>The MP4 did not load.</h3>
          <p>{state.message}</p>
          <Button
            className={styles.action}
            size="md"
            onClick={() => void loadClip()}
          >
            <RefreshCw aria-hidden="true" />
            Retry preview
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      <div className={styles.state}>
        <div className={styles.stateIcon}>
          <Clapperboard aria-hidden="true" />
        </div>
        <span className={styles.kicker}>Rendered MP4</span>
        <h3>Watch the delivered cut.</h3>
        <p>
          A fresh playback link is requested only when you load this preview.
        </p>
        <Button
          className={styles.action}
          size="md"
          onClick={() => void loadClip()}
        >
          <CirclePlay aria-hidden="true" />
          Load preview
        </Button>
      </div>
    </div>
  );
}

function humanizePreviewError(error: unknown) {
  if (error instanceof ApiError) {
    if (
      error.code === "not_authenticated" ||
      error.code === "token_expired" ||
      error.status === 401
    ) {
      return "Your session expired. Sign in again, then retry the preview.";
    }
    if (error.code === "clip_not_found" || error.status === 404) {
      return "This rendered clip is no longer available.";
    }
    if (error.status === 403) {
      return "This account no longer has access to the rendered clip.";
    }
  }

  return "Request a fresh playback link. The source thread and clip analysis remain available.";
}
