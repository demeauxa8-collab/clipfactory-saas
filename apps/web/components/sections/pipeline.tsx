"use client";

import dynamic from "next/dynamic";
import { forwardRef, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Youtube, FileText, Eye, Target, Scissors, Sparkles } from "lucide-react";
import { Container } from "@/components/ui/container";
import { AnimatedBeam } from "@/components/ui/animated-beam";
import { VisibilityGate } from "@/components/visuals/visibility-gate";
import { Reveal } from "@/components/visuals/reveal";
import { cn } from "@/lib/utils";

const PulseGrid = dynamic(() => import("@/components/originkit/pulse-grid"), {
  ssr: false,
});

const Node = forwardRef<
  HTMLDivElement,
  { className?: string; children: React.ReactNode; label?: string; lead?: boolean }
>(({ className, children, label, lead }, ref) => (
  <div className="flex flex-col items-center gap-2">
    <div
      ref={ref}
      className={cn(
        "z-10 grid size-14 place-items-center rounded-2xl border backdrop-blur-md",
        lead
          ? "border-[#0a84ff]/40 bg-[#0a84ff]/10 text-[#4da3ff] shadow-[0_0_28px_-6px_rgba(10,132,255,0.7)]"
          : "border-white/10 bg-white/[0.05] text-white/70",
        className,
      )}
    >
      {children}
    </div>
    {label ? (
      <span className="text-center text-[11px] font-medium leading-tight text-white/45">
        {label}
      </span>
    ) : null}
  </div>
));
Node.displayName = "Node";

/**
 * How the product actually works, drawn rather than listed: one source fans
 * out into the four passes that read it, and those converge back into a clip.
 * The beams carry the eye along the same path the video takes.
 */
export function Pipeline() {
  const reduced = useReducedMotion();
  const container = useRef<HTMLDivElement>(null);
  const source = useRef<HTMLDivElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const vision = useRef<HTMLDivElement>(null);
  const goal = useRef<HTMLDivElement>(null);
  const montage = useRef<HTMLDivElement>(null);
  const output = useRef<HTMLDivElement>(null);

  const passes = [
    { ref: transcript, icon: FileText, label: "Transcript" },
    { ref: vision, icon: Eye, label: "On-screen vision" },
    { ref: goal, icon: Target, label: "Series goal" },
    { ref: montage, icon: Scissors, label: "Multi-moment cut" },
  ];

  return (
    <section
      id="how-it-works"
      className="relative overflow-hidden border-b border-white/[0.06] py-24 md:py-32"
    >
      {/* Circuit board underneath — the traces read as data moving through. */}
      <VisibilityGate className="pointer-events-none opacity-[0.75] [mask-image:radial-gradient(70%_60%_at_50%_50%,#000_10%,transparent_70%)]">
        <PulseGrid
          boardColor="transparent"
          cellSize={72}
          thickness={1}
          lineColor="#141418"
          palette={["#0a84ff", "#7dd3fc"]}
          intensity={7}
          fadeIn={9}
          fadeOut={7}
          brightness={62}
        />
      </VisibilityGate>

      <Container className="relative">
        <div className="mx-auto max-w-2xl text-center">
          <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4da3ff]">
            How it works
          </span>
          <h2 className="mt-4 text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
            Four passes over the same video
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-white/50">
            A basic clipper cuts where the audio peaks. ClipFactory reads the
            words, watches the screen, weighs both against your goal, and only
            then decides where a clip starts and ends.
          </p>
        </div>

        <div
          ref={container}
          className="relative mx-auto mt-16 flex max-w-4xl items-stretch justify-between gap-6 px-2 md:mt-20"
        >
          <div className="flex flex-col justify-center">
            <Node ref={source} label="YouTube / Vimeo">
              <Youtube className="size-6" />
            </Node>
          </div>

          <div className="flex flex-col justify-center gap-6 md:gap-8">
            {passes.map(({ ref, icon: Icon, label }) => (
              <Node key={label} ref={ref} label={label}>
                <Icon className="size-5" />
              </Node>
            ))}
          </div>

          <div className="flex flex-col justify-center">
            <Node ref={output} label="Vertical clip" lead>
              <Sparkles className="size-6" />
            </Node>
          </div>

          {!reduced
            ? passes.map(({ ref, label }, i) => (
                <AnimatedBeam
                  key={`in-${label}`}
                  containerRef={container}
                  fromRef={source}
                  toRef={ref}
                  curvature={(i - 1.5) * 26}
                  pathColor="#ffffff"
                  pathOpacity={0.13}
                  pathWidth={2}
                  gradientStartColor="#0a84ff"
                  gradientStopColor="#7dd3fc"
                  duration={4.5}
                  delay={i * 0.35}
                />
              ))
            : null}

          {!reduced
            ? passes.map(({ ref, label }, i) => (
                <AnimatedBeam
                  key={`out-${label}`}
                  containerRef={container}
                  fromRef={ref}
                  toRef={output}
                  curvature={(i - 1.5) * -26}
                  pathColor="#ffffff"
                  pathOpacity={0.13}
                  pathWidth={2}
                  gradientStartColor="#7dd3fc"
                  gradientStopColor="#0a84ff"
                  duration={4.5}
                  delay={1.2 + i * 0.35}
                />
              ))
            : null}
        </div>

        <Reveal
          as="p"
          y={12}
          className="mx-auto mt-14 max-w-xl text-center text-[13px] text-white/35"
        >
          Every clip comes back with the reason it was picked — the timecodes it
          joined, and what was on screen when it did.
        </Reveal>
      </Container>
    </section>
  );
}
