"use client";

import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Check, CircleAlert, Radio } from "lucide-react";

import {
  ProductPanel,
  ProductStatus,
} from "@/components/product/product-primitives";
import { apiFetch } from "@/lib/api";

import styles from "./job-monitor.module.css";

const PHASES = [
  {
    key: "queued",
    label: "Queued",
    description: "Waiting for an available worker",
  },
  {
    key: "downloading",
    label: "Source",
    description: "Copying and checking the public video",
  },
  {
    key: "transcribing",
    label: "Words",
    description: "Locking transcript words to source time",
  },
  {
    key: "analyzing",
    label: "Story",
    description: "Finding setup, proof, payoff and campaign fit",
  },
  {
    key: "rendering",
    label: "Render",
    description: "Building vertical edits and running quality checks",
  },
  {
    key: "completed",
    label: "Ready",
    description: "Cuts and reasoning are available for review",
  },
] as const;

const PHASE_POSITIONS = [3, 22, 42, 62, 82, 97] as const;
const WAVEFORM = Array.from({ length: 84 }, (_, index) => {
  const voice = Math.abs(Math.sin(index * 0.71)) * 32;
  const cadence = Math.abs(Math.sin(index * 0.17 + 1.2)) * 26;
  const emphasis = index > 36 && index < 60 ? 16 : 0;
  return Math.round(12 + voice + cadence + emphasis);
});

type JobView = {
  job: {
    id: string;
    status: string;
    current_step: string | null;
    error_code: string | null;
    error_message: string | null;
  };
};

const POLL_INTERVAL_MS = 5000;
const TIMELINE_TRANSITION = {
  type: "spring" as const,
  stiffness: 250,
  damping: 34,
  mass: 0.82,
};

