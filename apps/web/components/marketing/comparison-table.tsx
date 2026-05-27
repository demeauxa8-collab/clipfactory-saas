import { Check, X } from "lucide-react";

type Cell =
  | { kind: "yes"; note?: string }
  | { kind: "no"; note?: string }
  | { kind: "text"; value: string };

type Row = {
  label: string;
  clipfactory: Cell;
  transcriptClipper: Cell;
  manualEditor: Cell;
};

const ROWS: Row[] = [
  {
    label: "Uses the goal of the clip series",
    clipfactory: { kind: "yes", note: "audience, offer, tone, objective" },
    transcriptClipper: { kind: "no", note: "often generic output" },
    manualEditor: { kind: "yes", note: "but slow and subjective" },
  },
  {
    label: "Can connect moments far apart",
    clipfactory: { kind: "yes", note: "setup, proof and payoff" },
    transcriptClipper: { kind: "no", note: "usually one timestamp" },
    manualEditor: { kind: "yes", note: "if the editor watches everything" },
  },
  {
    label: "Explains why each clip belongs",
    clipfactory: { kind: "yes" },
    transcriptClipper: { kind: "no", note: "often just one score" },
    manualEditor: { kind: "no", note: "depends on the person" },
  },
  {
    label: "Checks the moment before rendering",
    clipfactory: { kind: "yes" },
    transcriptClipper: { kind: "text", value: "Depends" },
    manualEditor: { kind: "yes" },
  },
  {
    label: "Looks at what happens on screen",
    clipfactory: { kind: "yes", note: "faces, products, action, proof" },
    transcriptClipper: { kind: "no", note: "mostly text-based" },
    manualEditor: { kind: "yes" },
  },
  {
    label: "EU-first processing path",
    clipfactory: { kind: "yes", note: "Frankfurt / Germany" },
    transcriptClipper: { kind: "text", value: "Depends" },
    manualEditor: { kind: "text", value: "Depends" },
  },
  {
    label: "No watermark on paid plan",
    clipfactory: { kind: "yes" },
    transcriptClipper: { kind: "text", value: "Depends" },
    manualEditor: { kind: "yes" },
  },
  {
    label: "Simple video-minute pricing",
    clipfactory: { kind: "yes", note: "1 credit = 1 source minute" },
    transcriptClipper: { kind: "text", value: "Often bundled" },
    manualEditor: { kind: "no", note: "time-based labor" },
  },
];

export function ComparisonTable() {
  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            ClipFactory vs basic AI clippers
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            Same video. Better clip series.
          </h2>
          <p className="mt-3 text-[var(--color-muted-foreground)]">
            Basic tools can find loud moments. ClipFactory is built to find clips that
            match the objective of the series, make sense in the full video, and still
            work visually on screen.
          </p>
        </div>

        <div className="mt-10 overflow-x-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-background)]">
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted)] text-left">
                <th className="px-5 py-4 font-medium">Capability</th>
                <th className="px-5 py-4 font-medium text-[var(--color-brand)]">ClipFactory</th>
                <th className="px-5 py-4 font-medium">Basic AI clipper</th>
                <th className="px-5 py-4 font-medium">Manual editor</th>
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
                    <CellView cell={row.transcriptClipper} />
                  </td>
                  <td className="px-5 py-4">
                    <CellView cell={row.manualEditor} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-[var(--color-muted-foreground)]">
          This is a positioning comparison, not a claim that every tool in the market behaves the
          same way. Spotted a weak claim? Ping{" "}
          <a className="underline" href="mailto:hello@clipfactory.app">hello@clipfactory.app</a>.
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
