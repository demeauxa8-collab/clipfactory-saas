"use client";

import Image from "next/image";
import * as React from "react";
import { Play } from "lucide-react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import {
  PROCESSING_PHASES,
  type ProcessingPreviewState,
  useProcessingSequence,
} from "./processing-sequence";
import { ClipGate } from "./clip-gate";
import styles from "./signal-timeline.module.css";

const EVENT_POSITIONS = [4, 18, 35, 54, 71, 87, 97] as const;

const TRANSCRIPT = [
  { text: "We stopped leading", at: 13, proof: false },
  { text: "with the promise.", at: 30, proof: false },
  { text: "The screen", at: 49, proof: false },
  { text: "already showed", at: 64, proof: false },
  { text: "the proof.", at: 79, proof: true },
] as const;

const CANDIDATES = [
  {
    label: "The tension",
    time: "02:14",
    score: 92,
    start: 10,
    width: 17,
    selected: false,
  },
  {
    label: "The proof",
    time: "09:32",
    score: 89,
    start: 43,
    width: 17,
    selected: true,
  },
  {
    label: "The payoff",
    time: "16:05",
    score: 86,
    start: 76,
    width: 15,
    selected: false,
  },
] as const;

const PLAYHEAD_LABELS = [
  "00:18",
  "02:14",
  "06:48",
  "09:32",
  "12:06",
  "16:05",
  "18:42",
] as const;

const WAVEFORM = Array.from({ length: 112 }, (_, index) => {
  const voice = Math.abs(Math.sin(index * 0.72)) * 34;
  const cadence = Math.abs(Math.sin(index * 0.19 + 1.4)) * 28;
  const emphasis = index > 45 && index < 68 ? 18 : 0;
  return Math.round(10 + voice + cadence + emphasis);
});

const ENTER = {
  duration: 0.28,
  ease: [0.23, 1, 0.32, 1] as [number, number, number, number],
};

const SPATIAL = {
  type: "spring" as const,
  duration: 0.62,
  bounce: 0,
};

type SignalTimelineProps = {
  previewState?: ProcessingPreviewState;
  demoMode?: boolean;
  onUnlock?: () => void;
};

