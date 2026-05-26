import { Fraunces, Inter } from "next/font/google";
import type { ReactNode } from "react";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["300", "400", "500", "600"],
});

export const metadata = {
  title: "V1 Editorial · ClipFactory preview",
  robots: { index: false, follow: false },
};

export default function EditorialLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className={`${fraunces.variable} ${inter.variable}`}
      style={{
        background: "#0A0A0A",
        color: "#F4F0E8",
        minHeight: "100dvh",
        fontFamily: "var(--font-inter), system-ui, sans-serif",
      }}
    >
      {children}
    </div>
  );
}
