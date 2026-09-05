"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// three.js touches `window` on import, so the shader canvas is client-only.
const Silk = dynamic(() => import("@/components/Silk"), { ssr: false });

type ShaderBackdropProps = {
  /** Base colour fed to the shader. Keep it dark — this sits behind text. */
  color?: string;
  speed?: number;
  scale?: number;
  noiseIntensity?: number;
  rotation?: number;
  /** Opacity of the shader layer itself. */
  intensity?: number;
  /** Radial mask so the shader fades out before it reaches the copy. */
  mask?: "top" | "center" | "bottom" | "none";
  className?: string;
};

const MASKS: Record<string, string> = {
  top: "radial-gradient(120% 90% at 50% 0%, #000 0%, #000 42%, transparent 78%)",
  center: "radial-gradient(90% 70% at 50% 50%, #000 0%, #000 38%, transparent 76%)",
  bottom: "radial-gradient(120% 90% at 50% 100%, #000 0%, #000 42%, transparent 78%)",
  none: "",
};

/**
 * A GLSL shader plane used as a section backdrop.
 *
 * It only mounts once the section is actually on screen, and stays unmounted
 * entirely for visitors who ask for reduced motion — those get the static
 * gradient underneath instead, which is why the wrapper always paints one.
 */
export function ShaderBackdrop({
  color = "#1b3350",
  speed = 3.2,
  scale = 1.4,
  noiseIntensity = 1.2,
  rotation = 0,
  intensity = 0.55,
  mask = "top",
  className,
}: ShaderBackdropProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => setActive(entry.isIntersecting),
      { rootMargin: "200px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const maskImage = MASKS[mask];

  return (
    <div
      ref={ref}
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      {active ? (
        <div
          className="absolute inset-0 transition-opacity duration-1000"
          style={{
            opacity: intensity,
            maskImage: maskImage || undefined,
            WebkitMaskImage: maskImage || undefined,
          }}
        >
          <Silk
            color={color}
            speed={speed}
            scale={scale}
            noiseIntensity={noiseIntensity}
            rotation={rotation}
          />
        </div>
      ) : null}
    </div>
  );
}
