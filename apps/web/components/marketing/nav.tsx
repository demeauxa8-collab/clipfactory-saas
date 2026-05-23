import Link from "next/link";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { NAV_PRIMARY, SITE } from "@/lib/site";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur">
      <Container className="flex h-14 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block h-5 w-5 rounded-sm bg-[var(--color-foreground)]" aria-hidden />
          {SITE.name}
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_PRIMARY.map((item) => (
            <Link
              key={item.href}
              href={item.href as never}
              className="hidden h-9 items-center px-3 text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] md:inline-flex"
            >
              {item.label}
            </Link>
          ))}
          <Link href="/login">
            <Button variant="ghost" size="sm">Sign in</Button>
          </Link>
          <Link href="/login">
            <Button size="sm">Start clipping</Button>
          </Link>
        </nav>
      </Container>
    </header>
  );
}
