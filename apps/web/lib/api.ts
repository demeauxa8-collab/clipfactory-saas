"use client";

import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: unknown;

  constructor(message: string, status: number, code?: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authHeader(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new ApiError("not_authenticated", 401, "not_authenticated");
  }
  return { Authorization: `Bearer ${token}` };
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await authHeader()),
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  const body = init?.json !== undefined ? JSON.stringify(init.json) : init?.body;

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    body,
  });

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const code =
      typeof detail === "object" && detail !== null && "detail" in (detail as Record<string, unknown>)
        ? extractCode((detail as { detail: unknown }).detail)
        : undefined;
    throw new ApiError(`HTTP ${res.status}`, res.status, code, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function extractCode(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null && "code" in (detail as Record<string, unknown>)) {
    return String((detail as { code: unknown }).code);
  }
  return undefined;
}
