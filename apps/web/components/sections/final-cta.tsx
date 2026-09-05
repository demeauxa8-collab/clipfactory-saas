"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Particles } from "@/components/ui/particles";
import { VisibilityGate } from "@/components/visuals/visibility-gate";
import { ShaderBackdrop } from "@/components/visuals/shader-backdrop";
import { Reveal } from "@/components/visuals/reveal";

export function FinalCta() {
  const reduced = useReducedMotion();

  return (
    <section className="relative isolate overflow-hidden py-28 md:py-36">
      <ShaderBackdrop
        color="#1d4670"
        speed={2.2}
        scale={1.7}
        noiseIntensity={1}
        intensity={0.8}
        mask="bottom"
      />
      <VisibilityGate className="-z-10">
        <Particles
          className="absolute inset-0"
          quantity={55}
          staticity={45}
          ease={60}
          color="#7dd3fc"
        />
      </VisibilityGate>

      <Container className="relative">
        <Reveal className="mx-auto max-w-2xl text-center">
          <h2 className="text-[clamp(2.2rem,4.4vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.035em] text-white">
            Your next series is
            <br />
            already in that video.
          </h2>
          <p className="mx-auto mt-6 max-w-lg text-[17px] leading-relaxed text-white/55">
            Paste one link and see what comes back. 29€ a month, 300 video
            minutes, no watermark and nothing taken from what you earn.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/login"
              className="group inline-flex h-13 items-center gap-2 rounded-full bg-white px-8 py-3.5 text-[15px] font-semibold text-black transition-transform duration-300 hover:scale-[1.03]"
            >
              Start clipping
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/pricing"
              className="inline-flex h-13 items-center rounded-full border border-white/15 bg-white/[0.04] px-7 py-3.5 text-[15px] font-medium text-white/85 backdrop-blur-md transition-colors hover:bg-white/[0.09]"
            >
              See pricing
            </Link>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
