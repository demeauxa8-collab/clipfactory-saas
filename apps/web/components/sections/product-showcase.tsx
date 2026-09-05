"use client";

import { motion, useReducedMotion } from "motion/react";
import { Play, Sparkles, Check } from "lucide-react";
import { Container } from "@/components/ui/container";
import { BorderBeam } from "@/components/ui/border-beam";
import { Reveal } from "@/components/visuals/reveal";
import { cn } from "@/lib/utils";

const ROWS = [
  { t: "12:04 → 12:41", title: "The pricing objection, answered", score: 94, state: "ready" },
  { t: "26:18 → 26:52", title: "Why most funnels leak", score: 88, state: "ready" },
  { t: "41:37 → 42:09", title: "The 3-step teardown", score: 81, state: "rendering" },
  { t: "58:02 → 58:44", title: "What nobody tells juniors", score: 76, state: "queued" },
];

/**
 * The dashboard, drawn in markup rather than screenshotted — it stays crisp at
 * every width and cannot drift out of date the way a PNG does.
 */
export function ProductShowcase() {
  const reduced = useReducedMotion();

  return (
    <section className="relative border-b border-white/[0.06] py-20 md:py-28">
      <Container>
        <Reveal y={40} className="relative mx-auto max-w-5xl">
          <div
            aria-hidden
            className="absolute -inset-x-10 -top-10 bottom-0 rounded-[3rem] bg-[radial-gradient(70%_50%_at_50%_0%,rgba(10,132,255,0.14),transparent_70%)] blur-2xl"
          />

          <div className="relative overflow-hidden rounded-[1.75rem] border border-white/[0.09] bg-[#0d0d10] shadow-[0_50px_140px_-50px_rgba(0,0,0,1)]">
            {/* Window chrome */}
            <div className="flex items-center gap-3 border-b border-white/[0.07] px-5 py-3.5">
              <div className="flex gap-1.5">
                {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
                  <span key={c} className="size-2.5 rounded-full" style={{ background: c }} />
                ))}
              </div>
              <div className="mx-auto flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.03] px-4 py-1 font-mono text-[11px] text-white/35">
                app.clipfactory.io / series
              </div>
            </div>

            <div className="grid gap-0 md:grid-cols-[1fr_1.35fr]">
              {/* Source panel */}
              <div className="border-white/[0.07] p-6 md:border-r">
                <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/30">
                  Source
                </span>
                <div className="mt-4 aspect-video overflow-hidden rounded-xl border border-white/[0.08] bg-[#08080a]">
                  <div className="relative h-full w-full bg-[linear-gradient(140deg,rgba(10,132,255,0.14),transparent_60%)]">
                    <div className="absolute inset-0 grid place-items-center">
                      <span className="grid size-10 place-items-center rounded-full border border-white/15 bg-black/40 backdrop-blur">
                        <Play className="size-3.5 fill-white/80 text-white/80" />
                      </span>
                    </div>
                    <span className="absolute bottom-2 right-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-white/60">
                      1:04:22
                    </span>
                  </div>
                </div>

                <p className="mt-4 text-[13px] font-medium text-white/70">
                  Series goal
                </p>
                <p className="mt-1.5 rounded-lg border border-white/[0.07] bg-white/[0.02] p-3 text-[12.5px] leading-relaxed text-white/45">
                  Clips for founders who already know the basics — skip the
                  intros, keep the objections.
                </p>

                <div className="mt-4 flex items-center gap-2 text-[12px] text-[#4da3ff]">
                  <Sparkles className="size-3.5" />
                  4 passes complete
                </div>
              </div>

              {/* Results panel */}
              <div className="p-6">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/30">
                    Clips found
                  </span>
                  <span className="font-mono text-[11px] text-white/30">4 of 4</span>
                </div>

                <ul className="mt-4 space-y-2">
                  {ROWS.map((r, i) => (
                    <Reveal
                      as="li"
                      key={r.title}
                      x={14}
                      y={0}
                      delay={0.15 + i * 0.08}
                      className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3"
                    >
                      <span className="aspect-[9/16] w-8 shrink-0 rounded-md border border-white/[0.08] bg-[linear-gradient(180deg,rgba(10,132,255,0.2),transparent)]" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13.5px] font-medium text-white/85">
                          {r.title}
                        </span>
                        <span className="mt-0.5 block font-mono text-[10.5px] text-white/30">
                          {r.t}
                        </span>
                      </span>
                      <span
                        className={cn(
                          "shrink-0 rounded-full px-2 py-0.5 font-mono text-[11px] font-semibold",
                          r.score >= 90
                            ? "bg-[#0a84ff]/15 text-[#4da3ff]"
                            : "bg-white/[0.06] text-white/45",
                        )}
                      >
                        {r.score}
                      </span>
                      <span className="w-16 shrink-0 text-right text-[10.5px] text-white/30">
                        {r.state === "ready" ? (
                          <span className="inline-flex items-center gap-1 text-[#34c759]">
                            <Check className="size-3" /> ready
                          </span>
                        ) : (
                          r.state
                        )}
                      </span>
                    </Reveal>
                  ))}
                </ul>
              </div>
            </div>

            <BorderBeam size={260} duration={12} colorFrom="#0a84ff" colorTo="#7dd3fc" />
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
