import Link from "next/link";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { NAV_PRIMARY, SITE } from "@/lib/site";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-background)_72%,transparent)] backdrop-blur-xl [backdrop-filter:saturate(180%)_blur(20px)]">
      <Container className="flex h-16 items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
        >
          <span
            className="relative inline-flex h-5 w-5 items-center justify-center rounded-[0.5rem] border border-[var(--color-border)] bg-[var(--color-muted)]"
            aria-hidden
          >
            <span className="h-2.5 w-1 rounded-full bg-[var(--color-brand)]" />
          </span>
          <span className="text-base">{SITE.name}</span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_PRIMARY.map((item) => (
            <Link
              key={item.href}
              href={item.href as never}
              className="hidden h-9 items-center rounded-full px-3.5 text-sm text-[var(--color-muted-foreground)] transition-[background-color,color,transform] duration-150 ease-out hover:-translate-y-0.5 hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)] md:inline-flex"
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
          <Link href="/login?next=/app/campaigns/new">
            <Button size="sm">Start clipping</Button>
          </Link>
        </nav>
      </Container>
    </header>
  );
}
