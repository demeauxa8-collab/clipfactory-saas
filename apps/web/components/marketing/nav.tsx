import Link from "next/link";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { NAV_PRIMARY, SITE } from "@/lib/site";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-[var(--color-background)]/76 backdrop-blur-xl">
      <Container className="flex h-16 items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
        >
          <span
            className="relative inline-flex h-5 w-5 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]"
            aria-hidden
          >
            <span className="h-2.5 w-1 rounded-sm bg-[var(--color-brand)] shadow-[0_0_18px_rgba(216,195,163,0.32)]" />
          </span>
          <span className="text-base">{SITE.name}</span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_PRIMARY.map((item) => (
            <Link
              key={item.href}
              href={item.href as never}
              className="hidden h-9 items-center rounded-md px-3 text-sm text-[var(--color-muted-foreground)] transition-all duration-300 hover:-translate-y-0.5 hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)] md:inline-flex"
            >
              {item.label}
            </Link>
          ))}
          <span className="mx-2 hidden h-5 w-px bg-[var(--color-border)] md:inline-block" />
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Sign in
            </Button>
          </Link>
          <Link href="/login">
            <Button size="sm">Start clipping</Button>
          </Link>
        </nav>
      </Container>
    </header>
  );
}
