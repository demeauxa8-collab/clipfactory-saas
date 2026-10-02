"use client";

import * as React from "react";

// Last-resort boundary: replaces the root layout when an error escapes every
// other boundary (otherwise the browser shows Next's bare "Application error").
// A full reload, not reset(), is the reliable recovery: the most common cause
// is a page loaded from a previous deployment requesting chunks that no longer
// exist.
export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    void import("@/lib/analytics")
      .then(({ track }) =>
        track("app_error", {
          boundary: "global",
          digest: error.digest ?? null,
          name: error.name,
          message: error.message.slice(0, 200),
          path: window.location.pathname,
        }),
      )
      .catch(() => {
        /* reporting must never block recovery */
      });
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "grid",
          placeItems: "center",
          background: "#09090b",
          color: "#fafafa",
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        }}
      >
        <main
          style={{ maxWidth: 420, padding: "0 16px", textAlign: "center" }}
        >
          <h1 style={{ fontSize: 20, lineHeight: 1.3, margin: "0 0 8px" }}>
            Something went wrong on this page.
          </h1>
          <p
            style={{
              fontSize: 15,
              lineHeight: 1.55,
              margin: "0 0 20px",
              color: "#a1a1aa",
            }}
          >
            Nothing was lost. Reloading usually fixes it, especially right
            after an update.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              font: "inherit",
              fontSize: 15,
              fontWeight: 600,
              padding: "10px 18px",
              borderRadius: 10,
              border: "none",
              background: "#fafafa",
              color: "#09090b",
              cursor: "pointer",
            }}
          >
            Reload the page
          </button>
        </main>
      </body>
    </html>
  );
}
