import type { NextConfig } from "next";

// Next.js dev (HMR / react-refresh) requires 'unsafe-eval', and localhost API
// calls are plain http — so the strict CSP only applies in production builds.
const isDev = process.env.NODE_ENV !== "production";

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob: https:",
  "font-src 'self' data:",
  "style-src 'self' 'unsafe-inline'",
  `script-src 'self' 'unsafe-inline' ${isDev ? "'unsafe-eval' " : ""}https://js.stripe.com https://challenges.cloudflare.com https://*.posthog.com https://*.i.posthog.com`,
  "connect-src 'self' http://localhost:8000 https://api.clipfactory.app https://*.supabase.co https://api.stripe.com https://challenges.cloudflare.com https://*.posthog.com https://*.i.posthog.com",
  "frame-src https://js.stripe.com https://hooks.stripe.com https://challenges.cloudflare.com",
  // upgrade-insecure-requests would rewrite http://localhost:8000 -> https and break local dev.
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const config: NextConfig = {
  // All route metadata is static and inexpensive. Keeping it in <head>
  // preserves compatibility with HTML-only auditors, link unfurlers and
  // crawlers instead of relying on streamed metadata in the document body.
  htmlLimitedBots: /.*/,
  reactStrictMode: true,
  poweredByHeader: false,
  typedRoutes: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=()" },
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
        ],
      },
    ];
  },
};

export default config;
