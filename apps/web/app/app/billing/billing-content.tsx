import { Container } from "@/components/ui/container";
import { CheckoutButton } from "./checkout-button";

export type Plan = {
  code: "starter" | "pro";
  name: string;
  price_eur_cents: number;
  credits_per_period: number;
  max_series_sources: number;
  stripe_price_id: string | null;
  is_active: boolean;
};

export type Subscription = {
  plan_code: string;
  status: string;
  current_period_end: string | null;
};

export function BillingContent({ status, sub, plans }: {
  status?: string;
  sub: Subscription | null;
  plans: Plan[];
}) {
  const currentPlan = plans.find((plan) => plan.code === sub?.plan_code);
  return (
    <Container className="py-10">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          Manage your ClipFactory subscription.
        </p>

        {status === "success" && (
          <div className="mt-4 rounded-md border border-[var(--color-border)] bg-[var(--color-muted)] p-3 text-sm text-[var(--color-foreground)]">
            Payment successful. Credits should appear within a minute.
          </div>
        )}
        {status === "cancel" && (
          <div className="mt-4 rounded-md border border-[var(--color-border)] bg-[var(--color-muted)] p-3 text-sm text-[var(--color-muted-foreground)]">
            Checkout canceled. You can resume any time.
          </div>
        )}

        <div className="pro-panel mt-8 rounded-lg p-6">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">Plan</p>
              <p className="mt-1 text-xl font-semibold">{sub ? `${currentPlan?.name ?? sub.plan_code} — ${sub.status}` : "No active plan"}</p>
            </div>
            <div className="text-right text-sm text-[var(--color-muted-foreground)]">
              {currentPlan && <p>{(currentPlan.price_eur_cents / 100).toFixed(0)}€ / month</p>}
              {currentPlan && <p>{currentPlan.credits_per_period.toLocaleString()} credits / month</p>}
            </div>
          </div>
          {sub?.current_period_end && (
            <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
              Renews on {new Date(sub.current_period_end).toLocaleDateString()}.
            </p>
          )}

          {sub && <div className="mt-6"><CheckoutButton portal label="Manage billing" /></div>}
        </div>

        {!sub && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold">Choose a plan</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {plans.map((plan) => {
                const ready = plan.is_active && (plan.code === "starter" || Boolean(plan.stripe_price_id));
                return (
                  <div key={plan.code} className="pro-card flex flex-col rounded-lg p-5">
                    <div className="flex items-baseline justify-between gap-3">
                      <h3 className="font-semibold">{plan.name}</h3>
                      <p className="text-lg font-semibold">{(plan.price_eur_cents / 100).toFixed(0)}€<span className="text-xs font-normal text-[var(--color-muted-foreground)]"> / month</span></p>
                    </div>
                    <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
                      {plan.credits_per_period.toLocaleString()} credits / month · {plan.max_series_sources > 1 ? `up to ${plan.max_series_sources} source videos per series` : "one video per job"}
                    </p>
                    <div className="mt-auto pt-6">
                      {ready
                        ? <CheckoutButton planCode={plan.code} label={`Start ${plan.name}`} />
                        : <a href="mailto:hello@clipfactory.app?subject=Pro%20plan%20waitlist" className="text-sm font-medium text-[var(--color-brand)] hover:underline">Ask about Pro availability →</a>}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
        {sub?.plan_code === "starter" && (
          <p className="mt-6 text-sm text-[var(--color-muted-foreground)]">
            Need multi-video series? <a href="mailto:hello@clipfactory.app?subject=Pro%20upgrade" className="text-[var(--color-brand)] hover:underline">Ask us about Pro</a>.
          </p>
        )}
      </div>
    </Container>
  );
}
