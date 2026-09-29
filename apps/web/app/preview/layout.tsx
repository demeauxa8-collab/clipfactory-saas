import { NO_INDEX } from "@/lib/seo";

export const metadata = { robots: NO_INDEX };

export default function PreviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
