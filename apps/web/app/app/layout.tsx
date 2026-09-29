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
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: ledger } = await supabase.from("credit_ledger").select("delta");
  const balance = (ledger ?? []).reduce(
    (total, entry) =>
      total + (typeof entry.delta === "number" ? entry.delta : 0),
    0,
  );

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
