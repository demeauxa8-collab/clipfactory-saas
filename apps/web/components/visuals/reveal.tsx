"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";
import { useEffect, useRef, useState } from "react";

type RevealProps = {
  children: React.ReactNode;
  className?: string;
  /** Seconds to wait once the element enters the viewport. */
  delay?: number;
  /** Distance travelled on entry, in px. */
  y?: number;
  x?: number;
  as?: "div" | "li" | "p" | "span" | "article";
} & Omit<HTMLMotionProps<"div">, "children" | "initial" | "animate">;

/**
 * Scroll-entry animation built on a plain IntersectionObserver.
 *
 * Motion's own `whileInView` left large parts of this page stuck at opacity 0
 * — verified in a clean headless run, with reduced-motion off — and content
 * that never appears is far worse than content that never animates. So the
 * observer is ours, and it fails open: the element is revealed on any doubt
 * (no observer support, an error, or a two-second timeout), never hidden.
 */
export function Reveal({
  children,
  className,
  delay = 0,
  y = 22,
  x = 0,
  as = "div",
  ...rest
}: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }

    // Anything already on screen at mount shows immediately.
    const rect = node.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      setShown(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { threshold: 0.05, rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(node);

    // Fail open — if nothing ever fires, the copy still has to be readable.
    const failsafe = window.setTimeout(() => setShown(true), 2500);

    return () => {
      observer.disconnect();
      window.clearTimeout(failsafe);
    };
  }, []);

  const Tag = motion[as] as typeof motion.div;

  if (reduced) {
    return (
      <Tag ref={ref} className={className} {...rest}>
        {children}
      </Tag>
    );
  }

  return (
    <Tag
      ref={ref}
      className={className}
      initial={{ opacity: 0, y, x }}
      animate={shown ? { opacity: 1, y: 0, x: 0 } : { opacity: 0, y, x }}
      transition={{ type: "spring", stiffness: 120, damping: 20, delay }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
