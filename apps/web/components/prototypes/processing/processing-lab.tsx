"use client";

import * as React from "react";
import { ProcessingFallback } from "./processing-fallback";
import { ProofManuscript } from "./proof-manuscript";
import type { ProcessingPreviewState } from "./processing-sequence";
import { SignalTimeline } from "./signal-timeline";
import { SourceCut } from "./source-cut";
import styles from "./processing-lab.module.css";

const VARIANTS = [
  { label: "Continuity", Component: SourceCut },
  { label: "Manuscript", Component: ProofManuscript },
  { label: "Timeline", Component: SignalTimeline },
] as const;

type ProcessingLabProps = {
  clean?: boolean;
  initialVariant: number;
  previewState?: ProcessingPreviewState;
};

export function ProcessingLab({
  clean = false,
  initialVariant,
  previewState = "auto",
}: ProcessingLabProps) {
  const [current, setCurrent] = React.useState(initialVariant);
  const [renderKey, setRenderKey] = React.useState(0);
  const pickerRef = React.useRef<HTMLElement>(null);
  const highlightRef = React.useRef<HTMLSpanElement>(null);
  const itemRefs = React.useRef<Array<HTMLButtonElement | null>>([]);

  const moveHighlight = React.useCallback(() => {
    const item = itemRefs.current[current];
    const highlight = highlightRef.current;
    if (!item || !highlight) return;

    highlight.style.width = `${item.offsetWidth}px`;
    highlight.style.transform = `translateX(${item.offsetLeft}px)`;
  }, [current]);

  const activate = React.useCallback((index: number) => {
    if (index < 0 || index >= VARIANTS.length) return;

    setCurrent(index);
    setRenderKey((key) => key + 1);

    const url = new URL(window.location.href);
    url.searchParams.set("v", String(index + 1));
    window.history.replaceState(null, "", url);
  }, []);

  const replay = React.useCallback(() => {
    setRenderKey((key) => key + 1);
  }, []);

  React.useLayoutEffect(() => {
    if (clean) return;
    moveHighlight();
  }, [clean, moveHighlight]);

  React.useEffect(() => {
    if (clean) return;

    let secondFrame = 0;
    const firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(() => {
        pickerRef.current?.setAttribute("data-ready", "");
      });
    });

    return () => {
      window.cancelAnimationFrame(firstFrame);
      window.cancelAnimationFrame(secondFrame);
    };
  }, [clean]);

  React.useEffect(() => {
    if (clean) return;
    window.addEventListener("resize", moveHighlight);
    return () => window.removeEventListener("resize", moveHighlight);
  }, [clean, moveHighlight]);

  React.useEffect(() => {
    if (clean) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (/^(INPUT|TEXTAREA|SELECT|BUTTON|A)$/.test(target.tagName) ||
          target.isContentEditable ||
          target.closest('[role="dialog"], [role="listbox"]'))
      ) {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const number = Number.parseInt(event.key, 10);
      if (number >= 1 && number <= VARIANTS.length) {
        activate(number - 1);
      } else if (event.key === "ArrowRight") {
        activate((current + 1) % VARIANTS.length);
      } else if (event.key === "ArrowLeft") {
        activate((current - 1 + VARIANTS.length) % VARIANTS.length);
      } else if (event.key === "r" || event.key === "R") {
        replay();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [activate, clean, current, replay]);

  const ActiveVariant = VARIANTS[current].Component;
  const fallbackState =
    previewState === "empty" || previewState === "error" ? previewState : null;

  return (
    <div className={styles.harness} data-picker={clean ? undefined : ""}>
      <div className={styles.stage} key={`${current}-${renderKey}`}>
        {fallbackState ? (
          <ProcessingFallback state={fallbackState} />
        ) : (
          <ActiveVariant previewState={previewState} />
        )}
      </div>

      {!clean ? (
        <nav
          ref={pickerRef}
          className="proto-picker"
          aria-label="Prototype variants"
        >
          <span
            ref={highlightRef}
            className="proto-picker-highlight"
            aria-hidden="true"
          />
          {VARIANTS.map((variant, index) => (
            <button
              key={variant.label}
              ref={(node) => {
                itemRefs.current[index] = node;
              }}
              type="button"
              className="proto-picker-item"
              data-active={current === index ? "" : undefined}
              aria-current={current === index ? "true" : undefined}
              onClick={() => activate(index)}
            >
              {variant.label}
            </button>
          ))}
          <span className="proto-picker-divider" aria-hidden="true" />
          <button
            type="button"
            className="proto-picker-item proto-picker-replay"
            aria-label="Replay animation (R)"
            onClick={replay}
          >
            ↻
          </button>
        </nav>
      ) : null}
    </div>
  );
}
