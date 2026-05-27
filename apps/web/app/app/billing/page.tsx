import { Container } from "@/components/ui/container";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { CheckoutButton } from "./checkout-button";

export const metadata = { title: "Billing" };

export default async function BillingPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const supabase = await createSupabaseServerClient();
  const { data: sub } = await supabase
    .from("subscriptions")
    .select("plan_code, status, current_period_end, cancel_at_period_end")
    .in("status", ["trialing", "active", "past_due"])
    .order("current_period_end", { ascending: false })
    .limit(1)
    .maybeSingle();

  return (
    <Container className="py-10">
      <div className="max-w-2xl">
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
              <p className="mt-1 text-xl font-semibold">{sub ? `Starter — ${sub.status}` : "No active plan"}</p>
            </div>
            <div className="text-right text-sm text-[var(--color-muted-foreground)]">
              <p>29€ / month</p>
              <p>300 credits / month</p>
            </div>
          </div>
          {sub?.current_period_end && (
            <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
              Renews on {new Date(sub.current_period_end).toLocaleDateString()}.
            </p>
          )}

          <div className="mt-6">
            <CheckoutButton hasActive={Boolean(sub)} />
          </div>
        </div>
      </div>
    </Container>
  );
}
