// Canonical origin, in order of trust:
//   1. NEXT_PUBLIC_SITE_URL — set this once a domain we own is attached;
//   2. the Vercel production URL, injected automatically by the platform;
//   3. localhost, for `next dev`.
//
// Never hard-code a domain here. A wrong value silently tells Google that the
// canonical version of every page lives somewhere else, which hands the whole
// site's ranking to whoever owns that domain.
function siteOrigin(): string {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL;
  if (explicit) return explicit.replace(/\/$/, "");
  const vercel = process.env.NEXT_PUBLIC_VERCEL_PROJECT_PRODUCTION_URL;
  if (vercel) return `https://${vercel}`;
  return "http://localhost:3000";
}

export const SITE = {
  url: siteOrigin(),
  name: "ClipFactory",
  legalName: "ClipFactory",
  shortDescription:
    "AI clip maker for creators. Turn long YouTube videos, podcasts, webinars and interviews into a focused series of Shorts, Reels and TikToks.",
  longDescription:
    "ClipFactory is an AI video clipping tool that turns long videos into a focused series of short vertical clips for TikTok, Instagram Reels and YouTube Shorts. Paste a YouTube or Vimeo link, explain who the clips are for and what the series should achieve, and ClipFactory finds strong moments, checks what happens on screen, connects moments when the edit needs it, adds captions and gives each clip a simple score.",
  tagline: "Long video in. Clip series out.",
  twitter: "@clipfactoryapp",
  // Single source for every mailto: on the site. The default belongs to the
  // clipfactory.app domain, which we do not own — set NEXT_PUBLIC_CONTACT_EMAIL
  // to a real inbox before sending anyone here.
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "hello@clipfactory.app",
  founder: "Augustin Demeaux",
  pricingFromEur: 29,
  freeTrialDays: 0,
  keywords: [
    "AI clipping tool",
    "AI clip maker",
    "AI video clip maker",
    "AI video clipping",
    "AI shorts generator",
    "AI montage tool",
    "AI vision video clipping",
    "context-aware AI clipper",
    "YouTube Shorts generator",
    "AI clipping for marketing campaigns",
    "YouTube to Shorts AI",
    "podcast to shorts AI",
    "webinar to shorts AI",
    "interview to shorts AI",
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
  { href: "/use-cases", label: "Use cases" },
  { href: "/pricing", label: "Pricing" },
  { href: "/vs/opusclip", label: "vs OpusClip" },
  { href: "/about", label: "About" },
] as const;
