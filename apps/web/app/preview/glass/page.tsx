import Link from "next/link";

export default function GlassPreview() {
  return (
    <main
      className="relative min-h-dvh overflow-hidden text-neutral-900 dark:text-neutral-50"
      style={{
        background:
          "radial-gradient(1200px 800px at 20% -10%, rgba(52,211,153,0.18), transparent 60%), radial-gradient(900px 600px at 100% 10%, rgba(99,102,241,0.18), transparent 60%), #F5F5F7",
      }}
    >
      <DarkAdaptive />
      <Nav />
      <Hero />
      <Bento />
      <ScoreBento />
      <Pipeline />
      <Pricing />
      <Footer />
    </main>
  );
}

function DarkAdaptive() {
  return (
    <style>{`
      @media (prefers-color-scheme: dark) {
        main { background: radial-gradient(1200px 800px at 20% -10%, rgba(52,211,153,0.22), transparent 60%), radial-gradient(900px 600px at 100% 10%, rgba(99,102,241,0.22), transparent 60%), #0B0B0F !important; }
      }
    `}</style>
  );
}

function Nav() {
  return (
    <header className="sticky top-3 z-50 mx-auto mt-3 flex w-[min(960px,calc(100%-1.5rem))] items-center justify-between rounded-full border border-white/40 bg-white/50 px-3 py-2 backdrop-blur-2xl dark:border-white/10 dark:bg-white/5">
      <Link
        href="/preview"
        className="flex items-center gap-2 px-3 py-1 text-sm font-semibold"
      >
        <span
          className="inline-flex h-6 w-6 items-center justify-center rounded-lg text-white"
          style={{
            background:
              "linear-gradient(135deg,#34D399,#059669)",
            boxShadow: "0 0 0 1px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.35)",
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
            <path d="M8 5v14l11-7L8 5z" fill="currentColor" />
          </svg>
        </span>
        ClipFactory
      </Link>
      <nav className="hidden gap-1 text-sm text-neutral-700 dark:text-neutral-300 md:flex">
        <a href="#bento" className="rounded-full px-3 py-1.5 hover:bg-white/60 dark:hover:bg-white/10">Product</a>
        <a href="#pipeline" className="rounded-full px-3 py-1.5 hover:bg-white/60 dark:hover:bg-white/10">How it works</a>
        <a href="#pricing" className="rounded-full px-3 py-1.5 hover:bg-white/60 dark:hover:bg-white/10">Pricing</a>
      </nav>
      <Link
        href="/login"
        className="rounded-full bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white shadow-sm dark:bg-white dark:text-neutral-900"
      >
        Sign in
      </Link>
    </header>
  );
}

function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-16 pt-20 text-center md:pt-28">
      <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-white/40 bg-white/50 px-3 py-1 text-xs font-medium backdrop-blur-xl dark:border-white/10 dark:bg-white/5">
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ background: "#34D399" }}
        />
        New · Campaign-first AI clipping
      </div>
      <h1 className="mx-auto mt-7 max-w-3xl text-balance text-[clamp(2.5rem,6vw,5rem)] font-semibold leading-[1.02] tracking-[-0.03em]">
        Less random virals.
        <br />
        <span
          style={{
            background: "linear-gradient(135deg,#34D399,#10B981 40%,#6366F1)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          More clips that fit your campaign.
        </span>
      </h1>
      <p className="mx-auto mt-6 max-w-2xl text-lg text-neutral-600 dark:text-neutral-400 md:text-xl">
        Reads your brief. Maps the whole video. Finds story arcs between
        distant moments. Ships vertical shorts with a score you can argue
        with.
      </p>
      <div className="mt-9 flex flex-wrap justify-center gap-3">
        <Link
          href="/login"
          className="rounded-full bg-neutral-900 px-6 py-3 text-base font-medium text-white shadow-[0_8px_24px_-8px_rgba(0,0,0,0.35)] transition hover:translate-y-[-1px] dark:bg-white dark:text-neutral-900"
        >
          Start clipping →
        </Link>
        <a
          href="#bento"
          className="rounded-full border border-white/40 bg-white/60 px-6 py-3 text-base font-medium backdrop-blur-xl dark:border-white/10 dark:bg-white/5"
        >
          See it work
        </a>
      </div>
      <p className="mt-4 text-xs text-neutral-500">
        No watermark · EU hosted · Cancel anytime · 29€/mo
      </p>
    </section>
  );
}

