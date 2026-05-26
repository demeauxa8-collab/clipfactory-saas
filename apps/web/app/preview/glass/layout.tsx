import { Inter } from "next/font/google";
import type { ReactNode } from "react";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
});

export const metadata = {
  title: "V2 Liquid Glass · ClipFactory preview",
  robots: { index: false, follow: false },
};

export default function GlassLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className={inter.variable}
      style={{
        fontFamily:
          "var(--font-inter), -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif",
        minHeight: "100dvh",
      }}
    >
      {children}
    </div>
  );
}
