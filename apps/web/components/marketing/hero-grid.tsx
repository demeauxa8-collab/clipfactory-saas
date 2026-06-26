/**
 * Premium hero backdrop — pure CSS, no image, no library.
 * Layers: a fine dotted grid masked to a soft ellipse, plus two slow-drifting
 * aurora glows in the brand emerald/teal family (never AI-purple, per the
 * skill's colour rules). The drift collapses to static under reduced motion.
 */
export function HeroGrid() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      {/* Fine dotted grid, faded toward the edges */}
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, var(--color-border) 1px, transparent 0)",
          backgroundSize: "28px 28px",
          maskImage:
            "radial-gradient(ellipse at 50% 35%, black 30%, transparent 75%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at 50% 35%, black 30%, transparent 75%)",
        }}
      />
      {/* Primary brand glow */}
      <div
        className="aurora absolute inset-x-0 top-[-10%] h-[520px] opacity-60"
        style={{
          background:
            "radial-gradient(ellipse 56% 60% at 50% 0%, var(--color-brand-soft) 0%, transparent 70%)",
        }}
      />
      {/* Secondary cool glow, offset, slower-feeling drift */}
      <div
        className="aurora absolute left-[-8%] top-[8%] h-[360px] w-[420px] opacity-40 blur-2xl"
        style={{
          animationDelay: "-7s",
          background:
            "radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--color-brand-2) 30%, transparent) 0%, transparent 70%)",
        }}
      />
      {/* Subtle top vignette for depth */}
      <div
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, color-mix(in srgb, var(--color-brand) 40%, transparent), transparent)",
        }}
      />
    </div>
  );
}
