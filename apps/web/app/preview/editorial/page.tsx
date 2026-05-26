import Link from "next/link";

const ACCENT = "#FF5C2A";
const PAPER = "#F4F0E8";
const INK = "#0A0A0A";

const serif = {
  fontFamily: "var(--font-fraunces), 'Iowan Old Style', 'Apple Garamond', serif",
  fontFeatureSettings: '"ss01", "ss02"',
} as const;

export default function EditorialPreview() {
  return (
    <>
      <Nav />
      <Hero />
      <Marquee />
      <PipelineEditorial />
      <ScoreEditorial />
      <ExampleEditorial />
      <PricingEditorial />
      <FooterEditorial />
    </>
  );
}

function Nav() {
  return (
    <header
      className="sticky top-0 z-50 flex items-center justify-between border-b px-6 py-4 backdrop-blur md:px-10"
      style={{ borderColor: "rgba(244,240,232,0.08)", background: "rgba(10,10,10,0.7)" }}
    >
      <Link href="/preview" className="flex items-center gap-2">
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: ACCENT }}
        />
        <span className="text-sm font-medium tracking-tight">ClipFactory</span>
        <span className="ml-2 text-[10px] uppercase tracking-[0.2em] text-neutral-500">
          /editorial preview
        </span>
      </Link>
      <nav className="hidden items-center gap-8 text-sm text-neutral-400 md:flex">
        <a href="#pipeline" className="hover:text-white">Pipeline</a>
        <a href="#score" className="hover:text-white">Le score</a>
        <a href="#pricing" className="hover:text-white">Tarifs</a>
      </nav>
      <Link
        href="/login"
        className="rounded-full px-4 py-2 text-sm font-medium transition"
        style={{ background: PAPER, color: INK }}
      >
        Démarrer →
      </Link>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden px-6 pt-16 pb-24 md:px-10 md:pt-24 md:pb-32">
      <div
        className="pointer-events-none absolute -left-40 top-40 h-[500px] w-[500px] rounded-full opacity-30 blur-3xl"
        style={{ background: ACCENT }}
      />
      <div className="relative mx-auto max-w-6xl">
        <p
          className="text-[11px] uppercase tracking-[0.3em] text-neutral-500"
        >
          Campaign-first AI clipping · EU hosted · 2026
        </p>
        <h1
          style={serif}
          className="mt-6 text-[clamp(2.75rem,7vw,6.5rem)] font-light leading-[0.95] tracking-[-0.02em]"
        >
          Ship the clip
          <br />
          <em
            className="italic"
            style={{ color: ACCENT, fontWeight: 400 }}
          >
            your campaign
          </em>
          <br />
          was supposed to be.
        </h1>
        <div className="mt-10 grid gap-10 md:grid-cols-[1.2fr_1fr]">
          <p className="max-w-xl text-lg leading-relaxed text-neutral-300 md:text-xl">
            ClipFactory lit ton brief, cartographie la vidéo entière, trouve
            les arcs narratifs entre des moments distants, et te livre des
            verticaux publiables — chacun avec un score que tu peux
            <em style={serif}> contester</em>.
          </p>
          <div className="flex flex-col items-start gap-3 md:items-end">
            <Link
              href="/login"
              className="inline-flex items-center gap-3 rounded-full px-6 py-3 text-base font-medium transition hover:opacity-90"
              style={{ background: ACCENT, color: INK }}
            >
              Start clipping
              <span>→</span>
            </Link>
            <a
              href="#pipeline"
              className="text-sm text-neutral-400 underline-offset-4 hover:text-white hover:underline"
            >
              Voir le pipeline en 4 étapes
            </a>
            <p className="text-xs text-neutral-500">
              29€/mois · Pas de watermark · EU
            </p>
          </div>
        </div>

        <div className="mt-20 grid gap-px overflow-hidden rounded-2xl bg-white/10 md:grid-cols-3">
          {[
            { k: "5", v: "scores par clip — hook, emotion, visual, fit, editing" },
            { k: "30 min", v: "de source max par vidéo, 3 clips out" },
            { k: "EU", v: "Frankfurt · Hetzner Germany · R2 EU" },
          ].map((s) => (
            <div
              key={s.k}
              className="bg-[#0A0A0A] p-8"
            >
              <p style={serif} className="text-5xl font-light tracking-tight" >
                {s.k}
              </p>
              <p className="mt-3 text-sm text-neutral-400">{s.v}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Marquee() {
  return (
    <section
      className="overflow-hidden border-y py-6"
      style={{ borderColor: "rgba(244,240,232,0.08)" }}
    >
      <div className="flex animate-[scroll_30s_linear_infinite] gap-12 whitespace-nowrap text-sm uppercase tracking-[0.25em] text-neutral-500">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="flex shrink-0 gap-12">
            <span>— Coaches</span>
            <span>— Indie founders</span>
            <span>— Podcasters</span>
            <span>— B2B SaaS</span>
            <span>— Newsletter ops</span>
            <span>— Faceless YT</span>
            <span>— Agencies</span>
            <span>— Educators</span>
          </div>
        ))}
      </div>
      <style>{`@keyframes scroll { from { transform: translateX(0) } to { transform: translateX(-50%) } }`}</style>
    </section>
  );
}

