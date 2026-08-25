"use client";

import { AlertTriangle, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ProductPanel,
  ProductStatus,
} from "@/components/product/product-primitives";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
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
