"use client";

import Image from "next/image";
import * as React from "react";
import { cn } from "@/lib/utils";
import styles from "./magnetic-carousel.module.css";

export type MagneticCarouselItem = {
  src: string;
  alt: string;
  label: string;
  meta?: string;
};

type MagneticCarouselProps = {
  items: readonly MagneticCarouselItem[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  ariaLabel?: string;
  className?: string;
  collapsedWidth?: number;
  hoverWidth?: number;
  selectedWidth?: number;
  influence?: number;
};

/**
 * Accessible ClipFactory adaptation of Originkit's Magnetic Carousel.
 * Mechanics source: https://www.originkit.dev/components/magneticcarousel
 */
export function MagneticCarousel({
  items,
  selectedIndex,
  onSelect,
  ariaLabel = "Candidate moments",
  className,
  collapsedWidth = 58,
  hoverWidth = 118,
  selectedWidth = 188,
  influence = 190,
}: MagneticCarouselProps) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const buttonRefs = React.useRef<Array<HTMLButtonElement | null>>([]);
  const reduceMotionRef = React.useRef(false);

  React.useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => {
      reduceMotionRef.current = media.matches;
    };

    updatePreference();
    media.addEventListener("change", updatePreference);
    return () => media.removeEventListener("change", updatePreference);
  }, []);

  const setMagnet = React.useCallback(
    (index: number, factor: number) => {
      const button = buttonRefs.current[index];
      if (!button) return;
      const selected = index === selectedIndex;
      const reveal = selected
        ? 0
        : ((hoverWidth - collapsedWidth) / 2) * (1 - factor);
      button.style.setProperty("--magnetic-clip", `${Math.max(0, reveal)}px`);
      button.style.setProperty(
        "--magnetic-scale",
        String(0.985 + factor * 0.015),
      );
      button.style.zIndex = selected ? "3" : factor > 0.05 ? "2" : "1";
    },
    [collapsedWidth, hoverWidth, selectedIndex],
  );

  const resetMagnet = React.useCallback(() => {
    items.forEach((_, index) =>
      setMagnet(index, index === selectedIndex ? 1 : 0),
    );
  }, [items, selectedIndex, setMagnet]);

  React.useEffect(() => {
    resetMagnet();
  }, [resetMagnet]);

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "touch" || reduceMotionRef.current) return;
    const root = rootRef.current;
    if (!root) return;
    const bounds = root.getBoundingClientRect();
    const slotWidths = items.map((_, index) =>
      index === selectedIndex ? selectedWidth : collapsedWidth,
    );
    const baseWidth =
      slotWidths.reduce((total, width) => total + width, 0) +
      (items.length - 1) * 6;
    const start = Math.max(0, (bounds.width - baseWidth) / 2);
    const pointer = event.clientX - bounds.left;
    let offset = start;

    items.forEach((_, index) => {
      const slotWidth = slotWidths[index] ?? collapsedWidth;
      const center = offset + slotWidth / 2;
      const normalized = Math.max(
        0,
        1 - Math.abs(pointer - center) / influence,
      );
      const factor = normalized * normalized * (3 - 2 * normalized);
      setMagnet(index, factor);
      offset += slotWidth + 6;
    });
  };

  const moveSelection = (next: number) => {
    const normalized = (next + items.length) % items.length;
    onSelect(normalized);
    buttonRefs.current[normalized]?.focus();
  };

  return (
    <div
      ref={rootRef}
      className={cn(styles.root, className)}
      role="listbox"
      aria-label={ariaLabel}
      aria-orientation="horizontal"
      onPointerMove={handlePointerMove}
      onPointerLeave={resetMagnet}
    >
      {items.map((item, index) => {
        const selected = index === selectedIndex;
        const initialClip = selected ? 0 : (hoverWidth - collapsedWidth) / 2;

        return (
          <button
            key={`${item.src}-${index}`}
            ref={(node) => {
              buttonRefs.current[index] = node;
            }}
            type="button"
            role="option"
            aria-selected={index === selectedIndex}
            aria-label={`${item.label}${item.meta ? `, ${item.meta}` : ""}`}
            className={styles.item}
            data-selected={selected ? "" : undefined}
            tabIndex={selected ? 0 : -1}
            style={
              {
                "--magnetic-slot-width": `${selected ? selectedWidth : collapsedWidth}px`,
                "--magnetic-visual-width": `${selected ? selectedWidth : hoverWidth}px`,
                "--magnetic-clip": `${initialClip}px`,
                "--magnetic-scale": selected ? 1 : 0.985,
              } as React.CSSProperties
            }
            onFocus={() => {
              if (reduceMotionRef.current) return;
              items.forEach((_, itemIndex) => {
                const factor =
                  itemIndex === index
                    ? 1
                    : Math.abs(itemIndex - index) === 1
                      ? 0.35
                      : 0;
                setMagnet(itemIndex, factor);
              });
            }}
            onBlur={resetMagnet}
            onClick={() => onSelect(index)}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight") {
                event.preventDefault();
                moveSelection(index + 1);
              } else if (event.key === "ArrowLeft") {
                event.preventDefault();
                moveSelection(index - 1);
              } else if (event.key === "Home") {
                event.preventDefault();
                moveSelection(0);
              } else if (event.key === "End") {
                event.preventDefault();
                moveSelection(items.length - 1);
              }
            }}
          >
            <span className={styles.surface} aria-hidden="true">
              <Image src={item.src} alt="" fill sizes="220px" />
              <span className={styles.scrim} />
              <span className={styles.copy}>
                <strong>{item.label}</strong>
                {item.meta ? <small>{item.meta}</small> : null}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
