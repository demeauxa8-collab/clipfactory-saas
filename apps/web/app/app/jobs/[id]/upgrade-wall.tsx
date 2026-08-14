"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { track } from "@/lib/analytics";

type CheckoutResp = { checkout_url: string };

/**
 * The paywall, placed under the finished clips rather than in front of them.
 * By the time this renders the visitor has already watched their own video get
 * cut, scored and captioned, and has one real clip in hand.
 */
export function UpgradeWall({
  lockedCount,
  totalCount,
}: {
  lockedCount: number;
  totalCount: number;
}) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    void track("paywall_seen", { locked_count: lockedCount, total_count: totalCount });
  }, [lockedCount, totalCount]);

  async function start() {
    setBusy(true);
    setError(null);
    void track("upgrade_clicked", { source: "job_paywall", locked_count: lockedCount });
    try {
      const r = await apiFetch<CheckoutResp>("/billing/checkout", {
        method: "POST",
        json: { plan_code: "starter" },
      });
      window.location.href = r.checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? (err.code ?? err.message) : "unexpected_error");
      setBusy(false);
    }
  }

  return (
    <div id="upgrade-wall" className="pro-card mt-8 scroll-mt-8 rounded-lg p-6">
      <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">
        Your clips are ready
      </p>
      <h3 className="mt-2 text-xl font-semibold tracking-tight">
        {lockedCount === totalCount
          ? `${totalCount} clips rendered, waiting for you`
          : `${lockedCount} of your ${totalCount} clips are still locked`}
      </h3>
      <p className="mt-2 max-w-prose text-sm text-[var(--color-muted-foreground)]">
        Cut, captioned and scored — already sitting on our servers in 1080×1920. Nothing left to
        render: pick a plan and every file downloads immediately.
      </p>

      <ul className="mt-5 grid gap-2 text-sm sm:grid-cols-2">
        {[
          "Download these clips right now",
          "300 video minutes every month",
          "No watermark, no revenue share",
          "Cancel anytime from Stripe",
        ].map((line) => (
          <li key={line} className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-muted-foreground)]" />
            <span>{line}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button onClick={start} disabled={busy}>
          {busy ? "Opening Stripe…" : "Download my clips — 29€/month"}
        </Button>
        <span className="text-xs text-[var(--color-muted-foreground)]">
          VAT included. No revenue share, ever.
        </span>
      </div>
      {error && <p className="mt-3 text-sm text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}
