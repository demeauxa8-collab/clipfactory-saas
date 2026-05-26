import Link from "next/link";

export const metadata = {
  title: "Design directions — ClipFactory",
  robots: { index: false, follow: false },
};

const VARIANTS = [
  {
    slug: "editorial",
    label: "V1 — Editorial dark cinéma",
    blurb:
      "Fond noir profond, Fraunces serif sur les titres, accent orange #FF5C2A. Studio premium / Loom-Cleo-Linear-pro.",
    swatch: ["#0A0A0A", "#FF5C2A", "#F4F0E8"],
  },
  {
    slug: "glass",
    label: "V2 — Liquid Glass / Apple HIG",
    blurb:
      "Bento layout, glass blurs, light/dark adaptive, micro-interactions. Cohérent avec ton projet Mood.",
    swatch: ["#F5F5F7", "#0A0A0A", "#34D399"],
  },
  {
    slug: "brutalist",
    label: "V3 — Brutalist tech agency",
    blurb:
      "Space Grotesk + JetBrains Mono, grille visible, BN max + accent fluo #C8FF00. AX Studio / Bureau Borsche.",
    swatch: ["#FFFFFF", "#000000", "#C8FF00"],
  },
];

export default function PreviewIndex() {
  return (
    <main className="min-h-dvh bg-neutral-50 dark:bg-neutral-950 px-6 py-16">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs uppercase tracking-[0.2em] text-neutral-500">
          Internal · Design directions
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50 md:text-4xl">
          Trois directions pour ClipFactory.
        </h1>
        <p className="mt-3 max-w-2xl text-neutral-600 dark:text-neutral-400">
          Même contenu, trois ambiances. Choisis-en une (ou un mix) avant qu'on
          déroule sur toutes les pages + dashboard.
        </p>

        <ul className="mt-10 grid gap-4">
          {VARIANTS.map((v) => (
            <li key={v.slug}>
              <Link
                href={`/preview/${v.slug}` as never}
                className="group flex items-stretch gap-5 rounded-xl border border-neutral-200 bg-white p-5 transition hover:border-neutral-900 hover:shadow-sm dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-50"
              >
                <div className="flex w-24 shrink-0 overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
                  {v.swatch.map((c) => (
                    <span
                      key={c}
                      className="flex-1"
                      style={{ background: c }}
                    />
                  ))}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-base font-medium text-neutral-900 dark:text-neutral-50">
                    {v.label}
                  </p>
                  <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
                    {v.blurb}
                  </p>
                </div>
                <div className="flex items-center text-sm text-neutral-400 transition group-hover:text-neutral-900 dark:group-hover:text-neutral-50">
                  Voir →
                </div>
              </Link>
            </li>
          ))}
        </ul>

        <p className="mt-12 text-xs text-neutral-500">
          Ces pages sont des prototypes statiques. La home en prod reste sur{" "}
          <Link href="/" className="underline">
            /
          </Link>{" "}
          tant que tu n'as pas choisi.
        </p>
      </div>
    </main>
  );
}
