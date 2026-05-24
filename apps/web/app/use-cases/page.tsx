import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Building2, Lightbulb } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";

export const metadata: Metadata = {
  title: "Use cases — who ClipFactory is built for",
  description:
    "Solo creators turning long-forms into vertical shorts. Agencies serving multiple clients without losing taste. Pick the workflow that matches yours.",
  alternates: { canonical: "/use-cases" },
};

const CASES = [
  {
    href: "/use-cases/creators",
    icon: Lightbulb,
    title: "For solo creators",
    body: "Your long-forms deserve clips that match your voice. Story arcs, scored picks, no watermark — designed for the operator who ships every week.",
  },
  {
    href: "/use-cases/agencies",
    icon: Building2,
    title: "For agencies",
    body: "Serve more clients without losing taste. Per-client briefs, defensible score breakdown, predictable billing — built for studios at scale.",
  },
] as const;

export default function UseCasesIndexPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "Use cases", href: "/use-cases" },
        ]}
      />
      <MarketingNav />
      <main className="flex-1">
        <Container className="max-w-5xl py-20">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-brand)]">
            Use cases
          </p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
            Two workflows. One engine.
          </h1>
          <p className="mt-4 max-w-2xl text-[var(--color-muted-foreground)] md:text-lg">
            Pick the path that matches yours — same campaign-first selection, different
            constraints.
          </p>

          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {CASES.map((c) => (
              <Link
                key={c.href}
                href={c.href as never}
                className="group flex flex-col rounded-xl border border-[var(--color-border)] p-8 transition-colors hover:border-[var(--color-brand)]"
              >
                <c.icon className="h-6 w-6 text-[var(--color-brand)]" />
                <h2 className="mt-6 text-2xl font-semibold tracking-tight">{c.title}</h2>
                <p className="mt-3 flex-1 text-[var(--color-muted-foreground)]">{c.body}</p>
                <span className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-[var(--color-brand)]">
                  See the workflow
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </span>
              </Link>
            ))}
          </div>

          <div className="mt-16 rounded-xl border border-[var(--color-border)] bg-[var(--color-muted)] p-8 text-center">
            <p className="text-sm text-[var(--color-muted-foreground)]">
              Doesn&apos;t fit your workflow?
            </p>
            <h2 className="mt-2 text-xl font-semibold">Write to us — we read every email.</h2>
            <Link href="mailto:hello@clipfactory.app" className="mt-4 inline-flex">
              <Button variant="secondary">hello@clipfactory.app</Button>
            </Link>
          </div>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
