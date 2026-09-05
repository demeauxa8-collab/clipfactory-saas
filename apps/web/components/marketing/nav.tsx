"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Menu, X } from "lucide-react";
import { ScrollProgress } from "@/components/ui/scroll-progress";
import { NAV_PRIMARY, SITE } from "@/lib/site";
import { cn } from "@/lib/utils";

export function MarketingNav() {
  const pathname = usePathname();
  const reduced = useReducedMotion();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  // The bar is a floating pill that only materialises once you leave the hero,
  // so the shader reads clean at the top of the page.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => setOpen(false), [pathname]);

  return (
    <>
      <ScrollProgress className="z-50 h-[2px] bg-[linear-gradient(90deg,#0a84ff,#7dd3fc)]" />

      <header className="pointer-events-none fixed inset-x-0 top-0 z-40 flex justify-center px-4 pt-3 md:pt-4">
        <motion.div
          initial={reduced ? false : { y: -18, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 140, damping: 20 }}
          className={cn(
            "pointer-events-auto flex w-full max-w-5xl items-center justify-between gap-2 rounded-full px-2 py-2 transition-all duration-500",
            scrolled
              ? "border border-white/10 bg-black/55 shadow-[0_18px_50px_-24px_rgba(0,0,0,0.95)] backdrop-blur-xl [backdrop-filter:saturate(180%)_blur(22px)]"
              : "border border-transparent bg-transparent",
          )}
        >
          <Link href="/" className="flex shrink-0 items-center gap-2.5 pl-2 pr-1">
            <span
              aria-hidden
              className="relative grid h-6 w-6 place-items-center rounded-[0.55rem] border border-white/12 bg-white/[0.06]"
            >
              <span className="h-2.5 w-1 rounded-full bg-[#0a84ff] shadow-[0_0_8px_1px_rgba(10,132,255,0.8)]" />
            </span>
            <span className="text-[15px] font-semibold tracking-[-0.02em] text-white">
              {SITE.name}
            </span>
          </Link>

          <nav className="hidden items-center md:flex">
            {NAV_PRIMARY.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href as never}
                  className={cn(
                    "relative inline-flex h-9 items-center rounded-full px-3.5 text-[13.5px] transition-colors",
                    active ? "text-white" : "text-white/55 hover:text-white/90",
                  )}
                >
                  {active ? (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-full bg-white/[0.09]"
                      transition={{ type: "spring", stiffness: 320, damping: 30 }}
                    />
                  ) : null}
                  <span className="relative">{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center gap-1.5">
            <Link
              href="/login"
              className="hidden h-9 items-center rounded-full px-3.5 text-[13.5px] text-white/70 transition-colors hover:text-white md:inline-flex"
            >
              Sign in
            </Link>
            <Link
              href="/login"
              className="inline-flex h-9 items-center rounded-full bg-white px-4 text-[13.5px] font-semibold text-black transition-transform duration-300 hover:scale-[1.03]"
            >
              Start clipping
            </Link>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label={open ? "Close menu" : "Open menu"}
              aria-expanded={open}
              className="grid h-9 w-9 place-items-center rounded-full border border-white/10 text-white/80 md:hidden"
            >
              {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </motion.div>
      </header>

      {open ? (
        <motion.div
          initial={reduced ? false : { opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed inset-x-4 top-20 z-40 rounded-3xl border border-white/10 bg-black/85 p-3 backdrop-blur-xl md:hidden"
        >
          {NAV_PRIMARY.map((item) => (
            <Link
              key={item.href}
              href={item.href as never}
              className="block rounded-2xl px-4 py-3 text-[15px] text-white/80 transition-colors hover:bg-white/[0.06] hover:text-white"
            >
              {item.label}
            </Link>
          ))}
          <Link
            href="/login"
            className="block rounded-2xl px-4 py-3 text-[15px] text-white/80 transition-colors hover:bg-white/[0.06] hover:text-white"
          >
            Sign in
          </Link>
        </motion.div>
      ) : null}
    </>
  );
}
