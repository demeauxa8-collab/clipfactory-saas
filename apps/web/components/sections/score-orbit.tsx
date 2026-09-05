"use client";

import { motion, useReducedMotion } from "motion/react";
import { Flame, Heart, Eye, Target } from "lucide-react";
import { Container } from "@/components/ui/container";
import { OrbitingCircles } from "@/components/ui/orbiting-circles";
import { AnimatedCircularProgressBar } from "@/components/ui/animated-circular-progress-bar";
import { Reveal } from "@/components/visuals/reveal";

const SCORES = [
  { label: "Hook", value: 94, note: "Opens on the objection, not the intro" },
  { label: "Emotion", value: 88, note: "Frustration → relief inside 30s" },
  { label: "Visual proof", value: 81, note: "The dashboard is on screen for it" },
  { label: "Goal fit", value: 92, note: "Matches the founder series you set" },
];

export function ScoreOrbit() {
  const reduced = useReducedMotion();

  return (
    <section className="relative overflow-hidden border-b border-white/[0.06] py-24 md:py-32">
      <Container>
        <div className="grid items-center gap-16 lg:grid-cols-2 lg:gap-20">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4da3ff]">
              The score
            </span>
            <h2 className="mt-4 text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
              Four numbers, each one explained
            </h2>
            <p className="mt-5 max-w-lg text-[17px] leading-relaxed text-white/50">
              You should never have to guess why a clip was chosen. Every clip
              ships with its reasoning, so you can overrule it in one read.
            </p>

            <ul className="mt-10 space-y-3">
              {SCORES.map((s, i) => (
                <Reveal
                  as="li"
                  key={s.label}
                  x={-16}
                  y={0}
                  delay={i * 0.08}
                  className="flex items-center gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4"
                >
                  <span className="w-24 shrink-0 text-[13.5px] font-medium text-white/80">
                    {s.label}
                  </span>
                  <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.07]">
                    <motion.span
                      initial={reduced ? false : { width: 0 }}
                      animate={{ width: `${s.value}%` }}
                      transition={{ delay: 0.35 + i * 0.08, duration: 0.9, ease: "easeOut" }}
                      className="absolute inset-y-0 left-0 rounded-full bg-[linear-gradient(90deg,#0a84ff,#7dd3fc)]"
                    />
                  </span>
                  <span className="w-8 shrink-0 text-right font-mono text-[13px] text-white/55">
                    {s.value}
                  </span>
                </Reveal>
              ))}
            </ul>
          </div>

          <div className="relative flex h-[420px] items-center justify-center">
            <div
              aria-hidden
              className="absolute size-72 rounded-full bg-[radial-gradient(circle,rgba(10,132,255,0.16),transparent_68%)] blur-2xl"
            />

            <AnimatedCircularProgressBar
              max={100}
              min={0}
              value={94}
              gaugePrimaryColor="#0a84ff"
              gaugeSecondaryColor="rgba(255,255,255,0.08)"
              className="size-40 text-white"
            />

            {!reduced ? (
              <>
                <OrbitingCircles radius={130} duration={26} iconSize={40}>
                  {[Flame, Heart, Eye, Target].map((Icon, i) => (
                    <span
                      key={i}
                      className="grid size-10 place-items-center rounded-xl border border-white/10 bg-[#121215] text-white/70 backdrop-blur-md"
                    >
                      <Icon className="size-4" />
                    </span>
                  ))}
                </OrbitingCircles>
                <OrbitingCircles radius={190} duration={34} reverse iconSize={34}>
                  {["12:04", "26:18", "41:37"].map((t) => (
                    <span
                      key={t}
                      className="rounded-full border border-white/10 bg-[#121215] px-2.5 py-1 font-mono text-[10px] text-white/45 backdrop-blur-md"
                    >
                      {t}
                    </span>
                  ))}
                </OrbitingCircles>
              </>
            ) : null}
          </div>
        </div>

      </Container>
    </section>
  );
}
