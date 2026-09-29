import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";
import { ArrowLeft, Check, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function ProductMark({ className }: { className?: string }) {
  return (
    <span className={cn("cf-mark", className)} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

export function ProductBrand({
  href = "/",
  compact = false,
}: {
  href?: Route;
  compact?: boolean;
}) {
  return (
    <Link className="cf-brand" href={href} aria-label="ClipFactory home">
      <ProductMark />
      {!compact ? <span>ClipFactory</span> : null}
    </Link>
  );
}

export function ProductPageIntro({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("cf-page-intro cf-enter", className)}>
      <div className="cf-page-intro__copy">
        {eyebrow ? <div className="cf-eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="cf-page-intro__actions">{actions}</div> : null}
    </header>
  );
}

export function ProductPanel({
  children,
  className,
  as: Element = "section",
  tone = "default",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "aside" | "div";
  tone?: "default" | "raised" | "paper" | "signal";
}) {
  return (
    <Element className={cn("cf-panel", `cf-panel--${tone}`, className)}>
      {children}
    </Element>
  );
}

export function ProductSectionTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="cf-section-title">
      <div>
        {eyebrow ? <p>{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <span>{description}</span> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function ProductStatus({
  children,
  tone = "neutral",
  pulse = false,
}: {
  children: ReactNode;
  tone?: "neutral" | "action" | "success" | "warning" | "danger";
  pulse?: boolean;
}) {
  return (
    <span className={cn("cf-status", `cf-status--${tone}`)}>
      <span
        className={cn("cf-status__dot", pulse && "cf-status__dot--pulse")}
      />
      {children}
    </span>
  );
}

export function ProductBackLink({
  href,
  children = "Back",
}: {
  href: Route;
  children?: ReactNode;
}) {
  return (
    <Link className="cf-back-link" href={href}>
      <ArrowLeft aria-hidden="true" />
      {children}
    </Link>
  );
}

export function ProductEmptyState({
  title,
  description,
  action,
  icon: Icon,
}: {
  title: ReactNode;
  description: ReactNode;
  action?: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="cf-empty-state">
      {Icon ? (
        <span className="cf-empty-state__icon">
          <Icon aria-hidden="true" />
        </span>
      ) : null}
      <h3>{title}</h3>
      <p>{description}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function ProductCheckList({ children }: { children: ReactNode }) {
  return <ul className="cf-check-list">{children}</ul>;
}

export function ProductCheck({ children }: { children: ReactNode }) {
  return (
    <li>
      <span aria-hidden="true">
        <Check />
      </span>
      {children}
    </li>
  );
}
