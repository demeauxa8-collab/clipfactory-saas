import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ClipFactory — Campaign-first AI clipping",
    template: "%s · ClipFactory",
  },
  description:
    "Turn long videos into publish-ready shorts scored by hook, emotion, visual context and campaign fit.",
  metadataBase: new URL("https://clipfactory.app"),
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-dvh flex flex-col">{children}</body>
    </html>
  );
}
