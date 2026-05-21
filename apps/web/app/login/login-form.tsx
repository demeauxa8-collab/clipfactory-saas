"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function LoginForm({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const [email, setEmail] = React.useState("");
  const [status, setStatus] = React.useState<"idle" | "sending" | "sent" | "error">(
    "idle"
  );
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const params = useSearchParams();
  const initialError = params.get("error");

  // Awaited searchParams support (Next.js 15 returns a Promise in some contexts)
  const [resolved, setResolved] = React.useState<{ next?: string; error?: string }>({});
  React.useEffect(() => {
    let cancelled = false;
    searchParams.then((s) => {
      if (!cancelled) setResolved(s ?? {});
    });
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email) return;
    setStatus("sending");
    setErrorMessage(null);

    try {
      const supabase = createSupabaseBrowserClient();
      const next = resolved.next ?? "/app";
      const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;

      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: redirectTo,
        },
      });

      if (error) {
        setStatus("error");
        setErrorMessage(error.message);
        return;
      }

      setStatus("sent");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Unexpected error");
    }
  }

  if (status === "sent") {
    return (
      <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-muted)] p-4 text-sm">
        <p className="font-medium">Check your email.</p>
        <p className="mt-1 text-[var(--color-muted-foreground)]">
          We sent a sign-in link to <span className="font-mono">{email}</span>.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <label htmlFor="email" className="text-sm font-medium">Email</label>
        <Input
          id="email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={status === "sending"}
        />
      </div>
      <Button type="submit" className="w-full" disabled={status === "sending"}>
        {status === "sending" ? "Sending…" : "Send sign-in link"}
      </Button>
      {(errorMessage || initialError) && (
        <p className="text-sm text-red-600">{errorMessage ?? initialError}</p>
      )}
    </form>
  );
}
