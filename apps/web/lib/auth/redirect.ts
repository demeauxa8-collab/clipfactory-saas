const AUTH_REDIRECT_BASE = "https://clipfactory.local";

/**
 * Keep post-authentication redirects inside authenticated ClipFactory routes.
 * URL parsing also rejects protocol-relative and malformed destinations.
 */
export function safeProtectedPath(value?: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/app";
  }

  try {
    const url = new URL(value, AUTH_REDIRECT_BASE);
    const isProtectedPath =
      url.pathname === "/app" ||
      url.pathname.startsWith("/app/") ||
      url.pathname === "/admin" ||
      url.pathname.startsWith("/admin/");

    if (url.origin !== AUTH_REDIRECT_BASE || !isProtectedPath) {
      return "/app";
    }

    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return "/app";
  }
}
