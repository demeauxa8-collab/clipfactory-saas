/**
 * Subtle dotted grid background for the hero — pure CSS via radial-gradient.
 * No image, no library, fades to transparent at the edges.
 */
export function HeroGrid() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
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
      <div
        className="absolute inset-x-0 top-0 h-[480px] opacity-50"
        style={{
          background:
            "radial-gradient(ellipse 60% 60% at 50% 0%, var(--color-brand-soft) 0%, transparent 70%)",
        }}
      />
    </div>
  );
}
