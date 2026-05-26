import Link from "next/link";
import { Github, Mail, Twitter } from "lucide-react";
import { Container } from "@/components/ui/container";
import { SITE } from "@/lib/site";

const PRODUCT = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/vs/opusclip", label: "vs OpusClip" },
  { href: "/changelog", label: "Changelog" },
];

const USE_CASES = [
  { href: "/use-cases/creators", label: "For creators" },
  { href: "/use-cases/agencies", label: "For agencies" },
  { href: "/faq", label: "FAQ" },
];

const COMPANY = [
  { href: "/about", label: "About" },
  { href: `mailto:${SITE.contactEmail}`, label: "Contact" },
  { href: "/legal/terms", label: "Terms" },
  { href: "/legal/privacy", label: "Privacy" },
];

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-[#050505] py-16 text-sm text-[var(--color-muted-foreground)]">
      <Container className="grid gap-12 md:grid-cols-12">
        {/* Brand + tagline */}
        <div className="md:col-span-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-base font-semibold text-[var(--color-foreground)]"
          >
            <span
              className="relative inline-flex h-5 w-5 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]"
              aria-hidden
            >
              <span className="h-2.5 w-1 rounded-sm bg-[var(--color-brand)]" />
            </span>
            {SITE.name}
          </Link>
          <p className="mt-4 max-w-xs leading-relaxed">
            AI video clipping for creators, podcasts and agencies. Long videos in,
            focused clip series out.
          </p>
          <div className="mt-6 flex items-center gap-3">
            <a
              href={`mailto:${SITE.contactEmail}`}
              aria-label="Email"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--color-border)] transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-brand)] hover:text-[var(--color-brand)]"
            >
              <Mail className="h-4 w-4" />
            </a>
            <a
              href="https://twitter.com/clipfactoryapp"
              aria-label="Twitter"
              rel="noreferrer"
              target="_blank"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--color-border)] transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-brand)] hover:text-[var(--color-brand)]"
            >
              <Twitter className="h-4 w-4" />
            </a>
            <a
              href="https://github.com/demeauxa8-collab/clipfactory-saas"
              aria-label="GitHub"
              rel="noreferrer"
              target="_blank"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--color-border)] transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-brand)] hover:text-[var(--color-brand)]"
            >
              <Github className="h-4 w-4" />
            </a>
          </div>
        </div>

        {/* Columns */}
        <div className="md:col-span-2">
          <FooterCol title="Product" items={PRODUCT} />
        </div>
        <div className="md:col-span-2">
          <FooterCol title="Use cases" items={USE_CASES} />
        </div>
        <div className="md:col-span-2">
          <FooterCol title="Company" items={COMPANY} />
        </div>

        {/* Newsletter */}
        <div className="md:col-span-2">
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-foreground)]">
            Updates
          </h4>
          <p className="text-xs leading-relaxed">
            New features, lessons learned shipping a one-person SaaS. One email, never spam.
          </p>
          <a
            href={`mailto:${SITE.contactEmail}?subject=Subscribe%20to%20updates`}
            className="mt-4 inline-flex items-center justify-center rounded-md border border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-3 py-2 text-xs font-medium text-[var(--color-brand)] transition-colors hover:bg-[var(--color-brand)] hover:text-[var(--color-brand-foreground)]"
          >
            Get product updates
          </a>
        </div>
      </Container>

      <Container className="mt-12 flex flex-col items-start justify-between gap-2 border-t border-[var(--color-border)] pt-6 text-xs md:flex-row">
        <p>
          © {new Date().getFullYear()} {SITE.name}. All rights reserved.
        </p>
        <p>Made with care in France · EU-hosted infrastructure</p>
      </Container>
    </footer>
  );
}

function FooterCol({
  title,
  items,
}: {
  title: string;
  items: readonly { href: string; label: string }[];
}) {
  return (
    <>
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-foreground)]">
        {title}
      </h4>
      <ul className="space-y-2">
        {items.map((it) => (
          <li key={it.href}>
            <Link
              href={it.href as never}
              className="hover:text-[var(--color-brand)]"
            >
              {it.label}
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
