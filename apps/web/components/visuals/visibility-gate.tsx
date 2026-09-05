"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Mounts its children only while the wrapper is near the viewport.
 *
 * Every animated canvas on this page owns a requestAnimationFrame loop that
 * keeps running whether or not it is on screen. With several of them alive at
 * once the compositor stalls, so each one is gated: off screen means unmounted,
 * which releases the WebGL context too. Reduced-motion visitors never mount it.
 */
export function VisibilityGate({
  children,
  className,
  rootMargin = "160px",
  respectReducedMotion = true,
}: {
  children: React.ReactNode;
  className?: string;
  rootMargin?: string;
  respectReducedMotion?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (
      respectReducedMotion &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [rootMargin, respectReducedMotion]);

  return (
    <div ref={ref} className={cn("absolute inset-0", className)} aria-hidden>
      {visible ? children : null}
    </div>
  );
}
