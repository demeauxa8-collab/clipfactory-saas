"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, Play, Link as LinkIcon } from "lucide-react";
import { Container } from "@/components/ui/container";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { AnimatedShinyText } from "@/components/ui/animated-shiny-text";
import { GridPattern } from "@/components/ui/grid-pattern";
import { ShaderBackdrop } from "@/components/visuals/shader-backdrop";
import { ClipStack } from "@/components/sections/clip-stack";
import { cn } from "@/lib/utils";

const PROOF = [
  "300 video minutes",
  "No watermark",
  "EU hosted",
];

export function Hero() {
  const reduced = useReducedMotion();

  // One spring, reused — every element enters on the same physical curve.
  const rise = (delay: number) => ({
    initial: reduced ? false : { opacity: 0, y: 22 },
    animate: { opacity: 1, y: 0 },
    transition: { type: "spring" as const, stiffness: 130, damping: 20, delay },
  });

  return (
    <section className="relative isolate overflow-hidden border-b border-white/[0.06]">
      <ShaderBackdrop
        color="#22507f"
        speed={2.4}
        scale={1.3}
        noiseIntensity={1}
        intensity={0.5}
        mask="top"
      />

      <GridPattern
        width={64}
        height={64}
        className={cn(
          "absolute inset-0 -z-10 h-full w-full fill-white/[0.02] stroke-white/[0.045]",
          "[mask-image:radial-gradient(110%_75%_at_50%_0%,#000_35%,transparent_75%)]",
        )}
      />

      {/* Grounds the section so copy never floats on raw shader noise. */}
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 h-80 bg-[linear-gradient(180deg,transparent,var(--background))]"
      />
      <div
        aria-hidden
        className="absolute inset-0 bg-[radial-gradient(85%_75%_at_18%_52%,rgba(11,11,13,0.97)_0%,rgba(11,11,13,0.82)_38%,transparent_72%)]"
      />

      <Container className="relative py-24 md:py-32 lg:py-36">
        <div className="grid items-center gap-16 lg:grid-cols-12 lg:gap-12">
          <div className="lg:col-span-7">
            <motion.div {...rise(0)}>
              <div className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-1 py-1 backdrop-blur-md">
                <span className="ml-2 mr-2 flex h-1.5 w-1.5 shrink-0 rounded-full bg-[#0a84ff] shadow-[0_0_10px_2px_rgba(10,132,255,0.7)]" />
                <AnimatedShinyText className="mr-3 text-[11px] font-medium uppercase tracking-[0.18em] text-white/75">
                  AI clip maker for long videos
                </AnimatedShinyText>
              </div>
            </motion.div>

            <motion.h1
              {...rise(0.08)}
              className="mt-7 max-w-[15ch] text-balance text-[clamp(2.7rem,5.4vw,4.4rem)] font-semibold leading-[0.98] tracking-[-0.035em] text-white"
            >
              Turn long videos into{" "}
              <span className="whitespace-nowrap text-[#4da3ff]">
                clips that land
              </span>
              <span aria-hidden>.</span>
            </motion.h1>

            <motion.p
              {...rise(0.16)}
              className="mt-8 max-w-xl text-[17px] leading-relaxed text-white/55 md:text-lg"
            >
              Paste a YouTube or Vimeo link and set the goal for your series.
              ClipFactory watches the whole video — what is said and what is on
              screen — then joins setup, proof and payoff into vertical clips
              you can post as they are.
            </motion.p>

            <motion.div {...rise(0.24)} className="mt-10">
              <form
                action="/login"
                className="group flex w-full max-w-xl items-center gap-2 rounded-full border border-white/12 bg-white/[0.04] p-1.5 backdrop-blur-xl transition-colors focus-within:border-[#0a84ff]/60 focus-within:bg-white/[0.06]"
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-full text-white/35">
                  <LinkIcon className="h-4 w-4" />
                </span>
                <input
                  type="url"
                  name="source"
                  inputMode="url"
                  placeholder="Paste a YouTube or Vimeo link"
                  aria-label="Video link"
                  className="min-w-0 flex-1 bg-transparent text-[15px] text-white placeholder:text-white/35 focus:outline-none"
                />
                <ShimmerButton
                  type="submit"
                  shimmerColor="#9ecbff"
                  background="#0a84ff"
                  shimmerDuration="2.6s"
                  className="h-11 shrink-0 px-6 text-[14.5px] font-semibold shadow-[0_16px_40px_-16px_rgba(10,132,255,0.9)]"
                >
                  Get clips
                  <ArrowRight className="ml-2 h-4 w-4" />
                </ShimmerButton>
              </form>

              <Link
                href="#how-it-works"
                className="group mt-5 inline-flex items-center gap-2.5 text-[14.5px] font-medium text-white/55 transition-colors hover:text-white"
              >
                <span className="grid h-7 w-7 place-items-center rounded-full border border-white/12 bg-white/[0.05] transition-transform group-hover:scale-110">
                  <Play className="h-2.5 w-2.5 fill-current" />
                </span>
                See how it works
              </Link>
            </motion.div>

            <motion.ul
              {...rise(0.32)}
              className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3 text-[13px] text-white/40"
            >
              <li className="font-medium text-white/70">29€/month</li>
              {PROOF.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <span aria-hidden className="h-1 w-1 rounded-full bg-white/25" />
                  {item}
                </li>
              ))}
            </motion.ul>
          </div>

          <div className="lg:col-span-5">
            <ClipStack />
          </div>
        </div>
      </Container>
    </section>
  );
}
