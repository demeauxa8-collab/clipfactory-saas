"use client";

// Loads PostHog (autocapture + session replay) when a key is configured, and
// emits SPA pageviews + user identification through the shared analytics layer.
// With no PostHog key the component still drives first-party pageview tracking.

import * as React from "react";
import Script from "next/script";
import { usePathname } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";
import { identify, track } from "@/lib/analytics";

const PH_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
const PH_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.posthog.com";

const PH_SNIPPET = `!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys getNextSurveyStep onSessionId".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);posthog.init('${PH_KEY}',{api_host:'${PH_HOST}',capture_pageview:false,autocapture:true,session_recording:{maskAllInputs:true}});`;

export function Analytics() {
  const pathname = usePathname();

  // Identify the authenticated user (once) so events tie to a person in PostHog.
  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
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
  }, []);

  // SPA pageviews — App Router client navigation does not reload the page.
  React.useEffect(() => {
    if (!pathname) return;
    void track("pageview", { path: pathname });
  }, [pathname]);

  if (!PH_KEY) return null;

  return (
    <Script id="posthog-init" strategy="afterInteractive">
      {PH_SNIPPET}
    </Script>
  );
}
