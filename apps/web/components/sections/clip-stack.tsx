"use client";

import { motion, useReducedMotion } from "motion/react";
import { Sparkles, Play } from "lucide-react";
import { BorderBeam } from "@/components/ui/border-beam";
import { cn } from "@/lib/utils";

type Clip = {
  title: string;
  score: number;
  timecode: string;
  reason: string;
};

const CLIPS: Clip[] = [
  {
    title: "The pricing objection, answered",
    score: 94,
    timecode: "12:04 → 12:41",
    reason: "Setup, proof and payoff in one arc",
  },
  {
    title: "Why most funnels leak",
    score: 88,
    timecode: "26:18 → 26:52",
    reason: "Strong hook in the first second",
  },
  {
    title: "The 3-step teardown",
    score: 81,
    timecode: "41:37 → 42:09",
    reason: "Visual proof on screen",
  },
];

/**
 * The hero's product visual: the long source video on the left resolving into
 * a stack of scored vertical clips. This IS the product in one image, so it
 * earns the space a generic screenshot would waste.
 */
export function ClipStack() {
  const reduced = useReducedMotion();

  return (
    <div className="relative mx-auto w-full max-w-[420px] [perspective:1600px]">
      {/* Ambient bloom behind the stack — sells depth without a hard glow. */}
      <div
        aria-hidden
        className="absolute -inset-x-16 -inset-y-10 rounded-[3rem] bg-[radial-gradient(60%_50%_at_50%_40%,rgba(10,132,255,0.18),transparent_70%)] blur-2xl"
      />

      <div
        className="relative"
        style={{ transformStyle: "preserve-3d" }}
      >
        {CLIPS.map((clip, i) => {
          const isLead = i === 0;
          return (
            <motion.article
              key={clip.title}
              initial={reduced ? false : { opacity: 0, y: 28, rotateY: -14 }}
              animate={{ opacity: 1, y: 0, rotateY: 0 }}
              transition={{
                type: "spring",
                stiffness: 120,
                damping: 18,
                delay: 0.25 + i * 0.12,
              }}
              className={cn(
                "absolute left-0 right-0 origin-top rounded-[1.75rem] border border-white/10",
                "bg-[linear-gradient(160deg,rgba(28,28,32,0.96),rgba(11,11,13,0.96))]",
                "shadow-[0_30px_80px_-30px_rgba(0,0,0,0.9)] backdrop-blur-xl",
              )}
              style={{
                top: i * 168,
                zIndex: CLIPS.length - i,
                scale: 1 - i * 0.035,
                filter: isLead ? undefined : `brightness(${1 - i * 0.05})`,
                opacity: 1 - i * 0.05,
              }}
            >
              <div className="flex items-start gap-4 p-5">
                {/* 9:16 frame — the format the product actually ships. */}
                <div className="relative aspect-[9/16] w-[64px] shrink-0 overflow-hidden rounded-xl border border-white/10 bg-[#08080a]">
                  <div className="absolute inset-x-0 top-0 h-1/2 bg-[linear-gradient(180deg,rgba(10,132,255,0.22),transparent)]" />
                  <div className="absolute inset-x-2 bottom-2 space-y-1">
                    <span className="block h-1.5 w-full rounded-full bg-white/70" />
                    <span className="block h-1.5 w-2/3 rounded-full bg-white/30" />
                  </div>
                  {isLead && !reduced ? (
                    <motion.span
                      aria-hidden
                      className="absolute inset-x-0 h-px bg-[linear-gradient(90deg,transparent,rgba(10,132,255,0.9),transparent)]"
                      animate={{ top: ["12%", "88%", "12%"] }}
                      transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
                    />
                  ) : null}
                  <div className="absolute inset-0 grid place-items-center">
                    <Play className="h-4 w-4 fill-white/80 text-white/80" />
                  </div>
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/40">
                      {clip.timecode}
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 font-mono text-[11px] font-semibold",
                        isLead
                          ? "bg-[#0a84ff]/15 text-[#4da3ff]"
                          : "bg-white/[0.06] text-white/50",
                      )}
                    >
                      {clip.score}
                    </span>
                  </div>
                  <h3 className="mt-2 truncate text-[15px] font-semibold tracking-[-0.01em] text-white">
                    {clip.title}
                  </h3>
                  <p className="mt-1 flex items-center gap-1.5 text-[12px] text-white/45">
                    <Sparkles className="h-3 w-3 shrink-0 text-[#0a84ff]" />
                    <span className="truncate">{clip.reason}</span>
                  </p>
                </div>
              </div>

              {isLead ? (
                <BorderBeam size={110} duration={7} colorFrom="#0a84ff" colorTo="#7dd3fc" />
              ) : null}
            </motion.article>
          );
        })}

        {/* Reserve the flow height the absolutely-positioned cards leave behind. */}
        <div className="invisible">
          <div className="p-5">
            <div className="aspect-[9/16] w-[64px]" />
          </div>
          <div style={{ height: (CLIPS.length - 1) * 168 }} />
        </div>
      </div>
    </div>
  );
}