export function SignalTimeline({
  previewState = "auto",
  demoMode = false,
  onUnlock,
}: SignalTimelineProps) {
  const { phase, complete, current, reduceMotion, isLong, isLoading } =
    useProcessingSequence(previewState);
  const titleId = React.useId();
  const phaseNumber = Math.min(phase + 1, PROCESSING_PHASES.length);
  const playheadLabel =
    PLAYHEAD_LABELS[Math.min(phase, PLAYHEAD_LABELS.length - 1)];
  const progressValue = complete ? 1 : EVENT_POSITIONS[phase] / 100;
  const fileName = isLong
    ? "Interview_master_final_with_remote_guest_and_product_walkthrough_version_07.mov"
    : "Interview_master.mov";
  const progressTransition = reduceMotion
    ? { duration: 0 }
    : {
        duration: 0.52,
        ease: [0.77, 0, 0.175, 1] as [number, number, number, number],
      };

  return (
    <main
      id="main-content"
      className={styles.room}
      data-complete={complete || undefined}
      data-phase={phase}
      data-long={isLong || undefined}
      aria-busy={isLoading || undefined}
      aria-labelledby={titleId}
    >
      <motion.div
        className={styles.source}
        initial={false}
        animate={{
          opacity: phase >= 3 ? 0.22 : 0.62,
          transform: phase >= 3 ? "scale(1.025)" : "scale(1)",
        }}
        transition={reduceMotion ? { duration: 0 } : ENTER}
        aria-hidden="true"
      >
        <Image
          src="/prototypes/cinematic-source-v1.webp"
          alt=""
          fill
          priority
          sizes="100vw"
        />
      </motion.div>
      <div className={styles.sourceShade} aria-hidden="true" />

      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>ClipFactory</span>
        </div>

        <div className={styles.titleBlock}>
          <span title={fileName}>{fileName}</span>
          <h1 id={titleId}>
            {complete ? "First clip ready" : "Building your first clip"}
          </h1>
        </div>

        <div
          className={styles.liveStatus}
          aria-live="polite"
          aria-atomic="true"
        >
          <span>
            {String(phaseNumber).padStart(2, "0")} /{" "}
            {String(PROCESSING_PHASES.length).padStart(2, "0")}
          </span>
          <strong>
            {isLoading
              ? "Preparing source"
              : complete
                ? "First clip ready"
                : current.label}
          </strong>
        </div>
      </header>

      <LayoutGroup id="signal-timeline">
        <section className={styles.stage} aria-label="Source-to-clip timeline">
          <figure className={styles.timeline}>
            <figcaption className={styles.srOnly}>
              The source waveform is matched to transcript events, campaign
              candidates, a vertical crop and a verified thirteen-second clip.
            </figcaption>

            <div className={styles.track}>
              <motion.div
                className={styles.waveReveal}
                initial={{ clipPath: "inset(0 100% 0 0)", opacity: 0.28 }}
                animate={{ clipPath: "inset(0 0% 0 0)", opacity: 1 }}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : {
                        clipPath: {
                          duration: 0.78,
                          ease: [0.77, 0, 0.175, 1],
                        },
                        opacity: ENTER,
                      }
                }
                aria-hidden="true"
              >
                <div className={styles.waveform}>
                  {WAVEFORM.map((height, index) => (
                    <i
                      key={index}
                      style={
                        {
                          "--wave-height": `${height}%`,
                        } as React.CSSProperties
                      }
                    />
                  ))}
                </div>
              </motion.div>

              <span className={styles.axis} aria-hidden="true" />
              <motion.span
                className={styles.processedLine}
                initial={false}
                animate={{ transform: `scaleX(${progressValue})` }}
                transition={progressTransition}
                aria-hidden="true"
              />

              <ol className={styles.events} aria-label="Processing events">
                {PROCESSING_PHASES.map((event, index) => {
                  const isCurrent = index === phase && !complete;
                  const isDone = complete || index < phase;

                  return (
                    <motion.li
                      key={event.label}
                      className={styles.event}
                      style={
                        {
                          "--event-position": `${EVENT_POSITIONS[index]}%`,
                        } as React.CSSProperties
                      }
                      initial={false}
                      animate={{
                        opacity: isDone || isCurrent ? 1 : 0.3,
                        transform: isCurrent
                          ? "translateX(-50%) scale(1)"
                          : "translateX(-50%) scale(0.94)",
                      }}
                      transition={reduceMotion ? { duration: 0 } : ENTER}
                      data-current={isCurrent || undefined}
                      data-done={isDone || undefined}
                      data-side={index % 2 === 0 ? "above" : "below"}
                      aria-current={isCurrent ? "step" : undefined}
                      aria-label={`${event.label}: ${event.detail}`}
                    >
                      <span className={styles.eventMark} aria-hidden="true" />
                      <span className={styles.eventCopy} aria-hidden="true">
                        <strong>{event.label}</strong>
                        <small>{event.detail}</small>
                      </span>
                    </motion.li>
                  );
                })}
              </ol>

              <AnimatePresence>
                {phase >= 1 && phase < 3 ? (
                  <motion.ul
                    className={styles.transcript}
                    aria-label="Transcript anchors"
                    initial={{
                      opacity: 0,
                      transform: "translate3d(0, 8px, 0)",
                    }}
                    animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
                    exit={{ opacity: 0, transform: "translate3d(0, 8px, 0)" }}
                    transition={reduceMotion ? { duration: 0 } : ENTER}
                  >
                    {TRANSCRIPT.map((word, index) => (
                      <motion.li
                        key={word.text}
                        style={
                          {
                            "--word-position": `${word.at}%`,
                          } as React.CSSProperties
                        }
                        initial={{
                          opacity: 0,
                          transform: "translate(-50%, 6px)",
                        }}
                        animate={{
                          opacity: 1,
                          transform: "translate(-50%, 0)",
                        }}
                        transition={{
                          ...ENTER,
                          delay: reduceMotion ? 0 : index * 0.045,
                        }}
                        data-proof={word.proof || undefined}
                      >
                        {word.text}
                      </motion.li>
                    ))}
                  </motion.ul>
                ) : null}
              </AnimatePresence>

              <AnimatePresence>
                {phase >= 2 && phase < 3 ? (
                  <motion.ol
                    className={styles.candidates}
                    aria-label="Three detected campaign moments"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={reduceMotion ? { duration: 0 } : ENTER}
                  >
                    {CANDIDATES.map((candidate, index) => (
                      <motion.li
                        key={candidate.label}
                        className={styles.candidate}
                        style={
                          {
                            "--candidate-start": `${candidate.start}%`,
                            "--candidate-width": `${candidate.width}%`,
                          } as React.CSSProperties
                        }
                        initial={{
                          opacity: 0,
                          transform: "translateY(8px) scale(0.96)",
                        }}
                        animate={{
                          opacity: 1,
                          transform: "translateY(0) scale(1)",
                        }}
                        transition={{
                          type: "spring",
                          duration: 0.46,
                          bounce: 0,
                          delay: reduceMotion ? 0 : index * 0.07,
                        }}
                        data-selected={candidate.selected || undefined}
                      >
                        <motion.span
                          className={styles.candidateSurface}
                          layoutId={
                            candidate.selected
                              ? "signal-timeline-winner"
                              : undefined
                          }
                          transition={reduceMotion ? { duration: 0 } : SPATIAL}
                          aria-hidden="true"
                        />
                        <span className={styles.candidateCopy}>
                          <strong>{candidate.label}</strong>
                          <small>
                            {candidate.time} · {candidate.score}
                          </small>
                        </span>
                      </motion.li>
                    ))}
                  </motion.ol>
                ) : null}
              </AnimatePresence>

              <motion.div
                className={styles.playheadTravel}
                initial={false}
                animate={{
                  transform: `translate3d(${progressValue * 100}%, 0, 0)`,
                }}
                transition={progressTransition}
                aria-hidden="true"
              >
                <span className={styles.playhead}>
                  <i />
                  <b>{playheadLabel}</b>
                </span>
              </motion.div>
            </div>
          </figure>

          <AnimatePresence>
            {phase >= 3 ? (
              <motion.figure
                className={styles.portrait}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={reduceMotion ? { duration: 0 } : ENTER}
              >
                <motion.div
                  className={styles.portraitFrame}
                  layoutId="signal-timeline-winner"
                  transition={reduceMotion ? { duration: 0 } : SPATIAL}
                  data-locking={(phase === 3 && !complete) || undefined}
                  data-ready={complete || undefined}
                >
                  <Image
                    src="/prototypes/founder-frame-4-v2.webp"
                    alt="Selected proof moment reframed as a vertical clip"
                    fill
                    priority
                    sizes="(max-width: 720px) 54vw, 280px"
                  />
                  <span className={styles.portraitShade} aria-hidden="true" />
                  <div className={styles.portraitMeta}>
                    <span>9:16 · auto frame</span>
                    <span>09:32</span>
                  </div>

                  <AnimatePresence>
                    {phase >= 4 ? (
                      <motion.p
                        className={styles.caption}
                        initial={{ opacity: 0, transform: "translateY(10px)" }}
                        animate={{ opacity: 1, transform: "translateY(0)" }}
                        transition={reduceMotion ? { duration: 0 } : ENTER}
                      >
                        {isLong
                          ? "The full walkthrough proves the exact result on screen before the founder finishes explaining the launch promise."
                          : "The proof arrives before the promise."}
                      </motion.p>
                    ) : null}
                  </AnimatePresence>

                  {phase >= 5 ? (
                    <motion.span
                      className={styles.verified}
                      initial={{ opacity: 0, transform: "translateY(6px)" }}
                      animate={{ opacity: 1, transform: "translateY(0)" }}
                      transition={reduceMotion ? { duration: 0 } : ENTER}
                    >
                      <i aria-hidden="true">✓</i>
                      Source verified
                    </motion.span>
                  ) : null}

                  {complete ? (
                    <ClipGate demoMode={demoMode} onUnlock={onUnlock}>
                      <motion.button
                        type="button"
                        className={styles.clipPlay}
                        initial={{ opacity: 0, transform: "scale(0.94)" }}
                        animate={{ opacity: 1, transform: "scale(1)" }}
                        transition={
                          reduceMotion
                            ? { duration: 0 }
                            : { type: "spring", stiffness: 220, damping: 19 }
                        }
                        aria-label="Play the first three seconds and unlock the full clip"
                      >
                        <Play aria-hidden="true" fill="currentColor" />
                      </motion.button>
                    </ClipGate>
                  ) : null}
                </motion.div>
                <figcaption>
                  <strong>The proof</strong>
                  <span>Candidate 02 of 27 · score 89</span>
                </figcaption>
              </motion.figure>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {complete ? (
              <motion.div
                className={styles.readyCopy}
                initial={{ opacity: 0, transform: "translate3d(0, 16px, 0)" }}
                animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
                transition={{
                  ...ENTER,
                  delay: reduceMotion ? 0 : 0.14,
                }}
              >
                <span>First clip ready</span>
                <h2>
                  Thirteen seconds.
                  <br />
                  Every frame earned.
                </h2>
                <p>
                  {isLong
                    ? "9:16 · campaign-fit · 11 source words · subject locked"
                    : "9:16 · campaign-fit · transcript-grounded"}
                </p>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </section>
      </LayoutGroup>
    </main>
  );
}
