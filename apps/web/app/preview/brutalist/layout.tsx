import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "700"],
});

export const metadata = {
  title: "V3 Brutalist · ClipFactory preview",
  robots: { index: false, follow: false },
};

export default function BrutalistLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className={`${display.variable} ${mono.variable}`}
      style={{
        background: "#FAFAF7",
        color: "#000000",
        minHeight: "100dvh",
        fontFamily: "var(--font-display), system-ui, sans-serif",
      }}
    >
      {children}
    </div>
  );
}
