import { ImageResponse } from "next/og";
import { SITE } from "@/lib/site";

export const runtime = "edge";
export const alt = `${SITE.name} — AI clip maker for Shorts, Reels and TikToks`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#0a0a0a",
          color: "#fafafa",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "80px",
          fontFamily: "Inter, system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 4,
              background: "#fafafa",
            }}
          />
          <span style={{ fontSize: 32, fontWeight: 600 }}>{SITE.name}</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div
            style={{
              fontSize: 28,
              color: "#a1a1aa",
              letterSpacing: 1,
              textTransform: "uppercase",
            }}
          >
            AI clip maker for long videos
          </div>
          <div
            style={{
              fontSize: 72,
              fontWeight: 600,
              lineHeight: 1.05,
              maxWidth: 1000,
            }}
          >
            Turn long videos into
            <br />
            Shorts, Reels and TikToks.
          </div>
        </div>

        <div
          style={{
            fontSize: 22,
            color: "#a1a1aa",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>From {SITE.pricingFromEur}€ / month — EU hosted</span>
          <span style={{ color: "#fafafa" }}>{SITE.url.replace(/^https?:\/\//, "")}</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
