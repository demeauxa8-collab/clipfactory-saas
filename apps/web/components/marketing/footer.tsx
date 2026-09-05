import Link from "next/link";
import { Github, Mail, Twitter } from "lucide-react";
import { Container } from "@/components/ui/container";
import { DotPattern } from "@/components/ui/dot-pattern";
import { SITE } from "@/lib/site";
import { cn } from "@/lib/utils";

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

function Column({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string }[];
}) {
  return (
    <div>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/30">
        {title}
      </h3>
      <ul className="mt-5 space-y-3">
        {links.map((l) => (
          <li key={l.href}>
            <Link
              href={l.href as never}
              className="text-[14px] text-white/50 transition-colors hover:text-white"
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MarketingFooter() {
  return (
    <footer className="relative overflow-hidden border-t border-white/[0.06] bg-[#08080a] pb-10 pt-20">
      <DotPattern
        width={26}
        height={26}
        cr={1}
        className={cn(
          "absolute inset-0 h-full w-full fill-white/[0.06]",
          "[mask-image:radial-gradient(70%_60%_at_50%_0%,#000,transparent_75%)]",
        )}
      />

      <Container className="relative">
        <div className="grid gap-12 md:grid-cols-12">
          <div className="md:col-span-5">
            <Link href="/" className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="grid size-6 place-items-center rounded-[0.55rem] border border-white/12 bg-white/[0.06]"
              >
                <span className="h-2.5 w-1 rounded-full bg-[#0a84ff] shadow-[0_0_8px_1px_rgba(10,132,255,0.8)]" />
              </span>
              <span className="text-[15px] font-semibold tracking-[-0.02em] text-white">
                {SITE.name}
              </span>
            </Link>

            <p className="mt-5 max-w-xs text-[14px] leading-relaxed text-white/40">
              Turn long videos into a focused series of vertical clips — with
              the reasoning behind every cut.
            </p>

            <div className="mt-7 flex items-center gap-2">
              {[
                { href: `mailto:${SITE.contactEmail}`, Icon: Mail, label: "Email" },
                { href: "https://github.com", Icon: Github, label: "GitHub" },
                { href: "https://x.com", Icon: Twitter, label: "X" },
              ].map(({ href, Icon, label }) => (
                <a
                  key={label}
                  href={href}
                  aria-label={label}
                  className="grid size-9 place-items-center rounded-full border border-white/[0.08] bg-white/[0.03] text-white/45 transition-colors hover:border-white/20 hover:text-white"
                >
                  <Icon className="size-4" />
                </a>
              ))}
            </div>
          </div>

          <div className="grid gap-10 sm:grid-cols-3 md:col-span-7">
            <Column title="Product" links={PRODUCT} />
            <Column title="Use cases" links={USE_CASES} />
            <Column title="Company" links={COMPANY} />
          </div>
        </div>

        <div className="mt-16 flex flex-col items-start justify-between gap-4 border-t border-white/[0.06] pt-8 sm:flex-row sm:items-center">
          <p className="text-[13px] text-white/30">
            © {new Date().getFullYear()} {SITE.name}. Processed in the EU.
          </p>
          <p className="text-[13px] text-white/30">
            29€/month · 300 video minutes · no watermark
          </p>
        </div>
      </Container>
    </footer>
  );
}
