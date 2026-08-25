import { PrototypeLab } from "@/components/prototypes/redesign/prototype-lab";

export const metadata = {
  title: "UI direction lab - ClipFactory",
  robots: { index: false, follow: false },
};

type RedesignPreviewPageProps = {
  searchParams: Promise<{
    v?: string | string[];
    clean?: string | string[];
  }>;
};

export default async function RedesignPreviewPage({
  searchParams,
}: RedesignPreviewPageProps) {
  const params = await searchParams;
  const rawVariant = Array.isArray(params.v) ? params.v[0] : params.v;
  const rawClean = Array.isArray(params.clean) ? params.clean[0] : params.clean;
  const parsedVariant = Number.parseInt(rawVariant ?? "1", 10);
  const initialVariant =
    Number.isFinite(parsedVariant) && parsedVariant >= 1 && parsedVariant <= 6
      ? parsedVariant - 1
      : 0;
  const clean = rawClean === "1" || rawClean === "true";

  return <PrototypeLab clean={clean} initialVariant={initialVariant} />;
}
