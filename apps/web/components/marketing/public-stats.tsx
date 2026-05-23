"use client";

import * as React from "react";
import { Container } from "@/components/ui/container";

type PublicStats = {
  clips_generated: number;
  hours_processed: number;
  creators_active: number;
};

const STATS_FALLBACK: PublicStats = {
  clips_generated: 0,
  hours_processed: 0,
  creators_active: 0,
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function PublicStats() {
  const [stats, setStats] = React.useState<PublicStats>(STATS_FALLBACK);
  const [loaded, setLoaded] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/public/stats`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: PublicStats | null) => {
        if (!cancelled && data) {
          setStats(data);
          setLoaded(true);
        }
      })
      .catch(() => {
        /* ignore — public stats are a nice-to-have on the landing */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const items = [
    { label: "Clips generated", value: stats.clips_generated },
    { label: "Hours analysed", value: stats.hours_processed },
    { label: "Active creators", value: stats.creators_active },
  ];

  return (
    <section className="border-b border-[var(--color-border)] bg-[var(--color-muted)]" aria-label="Public stats">
      <Container className="grid grid-cols-3 gap-6 py-10">
        {items.map((it) => (
          <div key={it.label}>
            <div className="text-3xl font-semibold tabular-nums md:text-4xl">
              {loaded ? it.value.toLocaleString("en-US") : "—"}
            </div>
            <div className="mt-1 text-xs text-[var(--color-muted-foreground)] md:text-sm">{it.label}</div>
          </div>
        ))}
      </Container>
    </section>
  );
}
