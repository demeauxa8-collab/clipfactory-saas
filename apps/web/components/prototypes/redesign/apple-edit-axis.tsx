"use client";

import { ArrowUpRight, ChevronRight } from "lucide-react";
import {
  AnimatePresence,
  animate,
  motion,
  type MotionValue,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import Image from "next/image";
import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import * as React from "react";

import { CampaignLensShader } from "./campaign-lens-shader";
import { EditAxisStory } from "./edit-axis-story";
import styles from "./apple-edit-axis.module.css";

const SOURCE_DURATION_SECONDS = 18 * 60 + 42;

const MOMENTS = [
  {
    id: "tension",
    label: "The tension",
    atSeconds: 2 * 60 + 14,
    score: 92,
    frame: "/prototypes/founder-frame-1-v2.webp",
    quote: "We stopped asking what could go viral.",
    reason:
      "The constraint arrives before the claim, giving the campaign a reason to keep watching.",
    breakdown: [
      ["Hook", 94],
      ["Campaign fit", 92],
      ["Visual proof", 86],
    ],
  },
  {
    id: "proof",
    label: "The proof",
    atSeconds: 9 * 60 + 32,
    score: 89,
    frame: "/prototypes/founder-frame-4-v2.webp",
    quote: "The proof arrives before the promise.",
    reason:
      "The product is visible while the founder names the result. Picture and claim reinforce each other.",
    breakdown: [
      ["Hook", 88],
      ["Campaign fit", 91],
      ["Visual proof", 96],
    ],
  },
  {
    id: "payoff",
    label: "The payoff",
    atSeconds: 16 * 60 + 5,
    score: 86,
    frame: "/prototypes/founder-frame-6-v2.webp",
    quote: "The story earns its conclusion.",
    reason:
      "The final decision resolves the opening constraint instead of ending on an isolated sound bite.",
    breakdown: [
      ["Hook", 82],
      ["Campaign fit", 90],
      ["Visual proof", 84],
    ],
  },
] as const;

const SOURCE_FRAMES = [
  "/prototypes/founder-frame-1-v2.webp",
  "/prototypes/founder-frame-2-v2.webp",
  "/prototypes/founder-frame-3-v2.webp",
  "/prototypes/founder-frame-4-v2.webp",
  "/prototypes/founder-frame-5-v2.webp",
  "/prototypes/founder-frame-6-v2.webp",
] as const;

const TICKS = Array.from({ length: 61 }, (_, index) => index);
const TIMELINE_CELL_COUNT = 12;

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.min(maximum, Math.max(minimum, value));
}

function progressForSeconds(seconds: number) {
  return seconds / SOURCE_DURATION_SECONDS;
}

// The aperture and filmstrip must sample the same temporal buckets. The strip
// has two cells per source frame, so each cell samples its own midpoint.
function frameIndexForProgress(progress: number) {
  return Math.min(
    SOURCE_FRAMES.length - 1,
    Math.floor(clamp(progress) * SOURCE_FRAMES.length),
  );
}

function frameForTimelineCell(index: number, cellCount: number) {
  return SOURCE_FRAMES[
    frameIndexForProgress((index + 0.5) / Math.max(1, cellCount))
  ];
}