function PipelineEditorial() {
  const steps = [
    { n: "01", t: "Brief", b: "Audience, niche, ton, objectif, tabous. Deux minutes d'écriture, chaque job en hérite." },
    { n: "02", t: "Cartographie", b: "Map visuelle + transcript par minute. Vision uniquement où ça compte, jamais sur la source complète." },
    { n: "03", t: "Arcs narratifs", b: "Setup→payoff, promesse→échec, avant→après. Les multi-segments stitch des moments distants." },
    { n: "04", t: "Clips expliqués", b: "Cinq scores par clip avec raisons. Tu gardes, tu raffines, ou tu tues." },
  ];
  return (
    <section id="pipeline" className="px-6 py-32 md:px-10">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-baseline justify-between gap-8 border-b pb-6"
             style={{ borderColor: "rgba(244,240,232,0.12)" }}>
          <p className="text-[11px] uppercase tracking-[0.3em] text-neutral-500">
            How it works
          </p>
          <p className="text-sm text-neutral-500">§ 01</p>
        </div>
        <h2
          style={serif}
          className="mt-10 max-w-3xl text-[clamp(2rem,4.5vw,3.75rem)] font-light leading-[1.05] tracking-tight"
        >
          Un brief en entrée. Des verticaux <em className="italic" style={{ color: ACCENT }}>publiables</em> en sortie.
        </h2>

        <ol className="mt-16 grid gap-px bg-white/10 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((s) => (
            <li key={s.n} className="bg-[#0A0A0A] p-8">
              <p
                style={serif}
                className="text-6xl font-extralight"
              >
                {s.n}
              </p>
              <div
                className="mt-6 h-px w-12"
                style={{ background: ACCENT }}
              />
              <h3 style={serif} className="mt-6 text-2xl">
                {s.t}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-neutral-400">
                {s.b}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function ScoreEditorial() {
  const scores = [
    { l: "Hook", v: 95, n: "Les 2 premières secondes — ce qui arrête le scroll." },
    { l: "Emotion", v: 88, n: "Tension, surprise, réaction." },
    { l: "Visual", v: 92, n: "Visage cam, action, objets — du contexte pour l'œil." },
    { l: "Fit", v: 90, n: "Match avec l'audience et le goal que t'as briefé." },
    { l: "Editing", v: 84, n: "Net du cut — pénalise frame sombre, face absente, slides moches." },
  ];
  return (
    <section
      id="score"
      className="border-y px-6 py-32 md:px-10"
      style={{ borderColor: "rgba(244,240,232,0.08)", background: "#100E0C" }}
    >
      <div className="mx-auto grid max-w-6xl gap-16 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <p className="text-[11px] uppercase tracking-[0.3em] text-neutral-500">
            A score you can argue with · § 02
          </p>
          <h2
            style={serif}
            className="mt-6 text-[clamp(2rem,4.5vw,3.75rem)] font-light leading-[1.05] tracking-tight"
          >
            Cinq nombres. <em className="italic" style={{ color: ACCENT }}>Cinq raisons.</em> Aucun black-box.
          </h2>
          <p className="mt-6 max-w-md leading-relaxed text-neutral-300">
            Chaque clip porte son explication. Si un clip score 87, tu vois
            pourquoi — et où sont passés les 13 restants. Pas d'accord ? Ton
            feedback nourrit le pick suivant.
          </p>
        </div>

        <article
          className="rounded-3xl border p-8"
          style={{ borderColor: "rgba(244,240,232,0.12)", background: "#0A0A0A" }}
        >
          <div className="flex items-baseline justify-between gap-6">
            <p style={serif} className="text-2xl leading-tight">
              "It cost him $50k<br />to learn that lesson."
            </p>
            <div className="text-right">
              <p style={serif} className="text-5xl font-light" >91</p>
              <p className="text-[10px] uppercase tracking-[0.2em] text-neutral-500">
                Total
              </p>
            </div>
          </div>
          <div className="mt-8 space-y-5">
            {scores.map((s) => (
              <div key={s.l}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-medium">{s.l}</span>
                  <span className="tabular-nums text-neutral-400">{s.v}</span>
                </div>
                <div className="mt-2 h-[2px] w-full rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${s.v}%`, background: ACCENT }}
                  />
                </div>
                <p className="mt-2 text-xs text-neutral-500">{s.n}</p>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function ExampleEditorial() {
  return (
    <section className="px-6 py-32 md:px-10">
      <div className="mx-auto max-w-6xl">
        <p className="text-[11px] uppercase tracking-[0.3em] text-neutral-500">
          Real example · § 03
        </p>
        <h2
          style={serif}
          className="mt-6 max-w-3xl text-[clamp(2rem,4.5vw,3.75rem)] font-light leading-[1.05]"
        >
          Un vlog. Deux moments à <em style={{ color: ACCENT }}>dix minutes</em> d'écart. Un seul clip.
        </h2>

        <div className="mt-16 grid gap-px bg-white/10 lg:grid-cols-[1fr_auto_1fr]">
          <div className="bg-[#0A0A0A] p-10">
            <p className="text-[10px] uppercase tracking-[0.2em] text-neutral-500">
              t = 02:14
            </p>
            <p style={serif} className="mt-4 text-2xl leading-snug">
              "Je vais te montrer comment j'ai perdu 50k en 2 heures."
            </p>
            <p className="mt-4 text-sm text-neutral-500">Setup</p>
          </div>
          <div className="hidden items-center justify-center bg-[#0A0A0A] px-8 lg:flex">
            <span style={{ color: ACCENT }} className="text-3xl">→</span>
          </div>
          <div className="bg-[#0A0A0A] p-10">
            <p className="text-[10px] uppercase tracking-[0.2em] text-neutral-500">
              t = 12:47
            </p>
            <p style={serif} className="mt-4 text-2xl leading-snug">
              "…et la leçon vaut chaque dollar. La voici en une phrase."
            </p>
            <p className="mt-4 text-sm text-neutral-500">Payoff</p>
          </div>
        </div>

        <p className="mt-8 max-w-2xl text-neutral-400">
          Les autres outils clip ces moments séparément et la magie disparaît.
          ClipFactory les stitch avec un crossfade audio propre.
        </p>
      </div>
    </section>
  );
}

function PricingEditorial() {
  return (
    <section
      id="pricing"
      className="border-t px-6 py-32 md:px-10"
      style={{ borderColor: "rgba(244,240,232,0.08)" }}
    >
      <div className="mx-auto max-w-6xl">
        <div className="flex items-baseline justify-between">
          <p className="text-[11px] uppercase tracking-[0.3em] text-neutral-500">
            Pricing · § 04
          </p>
          <p className="text-sm text-neutral-500">One plan to start.</p>
        </div>

        <div className="mt-12 grid gap-12 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h2
              style={serif}
              className="text-[clamp(2rem,4.5vw,3.75rem)] font-light leading-[1.05]"
            >
              Le prix que tu vois<br />est le prix <em className="italic" style={{ color: ACCENT }}>que tu paies</em>.
            </h2>
            <p className="mt-6 max-w-md text-neutral-400">
              Creator et Agency s'ouvriront quand l'API et le scheduling
              shipperont. Pour l'instant, un plan, fait pour les créateurs solos
              sérieux côté campagne.
            </p>
          </div>

          <article
            className="rounded-3xl p-10"
            style={{ background: PAPER, color: INK }}
          >
            <p className="text-[11px] uppercase tracking-[0.3em] text-neutral-500">
              Starter
            </p>
            <p style={serif} className="mt-3 text-7xl font-light tracking-tight">
              29€
              <span className="ml-2 text-base text-neutral-500">/ mois</span>
            </p>
            <ul className="mt-8 space-y-3 text-sm">
              {[
                "300 crédits / mois (1 crédit = 1 min de source)",
                "Jusqu'à 30 min par vidéo, 3 clips par vidéo",
                "Vertical 1080×1920, captions burned-in",
                "Score breakdown complet sur chaque clip",
                "EU hosted, no watermark, cancel anytime",
              ].map((f) => (
                <li key={f} className="flex gap-3">
                  <span style={{ color: ACCENT }}>—</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Link
              href="/login"
              className="mt-8 flex w-full items-center justify-center gap-2 rounded-full py-4 text-base font-medium transition hover:opacity-90"
              style={{ background: INK, color: PAPER }}
            >
              Start with Starter →
            </Link>
          </article>
        </div>
      </div>
    </section>
  );
}

function FooterEditorial() {
  return (
    <footer
      className="border-t px-6 py-16 md:px-10"
      style={{ borderColor: "rgba(244,240,232,0.08)" }}
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-8 md:flex-row md:items-end md:justify-between">
        <div>
          <p style={serif} className="text-5xl font-light leading-none">
            ClipFactory<span style={{ color: ACCENT }}>.</span>
          </p>
          <p className="mt-3 max-w-sm text-sm text-neutral-500">
            Campaign-first AI clipping. Made in EU, for creators who care about
            what they ship.
          </p>
        </div>
        <p className="text-xs text-neutral-600">
          © 2026 ClipFactory · /preview/editorial
        </p>
      </div>
    </footer>
  );
}
