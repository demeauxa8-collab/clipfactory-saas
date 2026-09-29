"use client";

import * as React from "react";
import { Check, LockKeyhole, Play, Sparkles } from "lucide-react";
import { AnimatePresence, animate, motion, useMotionValue } from "motion/react";
import { MagneticCarousel } from "@/components/originkit/magnetic-carousel";
import { CampaignLensShader } from "@/components/prototypes/redesign/campaign-lens-shader";
import { ClipGate } from "./clip-gate";
import {
  type ProcessingPreviewState,
  useProcessingSequence,
} from "./processing-sequence";
import styles from "./source-cut.module.css";

const MOMENTS = [
  {
    src: "/prototypes/founder-frame-1-v2.webp",
    alt: "Founder interview at 02:14",
    label: "The tension",
    meta: "02:14",
  },
  {
    src: "/prototypes/founder-frame-4-v2.webp",
    alt: "Founder interview at 09:32",
    label: "The proof",
    meta: "09:32",
  },
  {
    src: "/prototypes/founder-frame-6-v2.webp",
    alt: "Founder interview at 16:05",
    label: "The payoff",
    meta: "16:05",
  },
] as const;

const TRANSCRIPT = [
  "We",
  "stopped",
  "leading",
  "with",
  "the",
  "promise.",
  "The",
  "screen",
  "already",
  "showed",
  "the",
  "proof.",
] as const;

const EASE = [0.23, 1, 0.32, 1] as const;

type SourceCutProps = {
  previewState?: ProcessingPreviewState;
};

