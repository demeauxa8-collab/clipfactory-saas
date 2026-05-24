import {
  Globe2,
  LockKeyhole,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

const ITEMS = [
  { icon: ShieldCheck, label: "EU hosted" },
  { icon: LockKeyhole, label: "GDPR aware" },
  { icon: Sparkles, label: "No watermark" },
  { icon: RefreshCcw, label: "Cancel anytime" },
  { icon: Globe2, label: "No revenue share" },
];

export function TrustBar() {
  return (
    <section
      aria-label="Trust signals"
      className="border-b border-[var(--color-border)] bg-[var(--color-background)]"
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-8 gap-y-3 px-6 py-6 text-sm text-[var(--color-muted-foreground)]">
        {ITEMS.map((i) => (
          <div key={i.label} className="flex items-center gap-2">
            <i.icon className="h-4 w-4 text-[var(--color-brand)]" />
            <span className="font-medium">{i.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
