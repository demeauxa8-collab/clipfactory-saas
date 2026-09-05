import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { safeProtectedPath } from "@/lib/auth/redirect";

type CookieToSet = { name: string; value: string; options: CookieOptions };

// Vercel kills the middleware at 25s. Supabase being slow or paused must never
// cost us the whole request — fail closed to /login well before that.
const AUTH_TIMEOUT_MS = 3000;

// "Auth session missing" is what a signed-out visitor gets — a normal answer
// from a healthy service, not an outage. Only a request that never came back
// counts as degraded.
function isUnreachable(error: { name?: string; status?: number }): boolean {
  return (
    error.name === "AuthRetryableFetchError" ||
    error.status === 0 ||
    (typeof error.status === "number" && error.status >= 500)
  );
}

async function getUserOrNull(
  supabase: ReturnType<typeof createServerClient>,
): Promise<{ user: unknown | null; degraded: boolean }> {
  let timer: ReturnType<typeof setTimeout> | undefined;

  try {
    const result = await Promise.race([
      supabase.auth.getUser(),
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error("auth timeout")),
          AUTH_TIMEOUT_MS,
        );
      }),
    ]);

    if (result.error) {
      const degraded = isUnreachable(result.error);
      if (degraded) {
        console.warn("[middleware] auth unreachable:", result.error.message);
      }
      return { user: null, degraded };
    }
    return { user: result.data.user, degraded: false };
  } catch (error) {
    console.warn(
      "[middleware] auth unreachable:",
      error instanceof Error ? error.message : error,
    );
    return { user: null, degraded: true };
  } finally {
    clearTimeout(timer);
  }
}

export async function updateSession(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const isProtected =
    path === "/app" ||
    path.startsWith("/app/") ||
    path === "/admin" ||
    path.startsWith("/admin/");
  const isAuthRoute = path === "/login" || path === "/auth/callback";
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // Local UI work and static previews must remain inspectable without copying
  // production credentials into the worktree. Protected routes still fail closed.
  if (!supabaseUrl || !supabaseAnonKey) {
    if (isProtected) {
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = "/login";
      redirectUrl.search = "";
      redirectUrl.searchParams.set(
        "next",
        safeProtectedPath(`${path}${request.nextUrl.search}`),
      );
      redirectUrl.searchParams.set("auth", "unavailable");
      return NextResponse.redirect(redirectUrl);
    }
    if (path === "/auth/callback") {
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = "/login";
      redirectUrl.search = "";
      redirectUrl.searchParams.set("auth", "unavailable");
      return NextResponse.redirect(redirectUrl);
    }
    return NextResponse.next({ request });
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet: CookieToSet[]) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value),
        );
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // IMPORTANT: do not put logic between createServerClient and getUser().
  // Supabase docs say so — it's how the session gets refreshed.
  const { user, degraded } = await getUserOrNull(supabase);

  if (!user && isProtected) {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = "/login";
    redirectUrl.search = "";
    redirectUrl.searchParams.set(
      "next",
      safeProtectedPath(`${path}${request.nextUrl.search}`),
    );
    // Tells /login the bounce came from an unreachable auth service, not from
    // a genuinely signed-out visitor.
    if (degraded) redirectUrl.searchParams.set("auth", "unavailable");
    return NextResponse.redirect(redirectUrl);
  }

  if (user && isAuthRoute && path === "/login") {
    return NextResponse.redirect(
      new URL(
        safeProtectedPath(request.nextUrl.searchParams.get("next")),
        request.url,
      ),
    );
  }

  return response;
}
