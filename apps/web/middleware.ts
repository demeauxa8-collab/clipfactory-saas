import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  // Only routes that actually need a session. Marketing pages must stay up even
  // when Supabase is down — running auth on them once took the whole site to 504.
  matcher: [
    "/app",
    "/app/:path*",
    "/admin",
    "/admin/:path*",
    "/login",
    "/auth/:path*",
  ],
};