export function JobMonitor({
  jobId,
  initialStatus,
  initialStep,
}: {
  jobId: string;
  initialStatus: string;
  initialStep: string | null;
}) {
  const router = useRouter();
  const reduceMotion = Boolean(useReducedMotion());
  const isTerminal = (status: string) =>
    ["completed", "failed", "canceled"].includes(status);
  const { data, error, isLoading } = useSWR<JobView>(
    isTerminal(initialStatus) ? null : `/jobs/${jobId}`,
    (path: string) => apiFetch<JobView>(path),
    {
      refreshInterval: (latest) =>
        isTerminal(latest?.job.status ?? initialStatus) ? 0 : POLL_INTERVAL_MS,
      revalidateOnFocus: false,
    },
  );

  const status = data?.job.status ?? initialStatus;
  const step = data?.job.current_step ?? initialStep;
  const failed = status === "failed" || status === "canceled";
  const activeKey = failed ? phaseForStep(step) : status;
  const activeIndex = Math.max(
    0,
    PHASES.findIndex((phase) => phase.key === activeKey),
  );
  const activePhase = PHASES[activeIndex] ?? PHASES[0];
  const progress = status === "completed" ? 100 : PHASE_POSITIONS[activeIndex];
  const wasTerminal = React.useRef(isTerminal(initialStatus));

  React.useEffect(() => {
    if (!wasTerminal.current && isTerminal(status)) {
      wasTerminal.current = true;
      router.refresh();
    }
  }, [status, router]);

  const transition = reduceMotion ? { duration: 0 } : TIMELINE_TRANSITION;

  return (
    <ProductPanel className={styles.monitor}>
      <div className={styles.header}>
        <div>
          <p>Live source timeline</p>
          <h2>
            {failed
              ? "This source needs attention."
              : status === "completed"
                ? "The cuts are ready."
                : "Building evidence before the edit."}
          </h2>
        </div>
        <ProductStatus
          tone={
            failed ? "danger" : status === "completed" ? "success" : "action"
          }
          pulse={!failed && status !== "completed"}
        >
          {failed ? "Stopped" : status === "completed" ? "Ready" : "Live"}
        </ProductStatus>
      </div>

      <section className={styles.stage} aria-label="Analysis stages">
        <div className={styles.ambient} aria-hidden="true" />
        <div className={styles.waveform} aria-hidden="true">
          {WAVEFORM.map((height, index) => (
            <i
              key={index}
              data-processed={
                (index / (WAVEFORM.length - 1)) * 100 <= progress || undefined
              }
              style={{ "--wave-height": `${height}%` } as React.CSSProperties}
            />
          ))}
        </div>
        <span className={styles.axis} aria-hidden="true" />
        <motion.span
          className={styles.processedLine}
          initial={false}
          animate={{ transform: `scaleX(${progress / 100})` }}
          transition={transition}
          aria-hidden="true"
        />
        <motion.span
          className={styles.playhead}
          initial={false}
          animate={{ transform: `translate3d(${progress}%, 0, 0)` }}
          transition={transition}
          aria-hidden="true"
        >
          <i />
        </motion.span>

        <ol className={styles.phases} aria-live="polite">
          {PHASES.map((phase, index) => {
            const done = status === "completed" || index < activeIndex;
            const active = !done && index === activeIndex;
            const stopped = failed && active;
            const state = done
              ? "done"
              : stopped
                ? "failed"
                : active
                  ? "active"
                  : "pending";

            return (
              <li
                key={phase.key}
                data-state={state}
                style={
                  {
                    "--phase-position": `${PHASE_POSITIONS[index]}%`,
                  } as React.CSSProperties
                }
                aria-current={active ? "step" : undefined}
              >
                <span className={styles.marker} aria-hidden="true">
                  {done ? <Check /> : stopped ? <CircleAlert /> : <span />}
                </span>
                <span className={styles.phaseLabel}>{phase.label}</span>
                <span className={styles.srOnly}>
                  {phase.label}: {state}
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      <div className={styles.liveDetail} aria-live="polite" aria-atomic="true">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={`${status}:${step ?? "idle"}`}
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -5 }}
            transition={{
              duration: reduceMotion ? 0 : 0.2,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <span>
              {String(activeIndex + 1).padStart(2, "0")} /{" "}
              {String(PHASES.length).padStart(2, "0")}
            </span>
            <div>
              <strong>
                {failed ? "Processing stopped" : activePhase.description}
              </strong>
              <p>
                {step
                  ? humanizeStep(step)
                  : "Waiting for the next confirmed worker event"}
              </p>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      <div className={styles.footer}>
        {error ? (
          <p role="status">
            <CircleAlert aria-hidden="true" /> Live updates are interrupted. The
            last confirmed state is still shown.
          </p>
        ) : isLoading && !data ? (
          <p>
            <Radio aria-hidden="true" /> Reconnecting to the analysis log…
          </p>
        ) : status === "completed" ? (
          <p>
            <Check aria-hidden="true" /> Transcript, selected words and
            delivered cuts are ready below.
          </p>
        ) : failed ? (
          <p>
            <CircleAlert aria-hidden="true" /> Return to the campaign to submit
            a new source.
          </p>
        ) : (
          <p>
            <Radio aria-hidden="true" /> You can leave this page. ClipFactory
            will keep processing.
          </p>
        )}
        <span>No invented percentage or completion estimate.</span>
      </div>
    </ProductPanel>
  );
}

function phaseForStep(step: string | null) {
  if (!step) return "queued";
  if (["validate_url", "download", "probe", "check_credits"].includes(step))
    return "downloading";
  if (step === "transcribe") return "transcribing";
  if (
    [
      "select_arcs",
      "video_map",
      "story_arcs",
      "anchor_arcs",
      "verify_arcs",
      "snap_segments",
      "deep_vision",
    ].includes(step)
  )
    return "analyzing";
  if (["render", "render_qc"].includes(step)) return "rendering";
  if (step === "completed") return "completed";
  return "queued";
}

function humanizeStep(step: string) {
  const labels: Record<string, string> = {
    validate_url: "Checking the source address",
    download: "Copying the public source",
    probe: "Reading duration and format",
    check_credits: "Confirming plan and credit balance",
    transcribe: "Transcribing source words",
    select_arcs: "Finding candidate story arcs",
    video_map: "Mapping visible moments",
    story_arcs: "Connecting setup and payoff",
    anchor_arcs: "Anchoring selected words to time",
    verify_arcs: "Verifying candidate evidence",
    snap_segments: "Snapping the edit to transcript boundaries",
    deep_vision: "Inspecting visual proof",
    render: "Rendering vertical clips",
    render_qc: "Checking the final renders",
  };
  return labels[step] ?? step.replaceAll("_", " ");
}
