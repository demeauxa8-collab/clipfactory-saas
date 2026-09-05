import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CreditCard,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ProductCheck,
  ProductCheckList,
  ProductPageIntro,
  ProductPanel,
  ProductSectionTitle,
  ProductStatus,
} from "@/components/product/product-primitives";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { CheckoutButton } from "./checkout-button";
import styles from "./billing.module.css";

export const metadata = { title: "Billing" };

export default async function BillingPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status: checkoutStatus } = await searchParams;
  const supabase = await createSupabaseServerClient();
  const [subscriptionResult, ledgerResult] = await Promise.all([
    supabase
      .from("subscriptions")
      .select("plan_code, status, current_period_end, cancel_at_period_end")
      .order("current_period_end", { ascending: false, nullsFirst: false })
      .limit(1)
      .maybeSingle(),
    supabase.from("credit_ledger").select("delta"),
  ]);

  const subscription = subscriptionResult.data;
  const balance = (ledgerResult.data ?? []).reduce(
    (total, entry) =>
      total + (typeof entry.delta === "number" ? entry.delta : 0),
    0,
  );
  const isActive =
    subscription?.status === "active" || subscription?.status === "trialing";
  const isPastDue = subscription?.status === "past_due";
  const isCanceled = subscription?.status === "canceled";
  const canStartCheckout = !subscription || isCanceled;
  const remainingPct = Math.max(
    0,
    Math.min(100, Math.round((balance / 300) * 100)),
  );

  return (
    <div className="cf-page cf-page--narrow">
      <ProductPageIntro
        eyebrow="Plan and credits"
        title={
          isActive ? "Your account ledger." : "Keep the source thread moving."
        }
        description={
          isActive
            ? "A calm record of the plan that powers your analyses. Finished cuts remain separate from monthly credit usage."
            : "One plan unlocks the campaign-to-cut workflow. No tier maze, no feature comparison theater."
        }
        actions={
          isActive ? (
            <ProductStatus tone="success">Starter active</ProductStatus>
          ) : undefined
        }
      />

      {checkoutStatus === "success" ? (
        <ProductPanel tone="signal" className={styles.notice}>
          <CheckCircle2 aria-hidden="true" />
          <div>
            <strong>Checkout returned. We are confirming Starter.</strong>
            <p>
              Credits appear only after the billing event is processed. Refresh
              this page if the status does not update.
            </p>
          </div>
        </ProductPanel>
      ) : null}
      {checkoutStatus === "cancel" ? (
        <ProductPanel className={styles.notice}>
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Checkout closed.</strong>
            <p>
              Nothing was confirmed. Your campaign and source remain where you
              left them.
            </p>
          </div>
        </ProductPanel>
      ) : null}
      {isPastDue ? (
        <ProductPanel tone="signal" className={styles.notice}>
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Starter needs billing attention.</strong>
            <p>
              New analyses are paused. In-app payment recovery is not available
              yet, so support must resolve this account state.
            </p>
          </div>
        </ProductPanel>
      ) : null}
      {isCanceled ? (
        <ProductPanel className={styles.notice}>
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>Starter has ended.</strong>
            <p>
              Your existing campaigns and cuts remain in the workspace. A new
              Checkout can start a new billing period.
            </p>
          </div>
        </ProductPanel>
      ) : null}

      {canStartCheckout ? (
        <ProductPanel className={styles.paywall}>
          <section className={styles.offerCopy}>
            <ProductStatus tone="action">Starter</ProductStatus>
            <h2>Turn one campaign brief into evidence-backed cuts.</h2>
            <p>
              ClipFactory anchors words to the transcript, checks what is
              visible in-frame and explains why each selected moment fits the
              campaign.
            </p>
            <div className={styles.offerThread} aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </section>
          <aside className={styles.offerCard}>
            <div className={styles.priceRow}>
              <div>
                <span>Starter</span>
                <strong>€29</strong>
              </div>
              <p>per month</p>
            </div>
            <ProductCheckList>
              <ProductCheck>300 credits each month</ProductCheck>
              <ProductCheck>Up to 30 minutes per public source</ProductCheck>
              <ProductCheck>
                Up to 3 campaign-shaped clips per source
              </ProductCheck>
              <ProductCheck>One active analysis at a time</ProductCheck>
              <ProductCheck>YouTube and Vimeo in V1</ProductCheck>
            </ProductCheckList>
            <div className={styles.checkoutArea}>
              <CheckoutButton />
              <p>
                <ShieldCheck aria-hidden="true" /> Secure checkout is handled by
                Stripe.
              </p>
            </div>
          </aside>
        </ProductPanel>
      ) : (
        <div className={styles.ledgerGrid}>
          <ProductPanel className={styles.ledgerMain}>
            <ProductSectionTitle
              eyebrow="Current plan"
              title="Starter"
              description={
                subscription.current_period_end
                  ? `${subscription.cancel_at_period_end ? "Access ends" : "Current period renews"} ${new Date(subscription.current_period_end).toLocaleDateString()}.`
                  : "Plan period details are still syncing."
              }
              action={
                <ProductStatus
                  tone={isActive ? "success" : isPastDue ? "danger" : "neutral"}
                >
                  {readableSubscriptionStatus(subscription.status)}
                </ProductStatus>
              }
            />
            <div className={styles.creditLedger}>
              <div className={styles.creditNumber}>
                <span>Credits available</span>
                <strong>{balance}</strong>
                <small>of 300 monthly credits</small>
              </div>
              <div
                className={styles.creditMeter}
                aria-label={`${balance} of 300 credits available`}
              >
                <span style={{ transform: `scaleX(${remainingPct / 100})` }} />
              </div>
            </div>
            <dl className={styles.planFacts}>
              <div>
                <dt>Source limit</dt>
                <dd>30 minutes</dd>
              </div>
              <div>
                <dt>Requested cuts</dt>
                <dd>Up to 3</dd>
              </div>
              <div>
                <dt>Concurrency</dt>
                <dd>1 active job</dd>
              </div>
            </dl>
          </ProductPanel>

          <ProductPanel className={styles.accountPanel}>
            <CreditCard aria-hidden="true" />
            <h2>Billing controls</h2>
            <p>
              The current backend supports secure Checkout for activation, but
              not a customer billing portal yet.
            </p>
            <p className={styles.accountNote}>
              We intentionally do not show a fake “Manage subscription” control.
            </p>
          </ProductPanel>
        </div>
      )}

      <div className={styles.returnRow}>
        <Button asChild variant="secondary">
          <Link href="/app">
            Return to workspace
            <ArrowUpRight aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </div>
  );
}

function readableSubscriptionStatus(status: string) {
  const labels: Record<string, string> = {
    active: "Active",
    trialing: "Trialing",
    past_due: "Payment issue",
    canceled: "Canceled",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}