function formatTimeFromProgress(progress: number) {
  const seconds = Math.round(clamp(progress) * SOURCE_DURATION_SECONDS);
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function nearestMoment(progress: number) {
  return MOMENTS.reduce(
    (best, moment, index) =>
      Math.abs(progressForSeconds(moment.atSeconds) - progress) <
      Math.abs(progressForSeconds(MOMENTS[best].atSeconds) - progress)
        ? index
        : best,
    0,
  );
}

function BrandMark() {
  return (
    <span className={styles.brandMark} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

type TimelineProps = {
  progress: MotionValue<number>;
  activeMoment: number;
  activeFrame: number;
  axisX: number;
  timelineScale: number;
  inset: number;
  isScrubbing: boolean;
  onPointerDown: (event: React.PointerEvent<HTMLDivElement>) => void;
  onPointerMove: (event: React.PointerEvent<HTMLDivElement>) => void;
  onPointerEnd: (event: React.PointerEvent<HTMLDivElement>) => void;
  onSelectMoment: (index: number, immediate: boolean) => void;
  onKeyboardProgress: (progress: number) => void;
};

function SourceTimeline({
  progress,
  activeMoment,
  activeFrame,
  axisX,
  timelineScale,
  inset,
  isScrubbing,
  onPointerDown,
  onPointerMove,
  onPointerEnd,
  onSelectMoment,
  onKeyboardProgress,
}: TimelineProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const timeRef = React.useRef<HTMLSpanElement>(null);
  const [hasFocus, setHasFocus] = React.useState(false);
  // The dock contributes a 1px border and the 1px playhead is centered on its
  // own box. Subtracting both half-pixels keeps the visual axis identical to
  // the aperture center instead of landing 1.5 CSS pixels to its right.
  const localAxis = axisX - inset - 1.5;
  const stripTransform = useTransform(progress, (latest) => {
    const left = localAxis - latest * timelineScale;
    return `translate3d(${left}px, 0, 0)`;
  });

  React.useEffect(() => {
    const sync = (latest: number) => {
      if (inputRef.current) {
        inputRef.current.value = String(Math.round(clamp(latest) * 10000));
        inputRef.current.setAttribute(
          "aria-valuetext",
          `${formatTimeFromProgress(latest)}, nearest campaign moment ${MOMENTS[nearestMoment(latest)].label}`,
        );
      }
      if (timeRef.current) {
        timeRef.current.textContent = formatTimeFromProgress(latest);
      }
    };
    sync(progress.get());
    return progress.on("change", sync);
  }, [progress]);

  return (
    <div
      className={styles.timelineDock}
      data-scrubbing={isScrubbing ? "" : undefined}
    >
      <div className={styles.timelineMeta}>
        <span>Interview_master.mov</span>
        <span>18:42 · source</span>
      </div>

      <div
        className={styles.timelineViewport}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
      >
        <motion.div
          className={styles.sourceStrip}
          style={{ width: timelineScale, transform: stripTransform }}
        >
          <div className={styles.frameStrip} aria-hidden="true">
            {Array.from({ length: TIMELINE_CELL_COUNT }, (_, index) => (
              <span key={index}>
                <Image
                  src={frameForTimelineCell(index, TIMELINE_CELL_COUNT)}
                  alt=""
                  fill
                  unoptimized
                  fetchPriority="low"
                  sizes="120px"
                />
              </span>
            ))}
          </div>

          <div className={styles.tickStrip} aria-hidden="true">
            {TICKS.map((tick) => (
              <span
                key={tick}
                className={styles.timelineTick}
                data-major={tick % 10 === 0 ? "" : undefined}
                style={{ left: `${(tick / (TICKS.length - 1)) * 100}%` }}
              />
            ))}
          </div>

          {MOMENTS.map((moment, index) => (
            <button
              key={moment.id}
              type="button"
              className={styles.timelineMoment}
              data-active={activeMoment === index ? "" : undefined}
              aria-pressed={activeMoment === index}
              style={{ left: `${progressForSeconds(moment.atSeconds) * 100}%` }}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => onSelectMoment(index, event.detail === 0)}
            >
              <span />
              <small>{moment.label}</small>
            </button>
          ))}
        </motion.div>

        <div
          className={styles.opticalPlayhead}
          data-focus={hasFocus ? "" : undefined}
          style={{ left: localAxis }}
          aria-hidden="true"
        >
          <span ref={timeRef}>{formatTimeFromProgress(progress.get())}</span>
          <i />
        </div>

        <input
          ref={inputRef}
          className={styles.keyboardRange}
          type="range"
          min="0"
          max="10000"
          step="1"
          defaultValue={Math.round(progress.get() * 10000)}
          aria-label="Move through the source video"
          aria-valuetext={`${formatTimeFromProgress(progress.get())}, nearest campaign moment ${MOMENTS[activeMoment].label}`}
          style={{ left: localAxis }}
          onFocus={() => setHasFocus(true)}
          onBlur={() => setHasFocus(false)}
          onChange={(event) =>
            onKeyboardProgress(Number(event.currentTarget.value) / 10000)
          }
        />
      </div>

      <div className={styles.timelineFooter}>
        <span>Drag the source under the playhead</span>
        <span>
          Frame {activeFrame + 1} / {SOURCE_FRAMES.length}
        </span>
      </div>
    </div>
  );
}

export function AppleEditAxis() {
  const reduceMotion = useReducedMotion();
  const pathname = usePathname();
  const isPreview = pathname.startsWith("/preview/");
  const signInHref = "/login" as Route;
  const startHref = (
    isPreview
      ? "/preview/journey?screen=login"
      : "/login?next=/app/campaigns/new"
  ) as Route;
  const brandHref = (
    isPreview ? "/preview/redesign?v=6&clean=1" : "/"
  ) as Route;
  const heroRef = React.useRef<HTMLElement>(null);
  const stageRef = React.useRef<HTMLDivElement>(null);
  const timecodeRef = React.useRef<HTMLSpanElement>(null);
  const dragRef = React.useRef({
    pointerId: -1,
    originX: 0,
    originProgress: 0,
    lastX: 0,
    lastAt: 0,
    velocity: 0,
  });
  const progressAnimationRef = React.useRef<{ stop: () => void } | null>(null);
  const activeMomentRef = React.useRef(1);
  const activeFrameRef = React.useRef(3);
  const [stageSize, setStageSize] = React.useState({
    width: 1440,
    height: 900,
  });
  const [activeMoment, setActiveMoment] = React.useState(1);
  const [activeFrame, setActiveFrame] = React.useState(3);
  const [isScrubbing, setIsScrubbing] = React.useState(false);
  const [hasInteracted, setHasInteracted] = React.useState(false);
  const sourceProgress = useMotionValue(
    progressForSeconds(MOMENTS[1].atSeconds),
  );
  const apertureSpatialProgress = useMotionValue(0.68);

  const mobile = stageSize.width < 760;
  const apertureMargin = mobile ? 12 : 28;
  const heightByViewport = stageSize.height * (mobile ? 0.39 : 0.64);
  const apertureHeight = Math.max(
    mobile ? 286 : 430,
    Math.min(
      heightByViewport,
      mobile ? 338 : 660,
      Math.max(2, stageSize.width - apertureMargin * 2) / (9 / 16),
    ),
  );
  const apertureWidth = apertureHeight * (9 / 16);
  const desiredAxis = stageSize.width * (mobile ? 0.5 : 0.69);
  const apertureLeft = clamp(
    desiredAxis - apertureWidth / 2,
    apertureMargin,
    Math.max(apertureMargin, stageSize.width - apertureWidth - apertureMargin),
  );
  const axisX = apertureLeft + apertureWidth / 2;
  const apertureCenterYRatio = mobile ? 0.55 : 0.43;
  const apertureCenterY = stageSize.height * apertureCenterYRatio;
  const timelineInset = mobile ? 8 : 22;
  const timelineScale = mobile
    ? Math.max(stageSize.width * 1.35, 480)
    : Math.min(stageSize.width * 0.9, 1280);
  const reasonOnRight = axisX + apertureWidth / 2 + 248 < stageSize.width;
  const reasonLeft = reasonOnRight
    ? apertureLeft + apertureWidth + 16
    : apertureLeft - 232;

  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const stageTransform = useTransform(
    scrollYProgress,
    [0, 1],
    [
      "translate3d(0,0,0) scale(1)",
      reduceMotion
        ? "translate3d(0,0,0) scale(1)"
        : "translate3d(0,64px,0) scale(.975)",
    ],
  );
  const stageOpacity = useTransform(scrollYProgress, [0, 0.92], [1, 0.68]);

  React.useLayoutEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const update = () =>
      setStageSize({ width: stage.clientWidth, height: stage.clientHeight });
    const observer = new ResizeObserver(update);
    observer.observe(stage);
    update();
    return () => observer.disconnect();
  }, []);

  React.useLayoutEffect(() => {
    const minimumCenter = apertureMargin + apertureWidth / 2;
    const maximumCenter = Math.max(
      minimumCenter,
      stageSize.width - apertureMargin - apertureWidth / 2,
    );
    const travel = Math.max(1, maximumCenter - minimumCenter);
    apertureSpatialProgress.set(clamp((axisX - minimumCenter) / travel));
  }, [
    apertureMargin,
    apertureSpatialProgress,
    apertureWidth,
    axisX,
    stageSize.width,
  ]);

  React.useEffect(() => {
    const sync = (latest: number) => {
      if (timecodeRef.current) {
        timecodeRef.current.textContent = formatTimeFromProgress(latest);
      }

      const nextMoment = nearestMoment(latest);
      if (nextMoment !== activeMomentRef.current) {
        activeMomentRef.current = nextMoment;
        setActiveMoment(nextMoment);
      }

      const nextFrame = frameIndexForProgress(latest);
      if (nextFrame !== activeFrameRef.current) {
        activeFrameRef.current = nextFrame;
        setActiveFrame(nextFrame);
      }
    };

    sync(sourceProgress.get());
    return sourceProgress.on("change", sync);
  }, [sourceProgress]);

  const setProgress = React.useCallback(
    (next: number) => sourceProgress.set(clamp(next)),
    [sourceProgress],
  );

  const animateTo = React.useCallback(
    (destination: number, velocity = 0, immediate = false) => {
      progressAnimationRef.current?.stop();
      if (immediate || reduceMotion) {
        setProgress(destination);
        return;
      }
      progressAnimationRef.current = animate(
        sourceProgress,
        clamp(destination),
        {
          type: "spring",
          stiffness: 420,
          damping: 42,
          mass: 0.74,
          velocity,
        },
      );
    },
    [reduceMotion, setProgress, sourceProgress],
  );

  const selectMoment = React.useCallback(
    (index: number, immediate = false) => {
      animateTo(progressForSeconds(MOMENTS[index].atSeconds), 0, immediate);
    },
    [animateTo],
  );

  const handlePointerDown = React.useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0 && event.pointerType === "mouse") return;
      if (dragRef.current.pointerId !== -1) return;
      progressAnimationRef.current?.stop();
      const now = performance.now();
      dragRef.current = {
        pointerId: event.pointerId,
        originX: event.clientX,
        originProgress: sourceProgress.get(),
        lastX: event.clientX,
        lastAt: now,
        velocity: 0,
      };
      event.currentTarget.setPointerCapture(event.pointerId);
      setIsScrubbing(true);
      setHasInteracted(true);
    },
    [sourceProgress],
  );

  const handlePointerMove = React.useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (dragRef.current.pointerId !== event.pointerId) return;
      const delta = event.clientX - dragRef.current.originX;
      const next = dragRef.current.originProgress - delta / timelineScale;
      const now = performance.now();
      const elapsed = Math.max(8, now - dragRef.current.lastAt);
      dragRef.current.velocity =
        -((event.clientX - dragRef.current.lastX) / elapsed) *
        (1000 / timelineScale);
      dragRef.current.lastX = event.clientX;
      dragRef.current.lastAt = now;
      setProgress(next);
    },
    [setProgress, timelineScale],
  );

  const handlePointerEnd = React.useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (dragRef.current.pointerId !== event.pointerId) return;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }

      const velocity = dragRef.current.velocity;
      const projected = clamp(sourceProgress.get() + velocity * 0.18);
      const candidate = nearestMoment(projected);
      const candidateProgress = progressForSeconds(
        MOMENTS[candidate].atSeconds,
      );
      const destination =
        Math.abs(candidateProgress - projected) < 0.085
          ? candidateProgress
          : projected;

      dragRef.current.pointerId = -1;
      setIsScrubbing(false);
      animateTo(destination, velocity);
    },
    [animateTo, sourceProgress],
  );

  const handleKeyboardProgress = React.useCallback(
    (progress: number) => {
      progressAnimationRef.current?.stop();
      setProgress(progress);
    },
    [setProgress],
  );

  const active = MOMENTS[activeMoment];

  return (
    <main id="main-content" className={styles.page}>
      <section
        ref={heroRef}
        className={styles.hero}
        aria-labelledby="edit-axis-title"
      >
        <motion.div
          ref={stageRef}
          className={styles.heroStage}
          style={{ transform: stageTransform, opacity: stageOpacity }}
        >
          <CampaignLensShader
            imageSrc="/prototypes/cinematic-source-v1.webp"
            alt="A founder speaking during a filmed studio interview."
            lensProgress={apertureSpatialProgress}
            lensHeightPx={apertureHeight}
            lensWidthPx={apertureWidth}
            lensSideMarginPx={apertureMargin}
            lensCenterYRatio={apertureCenterYRatio}
            lensRadiusPx={mobile ? 24 : 31}
            priority
            className={styles.heroShader}
          />
          <div className={styles.heroShade} aria-hidden="true" />

          <motion.header
            className={styles.header}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(0,-10px,0)" }
            }
            animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.48,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <Link
              className={styles.brand}
              href={brandHref}
              aria-label="ClipFactory home"
            >
              <BrandMark /> <span>ClipFactory</span>
            </Link>
            <nav className={styles.primaryNav} aria-label="Primary navigation">
              <a href="#story">How it works</a>
              <a href="#campaign-v6">Features</a>
              <a href="#pricing">Pricing</a>
            </nav>
            <div className={styles.headerActions}>
              <Link className={styles.signIn} href={signInHref}>
                Sign in
              </Link>
              <Link className={styles.navCta} href={startHref}>
                Start a campaign <ArrowUpRight aria-hidden="true" />
              </Link>
            </div>
          </motion.header>

          <motion.div
            className={styles.heroCopy}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(0,20px,0)" }
            }
            animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.7,
              delay: reduceMotion ? 0 : 0.1,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <div className={styles.productEyebrow}>
              <span /> Campaign Lens <small>Example analysis</small>
            </div>
            <h1 id="edit-axis-title">Find the cut the story was hiding.</h1>
            <p>
              Scrub the source. The frame, transcript-grounded words and
              campaign reason stay locked to the same moment.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryCta} href={startHref}>
                Build your first clip <ArrowUpRight aria-hidden="true" />
              </Link>
              <a className={styles.secondaryCta} href="#story">
                Watch the assembly <ChevronRight aria-hidden="true" />
              </a>
            </div>
          </motion.div>

          <div
            className={styles.opticalAxis}
            aria-hidden="true"
            style={{
              left: axisX,
              top: apertureCenterY + apertureHeight / 2 + 8,
            }}
          />

          <motion.div
            className={styles.aperture}
            data-scrubbing={isScrubbing ? "" : undefined}
            data-campaign-lens=""
            style={{
              top: apertureCenterY,
              left: apertureLeft,
              width: apertureWidth,
              height: apertureHeight,
            }}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, clipPath: "inset(48% 0 round 31px)" }
            }
            animate={{ opacity: 1, clipPath: "inset(0% 0 round 31px)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.64,
              delay: reduceMotion ? 0 : 0.22,
              ease: [0.23, 1, 0.32, 1],
            }}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerEnd}
            onPointerCancel={handlePointerEnd}
          >
            <div className={styles.apertureSurface}>
              <AnimatePresence initial={false}>
                <motion.div
                  key={SOURCE_FRAMES[activeFrame]}
                  className={styles.apertureFrame}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{
                    duration: isScrubbing || reduceMotion ? 0 : 0.14,
                  }}
                >
                  <Image
                    src={SOURCE_FRAMES[activeFrame]}
                    alt=""
                    fill
                    priority
                    unoptimized
                    sizes="(max-width: 760px) 52vw, 380px"
                  />
                </motion.div>
              </AnimatePresence>
              <div className={styles.apertureShade} aria-hidden="true" />
              <div className={styles.apertureTopbar}>
                <span>9:16 · AUTO FRAME</span>
                <span ref={timecodeRef}>
                  {formatTimeFromProgress(sourceProgress.get())}
                </span>
              </div>
              <AnimatePresence initial={false}>
                <motion.div
                  key={active.id}
                  className={styles.apertureCaption}
                  initial={{
                    opacity: 0,
                    filter: reduceMotion || isScrubbing ? "none" : "blur(2px)",
                  }}
                  animate={{ opacity: 1, filter: "blur(0px)" }}
                  exit={{
                    opacity: 0,
                    filter: reduceMotion || isScrubbing ? "none" : "blur(2px)",
                  }}
                  transition={{ duration: isScrubbing ? 0 : 0.16 }}
                >
                  <strong>{active.quote}</strong>
                  <span>
                    {active.label} · candidate {activeMoment + 1} of 3
                  </span>
                </motion.div>
              </AnimatePresence>
              <div className={styles.apertureCorners} aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
            </div>
          </motion.div>

          <motion.aside
            className={styles.attachedReason}
            data-side={reasonOnRight ? "right" : "left"}
            style={{
              left: reasonLeft,
              top: apertureCenterY - 70,
            }}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(8px,0,0) scale(.98)" }
            }
            animate={{ opacity: 1, transform: "translate3d(0,0,0) scale(1)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.44,
              delay: reduceMotion ? 0 : 0.44,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <span className={styles.reasonScore}>{active.score}</span>
            <AnimatePresence initial={false}>
              <motion.div
                key={active.id}
                initial={{ opacity: 0, transform: "translate3d(4px,0,0)" }}
                animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
                exit={{ opacity: 0, transform: "translate3d(-4px,0,0)" }}
                transition={{
                  duration: isScrubbing ? 0 : 0.16,
                  ease: [0.23, 1, 0.32, 1],
                }}
              >
                <small>Nearest campaign candidate</small>
                <strong>{active.label}</strong>
                <p>{active.reason}</p>
              </motion.div>
            </AnimatePresence>
          </motion.aside>

          <div
            className={styles.dragPrompt}
            data-hidden={hasInteracted ? "" : undefined}
          >
            <span aria-hidden="true">↔</span> Drag inside the frame
          </div>

          <SourceTimeline
            progress={sourceProgress}
            activeMoment={activeMoment}
            activeFrame={activeFrame}
            axisX={axisX}
            timelineScale={timelineScale}
            inset={timelineInset}
            isScrubbing={isScrubbing}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerEnd={handlePointerEnd}
            onSelectMoment={selectMoment}
            onKeyboardProgress={handleKeyboardProgress}
          />
        </motion.div>
      </section>

      <EditAxisStory
        moments={MOMENTS}
        startHref={startHref}
        signInHref={signInHref}
      />
    </main>
  );
}
