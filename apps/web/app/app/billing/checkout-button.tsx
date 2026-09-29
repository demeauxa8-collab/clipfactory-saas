"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";

type BillingResp = { checkout_url?: string; portal_url?: string };

export function CheckoutButton({
  planCode,
  label,
  portal = false,
}: {
  planCode?: "starter" | "pro";
  label: string;
  portal?: boolean;
}) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function start() {
    setBusy(true);
    setError(null);
    void track("upgrade_clicked", { plan_code: planCode, portal });
    try {
      const r = await apiFetch<BillingResp>(portal ? "/billing/portal" : "/billing/checkout", {
        method: "POST",
        ...(portal ? {} : { json: { plan_code: planCode } }),
      });
      const url = portal ? r.portal_url : r.checkout_url;
      if (!url) throw new Error("missing_billing_url");
      window.location.href = url;
    } catch (err) {
      const detail = err instanceof ApiError
        ? (err.detail as { detail?: { message?: string } } | undefined)?.detail
        : undefined;
      setError(detail?.message ?? "Billing is unavailable. Please try again later.");
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button onClick={start} disabled={busy}>
        {busy ? "Opening Stripe…" : label}
      </Button>
      {error && <span role="alert" className="text-sm text-[var(--color-danger)]">{error}</span>}
    </div>
  );
}
