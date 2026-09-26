"use client";

import {
  AlertCircle,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  CirclePlay,
  LoaderCircle,
  RotateCcw,
  Upload,
} from "lucide-react";
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
import * as React from "react";

import { CampaignLensShader } from "./campaign-lens-shader";
import styles from "./apple-film-stage.module.css";

const MOMENTS = [
  {
    id: "tension",
    label: "The tension",
    time: "02:14",
    progress: 134 / 1122,
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
    time: "09:32",
    progress: 572 / 1122,
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
    time: "16:05",
    progress: 965 / 1122,
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

const TICK_COUNT = 54;
const TICKS = Array.from({ length: TICK_COUNT }, (_, index) => index);

type DemoState = "ready" | "loading" | "empty" | "error";

function nearestMoment(progress: number) {
  return MOMENTS.reduce(
    (best, moment, index) =>
      Math.abs(moment.progress - progress) <
      Math.abs(MOMENTS[best].progress - progress)
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

type MagneticTimelineProps = {
  value: number;
  progress: MotionValue<number>;
  activeMoment: number;
  onChange: (value: number) => void;
  onCommit: () => void;
};

function MagneticTimeline({
  value,
  progress,
  activeMoment,
  onChange,
  onCommit,
}: MagneticTimelineProps) {
  const [hoveredTick, setHoveredTick] = React.useState<number | null>(null);
  const rafRef = React.useRef(0);
  const progressScale = useTransform(progress, (latest) => `scaleX(${latest})`);
  const playheadLeft = useTransform(progress, (latest) => `${latest * 100}%`);

  const updateHover = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const raw = ((event.clientX - rect.left) / rect.width) * (TICK_COUNT - 1);
    const index = Math.max(0, Math.min(TICK_COUNT - 1, Math.round(raw)));
    window.cancelAnimationFrame(rafRef.current);
    rafRef.current = window.requestAnimationFrame(() => setHoveredTick(index));
  };

  React.useEffect(() => () => window.cancelAnimationFrame(rafRef.current), []);

  return (
    <div className={styles.timelineShell}>
      <div className={styles.timelineMeta}>
        <span>Interview_master.mov</span>
        <span>18:42</span>
      </div>

      <div
        className={styles.magneticRail}
        onPointerMove={updateHover}
        onPointerLeave={() => setHoveredTick(null)}
      >
        <div className={styles.tickField} aria-hidden="true">
          {TICKS.map((tick) => {
            const distance =
              hoveredTick === null
                ? Number.POSITIVE_INFINITY
                : Math.abs(tick - hoveredTick);
            const radius = 5;
            const rise =
              distance >= radius
                ? 0
                : 0.5 * (1 + Math.cos(Math.PI * (distance / radius)));
            const momentTick = MOMENTS.some(
              (moment) =>
                Math.abs(moment.progress * (TICK_COUNT - 1) - tick) < 1.5,
            );

            return (
              <span
                key={tick}
                className={styles.timelineTick}
                data-moment={momentTick ? "" : undefined}
                style={{
                  transform: `scaleY(${1 + rise * 2.6})`,
                  opacity: 0.24 + rise * 0.76,
                }}
              />
            );
          })}
        </div>

        <motion.div
          className={styles.timelineProgress}
          aria-hidden="true"
          style={{ transform: progressScale }}
        />
        <motion.span
          className={styles.playhead}
          aria-hidden="true"
          style={{ left: playheadLeft }}
        />

        <input
          className={styles.rangeInput}
          type="range"
          min="0"
          max="1000"
          step="1"
          value={Math.round(value * 1000)}
          aria-label="Explore the source timeline"
          aria-valuetext={`${MOMENTS[activeMoment].label}, ${MOMENTS[activeMoment].time}`}
          onChange={(event) => onChange(Number(event.target.value) / 1000)}
          onPointerUp={onCommit}
          onKeyUp={onCommit}
        />

        <div className={styles.timelineMarkers} aria-hidden="true">
          {MOMENTS.map((moment, index) => (
            <span
              key={moment.id}
              data-active={activeMoment === index ? "" : undefined}
              style={{ left: `${moment.progress * 100}%` }}
            />
          ))}
        </div>
      </div>

      <div className={styles.momentLabels}>
        {MOMENTS.map((moment, index) => (
          <button
            key={moment.id}
            type="button"
            data-active={activeMoment === index ? "" : undefined}
            onClick={() => onChange(moment.progress)}
          >
            <span>{moment.label}</span>
            <small>{moment.time}</small>
          </button>
        ))}
      </div>
    </div>
  );
}

function StatePreview({
  state,
  activeMoment,
}: {
  state: DemoState;
  activeMoment: number;
}) {
  const moment = MOMENTS[activeMoment];

  if (state === "loading") {
    return (
      <div className={styles.stateMessage} data-state="loading">
        <LoaderCircle aria-hidden="true" />
        <div>
          <span>Reading the whole story</span>
          <strong>Finding campaign moments · 62%</strong>
        </div>
        <div
          className={styles.progressTrack}
          aria-label="Analysis progress: 62%"
        >
          <span style={{ transform: "scaleX(.62)" }} />
        </div>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className={styles.stateMessage} data-state="empty">
        <CirclePlay aria-hidden="true" />
        <div>
          <span>No moment cleared your quality floor</span>
          <strong>Keep the source. Adjust the campaign brief.</strong>
        </div>
        <button type="button">Adjust brief</button>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className={styles.stateMessage} data-state="error">
        <AlertCircle aria-hidden="true" />
        <div>
          <span>We couldn’t read the audio track</span>
          <strong>Your source is still here. Nothing was charged.</strong>
        </div>
        <div className={styles.stateActions}>
          <button type="button">
            <RotateCcw aria-hidden="true" /> Try again
          </button>
          <button type="button">
            <Upload aria-hidden="true" /> Replace
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.inspectorBody}>
      <div className={styles.inspectorLead}>
        <span>Why this moment</span>
        <strong>{moment.quote}</strong>
        <p>{moment.reason}</p>
      </div>

      <div className={styles.scoreRows}>
        {moment.breakdown.map(([label, score]) => (
          <div key={label} className={styles.scoreRow}>
            <div>
              <span>{label}</span>
              <strong>{score}</strong>
            </div>
            <div aria-hidden="true">
              <span style={{ transform: `scaleX(${score / 100})` }} />
            </div>
          </div>
        ))}
      </div>

      <div className={styles.verifiedLine}>
        <Check aria-hidden="true" /> Quote verified against the source
        transcript
      </div>
    </div>
  );
}

export function AppleFilmStage() {
  const reduceMotion = useReducedMotion();
  const heroRef = React.useRef<HTMLElement>(null);
  const stageRef = React.useRef<HTMLDivElement>(null);
  const lensRef = React.useRef<HTMLDivElement>(null);
  const dragRef = React.useRef({
    pointerId: -1,
    originX: 0,
    originProgress: 0,
  });
  const snapAnimationRef = React.useRef<{ stop: () => void } | null>(null);
  const [activeMoment, setActiveMoment] = React.useState(1);
  const [activeCut, setActiveCut] = React.useState(1);
  const [isDragging, setIsDragging] = React.useState(false);
  const [hasDragged, setHasDragged] = React.useState(false);
  const [stageSize, setStageSize] = React.useState({
    width: 1280,
    height: 760,
  });
  const [demoState, setDemoState] = React.useState<DemoState>("ready");
  const lensProgress = useMotionValue<number>(MOMENTS[1].progress);
  const [timelineValue, setTimelineValue] = React.useState<number>(
    MOMENTS[1].progress,
  );
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const heroTransform = useTransform(
    scrollYProgress,
    [0, 1],
    [
      "translate3d(0, 0, 0) scale(1)",
      reduceMotion
        ? "translate3d(0, 0, 0) scale(1)"
        : "translate3d(0, 72px, 0) scale(.955)",
    ],
  );
  const heroOpacity = useTransform(scrollYProgress, [0, 0.9], [1, 0.72]);

  const lensHeight = Math.min(
    stageSize.height * (stageSize.width < 700 ? 0.55 : 0.68),
    stageSize.width < 700 ? 360 : 560,
  );
  const lensWidth = lensHeight * (9 / 16);
  const lensMargin = stageSize.width < 700 ? 12 : 28;
  const lensCenterYRatio =
    stageSize.width <= 400 ? 0.59 : stageSize.width < 700 ? 0.58 : 0.47;
  const lensTravel = Math.max(0, stageSize.width - lensWidth - lensMargin * 2);
  const lensTransform = useTransform(lensProgress, (progress) => {
    const left = lensMargin + progress * lensTravel;
    return `translate3d(${left}px, -50%, 0)`;
  });
  const cutSpacing = stageSize.width < 700 ? 112 : 188;

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

  React.useEffect(() => {
    let raf = 0;
    const unsubscribe = lensProgress.on("change", (value) => {
      window.cancelAnimationFrame(raf);
      raf = window.requestAnimationFrame(() => {
        setTimelineValue(value);
        setActiveMoment(nearestMoment(value));
      });
    });

    return () => {
      window.cancelAnimationFrame(raf);
      unsubscribe();
    };
  }, [lensProgress]);

  const moveLens = React.useCallback(
    (target: number, snap = false) => {
      const value = Math.max(0, Math.min(1, target));
      snapAnimationRef.current?.stop();
      if (!snap || reduceMotion) {
        lensProgress.set(value);
        return;
      }
      const destination = MOMENTS[nearestMoment(value)].progress;
      snapAnimationRef.current = animate(lensProgress, destination, {
        type: "spring",
        stiffness: 380,
        damping: 38,
        mass: 0.72,
        velocity: lensProgress.getVelocity(),
      });
    },
    [lensProgress, reduceMotion],
  );

  const commitLens = React.useCallback(() => {
    moveLens(lensProgress.get(), true);
  }, [lensProgress, moveLens]);

  const handleLensPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    snapAnimationRef.current?.stop();
    dragRef.current = {
      pointerId: event.pointerId,
      originX: event.clientX,
      originProgress: lensProgress.get(),
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsDragging(true);
  };

  const handleLensPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== event.pointerId || !isDragging) return;
    const delta = event.clientX - dragRef.current.originX;
    const next =
      dragRef.current.originProgress + delta / Math.max(lensTravel, 1);
    lensProgress.set(Math.max(0, Math.min(1, next)));
    setHasDragged(true);
  };

  const handleLensPointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current.pointerId = -1;
    setIsDragging(false);
    commitLens();
  };

  const selectCut = (index: number) => {
    setActiveCut(index);
    setDemoState("ready");
  };

  const changeCut = (direction: -1 | 1) => {
    selectCut((activeCut + direction + MOMENTS.length) % MOMENTS.length);
  };

  return (
    <main id="main-content" className={styles.page}>
      <section
        ref={heroRef}
        className={styles.hero}
        aria-labelledby="apple-film-title"
      >
        <motion.div
          ref={stageRef}
          className={styles.heroStage}
          style={{ transform: heroTransform, opacity: heroOpacity }}
        >
          <CampaignLensShader
            imageSrc="/prototypes/cinematic-source-v1.webp"
            alt="A founder speaking during a filmed studio interview."
            lensProgress={lensProgress}
            lensHeightRatio={stageSize.width < 700 ? 0.55 : 0.68}
            lensHeightPx={lensHeight}
            lensWidthPx={lensWidth}
            lensSideMarginPx={lensMargin}
            lensCenterYRatio={lensCenterYRatio}
            lensRadiusPx={stageSize.width < 700 ? 23 : 27}
            className={styles.heroShader}
          />
          <div className={styles.heroShade} aria-hidden="true" />

          <motion.header
            className={styles.header}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(0,-12px,0)" }
            }
            animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.5,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <Link
              className={styles.brand}
              href="/"
              aria-label="ClipFactory home"
            >
              <BrandMark />
              <span>ClipFactory</span>
            </Link>

            <nav className={styles.primaryNav} aria-label="Primary navigation">
              <a href="#story">How it works</a>
              <Link href="/features">Features</Link>
              <Link href="/pricing">Pricing</Link>
            </nav>

            <div className={styles.headerActions}>
              <Link className={styles.signIn} href="/login">
                Sign in
              </Link>
              <Link className={styles.navCta} href="/login?mode=signup">
                Try your video
                <ArrowUpRight aria-hidden="true" />
              </Link>
            </div>
          </motion.header>

          <motion.div
            className={styles.heroCopy}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(0,18px,0)" }
            }
            animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.72,
              delay: reduceMotion ? 0 : 0.12,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <p className={styles.productName}>Campaign Lens</p>
            <h1 id="apple-film-title">The story is already in there.</h1>
            <p className={styles.heroBody}>
              Move through the source. ClipFactory reveals the moments that
              belong to your campaign — and explains why.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryCta} href="/login?mode=signup">
                Try your video
                <ArrowUpRight aria-hidden="true" />
              </Link>
              <a className={styles.secondaryCta} href="#story">
                See the cut
              </a>
            </div>
          </motion.div>

          <motion.div
            ref={lensRef}
            className={styles.lens}
            data-campaign-lens=""
            data-dragging={isDragging ? "" : undefined}
            style={{
              width: lensWidth,
              height: lensHeight,
              transform: lensTransform,
            }}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{
              duration: reduceMotion ? 0 : 0.46,
              delay: reduceMotion ? 0 : 0.28,
            }}
            onPointerDown={handleLensPointerDown}
            onPointerMove={handleLensPointerMove}
            onPointerUp={handleLensPointerEnd}
            onPointerCancel={handleLensPointerEnd}
          >
            <div className={styles.lensSurface}>
              <div className={styles.lensTopbar}>
                <span>9:16</span>
                <span>{MOMENTS[activeMoment].time}</span>
              </div>
              <div className={styles.lensCorners} aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
              </div>
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={MOMENTS[activeMoment].id}
                  className={styles.lensCaption}
                  initial={
                    reduceMotion ? false : { opacity: 0, filter: "blur(2px)" }
                  }
                  animate={{ opacity: 1, filter: "blur(0px)" }}
                  exit={
                    reduceMotion
                      ? undefined
                      : { opacity: 0, filter: "blur(2px)" }
                  }
                  transition={{ duration: reduceMotion ? 0 : 0.18 }}
                >
                  <strong>{MOMENTS[activeMoment].quote}</strong>
                  <span>Clip {activeMoment + 1} of 3</span>
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>

          <motion.aside
            className={styles.whyPill}
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(10px,0,0) scale(.97)" }
            }
            animate={{ opacity: 1, transform: "translate3d(0,0,0) scale(1)" }}
            transition={{
              duration: reduceMotion ? 0 : 0.42,
              delay: reduceMotion ? 0 : 0.42,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            <span className={styles.scoreOrb}>
              {MOMENTS[activeMoment].score}
            </span>
            <span>
              <small>Why this moment</small>
              <strong>{MOMENTS[activeMoment].label}</strong>
            </span>
            <ChevronRight aria-hidden="true" />
          </motion.aside>

          <div
            className={styles.dragHint}
            data-hidden={hasDragged ? "" : undefined}
          >
            <span aria-hidden="true">↔</span> Drag the frame
          </div>

          <MagneticTimeline
            value={timelineValue}
            progress={lensProgress}
            activeMoment={activeMoment}
            onChange={(value) => moveLens(value)}
            onCommit={commitLens}
          />
        </motion.div>
      </section>

      <section
        id="story"
        className={styles.storySection}
        aria-labelledby="story-title"
      >
        <div className={styles.storyHeading}>
          <motion.p
            initial={reduceMotion ? false : { opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, amount: 0.7 }}
          >
            Magnetic story
          </motion.p>
          <motion.h2
            id="story-title"
            initial={
              reduceMotion
                ? false
                : { opacity: 0, transform: "translate3d(0,20px,0)" }
            }
            whileInView={{ opacity: 1, transform: "translate3d(0,0,0)" }}
            viewport={{ once: true, amount: 0.55 }}
            transition={{
              duration: reduceMotion ? 0 : 0.68,
              ease: [0.23, 1, 0.32, 1],
            }}
          >
            Distant moments. One earned cut.
          </motion.h2>
          <p>
            Setup, proof and payoff can live minutes apart. ClipFactory keeps
            their order, verifies the words, and builds the vertical story.
          </p>
        </div>

        <div className={styles.productStage}>
          <div className={styles.cutBrowser}>
            <div className={styles.cutBrowserTopbar}>
              <div>
                <span className={styles.liveDot} aria-hidden="true" />
                Product launch · 3 moments
              </div>
              <div className={styles.cutControls}>
                <button
                  type="button"
                  aria-label="Previous clip"
                  onClick={() => changeCut(-1)}
                >
                  <ChevronLeft aria-hidden="true" />
                </button>
                <span>
                  {activeCut + 1} / {MOMENTS.length}
                </span>
                <button
                  type="button"
                  aria-label="Next clip"
                  onClick={() => changeCut(1)}
                >
                  <ChevronRight aria-hidden="true" />
                </button>
              </div>
            </div>

            <div
              className={styles.coverflow}
              role="listbox"
              aria-label="Generated campaign clips"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "ArrowLeft") changeCut(-1);
                if (event.key === "ArrowRight") changeCut(1);
              }}
            >
              {MOMENTS.map((moment, index) => {
                const delta = index - activeCut;
                const transform =
                  delta === 0
                    ? "translate3d(0,0,0) rotateY(0deg) scale(1)"
                    : `translate3d(${delta * cutSpacing}px, 20px, ${Math.abs(delta) * -80}px) rotateY(${delta * -12}deg) scale(.86)`;
                return (
                  <motion.button
                    key={moment.id}
                    type="button"
                    role="option"
                    aria-selected={activeCut === index}
                    aria-label={`${moment.label}, score ${moment.score}`}
                    className={styles.cutCard}
                    data-active={activeCut === index ? "" : undefined}
                    animate={{
                      transform,
                      opacity: activeCut === index ? 1 : 0.52,
                    }}
                    transition={
                      reduceMotion
                        ? { duration: 0 }
                        : {
                            type: "spring",
                            stiffness: 310,
                            damping: 34,
                            mass: 0.78,
                          }
                    }
                    onClick={() => selectCut(index)}
                  >
                    <Image
                      src={moment.frame}
                      alt=""
                      fill
                      sizes="(max-width: 700px) 54vw, 260px"
                    />
                    <span className={styles.cutCardShade} aria-hidden="true" />
                    <span className={styles.cutCardMeta}>
                      <small>{moment.time}</small>
                      <strong>{moment.label}</strong>
                      <span>{moment.score}</span>
                    </span>
                  </motion.button>
                );
              })}
            </div>

            <div className={styles.storyline} aria-label="Selected story arc">
              {MOMENTS.map((moment, index) => (
                <button
                  key={moment.id}
                  type="button"
                  data-active={activeCut === index ? "" : undefined}
                  onClick={() => selectCut(index)}
                >
                  <Image src={moment.frame} alt="" fill sizes="160px" />
                  <span>{moment.label}</span>
                </button>
              ))}
              <span
                className={styles.storyPlayhead}
                aria-hidden="true"
                style={{ left: `${16.67 + activeCut * 33.33}%` }}
              />
            </div>
          </div>

          <aside
            id="inspector"
            className={styles.inspector}
            aria-label="Clip reasoning inspector"
          >
            <div className={styles.inspectorHeader}>
              <div>
                <span>Clip inspector</span>
                <strong>{MOMENTS[activeCut].label}</strong>
              </div>
              <span className={styles.inspectorScore}>
                {MOMENTS[activeCut].score}
              </span>
            </div>

            <div
              className={styles.stateSwitcher}
              data-state-switcher=""
              aria-label="Preview product states"
            >
              {(["ready", "loading", "empty", "error"] as DemoState[]).map(
                (state) => (
                  <button
                    key={state}
                    type="button"
                    data-active={demoState === state ? "" : undefined}
                    onClick={() => setDemoState(state)}
                  >
                    {state === "ready"
                      ? "Ready"
                      : state === "loading"
                        ? "Analyzing"
                        : state === "empty"
                          ? "Empty"
                          : "Error"}
                  </button>
                ),
              )}
            </div>

            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={`${demoState}-${activeCut}`}
                className={styles.stateViewport}
                initial={
                  reduceMotion ? false : { opacity: 0, filter: "blur(2px)" }
                }
                animate={{ opacity: 1, filter: "blur(0px)" }}
                exit={
                  reduceMotion ? undefined : { opacity: 0, filter: "blur(2px)" }
                }
                transition={{ duration: reduceMotion ? 0 : 0.18 }}
              >
                <StatePreview state={demoState} activeMoment={activeCut} />
              </motion.div>
            </AnimatePresence>
          </aside>
        </div>
      </section>

      <section className={styles.closing} aria-labelledby="closing-title">
        <div>
          <p>Starter · 300 source minutes</p>
          <h2 id="closing-title">Ship the clips you meant to make.</h2>
        </div>
        <div className={styles.closingAction}>
          <span>
            <strong>€29</strong> / month
          </span>
          <Link href="/login?mode=signup">
            Start clipping
            <ArrowUpRight aria-hidden="true" />
          </Link>
          <small>No watermark · cancel anytime</small>
        </div>
      </section>

      <footer className={styles.footer}>
        <Link className={styles.footerBrand} href="/">
          <BrandMark /> ClipFactory
        </Link>
        <nav aria-label="Footer navigation">
          <Link href="/features">Features</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/faq">FAQ</Link>
          <Link href="/legal/privacy">Privacy</Link>
        </nav>
        <span>Made for the whole story.</span>
      </footer>
    </main>
  );
}
