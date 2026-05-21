import Link from "next/link";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <>
      <header className="border-b border-[var(--color-border)]">
        <Container className="flex h-14 items-center justify-between">
          <Link href="/app" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="inline-block h-5 w-5 rounded-sm bg-[var(--color-foreground)]" aria-hidden />
            ClipFactory
          </Link>
          <nav className="flex items-center gap-1">
            <Link href="/app" className="h-9 px-3 inline-flex items-center text-sm hover:bg-[var(--color-muted)] rounded-md">Dashboard</Link>
            <Link href="/app/billing" className="h-9 px-3 inline-flex items-center text-sm hover:bg-[var(--color-muted)] rounded-md">Billing</Link>
            <form action="/auth/signout" method="post">
              <Button type="submit" variant="secondary" size="sm">Sign out</Button>
            </form>
          </nav>
        </Container>
      </header>
      <main className="flex-1">{children}</main>
    </>
  );
}
