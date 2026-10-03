import Link from "next/link";
import { redirect } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppNav } from "@/components/product/app-nav";
import { ProductBrand } from "@/components/product/product-primitives";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createSupabaseServerClient();
  // Auth and balance in parallel: the balance is read under the caller's RLS,
  // so it is only rendered once the user is confirmed below.
  const [
    {
      data: { user },
    },
    { data: balanceRow },
  ] = await Promise.all([
    supabase.auth.getUser(),
    supabase.from("credit_balances").select("balance").maybeSingle(),
  ]);
  if (!user) redirect("/login");

  const balance =
    typeof balanceRow?.balance === "number" ? balanceRow.balance : 0;

  return (
    <div className="cf-app">
      <header className="cf-app-chrome">
        <div className="cf-app-chrome__inner">
          <ProductBrand href="/app" />
          <AppNav />
          <div className="cf-app-chrome__actions">
            <Link
              className="cf-credit-chip"
              href="/app/billing"
              aria-label={`${balance} credits available`}
            >
              {balance} credits
            </Link>
            <form action="/auth/signout" method="post">
              <Button
                type="submit"
                variant="ghost"
                size="sm"
                aria-label="Sign out"
              >
                <LogOut aria-hidden="true" />
                <span className="cf-signout-label">Sign out</span>
              </Button>
            </form>
          </div>
        </div>
      </header>
      <main id="main-content">{children}</main>
      <AppNav mobile />
    </div>
  );
}
