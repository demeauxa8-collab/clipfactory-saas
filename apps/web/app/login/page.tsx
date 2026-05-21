import Link from "next/link";
import { Container } from "@/components/ui/container";
import { LoginForm } from "./login-form";

export const metadata = { title: "Sign in" };

export default function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  return (
    <Container className="flex flex-1 flex-col items-center justify-center py-16">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 inline-flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block h-5 w-5 rounded-sm bg-[var(--color-foreground)]" aria-hidden />
          ClipFactory
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Sign in to ClipFactory</h1>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          We will email you a one-time link. No password.
        </p>
        <div className="mt-8">
          <LoginForm searchParams={searchParams} />
        </div>
        <p className="mt-8 text-center text-xs text-[var(--color-muted-foreground)]">
          By signing in you agree to the{" "}
          <Link href="/legal/terms" className="underline">Terms</Link> and{" "}
          <Link href="/legal/privacy" className="underline">Privacy</Link>.
        </p>
      </div>
    </Container>
  );
}
