"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";

import CursorRingField from "@/components/originkit/cursor-ring-field";

import styles from "./kinetic-broadcast.module.css";

type Clip = {
  id: string;
  number: string;
  channel: string;
  title: string;
  word: string;
  duration: string;
  source: string;
  score: number;
  accent: string;
  audience: string;
  note: string;
  segments: Array<{ label: string; time: string }>;
};

const CLIPS: Clip[] = [
  {
    id: "belief",
    number: "01",
    channel: "OPEN",
    title: "The belief that stalls every creator",
    word: "BELIEF",
    duration: "00:31",
    source: "00:42",
    score: 94,
    accent: "#ff5a19",
    audience: "Solo creators",
    note: "A sharp claim opens the argument before the proof arrives.",
    segments: [
      { label: "HOOK", time: "00:42" },
      { label: "TURN", time: "07:18" },
      { label: "LAND", time: "14:06" },
    ],
  },
  {
    id: "pattern",
    number: "02",
    channel: "BREAK",
    title: "The pattern hiding across the interview",
    word: "PATTERN",
    duration: "00:44",
    source: "03:16",
    score: 91,
    accent: "#f2eedf",
    audience: "Creative teams",
    note: "Three distant observations become one coherent lesson.",
    segments: [
      { label: "SETUP", time: "03:16" },
      { label: "LINK", time: "09:27" },
      { label: "PROOF", time: "16:03" },
    ],
  },
  {
    id: "proof",
    number: "03",
    channel: "PROOF",
    title: "The result that changes the whole story",
    word: "RESULT",
    duration: "00:38",
    source: "05:09",
    score: 88,
    accent: "#ff7a29",
    audience: "Growth leads",
    note: "The payoff moves forward without losing the original context.",
    segments: [
      { label: "CLAIM", time: "05:09" },
      { label: "SHIFT", time: "11:42" },
      { label: "PAYOFF", time: "18:20" },
    ],
  },
  {
    id: "move",
    number: "04",
    channel: "MOVE",
    title: "The next move your audience can use",
    word: "MOVE",
    duration: "00:29",
    source: "08:54",
    score: 86,
    accent: "#d9ff3f",
    audience: "Agency clients",
    note: "A practical ending turns attention into a clear next action.",
    segments: [
      { label: "TENSION", time: "08:54" },
      { label: "METHOD", time: "13:11" },
      { label: "ACTION", time: "20:04" },
    ],
  },
];

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);

    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}

