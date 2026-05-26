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
      <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-[var(--color-background)]/78 backdrop-blur-xl">
        <Container className="flex h-14 items-center justify-between">
          <Link href="/app" className="flex items-center gap-2 font-semibold tracking-tight">
            <span
              className="relative inline-flex h-5 w-5 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]"
              aria-hidden
            >
              <span className="h-2.5 w-1 rounded-sm bg-[var(--color-brand)]" />
            </span>
            ClipFactory
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              href="/app"
              className="inline-flex h-9 items-center rounded-md px-3 text-sm text-[var(--color-muted-foreground)] transition-all duration-300 hover:-translate-y-0.5 hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)]"
            >
              Dashboard
            </Link>
            <Link
              href="/app/billing"
              className="inline-flex h-9 items-center rounded-md px-3 text-sm text-[var(--color-muted-foreground)] transition-all duration-300 hover:-translate-y-0.5 hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)]"
            >
              Billing
            </Link>
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
