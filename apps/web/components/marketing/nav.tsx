import Link from "next/link";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { NAV_PRIMARY, SITE } from "@/lib/site";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-[var(--color-background)]/85 backdrop-blur-md">
      <Container className="flex h-16 items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
        >
          <span
            className="inline-block h-6 w-6 rounded-md bg-[var(--color-brand)] shadow-[0_0_0_3px_rgba(5,150,105,0.12)]"
            aria-hidden
          />
          <span className="text-base">{SITE.name}</span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_PRIMARY.map((item) => (
            <Link
              key={item.href}
              href={item.href as never}
              className="hidden h-9 items-center rounded-md px-3 text-sm text-[var(--color-muted-foreground)] transition-colors hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)] md:inline-flex"
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
