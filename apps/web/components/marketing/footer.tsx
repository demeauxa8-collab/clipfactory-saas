import Link from "next/link";
import { Container } from "@/components/ui/container";

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] py-10 text-sm text-[var(--color-muted-foreground)]">
      <Container className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
        <div className="flex items-center gap-2">
          <span className="inline-block h-4 w-4 rounded-sm bg-[var(--color-foreground)]" aria-hidden />
          <span>ClipFactory — campaign-first AI clipping.</span>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2">
          <Link href="/legal/terms" className="hover:text-[var(--color-foreground)]">Terms</Link>
          <Link href="/legal/privacy" className="hover:text-[var(--color-foreground)]">Privacy</Link>
          <a href="mailto:hello@clipfactory.app" className="hover:text-[var(--color-foreground)]">Contact</a>
        </nav>
      </Container>
    </footer>
  );
}