export function SourceCut({ previewState = "auto" }: SourceCutProps) {
  const { phase, complete, current, events, reduceMotion, isLong, isLoading } =
    useProcessingSequence(previewState);
  const [selectedMoment, setSelectedMoment] = React.useState(1);
  const lensProgress = useMotionValue(0.04);

  React.useEffect(() => {
    const targets = [0.04, 0.2, 0.38, 0.58, 0.76, 0.92, 1];
    const target = targets[phase] ?? 1;
    if (reduceMotion) {
      lensProgress.set(target);
      return;
    }
    const controls = animate(lensProgress, target, {
      type: "spring",
      stiffness: 115,
      damping: 24,
      mass: 0.72,
    });
    return () => controls.stop();
  }, [lensProgress, phase, reduceMotion]);

  React.useEffect(() => {
    if (phase >= 3) setSelectedMoment(1);
  }, [phase]);

  const cropped = phase >= 4;
  const campaignName = isLong
    ? "Launch the product proof without losing the founder’s exact words or the on-screen evidence"
    : "Product proof";
  const fileName = isLong
    ? "Interview_master_final_with_remote_guest_and_product_walkthrough_version_07.mov"
    : "Interview_master.mov";

  return (
    <main
      id="main-content"
      className={styles.sourceCut}
      data-phase={phase}
      data-complete={complete ? "" : undefined}
      data-cropped={cropped ? "" : undefined}
      data-long={isLong ? "" : undefined}
      aria-busy={isLoading || undefined}
    >
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <strong>ClipFactory</strong>
        </div>
        <p className={styles.projectIdentity}>
          <span>{campaignName}</span>
          <small>{fileName}</small>
        </p>
        <span className={styles.truth}>Source-linked edit</span>
      </header>

      <section
        className={styles.experience}
        aria-labelledby="continuity-cut-title"
      >
        <div className={styles.statusCopy} role="status" aria-live="polite">
          <p>
            {isLoading
              ? "Preparing the source"
              : complete
                ? "First cut"
                : `Step ${phase + 1} of ${events.length}`}
          </p>
          <AnimatePresence mode="wait" initial={false}>
            <motion.h1
              id="continuity-cut-title"
              key={current.label}
              initial={{ opacity: 0, transform: "translate3d(0, 18px, 0)" }}
              animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
              exit={{ opacity: 0, transform: "translate3d(0, -12px, 0)" }}
              transition={{ duration: reduceMotion ? 0 : 0.42, ease: EASE }}
            >
              {isLoading
                ? "Bringing the story into focus."
                : complete
                  ? "The source became the cut."
                  : current.label}
            </motion.h1>
          </AnimatePresence>
          <p className={styles.statusDetail}>
            {isLoading
              ? "Reading the source frames and attaching your campaign brief."
              : complete
                ? "13 seconds · exact transcript · subject locked"
                : current.detail}
          </p>
        </div>

        <motion.div
          layout
          className={styles.mediaObject}
          data-cropped={cropped ? "" : undefined}
          transition={{
            layout: reduceMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 92, damping: 24 },
          }}
        >
          <CampaignLensShader
            imageSrc="/prototypes/cinematic-source-v1.webp"
            alt="Founder interview source transforming into the selected vertical clip"
            lensProgress={lensProgress}
            lensWidthPx={cropped ? 390 : 430}
            lensHeightRatio={cropped ? 0.93 : 0.84}
            lensSideMarginPx={cropped ? 18 : 46}
            lensRadiusPx={cropped ? 28 : 34}
            className={styles.shader}
          />
          <span className={styles.mediaShade} aria-hidden="true" />
          <span className={styles.localLight} aria-hidden="true" />

          <div className={styles.sourceMeta}>
            <span>{cropped ? "9:16 · subject lock" : "16:9 · source"}</span>
            <span>{phase >= 3 ? "09:32" : "18:42"}</span>
          </div>

          <AnimatePresence>
            {phase >= 1 && phase < 4 ? (
              <motion.p
                className={styles.transcript}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.28 }}
              >
                {TRANSCRIPT.map((word, index) => (
                  <motion.span
                    key={`${word}-${index}`}
                    data-proof={index >= 8 ? "" : undefined}
                    initial={{
                      opacity: 0,
                      transform: "translate3d(0, 11px, 0)",
                    }}
                    animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
                    transition={{
                      duration: reduceMotion ? 0 : 0.3,
                      delay: reduceMotion ? 0 : index * 0.038,
                      ease: EASE,
                    }}
                  >
                    {word}{" "}
                  </motion.span>
                ))}
              </motion.p>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {phase >= 4 ? (
              <motion.div
                className={styles.cropGuides}
                initial={{ opacity: 0, transform: "scaleX(1.35)" }}
                animate={{ opacity: 1, transform: "scaleX(1)" }}
                transition={{ duration: reduceMotion ? 0 : 0.62, ease: EASE }}
                aria-hidden="true"
              >
                <i />
                <i />
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {phase >= 5 ? (
              <motion.p
                className={styles.caption}
                initial={{
                  opacity: 0,
                  transform: "translate3d(0, 22px, 0)",
                  clipPath: "inset(100% 0 0 0)",
                }}
                animate={{
                  opacity: 1,
                  transform: "translate3d(0, 0, 0)",
                  clipPath: "inset(0% 0 0 0)",
                }}
                transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE }}
              >
                {isLong
                  ? "The on-screen walkthrough proves the exact result before the founder finishes explaining the launch promise."
                  : "The proof arrives before the promise."}
              </motion.p>
            ) : null}
          </AnimatePresence>

          {complete ? (
            <motion.svg
              className={styles.verifiedTrace}
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <motion.rect
                x="1"
                y="1"
                width="98"
                height="98"
                rx="5"
                pathLength="1"
                fill="none"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.82, ease: EASE }}
              />
            </motion.svg>
          ) : null}

          {complete ? (
            <ClipGate>
              <motion.button
                type="button"
                className={styles.playButton}
                initial={{ opacity: 0, transform: "scale(0.94)" }}
                animate={{ opacity: 1, transform: "scale(1)" }}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : {
                        type: "spring",
                        stiffness: 220,
                        damping: 18,
                        delay: 0.24,
                      }
                }
                aria-label="Play the first three seconds and unlock the full clip"
              >
                <Play aria-hidden="true" fill="currentColor" />
              </motion.button>
            </ClipGate>
          ) : null}
        </motion.div>

        <AnimatePresence>
          {phase >= 2 && phase < 4 ? (
            <motion.div
              className={styles.momentStrip}
              initial={{ opacity: 0, transform: "translate3d(0, 34px, 0)" }}
              animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
              exit={{ opacity: 0, transform: "translate3d(0, 18px, 0)" }}
              transition={{ duration: reduceMotion ? 0 : 0.48, ease: EASE }}
            >
              <p>
                <Sparkles aria-hidden="true" /> Three campaign moments
              </p>
              <MagneticCarousel
                items={MOMENTS}
                selectedIndex={selectedMoment}
                onSelect={setSelectedMoment}
                ariaLabel="Campaign moment candidates"
                collapsedWidth={52}
                hoverWidth={104}
                selectedWidth={178}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>

        {complete ? (
          <motion.aside
            className={styles.resultReason}
            initial={{ opacity: 0, transform: "translate3d(24px, 0, 0)" }}
            animate={{ opacity: 1, transform: "translate3d(0, 0, 0)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.5,
              ease: EASE,
              delay: reduceMotion ? 0 : 0.18,
            }}
          >
            <span>
              <Check aria-hidden="true" /> Verified against source
            </span>
            <strong>The proof · 89</strong>
            <p>The product is visible while the founder names the result.</p>
            <ClipGate>
              <button type="button" className={styles.unlockButton}>
                <LockKeyhole aria-hidden="true" />
                Watch the full cut
              </button>
            </ClipGate>
          </motion.aside>
        ) : null}

        <div
          className={styles.milestoneTrack}
          role="progressbar"
          aria-label="Clip processing progress"
          aria-valuemin={1}
          aria-valuemax={events.length}
          aria-valuenow={phase + 1}
          aria-valuetext={current.label}
        >
          <span className={styles.milestoneLine} aria-hidden="true">
            <i
              style={{ transform: `scaleX(${phase / (events.length - 1)})` }}
            />
          </span>
          {events.map((event, index) => (
            <span
              key={event.short}
              className={styles.milestone}
              data-status={event.status}
              title={event.label}
            >
              <i aria-hidden="true" />
              <span>{index === phase || complete ? event.short : ""}</span>
            </span>
          ))}
        </div>
      </section>
    </main>
  );
}
