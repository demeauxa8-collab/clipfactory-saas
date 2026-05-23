export const SITE = {
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://clipfactory.app",
  name: "ClipFactory",
  shortDescription:
    "Campaign-first AI clipping. Picks clips that fit your campaign, your audience and your past performance — not random viral moments.",
  longDescription:
    "ClipFactory turns long videos into publish-ready vertical shorts. Each clip is scored by hook, emotion, visual context and campaign fit, with an explanation you can argue with.",
  twitter: "@clipfactoryapp",
  contactEmail: "hello@clipfactory.app",
  founder: "Augustin Demeaux",
  pricingFromEur: 29,
} as const;

export const NAV_PRIMARY = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/faq", label: "FAQ" },
  { href: "/about", label: "About" },
] as const;
