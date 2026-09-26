"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { CreditCard, House, Plus, Target } from "lucide-react";
import { cn } from "@/lib/utils";

type NavItem = {
  href: Route;
  label: string;
  icon: typeof House;
  exact?: boolean;
};

const items: NavItem[] = [
  { href: "/app", label: "Workspace", icon: House, exact: true },
  { href: "/app/campaigns/new", label: "New brief", icon: Plus },
  { href: "/app/billing", label: "Billing", icon: CreditCard },
] as const;

function isActive(pathname: string, href: string, exact?: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();

  return (
    <nav
      className={cn(mobile ? "cf-mobile-nav" : "cf-app-nav")}
      aria-label={mobile ? "Mobile product navigation" : "Product navigation"}
    >
      {items.map(({ href, label, icon: Icon, exact }) => (
        <Link
          key={href}
          href={href}
          data-active={isActive(pathname, href, exact)}
        >
          <Icon aria-hidden="true" />
          <span>{label}</span>
        </Link>
      ))}
      {mobile ? (
        <Link
          href={
            (pathname.startsWith("/app/campaigns/") &&
            !pathname.endsWith("/new")
              ? pathname
              : "/app") as Route
          }
          data-active={
            pathname.startsWith("/app/campaigns/") && !pathname.endsWith("/new")
          }
        >
          <Target aria-hidden="true" />
          <span>Campaign</span>
        </Link>
      ) : null}
    </nav>
  );
}
