"use client";

import * as React from "react";
import Script from "next/script";
import { Check, ShieldAlert } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { track } from "@/lib/analytics";
import { safeProtectedPath } from "@/lib/auth/redirect";
import styles from "./login.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

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
        },
      ) => TurnstileWidgetId;
      execute: (widgetId: TurnstileWidgetId) => void;
      reset: (widgetId: TurnstileWidgetId) => void;
    };
  }
}

export function LoginForm({
  searchParams,
}: {
  searchParams: { next?: string; error?: string; auth?: string };
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
  const emailInputRef = React.useRef<HTMLInputElement | null>(null);
  const focusEmailOnIdleRef = React.useRef(false);
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const widgetIdRef = React.useRef<TurnstileWidgetId | null>(null);
  const turnstilePromiseRef = React.useRef<{
    resolve: (token: string) => void;
    reject: (error: Error) => void;
  } | null>(null);
  const initialError = searchParams.error;
  // Set by the middleware when it bounced us here because Supabase was
  // unreachable — the visitor may well still have a valid session.
  const authConfigured = SUPABASE_URL !== "" && SUPABASE_ANON_KEY !== "";
  const authUnavailable =
    searchParams.auth === "unavailable" || !authConfigured;
  const turnstileEnabled =
    TURNSTILE_SITE_KEY !== "" && TURNSTILE_SITE_KEY !== "TODO";
  const shouldReduceMotion = useReducedMotion();
  const nextPath = safeProtectedPath(searchParams.next);

  function callbackUrl(): string {
    return `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`;
  }

  const renderTurnstile = React.useCallback(() => {
    if (
      !turnstileEnabled ||
      !turnstileReady ||
      !widgetRef.current ||
      widgetIdRef.current
    ) {
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
        turnstilePromiseRef.current?.reject(
          new Error("Turnstile verification failed"),
        );
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
    void track("login_attempt", { method: "google" });
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
    void track("login_attempt", { method: "magic_link" });

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

  function handleUseAnotherEmail() {
    focusEmailOnIdleRef.current = true;
    setEmail("");
    setErrorMessage(null);
    setStatus("idle");
  }

  const initialErrorMessage = initialError
    ? initialError === "auth_callback_failed"
      ? "We couldn’t finish signing you in. Nothing was changed. Please try again."
      : "We couldn’t sign you in. Please try again."
    : null;
  const visibleError = errorMessage ?? initialErrorMessage;
  const swapInitial = shouldReduceMotion
    ? { opacity: 0 }
    : { opacity: 0, filter: "blur(2px)" };
  const swapExit = shouldReduceMotion
    ? { opacity: 0 }
    : { opacity: 0, filter: "blur(2px)" };
  const swapTransition = {
    duration: shouldReduceMotion ? 0.16 : 0.2,
    ease: [0.23, 1, 0.32, 1] as const,
  };

  return (
    <div className={styles.formRoot}>
      {turnstileEnabled && (
        <>
          <Script
            src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
            async
            defer
            onLoad={() => setTurnstileReady(true)}
          />
          <div ref={widgetRef} className={styles.turnstileMount} />
        </>
      )}

      <AnimatePresence initial={false} mode="wait">
        {status === "sent" ? (
          <motion.section
            key="sent"
            className={styles.sentState}
            initial={swapInitial}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            exit={swapExit}
            transition={swapTransition}
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            <span className={styles.sentIcon} aria-hidden="true">
              <Check />
            </span>
            <p className={styles.sentEyebrow}>Sign-in link sent</p>
            <h2>Check your inbox</h2>
            <p className={styles.sentCopy}>
              We sent a one-time sign-in link to{" "}
              <strong className={styles.sentEmail}>{email}</strong>.
            </p>
            <p className={styles.sentNote}>
              You can close this tab after opening the link.
            </p>
            <Button
              type="button"
              variant="secondary"
              size="lg"
              className={styles.secondaryButton}
              onClick={handleUseAnotherEmail}
            >
              Use another email
            </Button>
          </motion.section>
        ) : (
          <motion.div
            key="form"
            className={styles.formState}
            initial={swapInitial}
            animate={{ opacity: 1, filter: "blur(0px)" }}
            exit={swapExit}
            transition={swapTransition}
            onAnimationComplete={() => {
              if (focusEmailOnIdleRef.current) {
                focusEmailOnIdleRef.current = false;
                emailInputRef.current?.focus();
              }
            }}
          >
            {authUnavailable && (
              <div
                className={styles.serviceNotice}
                role="status"
                aria-live="polite"
              >
                <ShieldAlert aria-hidden="true" />
                <p>
                  <strong>
                    {authConfigured
                      ? "Sign-in is temporarily unavailable."
                      : "Sign-in is not configured in this local build."}
                  </strong>
                  <span>
                    {authConfigured
                      ? "We couldn’t confirm your session just now. Your work hasn’t been changed; wait a moment and try again."
                      : "No production credentials were copied into this worktree. Use the local journey preview to inspect the full flow."}
                  </span>
                </p>
              </div>
            )}

            <Button
              type="button"
              onClick={handleGoogle}
              disabled={
                !authConfigured ||
                googleStatus === "verifying" ||
                googleStatus === "redirecting"
              }
              aria-busy={
                googleStatus === "verifying" || googleStatus === "redirecting"
              }
              variant="secondary"
              size="lg"
              className={styles.googleButton}
            >
              <GoogleIcon className={styles.googleIcon} />
              {googleStatus === "verifying"
                ? "Checking browser…"
                : googleStatus === "redirecting"
                  ? "Redirecting to Google…"
                  : "Continue with Google"}
            </Button>

            <div
              className={styles.divider}
              role="separator"
              aria-label="or use a one-time link"
            >
              <span />
              <p>or use a one-time link</p>
              <span />
            </div>

            <form
              onSubmit={handleSubmit}
              className={styles.emailForm}
              aria-busy={status === "verifying" || status === "sending"}
            >
              <div className={styles.field}>
                <label htmlFor="email">Work email</label>
                <Input
                  ref={emailInputRef}
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  inputMode="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={!authConfigured || status === "sending"}
                  className={styles.emailInput}
                  aria-describedby={visibleError ? "login-error" : undefined}
                />
              </div>
              <Button
                type="submit"
                size="lg"
                className={styles.emailButton}
                disabled={
                  !authConfigured ||
                  status === "verifying" ||
                  status === "sending"
                }
              >
                {status === "verifying"
                  ? "Checking browser…"
                  : status === "sending"
                    ? "Sending sign-in link…"
                    : "Email me a sign-in link"}
              </Button>
            </form>

            {visibleError && (
              <p id="login-error" className={styles.errorMessage} role="alert">
                {visibleError}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
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
