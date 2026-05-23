import Link from "next/link";
import { Container } from "@/components/ui/container";
import { SITE } from "@/lib/site";

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] py-12 text-sm text-[var(--color-muted-foreground)]">
      <Container className="grid gap-10 md:grid-cols-4">
        <div className="md:col-span-2">
          <Link href="/" className="flex items-center gap-2 font-semibold text-[var(--color-foreground)]">
            <span className="inline-block h-4 w-4 rounded-sm bg-[var(--color-foreground)]" aria-hidden />
            {SITE.name}
          </Link>
          <p className="mt-3 max-w-sm">{SITE.shortDescription}</p>
          <p className="mt-3 text-xs">EU hosted · Built for creators and agencies.</p>
        </div>
        <div>
          <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--color-foreground)]">Product</h4>
          <ul className="space-y-2">
            <li><Link href="/features" className="hover:text-[var(--color-foreground)]">Features</Link></li>
            <li><Link href="/pricing" className="hover:text-[var(--color-foreground)]">Pricing</Link></li>
            <li><Link href="/faq" className="hover:text-[var(--color-foreground)]">FAQ</Link></li>
            <li><Link href="/changelog" className="hover:text-[var(--color-foreground)]">Changelog</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--color-foreground)]">Company</h4>
          <ul className="space-y-2">
            <li><Link href="/about" className="hover:text-[var(--color-foreground)]">About</Link></li>
            <li><a href={`mailto:${SITE.contactEmail}`} className="hover:text-[var(--color-foreground)]">Contact</a></li>
            <li><Link href="/legal/terms" className="hover:text-[var(--color-foreground)]">Terms</Link></li>
            <li><Link href="/legal/privacy" className="hover:text-[var(--color-foreground)]">Privacy</Link></li>
          </ul>
        </div>
      </Container>
      <Container className="mt-10 flex flex-col items-start justify-between gap-2 border-t border-[var(--color-border)] pt-6 text-xs md:flex-row">
        <p>© {new Date().getFullYear()} {SITE.name}. All rights reserved.</p>
        <p>Made with care in France.</p>
      </Container>
    </footer>
  );
}
