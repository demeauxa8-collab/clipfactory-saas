"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Link as LinkIcon } from "lucide-react";

/**
 * A single persistent way to start, surfaced once the hero's own field has
 * scrolled away and hidden again at the footer so it never covers the last CTA.
 */
export function StickyCta() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      const max = document.body.scrollHeight - window.innerHeight;
      setShow(y > 900 && y < max - 700);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <AnimatePresence>
      {show ? (
        <motion.div
          initial={{ y: 90, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 90, opacity: 0 }}
          transition={{ type: "spring", stiffness: 190, damping: 24 }}
          className="fixed inset-x-0 bottom-5 z-40 flex justify-center px-4"
        >
          <form
            action="/login"
            className="flex w-full max-w-lg items-center gap-2 rounded-full border border-white/12 bg-black/70 p-1.5 shadow-[0_24px_70px_-20px_rgba(0,0,0,0.95)] backdrop-blur-xl [backdrop-filter:saturate(180%)_blur(22px)]"
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
              className="min-w-0 flex-1 bg-transparent text-[14.5px] text-white placeholder:text-white/35 focus:outline-none"
            />
            <button
              type="submit"
              className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full bg-[#0a84ff] px-5 text-[14px] font-semibold text-white transition-transform duration-300 hover:scale-[1.03]"
            >
              Get clips
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </form>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
