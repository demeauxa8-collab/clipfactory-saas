"use client";

import * as React from "react";
import Script from "next/script";
import { useSearchParams } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

type TurnstileWidgetId = string;

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: {
          sitekey: string;
          size: "invisible";
          callback: (token: string) => void;
          "error-callback": () => void;
          "expired-callback": () => void;
        }
      ) => TurnstileWidgetId;
      execute: (widgetId: TurnstileWidgetId) => void;
      reset: (widgetId: TurnstileWidgetId) => void;
    };
  }
}

export function LoginForm({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const [email, setEmail] = React.useState("");
  const [status, setStatus] = React.useState<
    "idle" | "verifying" | "sending" | "sent" | "error"
  >("idle");
  const [googleStatus, setGoogleStatus] = React.useState<
    "idle" | "verifying" | "redirecting" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [turnstileReady, setTurnstileReady] = React.useState(false);
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const widgetIdRef = React.useRef<TurnstileWidgetId | null>(null);
  const turnstilePromiseRef = React.useRef<{
    resolve: (token: string) => void;
    reject: (error: Error) => void;
  } | null>(null);
  const params = useSearchParams();
  const initialError = params.get("error");
  const turnstileEnabled = TURNSTILE_SITE_KEY !== "" && TURNSTILE_SITE_KEY !== "TODO";

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

  const renderTurnstile = React.useCallback(() => {
    if (!turnstileEnabled || !turnstileReady || !widgetRef.current || widgetIdRef.current) {
      return;
    }
    if (!window.turnstile) return;
    widgetIdRef.current = window.turnstile.render(widgetRef.current, {
      sitekey: TURNSTILE_SITE_KEY,
      size: "invisible",
      callback(token) {
        turnstilePromiseRef.current?.resolve(token);
        turnstilePromiseRef.current = null;
      },
      "error-callback"() {
        turnstilePromiseRef.current?.reject(new Error("Turnstile verification failed"));
        turnstilePromiseRef.current = null;
      },
      "expired-callback"() {
        if (widgetIdRef.current) {
          window.turnstile?.reset(widgetIdRef.current);
        }
      },
    });
  }, [turnstileEnabled, turnstileReady]);

  React.useEffect(() => {
    renderTurnstile();
  }, [renderTurnstile]);

  async function executeTurnstile(): Promise<string | null> {
    if (!turnstileEnabled) return null;
    renderTurnstile();
    const widgetId = widgetIdRef.current;
    if (!widgetId || !window.turnstile) {
      throw new Error("Turnstile is not ready yet");
    }

    return await new Promise<string>((resolve, reject) => {
      turnstilePromiseRef.current = { resolve, reject };
      const timeout = window.setTimeout(() => {
        if (turnstilePromiseRef.current) {
          turnstilePromiseRef.current.reject(new Error("Turnstile timed out"));
          turnstilePromiseRef.current = null;
        }
      }, 10_000);

      const originalResolve = resolve;
      turnstilePromiseRef.current.resolve = (token: string) => {
        window.clearTimeout(timeout);
        originalResolve(token);
      };
      const originalReject = reject;
      turnstilePromiseRef.current.reject = (error: Error) => {
        window.clearTimeout(timeout);
        originalReject(error);
      };
      window.turnstile?.execute(widgetId);
    });
  }

  async function verifyTurnstile() {
    const token = await executeTurnstile();
    if (!token) return;
    const response = await fetch(`${API_URL}/auth/turnstile/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (widgetIdRef.current) {
      window.turnstile?.reset(widgetIdRef.current);
    }
    if (!response.ok) {
      throw new Error("Bot protection failed. Please try again.");
    }
  }

  async function handleGoogle() {
    setGoogleStatus("verifying");
    setErrorMessage(null);
    try {
      await verifyTurnstile();
      setGoogleStatus("redirecting");
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
    setStatus("verifying");
    setErrorMessage(null);

    try {
      await verifyTurnstile();
      setStatus("sending");
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
      {turnstileEnabled && (
        <>
          <Script
            src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
            async
            defer
            onLoad={() => setTurnstileReady(true)}
          />
          <div ref={widgetRef} />
        </>
      )}

      <Button
        type="button"
        onClick={handleGoogle}
        disabled={googleStatus === "verifying" || googleStatus === "redirecting"}
        variant="secondary"
        className="w-full"
      >
        <GoogleIcon className="h-4 w-4" />
        {googleStatus === "verifying"
          ? "Checking browser…"
          : googleStatus === "redirecting"
            ? "Redirecting to Google…"
            : "Continue with Google"}
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
        <Button
          type="submit"
          className="w-full"
          disabled={status === "verifying" || status === "sending"}
        >
          {status === "verifying"
            ? "Checking browser…"
            : status === "sending"
              ? "Sending…"
              : "Send sign-in link"}
        </Button>
      </form>

      {(errorMessage || initialError) && (
        <p className="text-sm text-[var(--color-danger)]">{errorMessage ?? initialError}</p>
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
