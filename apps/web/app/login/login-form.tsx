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
  const [googleStatus, setGoogleStatus] = React.useState<"idle" | "redirecting" | "error">(
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

  function callbackUrl(): string {
    const next = resolved.next ?? "/app";
    return `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;
  }

  async function handleGoogle() {
    setGoogleStatus("redirecting");
    setErrorMessage(null);
    try {
      const supabase = createSupabaseBrowserClient();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: callbackUrl(),
          queryParams: { access_type: "offline", prompt: "consent" },
        },
      });
      if (error) {
        setGoogleStatus("error");
        setErrorMessage(error.message);
      }
      // On success, Supabase redirects the page; no UI state to update here.
    } catch (err) {
      setGoogleStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Unexpected error");
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email) return;
    setStatus("sending");
    setErrorMessage(null);

    try {
      const supabase = createSupabaseBrowserClient();
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: callbackUrl() },
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
    <div className="space-y-4">
      <Button
        type="button"
        onClick={handleGoogle}
        disabled={googleStatus === "redirecting"}
        variant="secondary"
        className="w-full"
      >
        <GoogleIcon className="h-4 w-4" />
        {googleStatus === "redirecting" ? "Redirecting to Google…" : "Continue with Google"}
      </Button>

      <div className="relative flex items-center" role="separator" aria-label="or">
        <div className="h-px flex-1 bg-[var(--color-border)]" />
        <span className="px-3 text-xs uppercase tracking-wider text-[var(--color-muted-foreground)]">or</span>
        <div className="h-px flex-1 bg-[var(--color-border)]" />
      </div>

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
      </form>

      {(errorMessage || initialError) && (
        <p className="text-sm text-red-600">{errorMessage ?? initialError}</p>
      )}
    </div>
  );
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        d="M21.35 11.1H12v3.2h5.35c-.23 1.36-.91 2.51-1.95 3.28v2.72h3.15c1.84-1.7 2.9-4.2 2.9-7.2 0-.74-.07-1.46-.2-2z"
        fill="#4285F4"
      />
      <path
        d="M12 22c2.7 0 4.96-.9 6.6-2.42l-3.15-2.72c-.87.58-1.98.93-3.45.93-2.65 0-4.9-1.79-5.7-4.19H3.07v2.62A9.99 9.99 0 0 0 12 22z"
        fill="#34A853"
      />
      <path
        d="M6.3 13.6A6 6 0 0 1 5.95 12c0-.56.1-1.1.27-1.6V7.78H3.07A10 10 0 0 0 2 12c0 1.6.38 3.1 1.07 4.42L6.3 13.6z"
        fill="#FBBC05"
      />
      <path
        d="M12 6.4c1.47 0 2.78.5 3.82 1.5l2.85-2.84A9.97 9.97 0 0 0 12 2 9.99 9.99 0 0 0 3.07 7.78L6.3 10.4c.8-2.4 3.05-4 5.7-4z"
        fill="#EA4335"
      />
    </svg>
  );
}
