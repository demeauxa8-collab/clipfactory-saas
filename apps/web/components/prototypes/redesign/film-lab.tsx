"use client";

import Image from "next/image";
import Link from "next/link";
import { useRef, useState, type KeyboardEvent } from "react";

import styles from "./film-lab.module.css";

const clips = [
  {
    id: "opening-tension",
    number: "01",
    title: "The opening tension",
    range: "02:14 to 02:39",
    fitScore: 92,
    objectPosition: "74% center",
    rationale:
      "Starts on the clearest disagreement, then lands the line that reframes the campaign for this audience.",
  },
  {
    id: "proof-before-promise",
    number: "02",
    title: "Proof before promise",
    range: "08:06 to 08:34",
    fitScore: 88,
    objectPosition: "66% center",
    rationale:
      "Pairs the concrete example with the line that makes the campaign message credible.",
  },
  {
    id: "earned-reveal",
    number: "03",
    title: "The earned reveal",
    range: "12:47 to 13:05",
    fitScore: 84,
    objectPosition: "82% center",
    rationale:
      "Holds the answer until the final beat, so the edit earns its conclusion.",
  },
] as const;

export function FilmLab() {
  const [selectedClipIndex, setSelectedClipIndex] = useState(0);
  const proofRef = useRef<HTMLElement>(null);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedClip = clips[selectedClipIndex];

  const scrollToProof = () => {
    const proof = proofRef.current;

    if (!proof) return;

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    proof.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "start",
    });
    proof.focus({ preventScroll: true });
  };

  const selectClip = (index: number, shouldFocus = false) => {
    setSelectedClipIndex(index);

    if (shouldFocus) {
      tabRefs.current[index]?.focus();
    }
  };

  const handleTabKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    let nextIndex: number | null = null;

    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = (index + 1) % clips.length;
    }

    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = (index - 1 + clips.length) % clips.length;
    }

    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = clips.length - 1;

    if (nextIndex === null) return;

    event.preventDefault();
    selectClip(nextIndex, true);
  };

  return (
    <main id="main-content" className={styles.filmLab}>
      <div className={styles.pageGrain} aria-hidden="true" />

      <header className={styles.navShell}>
        <nav className={styles.nav} aria-label="Primary navigation">
          <Link
            className={styles.wordmark}
            href="/"
            aria-label="ClipFactory home"
          >
            <span className={styles.wordmarkMark}>CF</span>
            <span>ClipFactory</span>
          </Link>

          <div className={styles.navIndex} aria-label="Prototype edition">
            <span>Film Lab</span>
            <span aria-hidden="true">/</span>
            <span>01</span>
          </div>

          <div className={styles.navLinks}>
            <button
              className={styles.navProof}
              type="button"
              onClick={scrollToProof}
            >
              Proof
            </button>
            <Link href="/pricing">Pricing</Link>
            <Link className={styles.signIn} href="/login">
              Sign in
            </Link>
          </div>
        </nav>
      </header>

      <section className={styles.hero} aria-labelledby="film-lab-title">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>
            <span>Campaign editing</span>
            <span aria-hidden="true">/</span>
            <span>Source-led</span>
          </p>

          <h1 id="film-lab-title">
            Give it the campaign. <em>Get the clips that belong.</em>
          </h1>

          <p className={styles.supportingCopy}>
            ClipFactory links distant moments, builds the vertical edit, and
            explains why each clip fits your audience.
          </p>

          <div className={styles.heroActions}>
            <Link className={styles.primaryCta} href="/pricing">
              <span>Start Starter - €29</span>
              <span className={styles.ctaArrow} aria-hidden="true">
                ↗
              </span>
            </Link>
            <button
              className={styles.proofCta}
              type="button"
              onClick={scrollToProof}
            >
              <span className={styles.playMark} aria-hidden="true">
                ▶
              </span>
              Watch the proof
            </button>
          </div>

          <dl
            className={styles.inputLedger}
            aria-label="ClipFactory inputs and output"
          >
            <div>
              <dt>Input</dt>
              <dd>Long-form source</dd>
            </div>
            <div>
              <dt>Direction</dt>
              <dd>Campaign + audience</dd>
            </div>
            <div>
              <dt>Output</dt>
              <dd>Explained vertical edits</dd>
            </div>
          </dl>
        </div>

        <figure className={styles.heroStage}>
          <div className={styles.filmRail} aria-hidden="true" />
          <div className={styles.stageHeader}>
            <span>SOURCE / CAM-01</span>
            <span>16:9 MASTER</span>
          </div>
          <div className={styles.stageMedia}>
            <Image
              src="/prototypes/cinematic-source-v1.webp"
              alt="A creator speaking into a studio microphone in a warm, cinematic interview setting."
              fill
              priority
              sizes="(max-width: 860px) 94vw, 58vw"
            />
            <div className={styles.frameGuide} aria-hidden="true">
              <span>9:16</span>
            </div>
            <div className={styles.stageTimecode} aria-hidden="true">
              TC 00:08:06:12
            </div>
          </div>
          <figcaption className={styles.stageCaption}>
            <span>One source. Three campaign-shaped cuts.</span>
            <span className={styles.liveDot}>Source loaded</span>
          </figcaption>
        </figure>
      </section>

      <section
        className={styles.proof}
        id="film-lab-proof"
        ref={proofRef}
        tabIndex={-1}
        aria-labelledby="proof-title"
      >
        <div className={styles.proofHeading}>
          <p className={styles.sectionIndex}>01 / SOURCE TO CUT</p>
          <h2 id="proof-title">See the edit think.</h2>
          <p>
            The source remains visible. Each cut carries its timing, fit score,
            and editorial reason.
          </p>
        </div>

        <div className={styles.proofWorkspace}>
          <article
            className={styles.sourcePanel}
            aria-labelledby="source-panel-title"
          >
            <div className={styles.panelLabel}>
              <h3 id="source-panel-title">Source film</h3>
              <span>14:22</span>
            </div>

            <div className={styles.sourceMedia}>
              <Image
                src="/prototypes/cinematic-source-v1.webp"
                alt="The wide interview source used to compose the three vertical clips."
                fill
                sizes="(max-width: 860px) 92vw, 55vw"
              />
              <span className={styles.sourceBadge}>MASTER</span>
            </div>

            <div
              className={styles.timeline}
              aria-label="Three selected moments across the source"
            >
              <span className={styles.timelineTrack} aria-hidden="true" />
              {clips.map((clip, index) => (
                <button
                  className={`${styles.timelineMarker} ${
                    selectedClipIndex === index
                      ? styles.timelineMarkerActive
                      : ""
                  }`}
                  key={clip.id}
                  type="button"
                  style={{ left: `${[18, 56, 86][index]}%` }}
                  onClick={() => selectClip(index)}
                  aria-label={`Select clip ${clip.number}: ${clip.title}`}
                >
                  <span>{clip.number}</span>
                </button>
              ))}
            </div>

            <div className={styles.timelineScale} aria-hidden="true">
              <span>00:00</span>
              <span>07:11</span>
              <span>14:22</span>
            </div>
          </article>

          <article
            className={styles.cutPanel}
            aria-labelledby="cut-panel-title"
          >
            <div className={styles.panelLabel}>
              <h3 id="cut-panel-title">Vertical selects</h3>
              <span>3 CUTS</span>
            </div>

            <div
              className={styles.clipTabs}
              role="tablist"
              aria-label="Select a vertical clip"
            >
              {clips.map((clip, index) => {
                const isSelected = selectedClipIndex === index;

                return (
                  <button
                    className={`${styles.clipTab} ${isSelected ? styles.clipTabActive : ""}`}
                    id={`film-lab-tab-${clip.id}`}
                    key={clip.id}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    aria-controls="film-lab-clip-panel"
                    tabIndex={isSelected ? 0 : -1}
                    ref={(node) => {
                      tabRefs.current[index] = node;
                    }}
                    onClick={() => selectClip(index)}
                    onKeyDown={(event) => handleTabKeyDown(event, index)}
                  >
                    <span className={styles.clipCrop}>
                      <Image
                        src="/prototypes/cinematic-source-v1.webp"
                        alt=""
                        fill
                        sizes="(max-width: 560px) 84px, 12vw"
                        style={{ objectPosition: clip.objectPosition }}
                      />
                      <span className={styles.clipNumber}>{clip.number}</span>
                    </span>
                    <span className={styles.clipMeta}>
                      <strong>{clip.title}</strong>
                      <small>{clip.range}</small>
                    </span>
                  </button>
                );
              })}
            </div>

            <div
              className={styles.clipDetail}
              id="film-lab-clip-panel"
              role="tabpanel"
              aria-labelledby={`film-lab-tab-${selectedClip.id}`}
              aria-live="polite"
              tabIndex={0}
            >
              <div className={styles.scoreBlock}>
                <span>Campaign fit</span>
                <strong>
                  {selectedClip.fitScore}
                  <small>/100</small>
                </strong>
              </div>
              <div className={styles.rationaleBlock}>
                <span>Why this cut</span>
                <p>{selectedClip.rationale}</p>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}

export default FilmLab;
