"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { Check } from "lucide-react";
import { Container } from "@/components/ui/container";
import { BorderBeam } from "@/components/ui/border-beam";
import { Reveal } from "@/components/visuals/reveal";
import { cn } from "@/lib/utils";

const PLANS = [
  {
    name: "Starter",
    price: "29",
    tagline: "For one creator shipping a series every week.",
    features: [
      "300 video minutes a month",
      "Whole-video context analysis",
      "On-screen vision pass",
      "Multi-moment montage",
      "No watermark",
    ],
    cta: "Start clipping",
    lead: true,
  },
  {
    name: "Studio",
    price: "89",
    tagline: "For agencies running clips for several accounts.",
    features: [
      "1200 video minutes a month",
      "Everything in Starter",
      "Multiple series goals saved",
      "Priority rendering queue",
      "Team seats",
    ],
    cta: "Talk to us",
    lead: false,
  },
];

export function Pricing() {
  const reduced = useReducedMotion();

  return (
    <section id="pricing" className="relative border-b border-white/[0.06] py-24 md:py-32">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4da3ff]">
            Pricing
          </span>
          <h2 className="mt-4 text-[clamp(2rem,3.6vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-white">
            One price, no revenue share
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-white/50">
            You keep every clip and every view. Cancel whenever — nothing you
            already made gets locked behind the plan.
          </p>
        </div>

        <div className="mx-auto mt-14 grid max-w-4xl gap-5 md:grid-cols-2">
          {PLANS.map((plan, i) => (
            <Reveal
              key={plan.name}
              y={24}
              delay={i * 0.1}
              className={cn(
                "relative overflow-hidden rounded-[1.75rem] border p-8",
                plan.lead
                  ? "border-[#0a84ff]/30 bg-[linear-gradient(165deg,rgba(10,132,255,0.09),rgba(14,14,17,0.9))]"
                  : "border-white/[0.08] bg-[#0e0e11]",
              )}
            >
              {plan.lead ? (
                <BorderBeam size={190} duration={9} colorFrom="#0a84ff" colorTo="#7dd3fc" />
              ) : null}

              <div className="flex items-baseline justify-between">
                <h3 className="text-[17px] font-semibold text-white">{plan.name}</h3>
                {plan.lead ? (
                  <span className="rounded-full bg-[#0a84ff]/15 px-3 py-1 text-[11px] font-medium text-[#4da3ff]">
                    Most picked
                  </span>
                ) : null}
              </div>

              <p className="mt-3 text-[14px] text-white/45">{plan.tagline}</p>

              <div className="mt-7 flex items-baseline gap-1.5">
                <span className="text-5xl font-semibold tracking-[-0.04em] text-white">
                  {plan.price}€
                </span>
                <span className="text-[14px] text-white/35">/ month</span>
              </div>

              <ul className="mt-8 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-[14.5px] text-white/65">
                    <Check
                      className={cn(
                        "mt-0.5 size-4 shrink-0",
                        plan.lead ? "text-[#4da3ff]" : "text-white/30",
                      )}
                    />
                    {f}
                  </li>
                ))}
              </ul>

              <Link
                href="/login"
                className={cn(
                  "mt-9 flex h-12 items-center justify-center rounded-full text-[15px] font-semibold transition-transform duration-300 hover:scale-[1.02]",
                  plan.lead
                    ? "bg-[#0a84ff] text-white shadow-[0_16px_40px_-16px_rgba(10,132,255,0.9)]"
                    : "border border-white/12 bg-white/[0.04] text-white hover:bg-white/[0.08]",
                )}
              >
                {plan.cta}
              </Link>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}
