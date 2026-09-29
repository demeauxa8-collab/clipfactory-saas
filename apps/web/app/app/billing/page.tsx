import { createSupabaseServerClient } from "@/lib/supabase/server";
import { BillingContent, type Plan, type Subscription } from "./billing-content";

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
    .select("plan_code, status, current_period_end")
    .in("status", ["trialing", "active", "past_due"])
    .order("current_period_end", { ascending: false })
    .limit(1)
    .maybeSingle();
  const { data: planRows } = await supabase.from("plan_definitions")
    .select("code, name, price_eur_cents, credits_per_period, max_series_sources, stripe_price_id, is_active")
    .in("code", ["starter", "pro"]).order("price_eur_cents", { ascending: true });
  return <BillingContent status={status} sub={(sub ?? null) as Subscription | null} plans={(planRows ?? []) as Plan[]} />;
}
