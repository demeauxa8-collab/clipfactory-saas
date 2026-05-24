import { Check, X } from "lucide-react";

type Cell =
  | { kind: "yes"; note?: string }
  | { kind: "no"; note?: string }
  | { kind: "text"; value: string };

type Row = {
  label: string;
  clipfactory: Cell;
  opusclip: Cell;
  vizard: Cell;
};

const ROWS: Row[] = [
  {
    label: "Campaign brief drives clip selection",
    clipfactory: { kind: "yes", note: "audience, niche, tone, goal" },
    opusclip: { kind: "no" },
    vizard: { kind: "no" },
  },
  {
    label: "Story arcs across distant moments",
    clipfactory: { kind: "yes", note: "multi-segment clips" },
    opusclip: { kind: "no" },
    vizard: { kind: "no" },
  },
  {
    label: "Explained score (5 components)",
    clipfactory: { kind: "yes" },
    opusclip: { kind: "no", note: "single virality number" },
    vizard: { kind: "no" },
  },
  {
    label: "Anti-hallucination guard",
    clipfactory: { kind: "yes" },
    opusclip: { kind: "no" },
    vizard: { kind: "no" },
  },
  {
    label: "EU hosted (GDPR-friendly)",
    clipfactory: { kind: "yes", note: "Frankfurt / Germany" },
    opusclip: { kind: "no", note: "US" },
    vizard: { kind: "no", note: "US" },
  },
  {
    label: "No watermark on entry plan",
    clipfactory: { kind: "yes" },
    opusclip: { kind: "no" },
    vizard: { kind: "no" },
  },
  {
    label: "Revenue share",
    clipfactory: { kind: "text", value: "None" },
    opusclip: { kind: "text", value: "None" },
    vizard: { kind: "text", value: "None" },
  },
  {
    label: "Entry price",
    clipfactory: { kind: "text", value: "29€/mo" },
    opusclip: { kind: "text", value: "$19/mo" },
    vizard: { kind: "text", value: "$30/mo" },
  },
];

export function ComparisonTable() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            ClipFactory vs the rest
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Same input. Different rules.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Honest comparison — public competitor docs, last checked May 2026.
          </p>
        </div>

        <div className="mt-10 overflow-x-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-background)]">
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted)] text-left">
                <th className="px-5 py-4 font-medium">Capability</th>
                <th className="px-5 py-4 font-medium text-[var(--color-brand)]">ClipFactory</th>
                <th className="px-5 py-4 font-medium">OpusClip</th>
                <th className="px-5 py-4 font-medium">Vizard</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row, i) => (
                <tr
                  key={row.label}
                  className={
                    "border-b border-[var(--color-border)] last:border-b-0 " +
                    (i % 2 === 1 ? "bg-[var(--color-muted)]/30" : "")
                  }
                >
                  <td className="px-5 py-4 font-medium">{row.label}</td>
                  <td className="px-5 py-4">
                    <CellView cell={row.clipfactory} brand />
                  </td>
                  <td className="px-5 py-4">
                    <CellView cell={row.opusclip} />
                  </td>
                  <td className="px-5 py-4">
                    <CellView cell={row.vizard} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
          Source: public pricing &amp; feature pages of each tool. Spotted an error?
          Ping <a className="underline" href="mailto:hello@clipfactory.app">hello@clipfactory.app</a> and we&apos;ll fix it.
        </p>
      </div>
    </section>
  );
}

function CellView({ cell, brand = false }: { cell: Cell; brand?: boolean }) {
  if (cell.kind === "yes") {
    return (
      <div className="flex flex-col gap-0.5">
        <Check
          className={
            "h-4 w-4 " + (brand ? "text-[var(--color-brand)]" : "text-[var(--color-foreground)]")
          }
        />
        {cell.note && (
          <span className="text-xs text-[var(--color-muted-foreground)]">{cell.note}</span>
        )}
      </div>
    );
  }
  if (cell.kind === "no") {
    return (
      <div className="flex flex-col gap-0.5">
        <X className="h-4 w-4 text-[var(--color-muted-foreground)]" />
        {cell.note && (
          <span className="text-xs text-[var(--color-muted-foreground)]">{cell.note}</span>
        )}
      </div>
    );
  }
  return <span className="text-[var(--color-foreground)]/90">{cell.value}</span>;
}
