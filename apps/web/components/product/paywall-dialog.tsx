"use client";

import * as React from "react";

import {
  ProductCheck,
  ProductCheckList,
  ProductStatus,
} from "@/components/product/product-primitives";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import styles from "./paywall-dialog.module.css";

export type PaywallReason =
  "no_subscription" | "insufficient_credits" | "past_due";

export type PaywallSourceContext =
  | string
  | {
      title: string;
      detail?: string;
    };

export interface PaywallDialogProps {
  reason: PaywallReason;
  trigger: React.ReactElement;
  sourceContext?: PaywallSourceContext;
  availableCredits?: number;
  requiredCredits?: number;
  checkoutHref: string;
}

const reasonCopy: Record<
  PaywallReason,
  {
    status: string;
    tone: "action" | "warning" | "danger";
    title: string;
    description: string;
    action: string;
    support: string;
  }
> = {
  no_subscription: {
    status: "Starter required",
    tone: "action",
    title: "Your source is ready. Unlock the processing run.",
    description:
      "The campaign brief and source setup are already done. Activate Starter to run the real analysis and create up to three campaign-ready clips.",
    action: "Continue to secure checkout",
    support:
      "Stripe processes the payment securely. Your source draft stays in this browser tab.",
  },
  insufficient_credits: {
    status: "Credits required",
    tone: "warning",
    title: "This source needs more credits.",
    description:
      "ClipFactory uses one credit per minute of source video. Your source stays ready while you review billing.",
    action: "Review billing",
    support: "No credits are charged until processing starts.",
  },
  past_due: {
    status: "Payment needs attention",
    tone: "danger",
    title: "Update billing to keep processing.",
    description:
      "Your Starter payment could not be completed. Resolve billing before starting another analysis.",
    action: "Review billing",
    support: "Your existing campaigns and finished clips remain available.",
  },
};

const creditFormatter = new Intl.NumberFormat("en-US");

function normalizeSourceContext(sourceContext?: PaywallSourceContext) {
  if (!sourceContext) {
    return {
      title: "Your source is ready to enter processing.",
      detail: undefined,
    };
  }

  if (typeof sourceContext === "string") {
    return { title: sourceContext, detail: undefined };
  }

  return sourceContext;
}

export function PaywallDialog({
  reason,
  trigger,
  sourceContext,
  availableCredits,
  requiredCredits,
  checkoutHref,
}: PaywallDialogProps) {
  const checkoutButtonRef = React.useRef<HTMLButtonElement>(null);
  const copy = reasonCopy[reason];
  const source = normalizeSourceContext(sourceContext);
  const hasCreditContext =
    typeof availableCredits === "number" || typeof requiredCredits === "number";

  function continueToBilling() {
    window.location.assign(checkoutHref);
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent
        className={styles.dialog}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          checkoutButtonRef.current?.focus();
        }}
      >
        <div className={styles.layout}>
          <section className={styles.main}>
            <div className={styles.status}>
              <ProductStatus tone={copy.tone}>{copy.status}</ProductStatus>
            </div>

            <DialogTitle className={styles.title}>{copy.title}</DialogTitle>
            <DialogDescription className={styles.description}>
              {copy.description}
            </DialogDescription>

            <div className={styles.source}>
              <p className={styles.sourceLabel}>Ready to process</p>
              <p className={styles.sourceTitle}>{source.title}</p>
              {source.detail ? (
                <p className={styles.sourceDetail}>{source.detail}</p>
              ) : null}

              {hasCreditContext ? (
                <div
                  className={styles.creditGrid}
                  aria-label="Credit requirement"
                >
                  <div>
                    <span>Available</span>
                    <strong>
                      {typeof availableCredits === "number"
                        ? creditFormatter.format(availableCredits)
                        : "—"}
                    </strong>
                  </div>
                  <div>
                    <span>Required</span>
                    <strong>
                      {typeof requiredCredits === "number"
                        ? creditFormatter.format(requiredCredits)
                        : "—"}
                    </strong>
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <aside className={styles.plan} aria-label="Starter plan">
            <div>
              <p className={styles.planLabel}>ClipFactory plan</p>
              <div className={styles.planHead}>
                <p className={styles.planName}>Starter</p>
                <p className={styles.price}>
                  €29 <span>/ month</span>
                </p>
              </div>

              <div className={styles.checks}>
                <ProductCheckList>
                  <ProductCheck>300 credits each month</ProductCheck>
                  <ProductCheck>Up to 30 minutes per source</ProductCheck>
                  <ProductCheck>Up to 3 clips per source</ProductCheck>
                </ProductCheckList>
              </div>
            </div>

            <div className={styles.actions}>
              <Button
                ref={checkoutButtonRef}
                size="lg"
                type="button"
                onClick={continueToBilling}
              >
                {copy.action}
              </Button>
              <DialogClose asChild>
                <Button variant="ghost" type="button">
                  Not now
                </Button>
              </DialogClose>
              <p className={styles.support}>{copy.support}</p>
            </div>
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  );
}
