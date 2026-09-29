"use client";

import {
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Pause,
  Play,
  Scissors,
  Sparkles,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import * as React from "react";

import { DitherReveal } from "@/components/originkit/dither-reveal";

import styles from "./living-edit-space.module.css";

const CUTS = [
  {
    id: "constraint",
    label: "The constraint",
    time: "02:14",
    score: 92,
    frame: "/prototypes/founder-frame-1-v2.webp",
    transcript:
      "We stopped asking what could go viral and started with who had to believe us.",
    reason:
      "Opens on the founder's constraint, so the audience understands the tension before the claim.",
  },
  {
    id: "proof",
    label: "The proof",
    time: "09:32",
    score: 89,
    frame: "/prototypes/founder-frame-4-v2.webp",
    transcript:
      "Then the result is visible on screen. The proof arrives before the promise.",
    reason:
      "Pairs the product demonstration with the exact line that makes the campaign credible.",
  },
  {
    id: "payoff",
    label: "The payoff",
    time: "16:05",
    score: 86,
    frame: "/prototypes/founder-frame-6-v2.webp",
    transcript:
      "That is the moment the story earns its conclusion instead of forcing one.",
    reason:
      "Closes on the audience-specific decision and gives the edit a clear, earned landing.",
  },
] as const;

const WAVEFORM = [
  18, 31, 22, 47, 58, 29, 42, 66, 37, 52, 28, 73, 61, 35, 49, 24, 56, 78, 64,
  43, 32, 69, 52, 27, 39, 62, 81, 48, 33, 57, 71, 44, 29, 53, 76, 67, 41, 26,
  59, 84, 63, 36, 48, 72, 55, 31, 68, 79, 46, 28, 51, 74, 60, 38, 65, 82, 49,
  34, 58, 70, 45, 25, 54, 77, 62, 39, 50, 73, 56, 30, 67, 80,
];

type MobileView = "source" | "cut" | "why";

function formatTime(progress: number) {
  const totalSeconds = Math.round((progress / 100) * (18 * 60 + 42));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function RevealLine({
  children,
  delay,
  accent = false,
}: {
  children: React.ReactNode;
  delay: number;
  accent?: boolean;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <span className={styles.revealLine} data-accent={accent ? "" : undefined}>
      <motion.span
        className={styles.revealText}
        initial={reduceMotion ? false : { y: "108%" }}
        animate={{ y: 0 }}
        transition={{
          duration: reduceMotion ? 0 : 0.72,
          delay: reduceMotion ? 0 : delay + 0.18,
          ease: [0.23, 1, 0.32, 1],
        }}
      >
        {children}
      </motion.span>
      {!reduceMotion ? (
        <motion.span
          className={styles.revealBlock}
          aria-hidden="true"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: [0, 1, 1, 0] }}
          transition={{
            duration: 0.82,
            delay,
            times: [0, 0.35, 0.58, 1],
            ease: [0.77, 0, 0.175, 1],
          }}
        />
      ) : null}
    </span>
  );
}

