import Link from "next/link";

const NEON = "#C8FF00";
const BLACK = "#000000";
const PAPER = "#FAFAF7";

const mono = { fontFamily: "var(--font-mono), 'JetBrains Mono', monospace" } as const;

export default function BrutalistPreview() {
  return (
    <>
      <BgGrid />
      <Nav />
      <Hero />
      <TickerRow />
      <Pipeline />
      <Score />
      <ArcExample />
      <Pricing />
      <Foot />
    </>
  );
}

function BgGrid() {
  return (
    <style>{`
      body {
        background-image:
          linear-gradient(to right, rgba(0,0,0,0.06) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(0,0,0,0.06) 1px, transparent 1px);
        background-size: 48px 48px;
      }
    `}</style>
  );
}

function Nav() {
  return (
    <header
      className="sticky top-0 z-50 flex items-center justify-between border-b-2 px-6 py-3 md:px-10"
      style={{ borderColor: BLACK, background: PAPER }}
    >
      <Link href="/preview" className="flex items-center gap-3">
        <span
          className="inline-block h-5 w-5"
          style={{ background: BLACK, boxShadow: `4px 4px 0 ${NEON}` }}
        />
        <span style={mono} className="text-sm font-bold uppercase tracking-wider">
          CLIPFACTORY//
        </span>
        <span style={mono} className="hidden text-[10px] uppercase tracking-[0.2em] text-neutral-500 md:inline">
          v.preview · EU/2026
        </span>
      </Link>
      <nav className="hidden gap-6 text-xs font-bold uppercase tracking-widest md:flex" style={mono}>
        <a href="#pipeline">[01]_pipeline</a>
        <a href="#score">[02]_score</a>
        <a href="#pricing">[03]_pricing</a>
      </nav>
      <Link
        href="/login"
        className="border-2 px-4 py-2 text-xs font-bold uppercase tracking-widest transition hover:translate-y-[-2px]"
        style={{ ...mono, borderColor: BLACK, background: NEON, boxShadow: `4px 4px 0 ${BLACK}` }}
      >
        Start_→
      </Link>
    </header>
  );
}

