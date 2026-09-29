"use client";

import * as React from "react";
import { useReducedMotion } from "motion/react";

export const PROCESSING_PHASES = [
  {
    label: "Source secured",
    detail: "18:42 of interview footage is ready to inspect.",
    short: "Source",
  },
  {
    label: "Words anchored",
    detail: "12,408 transcript words are locked to source frames.",
    short: "Words",
  },
  {
    label: "Campaign moments found",
    detail: "Three moments answer the Product proof campaign brief.",
    short: "Moments",
  },
  {
    label: "The proof selected",
    detail: "09:32 keeps the product visible while the result is named.",
    short: "Proof",
  },
  {
    label: "Subject reframed",
    detail: "The speaker stays locked while 16:9 closes into 9:16.",
    short: "Frame",
  },
  {
    label: "Exact words composed",
    detail: "Verified transcript words become the on-screen caption.",
    short: "Caption",
  },
  {
    label: "First clip ready",
    detail: "A 13-second campaign cut is ready to preview.",
    short: "Ready",
  },
] as const;

export type ProcessingPreviewState =
  "auto" | "loading" | "processing" | "empty" | "error" | "success" | "long";

export type ProcessingEventStatus = "pending" | "active" | "complete";

const PHASE_DELAYS = [760, 920, 1120, 980, 1040, 1160] as const;

function forcedPhase(state: ProcessingPreviewState) {
  if (state === "loading" || state === "empty") return 0;
  if (state === "processing") return 3;
  if (state === "error") return 2;
  if (state === "success" || state === "long") {
    return PROCESSING_PHASES.length - 1;
  }
  return null;
}

export function useProcessingSequence(
  previewState: ProcessingPreviewState = "auto",
) {
  const reduceMotion = Boolean(useReducedMotion());
  const forced = forcedPhase(previewState);
  const [phase, setPhase] = React.useState(forced ?? 0);

  React.useEffect(() => {
    if (forced !== null) {
      setPhase(forced);
      return;
    }

    setPhase(0);
    let cancelled = false;
    let timer = 0;
    let next = 1;

    const advance = () => {
      if (cancelled || next >= PROCESSING_PHASES.length) return;
      setPhase(next);
      next += 1;
      if (next < PROCESSING_PHASES.length) {
        timer = window.setTimeout(advance, PHASE_DELAYS[next - 1]);
      }
    };

    timer = window.setTimeout(advance, PHASE_DELAYS[0]);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [forced, reduceMotion]);

  const boundedPhase = Math.max(
    0,
    Math.min(phase, PROCESSING_PHASES.length - 1),
  );
  const complete = boundedPhase === PROCESSING_PHASES.length - 1;
  const events = PROCESSING_PHASES.map((event, index) => ({
    ...event,
    status: (index < boundedPhase
      ? "complete"
      : index === boundedPhase
        ? "active"
        : "pending") as ProcessingEventStatus,
  }));

  return {
    phase: boundedPhase,
    complete,
    current: PROCESSING_PHASES[boundedPhase],
    events,
    reduceMotion,
    previewState,
    isLoading: previewState === "loading",
    hasError: previewState === "error",
    isEmpty: previewState === "empty",
    isLong: previewState === "long",
  };
}

export function clampPhase(phase: number, maximum: number) {
  return Math.max(0, Math.min(maximum, phase));
}
