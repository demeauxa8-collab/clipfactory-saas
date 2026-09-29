"use client";

import * as React from "react";
import {
  Maximize2,
  Minimize2,
  Pause,
  Play,
  Volume2,
  VolumeX,
} from "lucide-react";
import { cn } from "@/lib/utils";
import styles from "./video-player.module.css";

// Interaction mechanics adapted from https://21st.dev/@preetsuthar17/components/video-player

const SEEK_STEP_SECONDS = 5;

type SafariFullscreenVideo = HTMLVideoElement & {
  webkitDisplayingFullscreen?: boolean;
  webkitEnterFullscreen?: () => void;
  webkitExitFullscreen?: () => void;
};

type ProgressStyle = React.CSSProperties & {
  "--video-progress": string;
};

export type VideoPlayerProps = {
  src: string;
  title: string;
  className?: string;
  poster?: string;
  onPlaybackError?: (error: MediaError | null) => void;
};

export function VideoPlayer({
  src,
  title,
  className,
  poster,
  onPlaybackError,
}: VideoPlayerProps) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const instructionsId = React.useId();
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(0);
  const [duration, setDuration] = React.useState(0);
  const [volume, setVolume] = React.useState(1);
  const [isMuted, setIsMuted] = React.useState(false);
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [canFullscreen, setCanFullscreen] = React.useState(true);
  const [announcement, setAnnouncement] = React.useState("");

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setAnnouncement("");
    video.load();
  }, [src]);

  React.useEffect(() => {
    const root = rootRef.current;
    const video = videoRef.current as SafariFullscreenVideo | null;
    setCanFullscreen(
      Boolean(root?.requestFullscreen || video?.webkitEnterFullscreen),
    );

    function handleFullscreenChange() {
      setIsFullscreen(document.fullscreenElement === rootRef.current);
    }

    function handleWebkitFullscreenStart() {
      setIsFullscreen(true);
    }

    function handleWebkitFullscreenEnd() {
      setIsFullscreen(false);
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    video?.addEventListener(
      "webkitbeginfullscreen",
      handleWebkitFullscreenStart,
    );
    video?.addEventListener("webkitendfullscreen", handleWebkitFullscreenEnd);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      video?.removeEventListener(
        "webkitbeginfullscreen",
        handleWebkitFullscreenStart,
      );
      video?.removeEventListener(
        "webkitendfullscreen",
        handleWebkitFullscreenEnd,
      );
    };
  }, []);

  async function togglePlayback() {
    const video = videoRef.current;
    if (!video) return;

    if (video.paused || video.ended) {
      if (video.ended) video.currentTime = 0;
      try {
        await video.play();
      } catch {
        setIsPlaying(false);
        setAnnouncement(
          "Playback could not start. Try the play control again.",
        );
      }
      return;
    }

    video.pause();
  }

  function seekTo(nextTime: number) {
    const video = videoRef.current;
    if (!video) return;

    const mediaDuration = Number.isFinite(video.duration)
      ? video.duration
      : duration;
    const boundedTime = Math.min(
      Math.max(nextTime, 0),
      Math.max(mediaDuration, 0),
    );
    video.currentTime = boundedTime;
    setCurrentTime(boundedTime);
  }

  function skipBy(delta: number) {
    const video = videoRef.current;
    if (!video) return;

    seekTo(video.currentTime + delta);
    setAnnouncement(
      delta > 0 ? "Skipped forward 5 seconds." : "Skipped back 5 seconds.",
    );
  }

  function toggleMuted() {
    const video = videoRef.current;
    if (!video) return;

    if (video.muted || video.volume === 0) {
      if (video.volume === 0) video.volume = 0.5;
      video.muted = false;
      setAnnouncement("Sound on.");
      return;
    }

    video.muted = true;
    setAnnouncement("Sound muted.");
  }

  function handleVolumeChange(event: React.ChangeEvent<HTMLInputElement>) {
    const video = videoRef.current;
    if (!video) return;

    const nextVolume = Number(event.currentTarget.value);
    video.volume = nextVolume;
    video.muted = nextVolume === 0;
  }

  async function toggleFullscreen() {
    const root = rootRef.current;
    const video = videoRef.current as SafariFullscreenVideo | null;
    if (!root || !video) return;

    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (
        video.webkitDisplayingFullscreen &&
        video.webkitExitFullscreen
      ) {
        video.webkitExitFullscreen();
      } else if (root.requestFullscreen) {
        await root.requestFullscreen();
      } else if (video.webkitEnterFullscreen) {
        video.webkitEnterFullscreen();
      } else {
        setAnnouncement("Fullscreen is not available in this browser.");
      }
    } catch {
      setAnnouncement("Fullscreen could not be opened.");
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;

    const target = event.target as HTMLElement;
    if (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target.isContentEditable
    ) {
      return;
    }

    const key = event.key.toLowerCase();
    if (target instanceof HTMLButtonElement && (key === " " || key === "enter"))
      return;
    if (
      event.repeat &&
      (key === " " || key === "k" || key === "m" || key === "f")
    )
      return;

    if (key === " " || key === "k") {
      event.preventDefault();
      void togglePlayback();
    } else if (key === "m") {
      event.preventDefault();
      toggleMuted();
    } else if (key === "f") {
      event.preventDefault();
      void toggleFullscreen();
    } else if (key === "arrowleft") {
      event.preventDefault();
      skipBy(-SEEK_STEP_SECONDS);
    } else if (key === "arrowright") {
      event.preventDefault();
      skipBy(SEEK_STEP_SECONDS);
    }
  }

  const safeDuration = Number.isFinite(duration) ? Math.max(duration, 0) : 0;
  const progress =
    safeDuration > 0 ? Math.min(currentTime / safeDuration, 1) : 0;
  const audibleVolume = isMuted ? 0 : volume;
  const seekStyle = {
    "--video-progress": `${progress * 100}%`,
  } as ProgressStyle;
  const volumeStyle = {
    "--video-progress": `${audibleVolume * 100}%`,
  } as ProgressStyle;

  return (
    <div
      ref={rootRef}
      className={cn(styles.root, className)}
      role="region"
      tabIndex={0}
      aria-label={`Video player: ${title}`}
      aria-describedby={instructionsId}
      aria-keyshortcuts="Space K M F ArrowLeft ArrowRight"
      onKeyDown={handleKeyDown}
    >
      <video
        ref={videoRef}
        className={styles.video}
        src={src}
        poster={poster}
        preload="metadata"
        playsInline
        aria-label={title}
        onClick={() => void togglePlayback()}
        onLoadedMetadata={(event) => {
          const nextDuration = Number.isFinite(event.currentTarget.duration)
            ? event.currentTarget.duration
            : 0;
          setDuration(nextDuration);
          setCurrentTime(event.currentTarget.currentTime);
        }}
        onDurationChange={(event) => {
          const nextDuration = Number.isFinite(event.currentTarget.duration)
            ? event.currentTarget.duration
            : 0;
          setDuration(nextDuration);
        }}
        onTimeUpdate={(event) =>
          setCurrentTime(event.currentTarget.currentTime)
        }
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => {
          setIsPlaying(false);
          setAnnouncement("Playback ended.");
        }}
        onVolumeChange={(event) => {
          setVolume(event.currentTarget.volume);
          setIsMuted(
            event.currentTarget.muted || event.currentTarget.volume === 0,
          );
        }}
        onError={(event) => {
          setIsPlaying(false);
          setAnnouncement("The video could not be played.");
          onPlaybackError?.(event.currentTarget.error);
        }}
      >
        Your browser does not support HTML video.
      </video>

      <div
        className={styles.pausedMarker}
        data-visible={!isPlaying}
        aria-hidden="true"
      >
        <Play />
      </div>

      <div className={styles.controls}>
        <div className={styles.seekRow}>
          <span className={styles.time}>{formatTime(currentTime)}</span>
          <input
            className={styles.range}
            type="range"
            min="0"
            max={safeDuration || 0}
            step="0.01"
            value={Math.min(currentTime, safeDuration || 0)}
            disabled={safeDuration <= 0}
            style={seekStyle}
            aria-label="Seek video"
            aria-valuetext={`${describeTime(currentTime)} of ${describeTime(safeDuration)}`}
            onChange={(event) => seekTo(Number(event.currentTarget.value))}
          />
          <span className={styles.time}>{formatTime(safeDuration)}</span>
        </div>

        <div className={styles.transportRow}>
          <button
            className={styles.iconButton}
            type="button"
            aria-label={isPlaying ? "Pause video" : "Play video"}
            aria-keyshortcuts="Space K"
            onClick={() => void togglePlayback()}
          >
            {isPlaying ? (
              <Pause aria-hidden="true" />
            ) : (
              <Play aria-hidden="true" />
            )}
          </button>

          <div className={styles.volumeGroup}>
            <button
              className={styles.iconButton}
              type="button"
              aria-label={
                isMuted || volume === 0 ? "Unmute video" : "Mute video"
              }
              aria-keyshortcuts="M"
              aria-pressed={isMuted || volume === 0}
              onClick={toggleMuted}
            >
              {isMuted || volume === 0 ? (
                <VolumeX aria-hidden="true" />
              ) : (
                <Volume2 aria-hidden="true" />
              )}
            </button>
            <input
              className={cn(styles.range, styles.volumeRange)}
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={audibleVolume}
              style={volumeStyle}
              aria-label="Video volume"
              aria-valuetext={`${Math.round(audibleVolume * 100)} percent`}
              onChange={handleVolumeChange}
            />
          </div>

          <button
            className={styles.iconButton}
            type="button"
            aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            aria-keyshortcuts="F"
            aria-pressed={isFullscreen}
            disabled={!canFullscreen}
            onClick={() => void toggleFullscreen()}
          >
            {isFullscreen ? (
              <Minimize2 aria-hidden="true" />
            ) : (
              <Maximize2 aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      <p id={instructionsId} className={styles.srOnly}>
        Keyboard shortcuts: Space or K plays and pauses, M mutes, F toggles
        fullscreen, and the left and right arrow keys seek by 5 seconds when the
        player itself is focused.
      </p>
      <p
        className={styles.srOnly}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {announcement}
      </p>
    </div>
  );
}

function formatTime(seconds: number) {
  const totalSeconds = Math.max(
    0,
    Math.floor(Number.isFinite(seconds) ? seconds : 0),
  );
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainder = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }

  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function describeTime(seconds: number) {
  const totalSeconds = Math.max(
    0,
    Math.floor(Number.isFinite(seconds) ? seconds : 0),
  );
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainder = totalSeconds % 60;
  const parts = [];

  if (hours) parts.push(`${hours} ${hours === 1 ? "hour" : "hours"}`);
  if (minutes) parts.push(`${minutes} ${minutes === 1 ? "minute" : "minutes"}`);
  parts.push(`${remainder} ${remainder === 1 ? "second" : "seconds"}`);

  return parts.join(" ");
}
