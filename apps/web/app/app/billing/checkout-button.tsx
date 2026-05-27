"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";

type CheckoutResp = { checkout_url: string };

export function CheckoutButton({ hasActive }: { hasActive: boolean }) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const r = await apiFetch<CheckoutResp>("/billing/checkout", {
        method: "POST",
        json: { plan_code: "starter" },
      });
      window.location.href = r.checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.code ?? err.message : "unexpected_error");
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button onClick={start} disabled={busy}>
        {busy ? "Opening Stripe…" : hasActive ? "Manage / renew" : "Start Starter"}
      </Button>
      {error && <span className="text-sm text-[var(--color-danger)]">{error}</span>}
    </div>
  );
}
