"use client";

import * as React from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics";
import {
  ProductPanel,
  ProductStatus,
} from "@/components/product/product-primitives";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Report the crash so failures in the workspace become visible in analytics.
  // Only the digest, error name and a short message leave the browser.
  React.useEffect(() => {
    void track("app_error", {
      digest: error.digest ?? null,
      name: error.name,
      message: error.message.slice(0, 200),
      path: window.location.pathname,
    });
  }, [error]);

  return (
    <div className="cf-page cf-route-error">
      <ProductPanel tone="signal">
        <ProductStatus tone="danger">Workspace interrupted</ProductStatus>
        <AlertTriangle aria-hidden="true" />
        <h1>We could not load this part of the source thread.</h1>
        <p>
          Nothing was changed. Retry the request; your campaign, source and
          delivered cuts remain in their last confirmed state.
        </p>
        <Button type="button" onClick={reset}>
          <RefreshCcw aria-hidden="true" />
          Try again
        </Button>
      </ProductPanel>
    </div>
  );
}
