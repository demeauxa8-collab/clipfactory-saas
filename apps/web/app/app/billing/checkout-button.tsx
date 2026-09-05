"use client";

import * as React from "react";
import { ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";

type CheckoutResponse = { checkout_url: string };

export function CheckoutButton() {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function startCheckout() {
    setBusy(true);
    setError(null);
    void track("upgrade_clicked", { plan_code: "starter" });
    try {
      const response = await apiFetch<CheckoutResponse>("/billing/checkout", {
        method: "POST",
        json: { plan_code: "starter" },
      });
      window.location.assign(response.checkout_url);
    } catch (caught) {
      const code =
        caught instanceof ApiError
          ? (caught.code ?? caught.message)
          : "unexpected_error";
      setError(humanizeCheckoutError(code));
      setBusy(false);
    }
  }

  return (
    <div>
      <Button
        type="button"
        size="lg"
        onClick={startCheckout}
        disabled={busy}
        className="w-full"
      >
        {busy ? "Opening secure checkout…" : "Continue — €29/month"}
        {!busy ? <ArrowUpRight aria-hidden="true" /> : null}
      </Button>
      {error ? (
        <p className="mt-3 text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function humanizeCheckoutError(code: string) {
  if (code === "checkout_unavailable")
    return "Secure checkout is temporarily unavailable. Nothing was charged.";
  if (code === "token_expired")
    return "Your session expired. Sign in again before opening checkout.";
  return "Checkout did not open. Nothing was charged. Try again in a moment.";
}