function Hero() {
  return (
    <section
      className="relative border-b-2 px-6 py-20 md:px-10 md:py-32"
      style={{ borderColor: BLACK }}
    >
      <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <p style={mono} className="text-[11px] font-bold uppercase tracking-[0.25em]">
            [001] · CAMPAIGN_FIRST AI CLIPPING
          </p>
          <h1 className="mt-6 text-[clamp(3rem,9vw,8rem)] font-bold uppercase leading-[0.9] tracking-[-0.04em]">
            AI clipping
            <br />
            that fits
            <br />
            <span
              className="inline-block"
              style={{
                background: NEON,
                padding: "0 0.15em",
                boxShadow: `8px 8px 0 ${BLACK}`,
              }}
            >
              your_campaign
            </span>
            .
          </h1>
          <p className="mt-10 max-w-xl text-base leading-relaxed text-neutral-700 md:text-lg">
            Reads your brief. Maps the whole video. Stitches narrative arcs
            across distant moments. Explains every clip with five scores you
            can argue with.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link
              href="/login"
              className="inline-flex items-center gap-3 border-2 px-7 py-4 text-sm font-bold uppercase tracking-widest transition hover:translate-y-[-2px]"
              style={{ ...mono, borderColor: BLACK, background: BLACK, color: PAPER, boxShadow: `6px 6px 0 ${NEON}` }}
            >
              START_CLIPPING →
            </Link>
            <a
              href="#pipeline"
              className="inline-flex items-center gap-2 border-2 px-7 py-4 text-sm font-bold uppercase tracking-widest"
              style={{ ...mono, borderColor: BLACK, background: PAPER }}
            >
              SEE_PIPELINE
            </a>
          </div>
          <p style={mono} className="mt-6 text-[11px] uppercase tracking-widest text-neutral-500">
            29€/mo · NO_WATERMARK · EU_HOSTED · CANCEL_ANYTIME
          </p>
        </div>

        <div>
          <div
            className="aspect-[9/12] border-2 p-3"
            style={{ borderColor: BLACK, background: BLACK, boxShadow: `10px 10px 0 ${NEON}` }}
          >
            <div
              className="flex h-full flex-col justify-between p-5 text-white"
              style={{
                background:
                  "repeating-linear-gradient(135deg, rgba(255,255,255,0.04) 0 2px, transparent 2px 8px), #1A1A1A",
              }}
            >
              <div className="flex items-center justify-between">
                <p style={mono} className="text-[10px] uppercase tracking-widest text-neutral-500">
                  CLIP_034.mp4
                </p>
                <span
                  className="border px-2 py-0.5 text-[10px] font-bold"
                  style={{ ...mono, background: NEON, color: BLACK, borderColor: NEON }}
                >
                  91/100
                </span>
              </div>
              <div>
                <p className="text-2xl font-bold leading-tight">
                  It cost him $50k<br />to learn that lesson.
                </p>
                <div className="mt-6 space-y-2">
                  {[
                    ["HOOK", 95],
                    ["EMOTION", 88],
                    ["VISUAL", 92],
                    ["FIT", 90],
                    ["EDITING", 84],
                  ].map(([l, v]) => (
                    <div key={l as string} className="flex items-center gap-3" style={mono}>
                      <span className="w-16 text-[10px] uppercase tracking-widest">{l}</span>
                      <div className="h-1.5 flex-1 bg-white/15">
                        <div className="h-full" style={{ width: `${v}%`, background: NEON }} />
                      </div>
                      <span className="w-8 text-right text-[10px] tabular-nums">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <p style={mono} className="text-[10px] uppercase tracking-widest text-neutral-500">
                t=02:14 → t=12:47 · STITCHED
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function TickerRow() {
  return (
    <div
      className="overflow-hidden border-b-2 py-3"
      style={{ ...mono, borderColor: BLACK, background: BLACK, color: PAPER }}
    >
      <div className="flex animate-[ticker_25s_linear_infinite] gap-10 whitespace-nowrap text-xs font-bold uppercase tracking-[0.3em]">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="flex shrink-0 gap-10">
            <span>// COACHES</span>
            <span style={{ color: NEON }}>// INDIE FOUNDERS</span>
            <span>// PODCASTERS</span>
            <span style={{ color: NEON }}>// B2B SAAS</span>
            <span>// NEWSLETTER OPS</span>
            <span style={{ color: NEON }}>// FACELESS YT</span>
            <span>// AGENCIES</span>
            <span style={{ color: NEON }}>// EDUCATORS</span>
          </div>
        ))}
      </div>
      <style>{`@keyframes ticker { from { transform: translateX(0) } to { transform: translateX(-50%) } }`}</style>
    </div>
  );
}

function Pipeline() {
  const steps = [
    { n: "01", t: "BRIEF", b: "Audience, niche, ton, objectif, sujets bannis. 2 min d'écriture, chaque job en hérite." },
    { n: "02", t: "MAP", b: "Visual + transcript par minute. Vision uniquement où ça compte." },
    { n: "03", t: "ARCS", b: "Setup→payoff, promise→failure, before→after. Stitch entre moments distants." },
    { n: "04", t: "SHIP", b: "Vertical 1080×1920 + captions burned-in. 5 scores. Tu gardes ou tu kill." },
  ];
  return (
    <section id="pipeline" className="border-b-2 px-6 py-24 md:px-10" style={{ borderColor: BLACK }}>
      <div className="mx-auto max-w-7xl">
        <div className="flex items-baseline justify-between border-b-2 pb-6" style={{ borderColor: BLACK }}>
          <p style={mono} className="text-[11px] font-bold uppercase tracking-[0.25em]">
            §_01 / HOW_IT_WORKS
          </p>
          <p style={mono} className="text-[11px] uppercase tracking-widest text-neutral-500">
            4_STEPS
          </p>
        </div>
        <h2 className="mt-12 max-w-4xl text-[clamp(2.5rem,6vw,5rem)] font-bold uppercase leading-[0.95] tracking-tight">
          One brief in.<br />
          Publish-ready
          <span style={{ background: NEON, padding: "0 0.15em", marginLeft: "0.15em" }}>shorts</span>{" "}
          out.
        </h2>
        <ol className="mt-16 grid gap-0 md:grid-cols-4">
          {steps.map((s, idx) => (
            <li
              key={s.n}
              className="border-2 p-8"
              style={{
                borderColor: BLACK,
                background: idx % 2 === 0 ? PAPER : "#F0EFE8",
                marginLeft: idx > 0 ? "-2px" : 0,
                marginTop: 0,
              }}
            >
              <p style={mono} className="text-[10px] font-bold uppercase tracking-widest text-neutral-500">
                STEP_{s.n}
              </p>
              <p className="mt-4 text-5xl font-bold leading-none tracking-tight">{s.n}</p>
              <div className="mt-6 h-1 w-10" style={{ background: NEON }} />
              <h3 style={mono} className="mt-6 text-xl font-bold uppercase tracking-wider">
                {s.t}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-neutral-700">{s.b}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Score() {
  return (
    <section
      id="score"
      className="border-b-2 px-6 py-24 md:px-10"
      style={{ borderColor: BLACK, background: BLACK, color: PAPER }}
    >
      <div className="mx-auto max-w-7xl">
        <div className="flex items-baseline justify-between border-b pb-6" style={{ borderColor: "rgba(255,255,255,0.15)" }}>
          <p style={mono} className="text-[11px] font-bold uppercase tracking-[0.25em]" >
            §_02 / SCORE_BREAKDOWN
          </p>
          <p style={mono} className="text-[11px] uppercase tracking-widest text-neutral-500">
            NO_BLACK_BOX
          </p>
        </div>

        <h2 className="mt-12 max-w-4xl text-[clamp(2.5rem,6vw,5rem)] font-bold uppercase leading-[0.95] tracking-tight">
          Five numbers.<br />
          Five
          <span style={{ background: NEON, color: BLACK, padding: "0 0.15em", marginLeft: "0.15em" }}>
            reasons
          </span>
          .
        </h2>

        <div className="mt-16 grid gap-8 md:grid-cols-5">
          {[
            ["HOOK", 95, "First 2 seconds — what stops the scroll."],
            ["EMOTION", 88, "Tension, surprise, reaction."],
            ["VISUAL", 92, "Face cam, action, objects on screen."],
            ["FIT", 90, "Match with audience & goal you briefed."],
            ["EDITING", 84, "Penalises dark frames, missing faces."],
          ].map(([l, v, n]) => (
            <div
              key={l as string}
              className="border-2 p-6"
              style={{ borderColor: PAPER }}
            >
              <p style={mono} className="text-[10px] uppercase tracking-widest text-neutral-500">
                {l}
              </p>
              <p className="mt-3 text-6xl font-bold tabular-nums leading-none" style={{ color: NEON }}>
                {v}
              </p>
              <div className="mt-4 h-1 w-full bg-white/15">
                <div className="h-full" style={{ width: `${v}%`, background: NEON }} />
              </div>
              <p className="mt-5 text-xs leading-relaxed text-neutral-400">{n}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ArcExample() {
  return (
    <section className="border-b-2 px-6 py-24 md:px-10" style={{ borderColor: BLACK }}>
      <div className="mx-auto max-w-7xl">
        <div className="flex items-baseline justify-between border-b-2 pb-6" style={{ borderColor: BLACK }}>
          <p style={mono} className="text-[11px] font-bold uppercase tracking-[0.25em]" >
            §_03 / REAL_EXAMPLE
          </p>
          <p style={mono} className="text-[11px] uppercase tracking-widest text-neutral-500">
            ARC_STITCH
          </p>
        </div>

        <h2 className="mt-12 max-w-4xl text-[clamp(2.5rem,6vw,5rem)] font-bold uppercase leading-[0.95]">
          One vlog.<br />Two moments
          <span style={{ background: NEON, padding: "0 0.15em", marginLeft: "0.15em" }}>10 min</span>{" "}
          apart.
        </h2>

        <div className="mt-16 grid items-stretch gap-0 md:grid-cols-[1fr_auto_1fr]">
          <div className="border-2 p-8" style={{ borderColor: BLACK, background: PAPER }}>
            <p style={mono} className="text-[10px] uppercase tracking-widest">
              t = 02:14 · SETUP
            </p>
            <p className="mt-4 text-2xl font-bold leading-tight">
              "I'll show you how I lost 50k in two hours."
            </p>
          </div>
          <div
            className="hidden items-center justify-center border-y-2 px-8 md:flex"
            style={{ borderColor: BLACK, background: NEON }}
          >
            <span className="text-3xl font-bold">→</span>
          </div>
          <div
            className="border-2 p-8"
            style={{ borderColor: BLACK, background: BLACK, color: PAPER, marginLeft: "-2px" }}
          >
            <p style={mono} className="text-[10px] uppercase tracking-widest text-neutral-500">
              t = 12:47 · PAYOFF
            </p>
            <p className="mt-4 text-2xl font-bold leading-tight">
              "…and the lesson is worth every dollar. Here it is."
            </p>
          </div>
        </div>

        <p className="mt-8 max-w-2xl text-neutral-700">
          Other tools clip these separately and the magic is gone. ClipFactory
          stitches them with a clean audio crossfade.
        </p>
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section id="pricing" className="border-b-2 px-6 py-24 md:px-10" style={{ borderColor: BLACK }}>
      <div className="mx-auto max-w-7xl">
        <div className="flex items-baseline justify-between border-b-2 pb-6" style={{ borderColor: BLACK }}>
          <p style={mono} className="text-[11px] font-bold uppercase tracking-[0.25em]" >
            §_04 / PRICING
          </p>
          <p style={mono} className="text-[11px] uppercase tracking-widest text-neutral-500">
            1_PLAN · 0_TRAP
          </p>
        </div>

        <div className="mt-12 grid gap-10 lg:grid-cols-[1.2fr_1fr]">
          <h2 className="text-[clamp(2.5rem,6vw,5rem)] font-bold uppercase leading-[0.95]">
            The price you see<br />
            is the price you
            <span style={{ background: NEON, padding: "0 0.15em", marginLeft: "0.15em" }}>pay</span>
            .
          </h2>

          <div
            className="border-2 p-10"
            style={{ borderColor: BLACK, background: PAPER, boxShadow: `12px 12px 0 ${NEON}` }}
          >
            <p style={mono} className="text-[11px] font-bold uppercase tracking-widest">
              STARTER · 29€/MO
            </p>
            <p className="mt-4 text-7xl font-bold leading-none tracking-tight tabular-nums">
              29€
            </p>
            <ul className="mt-8 space-y-3 text-sm">
              {[
                "300 credits / month · 1 credit = 1 min source",
                "Up to 30 min per video, 3 clips out",
                "Vertical 1080×1920 + captions burned-in",
                "Full 5-score breakdown",
                "EU hosted · No watermark · Cancel anytime",
              ].map((f) => (
                <li key={f} className="flex items-start gap-3">
                  <span style={mono} className="font-bold">→</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/login"
              className="mt-10 flex w-full items-center justify-center gap-3 border-2 py-4 text-sm font-bold uppercase tracking-widest"
              style={{ ...mono, borderColor: BLACK, background: BLACK, color: PAPER }}
            >
              START_WITH_STARTER →
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function Foot() {
  return (
    <footer className="px-6 py-12 md:px-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-5xl font-bold uppercase leading-none tracking-tight">
            CLIPFACTORY<span style={{ background: NEON }}>.</span>
          </p>
          <p style={mono} className="mt-3 text-xs uppercase tracking-widest text-neutral-500">
            // CAMPAIGN-FIRST AI CLIPPING · MADE IN EU
          </p>
        </div>
        <p style={mono} className="text-[10px] uppercase tracking-widest text-neutral-500">
          © 2026 / /preview/brutalist
        </p>
      </div>
    </footer>
  );
}
