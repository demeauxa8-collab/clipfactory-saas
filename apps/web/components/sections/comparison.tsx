"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { Check, X, ArrowRight, ShieldCheck } from "lucide-react";
import { Container } from "@/components/ui/container";
import { BorderBeam } from "@/components/ui/border-beam";
import { Reveal } from "@/components/visuals/reveal";
import { cn } from "@/lib/utils";

// Structure adapted from the 21st.dev "Us vs Them" block, restyled onto the
// ClipFactory surface and rewritten with claims we can actually stand behind.
const OURS = [
  "Reads the whole video before choosing anything",
  "Checks what is on screen, not just the transcript",
  "Joins setup, proof and payoff into one clip",
  "Takes a series goal and clips against it",
  "Explains why each clip was picked",
  "Flat 29€/month — no cut of what you earn",
  "No watermark on any paid plan",
  "Processed in the EU",
];

const THEIRS = [
  "Scores sentences in isolation",
  "Mostly text-driven, blind to the screen",
  "One continuous timestamp per clip",
  "Same output whoever the audience is",
  "A single opaque virality number",
  "Credit bundles that expire",
  "Watermarks below the paid tier",
  "Processing location often unstated",
];

function Row({ text, ok }: { text: string; ok: boolean }) {
  return (
    <li className="flex items-start gap-3">
      <span
        className={cn(
          "mt-0.5 grid size-[18px] shrink-0 place-items-center rounded-md",
          ok ? "bg-[#0a84ff]/15 text-[#4da3ff]" : "bg-white/[0.05] text-white/30",
        )}
      >
        {ok ? <Check className="size-3" /> : <X className="size-3" />}
      </span>
      <span className={cn("text-[14.5px] leading-snug", ok ? "text-white/80" : "text-white/40")}>
        {text}
      </span>
    </li>
  );
}

export function Comparison() {
  const reduced = useReducedMotion();

  return (
    <section className="relative border-b border-white/[0.06] py-24 md:py-32">
      <Container>
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3.5 py-1.5 text-[11px] font-medium uppercase tracking-[0.18em] text-white/60">
            <ShieldCheck className="size-3.5 text-[#4da3ff]" />
            Why ClipFactory
          </span>
          <h2 className="mt-5 text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
            Built differently, on purpose
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-white/50">
            A positioning comparison against how basic AI clippers typically
            behave — not a claim that every tool on the market works this way.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Reveal className="relative overflow-hidden rounded-[1.75rem] border border-[#0a84ff]/30 bg-[linear-gradient(165deg,rgba(10,132,255,0.08),rgba(14,14,17,0.92))] p-8">
            <BorderBeam size={200} duration={10} colorFrom="#0a84ff" colorTo="#7dd3fc" />
            <div className="flex items-center gap-2.5">
              <h3 className="text-[17px] font-semibold text-white">ClipFactory</h3>
              <span className="rounded-full bg-[#0a84ff]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#4da3ff]">
                What you get
              </span>
            </div>
            <p className="mt-2.5 text-[14px] text-white/45">
              Context first, then the cut — and it tells you what it was thinking.
            </p>

            <ul className="mt-7 flex flex-col gap-3.5">
              {OURS.map((t) => (
                <Row key={t} text={t} ok />
              ))}
            </ul>

            <Link
              href="/login"
              className="mt-8 flex h-12 items-center justify-center gap-2 rounded-full bg-[#0a84ff] text-[15px] font-semibold text-white shadow-[0_16px_40px_-16px_rgba(10,132,255,0.9)] transition-transform duration-300 hover:scale-[1.02]"
            >
              Start clipping
              <ArrowRight className="size-4" />
            </Link>
          </Reveal>

          <Reveal delay={0.1} className="rounded-[1.75rem] border border-white/[0.08] bg-[#0e0e11] p-8">
            <h3 className="text-[17px] font-semibold text-white/70">A basic AI clipper</h3>
            <p className="mt-2.5 text-[14px] text-white/35">
              Fast, cheap, and frequently confident about the wrong 30 seconds.
            </p>

            <ul className="mt-7 flex flex-col gap-3.5">
              {THEIRS.map((t) => (
                <Row key={t} text={t} ok={false} />
              ))}
            </ul>

            <p className="mt-8 flex h-12 items-center justify-center rounded-full border border-white/[0.07] text-[13px] text-white/30">
              Spotted a weak claim? Tell us.
            </p>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