export function KineticBroadcast() {
  const [activeIndex, setActiveIndex] = useState(0);
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const coarsePointer = useMediaQuery("(pointer: coarse)");
  const stageId = useId();
  const railButtons = useRef<Array<HTMLButtonElement | null>>([]);
  const previousActiveIndex = useRef(activeIndex);
  const activeClip = CLIPS[activeIndex];

  const selectClip = (index: number) => {
    setActiveIndex((index + CLIPS.length) % CLIPS.length);
  };

  const showPrevious = () => selectClip(activeIndex - 1);
  const showNext = () => selectClip(activeIndex + 1);

  const handleRailKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      showPrevious();
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      showNext();
    }
    if (event.key === "Home") {
      event.preventDefault();
      selectClip(0);
    }
    if (event.key === "End") {
      event.preventDefault();
      selectClip(CLIPS.length - 1);
    }
  };

  useEffect(() => {
    if (previousActiveIndex.current === activeIndex) return;
    previousActiveIndex.current = activeIndex;

    const activeButton = railButtons.current[activeIndex];
    activeButton?.scrollIntoView({
      behavior: reducedMotion ? "auto" : "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [activeIndex, reducedMotion]);

  const clipStyle = {
    "--clip-accent": activeClip.accent,
  } as CSSProperties;

  return (
    <main className={styles.root} id="main-content">
      <nav
        className={styles.nav}
        id="kinetic-top"
        aria-label="Primary navigation"
      >
        <a className={styles.brand} href="/" aria-label="ClipFactory home">
          <span className={styles.brandMark} aria-hidden="true">
            CF
          </span>
          <span>ClipFactory</span>
        </a>

        <div className={styles.navLinks}>
          <a href="#kinetic-clips">Clips</a>
          <a href="#kinetic-proof">Proof</a>
          <a href="/pricing">Pricing</a>
        </div>

        <a className={styles.navCta} href="/pricing">
          Start creating
          <span aria-hidden="true">↗</span>
        </a>
      </nav>

      <section className={styles.hero} aria-labelledby="kinetic-headline">
        <div className={styles.heroCopy}>
          <div className={styles.eyebrow}>
            <span>Campaign broadcast</span>
            <span>Edition 01</span>
          </div>

          <h1 className={styles.headline} id="kinetic-headline">
            <span>Give it the campaign.</span>
            <span className={styles.headlineAccent}>
              Get the clips that belong.
            </span>
          </h1>

          <p className={styles.supporting}>
            ClipFactory links distant moments, builds the vertical edit, and
            explains why each clip fits your audience.
          </p>

          <div className={styles.actions}>
            <a className={styles.primaryAction} href="/pricing">
              Start Starter - €29
              <span aria-hidden="true">↗</span>
            </a>
            <a className={styles.secondaryAction} href="#kinetic-proof">
              Watch the proof
              <span aria-hidden="true">↓</span>
            </a>
          </div>
        </div>

        <section
          className={styles.broadcast}
          id="kinetic-clips"
          aria-label="Campaign clip selector"
          aria-roledescription="carousel"
          tabIndex={0}
          onKeyDown={handleRailKeyDown}
        >
          <div className={styles.shaderSurface} aria-hidden="true">
            {reducedMotion ? (
              <div className={styles.shaderFallback} />
            ) : (
              <CursorRingField
                background="#11120f"
                colors={{
                  items: [
                    "#ff5a19",
                    "#ff8a38",
                    "#f2eedf",
                    "#d9ff3f",
                    "#23251f",
                  ],
                }}
                density={coarsePointer ? 150 : 280}
                dotSize={coarsePointer ? 88 : 106}
                speed={coarsePointer ? 2 : 4}
                cameraDistance={164}
                ring={{ radius: 13, width: 7, push: 18, turbulence: 22 }}
                style={{ position: "absolute", inset: 0 }}
              />
            )}
          </div>

          <div className={styles.broadcastHeader}>
            <div className={styles.onAir}>
              <span className={styles.onAirDot} aria-hidden="true" />
              Campaign 014 / example
            </div>
            <span className={styles.inputHint}>
              {coarsePointer ? "Tap a clip" : "Use arrow keys"}
            </span>
          </div>

          <figure
            className={styles.stageCard}
            id={stageId}
            key={activeClip.id}
            style={clipStyle}
            aria-labelledby={stageId + "-title"}
          >
            <div className={styles.verticalFrame}>
              <div className={styles.frameNoise} aria-hidden="true" />
              <div className={styles.frameTopline}>
                <span>{activeClip.channel}</span>
                <span>{activeClip.duration}</span>
              </div>
              <span className={styles.frameNumber} aria-hidden="true">
                {activeClip.number}
              </span>
              <strong className={styles.frameWord}>{activeClip.word}</strong>
              <div className={styles.captionPlate}>
                <span>ClipFactory edit</span>
                <span>{activeClip.audience}</span>
              </div>
            </div>

            <figcaption className={styles.stageCaption}>
              <div>
                <span className={styles.captionLabel}>
                  Clip {activeClip.number} / Source {activeClip.source}
                </span>
                <h2 id={stageId + "-title"}>{activeClip.title}</h2>
              </div>
              <div
                className={styles.score}
                aria-label={activeClip.score + " match score"}
              >
                <strong>{activeClip.score}</strong>
                <span>match</span>
              </div>
            </figcaption>
          </figure>

          <div className={styles.railDock}>
            <div className={styles.railControls}>
              <button
                className={styles.arrowButton}
                type="button"
                onClick={showPrevious}
                aria-label="Show previous clip"
                aria-controls={stageId}
              >
                ←
              </button>
              <span aria-hidden="true">
                {String(activeIndex + 1).padStart(2, "0")} /{" "}
                {String(CLIPS.length).padStart(2, "0")}
              </span>
              <button
                className={styles.arrowButton}
                type="button"
                onClick={showNext}
                aria-label="Show next clip"
                aria-controls={stageId}
              >
                →
              </button>
            </div>

            <ol className={styles.clipRail} aria-label="Campaign clips">
              {CLIPS.map((clip, index) => {
                const isActive = index === activeIndex;

                return (
                  <li className={styles.railItem} key={clip.id}>
                    <button
                      className={styles.railClip}
                      data-active={isActive ? "true" : "false"}
                      type="button"
                      onClick={() => selectClip(index)}
                      aria-label={
                        "Show clip " + clip.number + ": " + clip.title
                      }
                      aria-current={isActive ? "true" : undefined}
                      aria-controls={stageId}
                      ref={(node) => {
                        railButtons.current[index] = node;
                      }}
                    >
                      <span className={styles.railNumber}>{clip.number}</span>
                      <span className={styles.railTitle}>{clip.title}</span>
                      <span className={styles.railScore}>{clip.score}</span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>

          <p className={styles.srOnly} aria-live="polite" aria-atomic="true">
            {"Clip " +
              activeClip.number +
              " selected. " +
              activeClip.title +
              ". Match score " +
              activeClip.score +
              "."}
          </p>
        </section>
      </section>

      <section
        className={styles.proof}
        id="kinetic-proof"
        aria-labelledby="proof-title"
      >
        <div className={styles.proofHeader}>
          <span>Proof 01</span>
          <span>Source to vertical edit</span>
        </div>

        <div className={styles.proofGrid}>
          <div className={styles.proofCopy}>
            <span className={styles.proofKicker}>
              Campaign logic, made visible
            </span>
            <h2 id="proof-title">
              Distant moments become one vertical argument.
            </h2>
            <p>{activeClip.note}</p>

            <div className={styles.proofScore}>
              <div className={styles.proofScoreLabel}>
                <span>Audience match</span>
                <strong>{activeClip.score} / 100</strong>
              </div>
              <div
                className={styles.scoreTrack}
                role="progressbar"
                aria-label="Audience match"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={activeClip.score}
              >
                <span style={{ width: activeClip.score + "%" }} />
              </div>
            </div>
          </div>

          <div className={styles.editMap}>
            <div className={styles.sourceBar}>
              <div>
                <span>Original source</span>
                <strong>Founder interview</strong>
              </div>
              <span>21:36</span>
            </div>

            <ol className={styles.segmentList}>
              {activeClip.segments.map((segment, index) => (
                <li key={segment.label}>
                  <span className={styles.segmentIndex}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className={styles.segmentLabel}>{segment.label}</span>
                  <strong>{segment.time}</strong>
                  <span className={styles.segmentLine} aria-hidden="true" />
                </li>
              ))}
            </ol>

            <div className={styles.editResult} style={clipStyle}>
              <div className={styles.resultPoster} aria-hidden="true">
                <span>{activeClip.word}</span>
              </div>
              <div className={styles.resultCopy}>
                <span>Vertical edit built</span>
                <strong>{activeClip.title}</strong>
                <p>{activeClip.duration} total runtime</p>
              </div>
              <span className={styles.resultScore}>{activeClip.score}</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
