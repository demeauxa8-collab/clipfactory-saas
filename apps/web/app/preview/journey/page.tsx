import type { Metadata } from "next";
import {
  JourneyPreview,
  type JourneyFixtureState,
  type JourneyScreen,
} from "./journey-preview";

export const metadata: Metadata = {
  title: "Customer journey preview - ClipFactory",
  description:
    "Interactive ClipFactory customer journey from sign-in to the first unlocked clip.",
  robots: { index: false, follow: false },
};

type JourneyPreviewPageProps = {
  searchParams: Promise<{
    screen?: string | string[];
    state?: string | string[];
    lab?: string | string[];
  }>;
};

const SCREENS = new Set<JourneyScreen>([
  "login",
  "paywall",
  "brief",
  "source",
  "processing",
  "result",
  "workspace",
]);

const FIXTURE_STATES = new Set<JourneyFixtureState>([
  "default",
  "loading",
  "empty",
  "error",
  "success",
]);

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function JourneyPreviewPage({
  searchParams,
}: JourneyPreviewPageProps) {
  const params = await searchParams;
  const requestedScreen = first(params.screen) as JourneyScreen | undefined;
  const requestedState = first(params.state) as JourneyFixtureState | undefined;
  const lab = first(params.lab) === "1";

  const safeRequestedScreen =
    requestedScreen && SCREENS.has(requestedScreen) ? requestedScreen : "login";
  const initialScreen =
    !lab && safeRequestedScreen === "paywall"
      ? "processing"
      : safeRequestedScreen;
  const initialState =
    requestedState && FIXTURE_STATES.has(requestedState)
      ? requestedState
      : "default";

  return (
    <JourneyPreview
      initialScreen={initialScreen}
      initialState={initialState}
      lab={lab}
    />
  );
}
