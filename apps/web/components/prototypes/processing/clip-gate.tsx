"use client";

import Link from "next/link";
import * as React from "react";
import { ArrowUpRight, Check, LockKeyhole, Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import styles from "./clip-gate.module.css";

type ClipGateProps = {
  children: React.ReactElement;
  demoMode?: boolean;
  onUnlock?: () => void;
};

export function ClipGate({
  children,
  demoMode = false,
  onUnlock,
}: ClipGateProps) {
  const primaryLinkRef = React.useRef<HTMLAnchorElement>(null);
  const primaryButtonRef = React.useRef<HTMLButtonElement>(null);
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const [open, setOpen] = React.useState(false);
  const [previewSecond, setPreviewSecond] = React.useState(0);
  const [previewStatus, setPreviewStatus] = React.useState("");
  const [replayKey, setReplayKey] = React.useState(0);
  const [reduceMotion, setReduceMotion] = React.useState(false);

  React.useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => setReduceMotion(media.matches);

    syncPreference();
    media.addEventListener("change", syncPreference);
    return () => media.removeEventListener("change", syncPreference);
  }, []);

  React.useEffect(() => {
    if (!open) return;

    let video: HTMLVideoElement | null = null;
    let active = true;

    const startPreview = () => {
      if (!video || !active) return;

      if (reduceMotion) {
        video.pause();
        video.currentTime = Math.min(3, video.duration || 3);
        setPreviewSecond(3);
        setPreviewStatus(
          "Preview paused at three seconds to respect reduced motion. The full cut is locked.",
        );
        return;
      }

      video.currentTime = 0;
      setPreviewSecond(0);
      setPreviewStatus("Three-second preview started.");
      void video.play().catch(() => {
        setPreviewStatus("Three-second preview ready. Use Replay to start it.");
      });
    };

    const connectPreview = window.requestAnimationFrame(() => {
      video = videoRef.current;
      if (!video) return;

      if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
        startPreview();
      } else {
        video.addEventListener("loadedmetadata", startPreview, { once: true });
      }
    });

    return () => {
      active = false;
      window.cancelAnimationFrame(connectPreview);
      video?.removeEventListener("loadedmetadata", startPreview);
      video?.pause();
    };
  }, [open, reduceMotion, replayKey]);

  const replayPreview = () => {
    const video = videoRef.current;
    if (!video) return;

    if (reduceMotion) {
      const targetSecond = previewSecond >= 3 ? 0 : 3;
      video.pause();
      video.currentTime = targetSecond;
      setPreviewSecond(targetSecond);
      setPreviewStatus(
        targetSecond === 0
          ? "Showing the first frame of the preview."
          : "Showing the locked frame at three seconds.",
      );
      return;
    }

    setReplayKey((key) => key + 1);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent
        className={styles.sheet}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          if (demoMode && onUnlock) {
            primaryButtonRef.current?.focus();
          } else {
            primaryLinkRef.current?.focus();
          }
        }}
      >
        <div className={styles.preview}>
          <video
            ref={videoRef}
            src="/prototypes/first-cut-teaser-v1.mp4"
            poster="/prototypes/founder-frame-3-v2.webp"
            muted
            playsInline
            preload="auto"
            className={styles.previewFrame}
            aria-hidden="true"
            onTimeUpdate={(event) => {
              setPreviewSecond(
                Math.min(3, Math.floor(event.currentTarget.currentTime + 0.08)),
              );
            }}
            onEnded={() => {
              setPreviewSecond(3);
              setPreviewStatus(
                "Preview complete at three seconds. The full cut is locked.",
              );
            }}
          />
          <span className={styles.previewShade} aria-hidden="true" />
          <span className={styles.previewTime} aria-hidden="true">
            00:0{previewSecond} / 00:13
          </span>
          {previewSecond >= 3 ? (
            <span className={styles.previewLock} aria-hidden="true">
              <LockKeyhole />
            </span>
          ) : null}
          <p>The proof arrives before the promise.</p>
          <p className={styles.srOnly} aria-live="polite" aria-atomic="true">
            {previewStatus}
          </p>
        </div>

        <section className={styles.offer}>
          <div className={styles.eyebrow}>
            <span />
            Your first campaign cut is ready
          </div>
          <DialogTitle className={styles.title}>
            You have seen the proof. Unlock the full cut.
          </DialogTitle>
          <DialogDescription className={styles.description}>
            Keep this 13-second edit and its exact transcript evidence. Starter
            can generate up to two more campaign-shaped clips from the same
            source.
          </DialogDescription>

          <div className={styles.price}>
            <strong>29€</strong>
            <span>per month · 300 credits included</span>
          </div>

          <ul className={styles.reasons}>
            <li>
              <Check aria-hidden="true" /> Full 1080×1920 cut, no watermark
            </li>
            <li>
              <Check aria-hidden="true" /> Exact words verified against the
              source
            </li>
            <li>
              <Check aria-hidden="true" /> Up to three clips shaped by your
              campaign
            </li>
          </ul>

          {demoMode && onUnlock ? (
            <button
              ref={primaryButtonRef}
              type="button"
              className={styles.primaryAction}
              onClick={() => {
                setOpen(false);
                onUnlock();
              }}
            >
              Unlock this local preview
              <ArrowUpRight aria-hidden="true" />
            </button>
          ) : (
            <Link
              ref={primaryLinkRef}
              href="/app/billing"
              className={styles.primaryAction}
            >
              Unlock with Starter
              <ArrowUpRight aria-hidden="true" />
            </Link>
          )}
          <button
            type="button"
            className={styles.secondaryAction}
            onClick={replayPreview}
          >
            <Play aria-hidden="true" />
            {reduceMotion
              ? previewSecond >= 3
                ? "Show preview start"
                : "Show locked frame"
              : "Replay the 3-second preview"}
          </button>
          <p className={styles.keepNote}>
            {demoMode
              ? "Local journey preview · no payment or account change is made."
              : "Your source, campaign brief and this selected moment stay saved."}
          </p>
        </section>
      </DialogContent>
    </Dialog>
  );
}
