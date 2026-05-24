export const SITE = {
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://clipfactory.app",
  name: "ClipFactory",
  legalName: "ClipFactory",
  shortDescription:
    "Campaign-first AI clipping. Turn long videos into vertical shorts that match your audience — not random viral picks. Every clip ships with a score you can argue with.",
  longDescription:
    "ClipFactory is the AI clipping tool built for creators and agencies who run real campaigns. Instead of 10 generic viral clips, ClipFactory reads your campaign brief, maps the whole video, finds narrative arcs across distant moments, and renders publish-ready vertical shorts. Every clip ships with an explained score — no black-box virality number.",
  tagline: "Less random virals. More clips that fit your campaign.",
  twitter: "@clipfactoryapp",
  contactEmail: "hello@clipfactory.app",
  founder: "Augustin Demeaux",
  pricingFromEur: 29,
  freeTrialDays: 0,
  keywords: [
    "AI clipping tool",
    "AI video clipping",
    "campaign-first AI clipping",
    "YouTube to Shorts AI",
    "podcast to shorts AI",
    "long video to shorts",
    "AI viral clip generator",
    "AI video editing for creators",
    "AI shorts for agencies",
    "explainable AI clipping score",
    "vertical short generator",
    "TikTok Reels Shorts generator",
    "AI clip from long video",
    "EU hosted AI clipping",
    "campaign brief AI editor",
    "narrative arcs AI clipping",
    "multi-segment AI clipping",
    "story-first AI shorts",
    "AI montage long video",
    "automatic vertical clip",
  ],
} as const;

export const NAV_PRIMARY = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/faq", label: "FAQ" },
  { href: "/about", label: "About" },
] as const;
