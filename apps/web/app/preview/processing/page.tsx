import { ProcessingLab } from "@/components/prototypes/processing/processing-lab";
import type { ProcessingPreviewState } from "@/components/prototypes/processing/processing-sequence";

export const metadata = {
  title: "Processing motion lab - ClipFactory",
  robots: { index: false, follow: false },
};

type ProcessingPreviewPageProps = {
  searchParams: Promise<{
    v?: string | string[];
    clean?: string | string[];
    state?: string | string[];
  }>;
};

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ProcessingPreviewPage({
  searchParams,
}: ProcessingPreviewPageProps) {
  const params = await searchParams;
  const parsedVariant = Number.parseInt(first(params.v) ?? "3", 10);
  const initialVariant =
    Number.isFinite(parsedVariant) && parsedVariant >= 1 && parsedVariant <= 3
      ? parsedVariant - 1
      : 2;
  const cleanValue = first(params.clean);
  const clean = cleanValue === "1" || cleanValue === "true";
  const requestedState = first(params.state) ?? "auto";
  const allowedStates: ProcessingPreviewState[] = [
    "auto",
    "loading",
    "processing",
    "empty",
    "error",
    "success",
    "long",
  ];
  const previewState = allowedStates.includes(
    requestedState as ProcessingPreviewState,
  )
    ? (requestedState as ProcessingPreviewState)
    : "auto";

  return (
    <ProcessingLab
      clean={clean}
      initialVariant={initialVariant}
      previewState={previewState}
    />
  );
}
