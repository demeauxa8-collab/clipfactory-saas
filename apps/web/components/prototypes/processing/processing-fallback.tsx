"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, RotateCcw, TriangleAlert, Upload } from "lucide-react";
import type { ProcessingPreviewState } from "./processing-sequence";
import styles from "./processing-fallback.module.css";

type ProcessingFallbackProps = {
  state: Extract<ProcessingPreviewState, "empty" | "error">;
};

export function ProcessingFallback({ state }: ProcessingFallbackProps) {
  const isError = state === "error";

  const restart = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("state");
    window.location.assign(url);
  };

  return (
    <main id="main-content" className={styles.fallback}>
      <Image
        src="/prototypes/cinematic-source-v1.webp"
        alt=""
        fill
        priority
        sizes="100vw"
        className={styles.backdrop}
      />
      <span className={styles.shade} aria-hidden="true" />

      <header className={styles.header}>
        <div className={styles.brand}>
          <span aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          ClipFactory
        </div>
        <span>Product proof · Interview_master.mov</span>
      </header>

      <section
        className={styles.message}
        role={isError ? "alert" : "status"}
        aria-labelledby="processing-fallback-title"
      >
        <div className={styles.signal} data-error={isError ? "" : undefined}>
          {isError ? (
            <TriangleAlert aria-hidden="true" />
          ) : (
            <Upload aria-hidden="true" />
          )}
        </div>
        <p className={styles.eyebrow}>
          {isError ? "Source handoff paused" : "No source yet"}
        </p>
        <h1 id="processing-fallback-title">
          {isError
            ? "The source stayed safe. The transcript handoff did not."
            : "Bring the source into the same story thread."}
        </h1>
        <p className={styles.explanation}>
          {isError
            ? "ClipFactory stopped before selecting a moment. Your campaign brief and original video are unchanged, so you can retry this stage without starting over."
            : "Add the interview used by this campaign. ClipFactory needs the source frames and their exact transcript timing before it can build the first cut."}
        </p>
        <div className={styles.actions}>
          {isError ? (
            <button type="button" className={styles.primary} onClick={restart}>
              <RotateCcw aria-hidden="true" />
              Restart this stage
            </button>
          ) : (
            <Link href="/app/campaigns/new" className={styles.primary}>
              <Upload aria-hidden="true" />
              Choose a source
            </Link>
          )}
          <Link href="/app" className={styles.secondary}>
            <ArrowLeft aria-hidden="true" />
            Back to campaign
          </Link>
        </div>
        {isError ? (
          <p className={styles.technical}>
            Stage: transcript_anchor · Request CF-1492
          </p>
        ) : null}
      </section>

      <footer className={styles.footer}>
        The campaign context stays attached while this stage is resolved.
      </footer>
    </main>
  );
}