export function LivingEditSpace() {
  const reduceMotion = useReducedMotion();
  const [selectedCut, setSelectedCut] = React.useState(0);
  const [scrub, setScrub] = React.useState(23);
  const [proofMode, setProofMode] = React.useState(false);
  const [proofPhase, setProofPhase] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [mobileView, setMobileView] = React.useState<MobileView>("source");
  const proofTimers = React.useRef<number[]>([]);
  const selected = CUTS[selectedCut];

  const clearProofTimers = React.useCallback(() => {
    proofTimers.current.forEach((timer) => window.clearTimeout(timer));
    proofTimers.current = [];
  }, []);

  React.useEffect(() => clearProofTimers, [clearProofTimers]);

  const selectCut = React.useCallback((index: number) => {
    setSelectedCut(index);
    setScrub([12, 51, 86][index]);
    setMobileView("cut");
  }, []);

  const startProof = React.useCallback(() => {
    clearProofTimers();
    setProofMode(true);
    setProofPhase(1);
    setIsPlaying(false);

    if (reduceMotion) {
      setProofPhase(3);
      setSelectedCut(1);
      setScrub(51);
      setMobileView("cut");
      return;
    }

    proofTimers.current = [
      window.setTimeout(() => setProofPhase(2), 560),
      window.setTimeout(() => {
        setSelectedCut(1);
        setScrub(51);
        setMobileView("cut");
      }, 1080),
      window.setTimeout(() => setProofPhase(3), 1580),
    ];
  }, [clearProofTimers, reduceMotion]);

  const leaveProof = () => {
    clearProofTimers();
    setProofMode(false);
    setProofPhase(0);
    setMobileView("source");
  };

  const moveCut = (direction: -1 | 1) => {
    const next = (selectedCut + direction + CUTS.length) % CUTS.length;
    selectCut(next);
  };

  const handleScrub = (event: React.ChangeEvent<HTMLInputElement>) => {
    clearProofTimers();
    setProofMode(true);
    setProofPhase(3);
    setScrub(Number(event.target.value));
  };

  const spring = reduceMotion
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 240, damping: 28, mass: 0.8 };

  return (
    <main
      id="main-content"
      className={styles.studio}
      data-proof={proofMode ? "" : undefined}
      data-phase={proofPhase}
    >
      <div className={styles.paperNoise} aria-hidden="true" />

      <motion.header
        className={styles.header}
        initial={reduceMotion ? false : { opacity: 0, y: -14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: reduceMotion ? 0 : 0.48,
          ease: [0.23, 1, 0.32, 1],
        }}
      >
        <Link className={styles.brand} href="/" aria-label="ClipFactory home">
          <span className={styles.brandGlyph} aria-hidden="true">
            <span />
            <span />
          </span>
          ClipFactory
        </Link>

        <div
          className={styles.sessionLabel}
          aria-label="Current example campaign"
        >
          <span className={styles.sessionDot} aria-hidden="true" />
          Founder proof <span>/</span> Product launch
        </div>

        <nav className={styles.headerActions} aria-label="Primary navigation">
          <Link className={styles.quietLink} href="/pricing">
            Pricing
          </Link>
          <Link className={styles.quietLink} href="/login">
            Sign in
          </Link>
          <Link className={styles.headerCta} href="/pricing">
            Start Starter <span>€29</span>
            <ArrowUpRight aria-hidden="true" size={15} strokeWidth={1.8} />
          </Link>
        </nav>
      </motion.header>

      <section className={styles.intro} aria-labelledby="living-edit-title">
        <p className={styles.eyebrow}>
          <Scissors size={13} aria-hidden="true" />
          Campaign-first clipping
        </p>
        <motion.h1
          id="living-edit-title"
          layout
          className={styles.headline}
          transition={spring}
        >
          <RevealLine delay={0.08}>Give it the campaign.</RevealLine>
          <RevealLine delay={0.18} accent>
            Get the clips that belong.
          </RevealLine>
        </motion.h1>
        <motion.p layout className={styles.subhead} transition={spring}>
          ClipFactory finds the distant moments, builds the vertical edit, and
          shows why it fits the audience.
        </motion.p>

        <div className={styles.introActions}>
          <motion.button
            className={styles.proofButton}
            type="button"
            onClick={proofMode ? leaveProof : startProof}
            whileTap={reduceMotion ? undefined : { scale: 0.97 }}
          >
            <span className={styles.proofButtonIcon} aria-hidden="true">
              {proofMode ? (
                <Pause size={15} fill="currentColor" />
              ) : (
                <Play size={14} fill="currentColor" />
              )}
            </span>
            {proofMode ? "Reset the proof" : "Watch the proof"}
          </motion.button>
          <span className={styles.proofHint}>
            18:42 source → 3 campaign cuts
          </span>
        </div>
      </section>

      <div
        className={styles.mobileTabs}
        role="tablist"
        aria-label="Studio view"
      >
        {(["source", "cut", "why"] as const).map((view) => (
          <button
            key={view}
            type="button"
            role="tab"
            aria-selected={mobileView === view}
            onClick={() => setMobileView(view)}
          >
            {view === "source" ? "Source" : view === "cut" ? "Cut" : "Why"}
          </button>
        ))}
      </div>

      <section
        className={styles.canvas}
        data-mobile-view={mobileView}
        aria-label="Interactive campaign edit"
      >
        <svg
          className={styles.connections}
          viewBox="0 0 1200 720"
          aria-hidden="true"
        >
          <motion.path
            d="M 395 525 C 600 620, 760 220, 1010 208"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{
              pathLength: proofPhase >= 1 ? 1 : 0,
              opacity: proofPhase >= 1 ? 0.62 : 0,
            }}
            transition={{
              duration: reduceMotion ? 0 : 0.72,
              ease: [0.23, 1, 0.32, 1],
            }}
          />
          <motion.path
            d="M 565 525 C 720 548, 805 360, 1034 353"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{
              pathLength: proofPhase >= 1 ? 1 : 0,
              opacity: proofPhase >= 1 ? 0.82 : 0,
            }}
            transition={{
              duration: reduceMotion ? 0 : 0.72,
              delay: reduceMotion ? 0 : 0.08,
              ease: [0.23, 1, 0.32, 1],
            }}
          />
          <motion.path
            d="M 718 525 C 810 500, 880 455, 1015 494"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{
              pathLength: proofPhase >= 1 ? 1 : 0,
              opacity: proofPhase >= 1 ? 0.58 : 0,
            }}
            transition={{
              duration: reduceMotion ? 0 : 0.72,
              delay: reduceMotion ? 0 : 0.16,
              ease: [0.23, 1, 0.32, 1],
            }}
          />
        </svg>

        <motion.article
          className={styles.sourceCard}
          data-panel="source"
          animate={
            proofMode && !reduceMotion
              ? { x: -18, y: -8, rotate: -0.7, scale: 0.965 }
              : { x: 0, y: 0, rotate: 0, scale: 1 }
          }
          transition={spring}
        >
          <div className={styles.sourceTopbar}>
            <span className={styles.sourceIdentity}>
              <span className={styles.recordDot} aria-hidden="true" />
              Interview_master.mov
            </span>
            <span>16:9 / 18:42</span>
          </div>

          <div className={styles.sourceMedia}>
            <DitherReveal
              image="/prototypes/founder-frame-1-v2.webp"
              alt="A founder explaining a product during a filmed studio interview."
              revealRadius={150}
            />
            <div className={styles.sourceShade} aria-hidden="true" />
            <div className={styles.frameCrop} aria-hidden="true">
              <span>9:16</span>
            </div>
            <div className={styles.timecode}>{formatTime(scrub)}</div>
            <button
              className={styles.playControl}
              type="button"
              aria-label={
                isPlaying ? "Pause example source" : "Play example source"
              }
              onClick={() => setIsPlaying((value) => !value)}
            >
              {isPlaying ? (
                <Pause size={15} fill="currentColor" />
              ) : (
                <Play size={15} fill="currentColor" />
              )}
            </button>
          </div>

          <div className={styles.briefRail} aria-label="Campaign brief">
            <span className={styles.briefLabel}>Brief</span>
            <span>
              <b>Audience</b> Solo founders
            </span>
            <span>
              <b>Goal</b> Credible launch
            </span>
            <span>
              <b>Avoid</b> Empty hype
            </span>
          </div>
        </motion.article>

        <aside
          className={styles.outputArea}
          data-panel="cut"
          aria-label="Candidate clips"
        >
          <div className={styles.outputHeading}>
            <span>Campaign cuts</span>
            <span>
              {selectedCut + 1} / {CUTS.length}
            </span>
          </div>

          <div className={styles.clipStack}>
            {CUTS.map((cut, index) => {
              const distance = index - selectedCut;
              const isSelected = index === selectedCut;
              return (
                <motion.button
                  key={cut.id}
                  className={styles.clipCard}
                  type="button"
                  aria-label={`Select ${cut.label}, campaign fit ${cut.score}`}
                  aria-pressed={isSelected}
                  drag={reduceMotion ? false : true}
                  dragConstraints={{
                    left: -24,
                    right: 24,
                    top: -18,
                    bottom: 18,
                  }}
                  dragElastic={0.08}
                  dragSnapToOrigin
                  onClick={() => selectCut(index)}
                  animate={{
                    x: distance * (proofMode ? 13 : 19),
                    y: distance * (proofMode ? 12 : 17),
                    rotate: distance * (proofMode ? 2.6 : 5.4),
                    scale: isSelected
                      ? 1
                      : Math.max(0.86, 0.93 - Math.abs(distance) * 0.02),
                    opacity: Math.abs(distance) > 1 ? 0.72 : 1,
                    zIndex: isSelected ? 5 : 3 - Math.abs(distance),
                  }}
                  whileHover={
                    reduceMotion ? undefined : { y: distance * 12 - 5 }
                  }
                  whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                  transition={spring}
                >
                  <Image
                    src={cut.frame}
                    alt=""
                    fill
                    sizes="(max-width: 720px) 54vw, 15vw"
                    className={styles.clipImage}
                  />
                  <span className={styles.clipVignette} aria-hidden="true" />
                  <span className={styles.clipMeta}>
                    <span>{cut.time}</span>
                    <span>{cut.label}</span>
                  </span>
                  <span className={styles.clipFit}>
                    <Check size={11} aria-hidden="true" /> Fit {cut.score}
                  </span>
                </motion.button>
              );
            })}
          </div>

          <div className={styles.clipControls}>
            <button
              type="button"
              onClick={() => moveCut(-1)}
              aria-label="Previous clip"
            >
              <ChevronLeft size={16} />
            </button>
            <span>{selected.label}</span>
            <button
              type="button"
              onClick={() => moveCut(1)}
              aria-label="Next clip"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </aside>

        <aside className={styles.inspector} data-panel="why" aria-live="polite">
          <div className={styles.inspectorHeader}>
            <span>
              <Sparkles size={13} aria-hidden="true" /> Why it belongs
            </span>
            <span>Campaign fit {selected.score}</span>
          </div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={selected.id}
              className={styles.inspectorBody}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
              transition={{
                duration: reduceMotion ? 0 : 0.18,
                ease: [0.23, 1, 0.32, 1],
              }}
            >
              <p className={styles.transcript}>“{selected.transcript}”</p>
              <p className={styles.reason}>{selected.reason}</p>
            </motion.div>
          </AnimatePresence>
        </aside>

        <AnimatePresence>
          {proofPhase === 2 && !reduceMotion
            ? CUTS.map((cut, index) => (
                <motion.div
                  key={`fragment-${cut.id}`}
                  className={styles.assemblingFragment}
                  style={{ left: `${34 + index * 14}%` }}
                  initial={{ opacity: 0, x: 0, y: 0, scale: 0.9 }}
                  animate={{
                    opacity: [0, 1, 1, 0],
                    x: [0, `${22 - index * 3}vw`],
                    y: [0, `${-17 + index * 2}vh`],
                    scale: [0.9, 1, 0.94, 0.86],
                  }}
                  exit={{ opacity: 0 }}
                  transition={{
                    duration: 0.62,
                    delay: index * 0.06,
                    ease: [0.77, 0, 0.175, 1],
                  }}
                  aria-hidden="true"
                >
                  <Image src={cut.frame} alt="" fill sizes="100px" />
                </motion.div>
              ))
            : null}
        </AnimatePresence>

        <div className={styles.timeline} aria-label="Source timeline">
          <div className={styles.timelineTopline}>
            <span>Source tape</span>
            <span>{formatTime(scrub)} / 18:42</span>
          </div>
          <div className={styles.waveform} aria-hidden="true">
            {WAVEFORM.map((height, index) => (
              <span key={index} style={{ height: `${height}%` }} />
            ))}
          </div>
          <div className={styles.momentButtons}>
            {CUTS.map((cut, index) => (
              <button
                key={cut.id}
                type="button"
                className={styles.momentButton}
                data-selected={selectedCut === index ? "" : undefined}
                style={{ left: `${[12, 51, 86][index]}%` }}
                onClick={() => selectCut(index)}
                aria-label={`Jump to ${cut.label} at ${cut.time}`}
              >
                <span>{index + 1}</span>
              </button>
            ))}
          </div>
          <input
            className={styles.scrubber}
            type="range"
            min="0"
            max="100"
            value={scrub}
            aria-label="Scrub through the example source"
            onChange={handleScrub}
            style={{ "--scrub": `${scrub}%` } as React.CSSProperties}
          />
          <span
            className={styles.playhead}
            style={{ left: `${scrub}%` }}
            aria-hidden="true"
          />
        </div>

        <div className={styles.canvasLegend} aria-hidden="true">
          Drag a cut · Scrub the source · Select a moment
        </div>
      </section>
    </main>
  );
}
