"use client";

import { motion, useReducedMotion } from "motion/react";
import { Eye, Layers, Target, Gauge, ShieldCheck } from "lucide-react";
import { Container } from "@/components/ui/container";
import { MagicCard } from "@/components/ui/magic-card";
import { Meteors } from "@/components/ui/meteors";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Reveal } from "@/components/visuals/reveal";
import { cn } from "@/lib/utils";

function Cell({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <MagicCard
      gradientColor="#0a84ff"
      gradientOpacity={0.12}
      gradientFrom="#0a84ff"
      gradientTo="#7dd3fc"
      className={cn(
        "group relative overflow-hidden rounded-[1.75rem] border border-white/[0.08] bg-[#0e0e11] p-0",
        className,
      )}
    >
      <div className="relative z-10 flex h-full flex-col p-7">{children}</div>
    </MagicCard>
  );
}

function CellHead({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <>
      <span className="grid size-10 place-items-center rounded-xl border border-white/10 bg-white/[0.05] text-[#4da3ff]">
        <Icon className="size-[18px]" />
      </span>
      <h3 className="mt-5 text-[19px] font-semibold tracking-[-0.02em] text-white">
        {title}
      </h3>
      <p className="mt-2.5 text-[14.5px] leading-relaxed text-white/45">{body}</p>
    </>
  );
}

export function FeatureBento() {
  const reduced = useReducedMotion();

  return (
    <section className="relative border-b border-white/[0.06] py-24 md:py-32">
      <Container>
        <div className="max-w-2xl">
          <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4da3ff]">
            Why it is better
          </span>
          <h2 className="mt-4 text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
            A clipper that watched the whole thing
          </h2>
        </div>

        <Reveal y={24} className="mt-14 grid gap-4 md:grid-cols-3 md:grid-rows-2">
          <Cell className="md:col-span-2">
            <CellHead
              icon={Layers}
              title="Whole-video context"
              body="Most tools score sentences in isolation. ClipFactory holds the full arc in memory, so a callback at 41:00 still knows what was set up at 12:00."
            />
            {/* The bar strip is the transcript; the lit span is the clip it kept. */}
            <div className="mt-auto flex items-end gap-[3px] pt-8">
              {Array.from({ length: 52 }).map((_, i) => {
                const kept = i > 17 && i < 27;
                return (
                  <motion.span
                    key={i}
                    initial={reduced ? false : { scaleY: 0.25 }}
                    animate={{ scaleY: 1 }}
                    transition={{ delay: i * 0.012, duration: 0.4 }}
                    className={cn(
                      "w-full origin-bottom rounded-full",
                      kept ? "bg-[#0a84ff]" : "bg-white/[0.13]",
                    )}
                    style={{
                      height: kept
                        ? 20 + ((i * 13) % 22)
                        : 6 + ((i * 7) % 14),
                    }}
                  />
                );
              })}
            </div>
          </Cell>

          <Cell>
            <Meteors number={14} />
            <CellHead
              icon={Eye}
              title="On-screen vision"
              body="It checks what is actually visible — the product, the face, the reaction, the proof — so a clip that only reads well never ships."
            />
          </Cell>

          <Cell>
            <CellHead
              icon={Target}
              title="Your series goal"
              body="Tell it who the clips are for. The same video yields a different set for a founder audience than for a cold one."
            />
          </Cell>

          <Cell>
            <CellHead
              icon={Gauge}
              title="Scores you can read"
              body="Hook, emotion, visual proof and goal fit — each one explained in a line, never a single opaque number."
            />
            <div className="mt-auto flex items-baseline gap-1.5 pt-8">
              <NumberTicker
                value={94}
                className="text-4xl font-semibold tracking-[-0.04em] text-white"
              />
              <span className="text-sm text-white/35">/ 100 hook score</span>
            </div>
          </Cell>

          <Cell>
            <CellHead
              icon={ShieldCheck}
              title="Yours to keep"
              body="No watermark, no revenue share, EU hosted. Cancel whenever — the clips you already made stay yours."
            />
          </Cell>
        </Reveal>
      </Container>
    </section>
  );
}