function GlassCard({
  className = "",
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-3xl border border-white/40 bg-white/50 p-6 shadow-[0_2px_30px_-12px_rgba(0,0,0,0.08)] backdrop-blur-2xl dark:border-white/10 dark:bg-white/5 ${className}`}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-3xl"
        style={{
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.4), rgba(255,255,255,0) 30%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

function Bento() {
  return (
    <section id="bento" className="mx-auto max-w-6xl px-6 pb-16">
      <div className="grid auto-rows-[180px] grid-cols-6 gap-4">
        {/* Big clip preview */}
        <GlassCard className="col-span-6 row-span-2 md:col-span-4">
          <p className="text-xs uppercase tracking-wider text-neutral-500">
            Live clip preview
          </p>
          <div className="mt-4 grid gap-6 md:grid-cols-[200px_1fr]">
            <div
              className="relative aspect-[9/16] overflow-hidden rounded-2xl"
              style={{
                background:
                  "linear-gradient(180deg,#1F1F23 0%,#0F0F12 100%)",
              }}
            >
              <div className="absolute inset-x-0 top-4 mx-auto h-1 w-12 rounded-full bg-white/30" />
              <div className="absolute inset-x-4 bottom-4 text-white">
                <p className="text-[11px] text-white/60">@you · 0:08 / 0:42</p>
                <p className="mt-1 text-base font-semibold leading-snug">
                  It cost him $50k to learn that lesson.
                </p>
              </div>
              <div
                className="absolute right-3 top-3 rounded-full px-2 py-0.5 text-[10px] font-bold text-white"
                style={{ background: "#34D399" }}
              >
                91
              </div>
            </div>
            <div className="space-y-3">
              {[
                ["Hook", 95],
                ["Emotion", 88],
                ["Visual proof", 92],
                ["Campaign fit", 90],
                ["Editing", 84],
              ].map(([l, v]) => (
                <div key={l as string}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-medium">{l}</span>
                    <span className="tabular-nums text-neutral-500">{v}</span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-neutral-200/80 dark:bg-white/10">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${v}%`,
                        background:
                          "linear-gradient(90deg,#34D399,#10B981)",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>

        <GlassCard className="col-span-3 md:col-span-2">
          <p className="text-xs uppercase tracking-wider text-neutral-500">
            EU hosted
          </p>
          <p className="mt-4 text-3xl font-semibold tracking-tight">
            Frankfurt · Hetzner · R2 EU
          </p>
          <p className="mt-2 text-sm text-neutral-500">
            Source files deleted after 14 days. Clips after 60.
          </p>
        </GlassCard>

        <GlassCard className="col-span-3 md:col-span-2">
          <p className="text-xs uppercase tracking-wider text-neutral-500">
            Per clip
          </p>
          <p className="mt-4 text-3xl font-semibold tracking-tight">
            5 scores, 5 reasons
          </p>
          <p className="mt-2 text-sm text-neutral-500">
            Hook · Emotion · Visual · Fit · Editing — no black box.
          </p>
        </GlassCard>

        <GlassCard className="col-span-6 md:col-span-4">
          <p className="text-xs uppercase tracking-wider text-neutral-500">
            Story arcs
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-[1fr_auto_1fr]">
            <div
              className="rounded-2xl border border-white/40 bg-white/60 p-4 backdrop-blur-xl dark:border-white/10 dark:bg-white/5"
            >
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                02:14 · Setup
              </p>
              <p className="mt-2 font-medium leading-snug">
                "I'll show you how I lost 50k in two hours."
              </p>
            </div>
            <div className="hidden items-center justify-center text-2xl text-emerald-500 md:flex">→</div>
            <div
              className="rounded-2xl border border-white/40 bg-white/60 p-4 backdrop-blur-xl dark:border-white/10 dark:bg-white/5"
            >
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                12:47 · Payoff
              </p>
              <p className="mt-2 font-medium leading-snug">
                "…and the lesson is worth every dollar. Here it is."
              </p>
            </div>
          </div>
          <p className="mt-3 text-sm text-neutral-500">
            One vlog. Two moments ten minutes apart. One stitched clip.
          </p>
        </GlassCard>
      </div>
    </section>
  );
}

