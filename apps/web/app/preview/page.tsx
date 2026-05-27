import Link from "next/link";

export const metadata = {
  title: "Preview — ClipFactory",
  robots: { index: false, follow: false },
};

const VARIANTS = [
  {
    slug: "dashboard",
    label: "Dashboard preview",
    blurb:
      "User dashboard, job review and admin snapshot with demo data. Use it to review the product UI without Supabase magic-link auth.",
    swatch: ["#050505", "#D8C3A3", "#F5F5F7"],
  },
];

export default function PreviewIndex() {
  return (
    <main className="min-h-dvh bg-neutral-50 dark:bg-neutral-950 px-6 py-16">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs uppercase tracking-[0.2em] text-neutral-500">
          Internal preview
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50 md:text-4xl">
          ClipFactory preview routes.
        </h1>
        <p className="mt-3 max-w-2xl text-neutral-600 dark:text-neutral-400">
          Review the production UI with static demo data before the external
          services are fully connected.
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
                  View -&gt;
                </div>
              </Link>
            </li>
          ))}
        </ul>

        <p className="mt-12 text-xs text-neutral-500">
          These pages are static internal previews. The public site is still{" "}
          <Link href="/" className="underline">
            /
          </Link>{" "}
          .
        </p>
      </div>
    </main>
  );
}
