"use client";

// Client-side analytics. Two sinks, both best-effort and non-throwing:
//   1. PostHog (autocapture + explicit events) when NEXT_PUBLIC_POSTHOG_KEY is set.
//   2. First-party API sink (/events) for authenticated users.
// Analytics must never break the UI, so every path swallows its own errors.

import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ANON_KEY = "cf_anon_id";

type Props = Record<string, unknown>;

interface PostHogLike {
  capture: (event: string, props?: Props) => void;
  identify: (id: string, props?: Props) => void;
}

function posthog(): PostHogLike | undefined {
  if (typeof window === "undefined") return undefined;
  return (window as unknown as { posthog?: PostHogLike }).posthog;
}

export function getAnonId(): string {
  if (typeof window === "undefined") return "";
  try {
    let id = window.localStorage.getItem(ANON_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `anon_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      window.localStorage.setItem(ANON_KEY, id);
    }
    return id;
  } catch {
    return "";
  }
}

async function sessionToken(): Promise<string | null> {
  try {
    const supabase = createSupabaseBrowserClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
}

export async function track(event: string, properties: Props = {}): Promise<void> {
  // 1) PostHog (if the snippet has loaded).
  try {
    posthog()?.capture(event, properties);
  } catch {
    /* ignore */
  }

  // 2) First-party sink — only when authenticated (the endpoint requires a JWT).
  try {
    const token = await sessionToken();
    if (!token) return;
    await fetch(`${API_URL}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      keepalive: true,
      body: JSON.stringify({
        event,
        properties,
        path: typeof window !== "undefined" ? window.location.pathname : null,
        referrer: typeof document !== "undefined" ? document.referrer || null : null,
        anon_id: getAnonId(),
        session_id: getAnonId(),
      }),
    });
  } catch {
    /* analytics must never throw */
  }
}

export function identify(userId: string, props: Props = {}): void {
  try {
    posthog()?.identify(userId, props);
  } catch {
    /* ignore */
  }
}
