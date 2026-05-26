import Link from "next/link";
import { redirect } from "next/navigation";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const metadata = { title: "Admin" };

const NAV = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/finance", label: "Finance" },
] as const;

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    redirect("/login?next=/admin");
  }

  // Server-side gating: refuse if not is_admin.
  const { data: profile } = await supabase
    .from("profiles")
    .select("is_admin, email")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!profile || !profile.is_admin) {
    redirect("/app");
  }

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-[var(--color-background)]/78 backdrop-blur-xl">
        <Container className="flex h-14 items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="flex items-center gap-2 font-semibold tracking-tight">
              <span
                className="relative inline-flex h-5 w-5 items-center justify-center rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]"
                aria-hidden
              >
                <span className="h-2.5 w-1 rounded-sm bg-[var(--color-brand)]" />
              </span>
              ClipFactory
              <span className="ml-1 rounded-sm border border-[var(--color-border)] bg-[var(--color-muted)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-muted-foreground)]">
                ADMIN
              </span>
            </Link>
            <nav className="hidden gap-1 md:flex">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href as never}
                  className="inline-flex h-9 items-center rounded-md px-3 text-sm text-[var(--color-muted-foreground)] transition-all duration-300 hover:-translate-y-0.5 hover:bg-[var(--color-muted)] hover:text-[var(--color-foreground)]"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--color-muted-foreground)]">
            <span className="hidden md:inline">{profile.email}</span>
            <Link href="/app">
              <Button variant="secondary" size="sm">Exit admin</Button>
            </Link>
            <form action="/auth/signout" method="post">
              <Button type="submit" variant="ghost" size="sm">Sign out</Button>
            </form>
          </div>
        </Container>
      </header>
      <main className="flex-1">{children}</main>
    </>
  );
}
