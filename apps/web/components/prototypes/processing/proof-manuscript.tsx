"use client";

import Image from "next/image";
import { Check, Play } from "lucide-react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { ClipGate } from "./clip-gate";
import {
  type ProcessingPreviewState,
  useProcessingSequence,
} from "./processing-sequence";
import styles from "./proof-manuscript.module.css";

const EASE_OUT = [0.22, 1, 0.36, 1] as const;
const PROOF_WORDS = [
  "The",
  "screen",
  "already",
  "showed",
  "the",
  "proof.",
] as const;
const LONG_PROOF_WORDS = [
  "The",
  "full",
  "walkthrough",
  "had",
  "already",
  "shown",
  "the",
  "exact",
  "result",
  "on",
  "screen.",
] as const;

function ClipFrame({
  phase,
  reduceMotion,
}: {
  phase: number;
  reduceMotion: boolean;
}) {
  const frame = Math.max(3, Math.min(6, phase + 1));

  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div
        key={frame}
        className={styles.clipImage}
        initial={{ opacity: 0, scale: 1.035 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={reduceMotion ? undefined : { opacity: 0, scale: 0.985 }}
        transition={{ duration: reduceMotion ? 0 : 0.42, ease: EASE_OUT }}
      >
        <Image
          src={`/prototypes/founder-frame-${frame}-v2.webp`}
          alt="Founder interview reframed as the selected vertical clip"
          fill
          priority
          sizes="(max-width: 640px) 72vw, 30vw"
        />
      </motion.div>
    </AnimatePresence>
  );
}

export function ProofManuscript({
  previewState = "auto",
}: {
  previewState?: ProcessingPreviewState;
}) {
  const { phase, complete, current, reduceMotion, isLong, isLoading } =
    useProcessingSequence(previewState);
  const transcriptReady = phase >= 1;
  const proofFound = phase >= 2;
  const extracted = phase >= 3;
  const composed = phase >= 4;
  const verified = phase >= 5;
  const milestoneProgress = phase / 6;
  const proofWords = isLong ? LONG_PROOF_WORDS : PROOF_WORDS;
  const proofSentence = isLong
    ? "The full walkthrough had already shown the exact result on screen."
    : "The screen already showed the proof.";
  const captionCopy = isLong
    ? "The walkthrough proves the exact result on screen before the founder finishes explaining the launch promise."
    : "The proof arrives before the promise.";
  const pageTitle = isLoading
    ? "Preparing your source transcript"
    : complete
      ? isLong
        ? "Your long-form campaign proof is ready"
        : "Your first campaign cut is ready"
      : `Building your first campaign cut — ${current.label}`;

  return (
    <main
      id="main-content"
      className={styles.proof}
      data-complete={complete || undefined}
      data-extracted={extracted || undefined}
      data-long={isLong || undefined}
      aria-busy={isLoading || undefined}
    >
      <motion.div
        className={styles.sourceBackdrop}
        initial={{ opacity: 0, scale: 1.035 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduceMotion ? 0 : 1.1, ease: EASE_OUT }}
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
      <div className={styles.inkWash} aria-hidden="true" />
      <motion.div
        className={styles.blueLight}
        animate={{
          opacity: proofFound ? (complete ? 0.34 : 0.2) : 0.06,
          scale: proofFound ? 1 : 0.82,
        }}
        transition={{ duration: reduceMotion ? 0 : 0.7, ease: EASE_OUT }}
        aria-hidden="true"
      />

      <header className={styles.folioHeader}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <strong>ClipFactory</strong>
        </div>
        <p className={styles.documentName}>
          {isLong
            ? "Campaign proof · exact founder language for the launch story and its visible product result"
            : "Campaign proof · working transcript"}
        </p>
        <p className={styles.sourceTime}>
          <span
            title={
              isLong
                ? "Interview_master_product_walkthrough_final_07.mov"
                : "Interview_master.mov"
            }
          >
            {isLong
              ? "Interview_master_product_walkthrough_final_07.mov"
              : "Interview_master.mov"}
          </span>
          <time>09:32</time>
        </p>
      </header>

      <LayoutGroup id="proof-manuscript">
        <motion.section
          className={styles.manuscript}
          animate={{
            opacity: complete ? 0.72 : 1,
          }}
          transition={{ duration: reduceMotion ? 0 : 0.62, ease: EASE_OUT }}
          aria-label="Source transcript"
        >
          <motion.h1
            className={styles.kicker}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.46, ease: EASE_OUT }}
          >
            {pageTitle}
          </motion.h1>

          <blockquote className={styles.transcript}>
            <motion.span
              className={styles.sentence}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: transcriptReady ? 1 : 0.48, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.52, ease: EASE_OUT }}
            >
              {isLong
                ? "We had spent the launch explaining every promise before showing the product. "
                : "We stopped leading with the promise. "}
            </motion.span>

            {!extracted ? (
              <motion.span
                layoutId="proof-passage"
                className={styles.proofPassage}
                data-found={proofFound || undefined}
                transition={{
                  layout: reduceMotion
                    ? { duration: 0 }
                    : {
                        type: "spring",
                        stiffness: 210,
                        damping: 28,
                        mass: 0.82,
                      },
                }}
              >
                {proofWords.map((word, index) => (
                  <motion.span
                    key={`${word}-${index}`}
                    initial={{ opacity: 0.28, y: 10 }}
                    animate={{
                      opacity: transcriptReady ? 1 : 0.34,
                      y: 0,
                    }}
                    transition={{
                      duration: reduceMotion ? 0 : 0.34,
                      delay: reduceMotion ? 0 : index * 0.045,
                      ease: EASE_OUT,
                    }}
                  >
                    {word}
                    {index < proofWords.length - 1 ? " " : ""}
                  </motion.span>
                ))}
              </motion.span>
            ) : (
              <span className={styles.passageGhost} aria-hidden="true">
                {proofSentence}{" "}
              </span>
            )}

            <motion.span
              className={styles.sentence}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: transcriptReady ? 1 : 0.3, y: 0 }}
              transition={{
                duration: reduceMotion ? 0 : 0.52,
                delay: reduceMotion ? 0 : 0.12,
                ease: EASE_OUT,
              }}
            >
              {isLong
                ? " Once the audience could see the workflow and the outcome together, the rest of the explanation became unnecessary."
                : " Once the product was visible, the result needed no explanation."}
            </motion.span>
          </blockquote>

          <AnimatePresence>
            {proofFound && !extracted ? (
              <motion.div
                className={styles.wordAnchor}
                initial={{ opacity: 0, scaleX: 0.7, y: 8 }}
                animate={{ opacity: 1, scaleX: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{
                  duration: reduceMotion ? 0 : 0.42,
                  ease: EASE_OUT,
                }}
              >
                <span>09:32.08—09:36.21</span>
                <strong>{proofWords.length} timed source words</strong>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <motion.p
            className={styles.marginNote}
            animate={{ opacity: proofFound ? 1 : 0.18 }}
            transition={{ duration: reduceMotion ? 0 : 0.42 }}
          >
            {isLong
              ? "The launch brief asks for a visible workflow, a named outcome and the founder’s exact language in one cut."
              : "Campaign asks for visible proof before the promise."}
          </motion.p>
        </motion.section>

        <AnimatePresence>
          {extracted ? (
            <motion.figure
              layoutId="proof-passage"
              layout
              className={styles.verticalClip}
              initial={{ opacity: 0.2 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{
                opacity: { duration: reduceMotion ? 0 : 0.28 },
                layout: reduceMotion
                  ? { duration: 0 }
                  : {
                      type: "spring",
                      stiffness: 190,
                      damping: 27,
                      mass: 0.9,
                    },
              }}
            >
              <ClipFrame phase={phase} reduceMotion={reduceMotion} />
              <div className={styles.clipShade} aria-hidden="true" />
              <div className={styles.clipChrome}>
                <span>9:16 · source frame</span>
                <span>09:32</span>
              </div>

              <AnimatePresence>
                {composed ? (
                  <motion.figcaption
                    className={styles.caption}
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: reduceMotion ? 0 : 0.48,
                      ease: EASE_OUT,
                    }}
                  >
                    {captionCopy}
                  </motion.figcaption>
                ) : null}
              </AnimatePresence>

              <AnimatePresence>
                {verified ? (
                  <motion.div
                    className={styles.verification}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: reduceMotion ? 0 : 0.4,
                      ease: EASE_OUT,
                    }}
                  >
                    <Check aria-hidden="true" />
                    <span>Matched to transcript</span>
                  </motion.div>
                ) : null}
              </AnimatePresence>

              {complete ? (
                <ClipGate>
                  <motion.button
                    type="button"
                    className={styles.clipPlay}
                    initial={{ opacity: 0, scale: 0.94 }}
                    animate={{ opacity: 1, scale: 1 }}
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
            </motion.figure>
          ) : null}
        </AnimatePresence>
      </LayoutGroup>

      <AnimatePresence>
        {extracted ? (
          <>
            <motion.div
              key="proof-thread-desktop"
              className={`${styles.proofThread} ${styles.proofThreadDesktop}`}
              initial={{ opacity: 0, transform: "scaleX(0)" }}
              animate={{
                opacity: complete ? 0.28 : 0.82,
                transform: "scaleX(1)",
              }}
              exit={{ opacity: 0, transform: "scaleX(0)" }}
              transition={{ duration: reduceMotion ? 0 : 0.66, ease: EASE_OUT }}
              aria-hidden="true"
            />
            <motion.div
              key="proof-thread-mobile"
              className={`${styles.proofThread} ${styles.proofThreadMobile}`}
              initial={{ opacity: 0, transform: "scaleY(0)" }}
              animate={{
                opacity: complete ? 0.28 : 0.82,
                transform: "scaleY(1)",
              }}
              exit={{ opacity: 0, transform: "scaleY(0)" }}
              transition={{ duration: reduceMotion ? 0 : 0.66, ease: EASE_OUT }}
              aria-hidden="true"
            />
          </>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {complete ? (
          <motion.div
            className={styles.readyCue}
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.58, ease: EASE_OUT }}
            aria-live="polite"
          >
            <span>First cut</span>
            <strong>13 seconds. Ready to watch.</strong>
            <Play aria-hidden="true" fill="currentColor" />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <footer className={styles.processingFooter}>
        <div className={styles.phaseCopy} aria-live="polite">
          <span>{String(Math.min(phase + 1, 7)).padStart(2, "0")} / 07</span>
          <p>
            <strong>{isLoading ? "Preparing source" : current.label}</strong>
            <small>
              {isLoading
                ? "Reading frames and campaign context before anchoring words."
                : current.detail}
            </small>
          </p>
        </div>
        <div
          className={styles.progressTrack}
          role="progressbar"
          aria-label="Clip processing milestones"
          aria-valuemin={1}
          aria-valuemax={7}
          aria-valuenow={phase + 1}
          aria-valuetext={`${current.label}, milestone ${phase + 1} of 7`}
        >
          <motion.span
            initial={false}
            animate={{ scaleX: milestoneProgress }}
            transition={{ duration: reduceMotion ? 0 : 0.55, ease: EASE_OUT }}
          />
        </div>
        <span className={styles.footerSource}>18:42 source · words locked</span>
      </footer>
    </main>
  );
}
