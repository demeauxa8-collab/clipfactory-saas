"use client";

import * as React from "react";
import { AppleEditAxis } from "./apple-edit-axis";
import { AppleFilmStage } from "./apple-film-stage";
import { FilmLab } from "./film-lab";
import { KineticBroadcast } from "./kinetic-broadcast";
import { LivingEditSpace } from "./living-edit-space";
import { SignalRoom } from "./signal-room";
import styles from "./prototype-lab.module.css";

const VARIANTS = [
  { label: "Film Lab", Component: FilmLab },
  { label: "Signal Room", Component: SignalRoom },
  { label: "Kinetic", Component: KineticBroadcast },
  { label: "Living Edit", Component: LivingEditSpace },
  { label: "Campaign Lens", Component: AppleFilmStage },
  { label: "Edit Axis", Component: AppleEditAxis },
] as const;

type PrototypeLabProps = {
  clean?: boolean;
  initialVariant: number;
};

export function PrototypeLab({
  clean = false,
  initialVariant,
}: PrototypeLabProps) {
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

  const centerActiveItem = React.useCallback(() => {
    const picker = pickerRef.current;
    const item = itemRefs.current[current];

    if (!picker || !item || !window.matchMedia("(max-width: 500px)").matches) {
      return;
    }

    const left = item.offsetLeft - (picker.clientWidth - item.offsetWidth) / 2;
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    picker.scrollTo({
      left: Math.max(0, left),
      behavior:
        picker.hasAttribute("data-ready") && !reduceMotion ? "smooth" : "auto",
    });
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
    centerActiveItem();
  }, [centerActiveItem, clean, moveHighlight]);

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

    const handleResize = () => {
      moveHighlight();
      centerActiveItem();
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [centerActiveItem, clean, moveHighlight]);

  React.useEffect(() => {
    if (clean) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (/^(A|BUTTON|INPUT|TEXTAREA|SELECT)$/.test(target.tagName) ||
          target.isContentEditable ||
          target.closest(
            '[role="button"], [role="listbox"], [role="slider"], [role="tablist"]',
          ))
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

  return (
    <div className={styles.harness}>
      <div className={styles.stage} key={`${current}-${renderKey}`}>
        <ActiveVariant />
      </div>

      {!clean ? (
        <nav
          ref={pickerRef}
          className="proto-picker"
          data-position={current === 5 ? "side" : undefined}
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
              data-short={index + 1}
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
