"use client";

import { Marquee } from "@/components/ui/marquee";

// Placeholder wordmarks until real customer logos exist — they read as a
// scanning band of source types rather than claiming customers we don't have.
const SOURCES = [
  "Podcasts",
  "Webinars",
  "Interviews",
  "Conference talks",
  "Course modules",
  "Livestreams",
  "Panel debates",
  "Product demos",
];

export function LogoBand() {
  return (
    <section className="relative border-b border-white/[0.06] py-10">
      <div className="relative">
        <Marquee pauseOnHover className="[--duration:38s] [--gap:3.5rem]">
          {SOURCES.map((s) => (
            <span
              key={s}
              className="flex items-center gap-3.5 text-[15px] font-medium tracking-[-0.01em] text-white/30 transition-colors hover:text-white/60"
            >
              <span aria-hidden className="h-1 w-1 rounded-full bg-[#0a84ff]/60" />
              {s}
            </span>
          ))}
        </Marquee>
        {/* Fade the band into the page rather than letting it hit the edges. */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-32 bg-[linear-gradient(90deg,var(--background),transparent)]" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-32 bg-[linear-gradient(270deg,var(--background),transparent)]" />
      </div>
    </section>
  );
}
