"use client";

// Loads PostHog (autocapture + session replay) when a key is configured, and
// emits SPA pageviews + user identification through the shared analytics layer.
// With no PostHog key the component still drives first-party pageview tracking.

import * as React from "react";
import Script from "next/script";
import { usePathname } from "next/navigation";

const PH_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
const PH_HOST =
  process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.posthog.com";

const PH_SNIPPET = `!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys getNextSurveyStep onSessionId".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);posthog.init('${PH_KEY}',{api_host:'${PH_HOST}',capture_pageview:false,autocapture:true,session_recording:{maskAllInputs:true}});`;

export function Analytics() {
  const pathname = usePathname();
  const isAuthenticatedSurface =
    pathname?.startsWith("/app") || pathname?.startsWith("/admin");

  // Public pages must not pay the Supabase bundle cost just to discover that
  // there is no session. Auth-only analytics are loaded after hydration and
  // only inside authenticated product surfaces.
  React.useEffect(() => {
    if (!isAuthenticatedSurface) return;

    let active = true;
    (async () => {
      try {
        const [{ createSupabaseBrowserClient }, { identify }] =
          await Promise.all([
            import("@/lib/supabase/browser"),
            import("@/lib/analytics"),
          ]);
        const supabase = createSupabaseBrowserClient();
        const { data } = await supabase.auth.getUser();
        if (active && data.user) identify(data.user.id);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      active = false;
    };
  }, [isAuthenticatedSurface]);

  // SPA pageviews: App Router client navigation does not reload the page.
  React.useEffect(() => {
    if (!pathname) return;
    if (!PH_KEY && !isAuthenticatedSurface) return;

    void import("@/lib/analytics").then(({ track }) =>
      track("pageview", { path: pathname }),
    );
  }, [isAuthenticatedSurface, pathname]);

  if (!PH_KEY) return null;

  return (
    <Script id="posthog-init" strategy="afterInteractive">
      {PH_SNIPPET}
    </Script>
  );
}
