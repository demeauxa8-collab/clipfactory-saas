"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { MarketingBrand } from "./brand";

export function MarketingNav({ language = "en" }: { language?: "en" | "fr" }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const fr = language === "fr";
  const links = fr
    ? [
        { href: "/clipping-ia", label: "Clipping IA" },
        { href: "#workflow", label: "Comment ça marche" },
        { href: "#pricing", label: "Tarif" },
        { href: "#questions", label: "Questions" },
      ]
    : [
        { href: "/features", label: "Features" },
        { href: "/pricing", label: "Pricing" },
        { href: "/guides", label: "Guides" },
        { href: "/clipping-tools", label: "Clipping tools" },
      ];
  useEffect(() => {
    setOpen(false);
  }, [pathname]);
  return (
    <header
      className="marketing-nav"
      lang={language}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          setOpen(false);
          trigger.current?.focus();
        }
      }}
    >
      <div className="marketing-nav-bar">
        <MarketingBrand />
        <nav
          aria-label={fr ? "Navigation principale" : "Main navigation"}
          className="marketing-nav-links"
        >
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href as Route}
              aria-current={
                pathname === href || pathname.startsWith(`${href}/`)
                  ? "page"
                  : undefined
              }
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="marketing-nav-actions">
          <Link className="marketing-sign-in" href="/login">
            {fr ? "Connexion" : "Sign in"}
          </Link>
          <Link
            className="marketing-nav-cta"
            href="/login?next=/app/campaigns/new"
          >
            {fr ? "Créer un clip" : "Start a campaign"}
            <ArrowUpRight aria-hidden="true" size={14} />
          </Link>
          <button
            ref={trigger}
            className="marketing-menu-toggle"
            type="button"
            aria-expanded={open}
            aria-controls="marketing-mobile-menu"
            aria-label={
              fr
                ? open
                  ? "Fermer le menu"
                  : "Ouvrir le menu"
                : open
                  ? "Close menu"
                  : "Open menu"
            }
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
      <nav
        id="marketing-mobile-menu"
        hidden={!open}
        className="marketing-mobile-menu"
        aria-label={fr ? "Navigation mobile" : "Mobile navigation"}
      >
        {links.map(({ href, label }) => (
          <Link
            key={href}
            href={href as Route}
            aria-current={
              pathname === href || pathname.startsWith(`${href}/`)
                ? "page"
                : undefined
            }
            onClick={() => setOpen(false)}
          >
            {label}
          </Link>
        ))}
        <Link href="/login" onClick={() => setOpen(false)}>
          {fr ? "Connexion" : "Sign in"}
        </Link>
      </nav>
    </header>
  );
}