function ScoreBento() {
  return null;
}

function Pipeline() {
  const steps = [
    { n: "01", t: "Brief", b: "Audience, niche, tone, goal. Two minutes." },
    { n: "02", t: "Map", b: "Visual + transcript per minute. Vision only where it counts." },
    { n: "03", t: "Arcs", b: "Setup→payoff, promise→failure stitched across distant moments." },
    { n: "04", t: "Ship", b: "Vertical 1080×1920, captions, 5 scores per clip." },
  ];
  return (
    <section id="pipeline" className="mx-auto max-w-6xl px-6 pb-16">
      <div className="mb-8 flex items-baseline justify-between">
        <h2 className="text-2xl font-semibold tracking-[-0.02em] md:text-3xl">
          The pipeline.
        </h2>
        <p className="text-sm text-neutral-500">One brief in, shorts out.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {steps.map((s) => (
          <GlassCard key={s.n}>
            <p className="text-xs uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              {s.n}
            </p>
            <p className="mt-2 text-xl font-semibold tracking-tight">{s.t}</p>
            <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
              {s.b}
            </p>
          </GlassCard>
        ))}
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section id="pricing" className="mx-auto max-w-6xl px-6 pb-20">
      <div className="mb-8 flex items-baseline justify-between">
        <h2 className="text-2xl font-semibold tracking-[-0.02em] md:text-3xl">
          One plan to start.
        </h2>
        <p className="text-sm text-neutral-500">No surprises.</p>
      </div>
      <GlassCard className="md:p-10">
        <div className="grid gap-8 md:grid-cols-[1fr_1.2fr] md:items-center">
          <div>
            <p className="text-xs uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              Starter
            </p>
            <p className="mt-2 flex items-baseline gap-2 text-6xl font-semibold tracking-tight">
              29€
              <span className="text-base font-normal text-neutral-500">/month</span>
            </p>
            <p className="mt-2 text-sm text-neutral-500">
              For solo creators getting serious about campaign-driven
              clipping.
            </p>
            <Link
              href="/login"
              className="mt-6 inline-flex rounded-full bg-neutral-900 px-6 py-3 text-base font-medium text-white shadow-sm dark:bg-white dark:text-neutral-900"
            >
              Start with Starter →
            </Link>
          </div>
          <ul className="space-y-3 text-sm">
            {[
              "300 credits / month (1 credit = 1 min of source)",
              "Up to 30 min per video, 3 clips per video",
              "Vertical 1080×1920 with burned-in captions",
              "Full 5-score breakdown on every clip",
              "EU hosted · No watermark · Cancel anytime",
            ].map((f) => (
              <li key={f} className="flex items-start gap-2.5">
                <span
                  className="mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-white"
                  style={{
                    background: "linear-gradient(135deg,#34D399,#10B981)",
                  }}
                >
                  <svg width="9" height="9" viewBox="0 0 12 12" fill="none">
                    <path d="M2 6.5L5 9.5L10 3.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      </GlassCard>
    </section>
  );
}

function Footer() {
  return (
    <footer className="mx-auto max-w-6xl px-6 pb-10">
      <div className="rounded-3xl border border-white/40 bg-white/40 px-6 py-5 text-sm text-neutral-500 backdrop-blur-xl dark:border-white/10 dark:bg-white/5">
        © 2026 ClipFactory · Made in EU · /preview/glass
      </div>
    </footer>
  );
}
