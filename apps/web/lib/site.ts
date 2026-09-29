export const SITE = {
  url: new URL(
    process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
      "https://clipfactory-saas-demeauxa8-1591s-projects.vercel.app",
  ).origin,
  name: "ClipFactory",
  legalName: "ClipFactory",
  shortDescription:
    "AI clip maker for creators. Turn long YouTube videos, podcasts, webinars and interviews into a focused series of Shorts, Reels and TikToks.",
  longDescription:
    "ClipFactory is an AI video clipping tool that turns long videos into a focused series of short vertical clips for TikTok, Instagram Reels and YouTube Shorts. Paste a YouTube or Vimeo link, explain who the clips are for and what the series should achieve, and ClipFactory finds strong moments, checks what happens on screen, connects moments when the edit needs it, adds captions and gives each clip a simple score.",
  tagline: "Long video in. Clip series out.",
  contactEmail: "hello@clipfactory.app",
  founder: "Augustin Demeaux",
  pricingFromEur: 29,
  freeTrialDays: 0,
} as const;

export const NAV_PRIMARY = [
  { href: "/features", label: "Features" },
  { href: "/use-cases", label: "Use cases" },
  { href: "/pricing", label: "Pricing" },
  { href: "/vs/opusclip", label: "vs OpusClip" },
  { href: "/guides", label: "Guides" },
] as const;
