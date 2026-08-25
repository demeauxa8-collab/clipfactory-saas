"use client";

import Image from "next/image";
import * as React from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clapperboard,
  Clock3,
  CreditCard,
  Download,
  Film,
  Gauge,
  Link2,
  LoaderCircle,
  LockKeyhole,
  Mail,
  Play,
  RefreshCcw,
  ScanText,
  Sparkles,
  Target,
  TriangleAlert,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SignalTimeline } from "@/components/prototypes/processing/signal-timeline";
import styles from "./journey-preview.module.css";

export type JourneyScreen =
  | "login"
  | "paywall"
  | "brief"
  | "source"
  | "processing"
  | "result"
  | "workspace";

export type JourneyFixtureState =
  "default" | "loading" | "empty" | "error" | "success";

type JourneyPreviewProps = {
  initialScreen: JourneyScreen;
  initialState: JourneyFixtureState;
  lab?: boolean;
};

type ScreenProps = {
  fixtureState: JourneyFixtureState;
  navigate: (screen: JourneyScreen, state?: JourneyFixtureState) => void;
  setFixtureState: (state: JourneyFixtureState) => void;
};

const SCREEN_STEPS: Array<{
  id: JourneyScreen;
  label: string;
  detail: string;
}> = [
  { id: "login", label: "Sign in", detail: "Open a workspace" },
  { id: "brief", label: "Campaign", detail: "Set editorial intent" },
  { id: "source", label: "Source", detail: "Paste a video URL" },
  { id: "processing", label: "Build", detail: "Watch the first cut form" },
  { id: "result", label: "Review", detail: "Inspect candidates" },
  { id: "workspace", label: "Workspace", detail: "Keep the work moving" },
];

const FIXTURE_STATES: Array<{
  id: JourneyFixtureState;
  label: string;
}> = [
  { id: "default", label: "Default" },
  { id: "loading", label: "Loading" },
  { id: "empty", label: "Empty" },
  { id: "error", label: "Error" },
  { id: "success", label: "Success" },
];

const CLIPS = [
  {
    id: "proof",
    shortLabel: "01 · Proof",
    title: "The proof arrives before the promise.",
    moment: "09:32–09:45",
    duration: "13 sec",
    score: 89,
    image: "/prototypes/founder-frame-4-v2.webp",
    rationale:
      "The product is visible while the founder names the result. Picture and claim reinforce each other.",
    transcript:
      "We stopped leading with the promise. The screen already showed the proof.",
    metrics: [
      ["Hook", 88],
      ["Campaign fit", 91],
      ["Visual proof", 96],
    ] as const,
  },
  {
    id: "tension",
    shortLabel: "02 · Tension",
    title: "The sentence that changes the frame.",
    moment: "02:14–02:29",
    duration: "15 sec",
    score: 92,
    image: "/prototypes/founder-frame-2-v2.webp",
    rationale:
      "A concise contradiction creates tension before the explanation. It fits the campaign's direct tone.",
    transcript:
      "Everyone thought the feature was the problem. The audience was the problem.",
    metrics: [
      ["Hook", 94],
      ["Campaign fit", 90],
      ["Visual proof", 84],
    ] as const,
  },
  {
    id: "payoff",
    shortLabel: "03 · Payoff",
    title: "One decision closes the story arc.",
    moment: "16:05–16:23",
    duration: "18 sec",
    score: 86,
    image: "/prototypes/founder-frame-6-v2.webp",
    rationale:
      "The answer lands cleanly and can close a short sequence without needing off-screen context.",
    transcript:
      "That is when we cut the feature list and let one customer result carry the story.",
    metrics: [
      ["Hook", 80],
      ["Campaign fit", 88],
      ["Visual proof", 90],
    ] as const,
  },
] as const;

const PROCESS_STEPS = [
  ["Validate source", "YouTube or Vimeo URL"],
  ["Read the source", "Download and inspect media"],
  ["Anchor the words", "Transcript with source timing"],
  ["Match the brief", "Audience, goal and tone"],
  ["Inspect candidates", "Visual and editorial checks"],
  ["Prepare delivery", "Render the selected moments"],
] as const;

const WAVEFORM = [
  28, 52, 36, 70, 44, 62, 88, 46, 58, 78, 34, 66, 92, 52, 74, 40, 82, 56, 68,
  38, 60, 84, 48, 72, 42, 64, 90, 50, 76, 36, 58, 80,
];

const SCREEN_SET = new Set<JourneyScreen>(SCREEN_STEPS.map((step) => step.id));
const STATE_SET = new Set<JourneyFixtureState>(
  FIXTURE_STATES.map((state) => state.id),
);

const SCREEN_TRANSITION = {
  type: "spring" as const,
  duration: 0.38,
  bounce: 0,
};

const INDICATOR_TRANSITION = {
  type: "spring" as const,
  duration: 0.4,
  bounce: 0,
};

export function JourneyPreview({
  initialScreen,
  initialState,
  lab = false,
}: JourneyPreviewProps) {
  const [screen, setScreen] = React.useState(initialScreen);
  const [fixtureState, setFixtureStateValue] = React.useState(initialState);
  const [direction, setDirection] = React.useState(1);
  const reduceMotion = Boolean(useReducedMotion());

  const currentIndex = Math.max(
    0,
    SCREEN_STEPS.findIndex((step) => step.id === screen),
  );

  const writeUrl = React.useCallback(
    (
      nextScreen: JourneyScreen,
      nextState: JourneyFixtureState,
      method: "pushState" | "replaceState",
    ) => {
      const url = new URL(window.location.href);
      url.searchParams.set("screen", nextScreen);
      if (nextState === "default") {
        url.searchParams.delete("state");
      } else {
        url.searchParams.set("state", nextState);
      }
      window.history[method]({}, "", url);
    },
    [],
  );

  const navigate = React.useCallback(
    (nextScreen: JourneyScreen, nextState: JourneyFixtureState = "default") => {
      const nextIndex = SCREEN_STEPS.findIndex(
        (step) => step.id === nextScreen,
      );
      setDirection(nextIndex >= currentIndex ? 1 : -1);
      setScreen(nextScreen);
      setFixtureStateValue(nextState);
      writeUrl(nextScreen, nextState, "pushState");
    },
    [currentIndex, writeUrl],
  );

  const setFixtureState = React.useCallback(
    (nextState: JourneyFixtureState) => {
      setFixtureStateValue(nextState);
      writeUrl(screen, nextState, "replaceState");
    },
    [screen, writeUrl],
  );

  React.useEffect(() => {
    const onPopState = () => {
      const params = new URL(window.location.href).searchParams;
      const nextScreen = params.get("screen") as JourneyScreen | null;
      const nextState = params.get("state") as JourneyFixtureState | null;
      const safeScreen =
        nextScreen && SCREEN_SET.has(nextScreen) ? nextScreen : "login";
      const safeState =
        nextState && STATE_SET.has(nextState) ? nextState : "default";
      const nextIndex = SCREEN_STEPS.findIndex(
        (step) => step.id === safeScreen,
      );
      setDirection(nextIndex >= currentIndex ? 1 : -1);
      setScreen(safeScreen);
      setFixtureStateValue(safeState);
    };

    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [currentIndex]);

  const previousScreen = SCREEN_STEPS[currentIndex - 1]?.id;
  const nextScreen = SCREEN_STEPS[currentIndex + 1]?.id;

  if (!lab && screen === "processing") {
    return (
      <div className={styles.immersiveJourney}>
        <div className={styles.immersiveControls}>
          <button type="button" onClick={() => navigate("source")}>
            <ArrowLeft aria-hidden="true" />
            Back to source
          </button>
          <p>
            <span aria-hidden="true" />
            First campaign trial · local preview
          </p>
        </div>
        <SignalTimeline
          demoMode
          previewState={fixtureState === "success" ? "success" : "auto"}
          onUnlock={() => navigate("result", "success")}
        />
      </div>
    );
  }

  return (
    <div className={styles.journey} data-lab={lab || undefined}>
      <div className={styles.shell}>
        <header className={styles.topbar}>
          <div className={styles.brandCluster}>
            <span className={styles.productMark} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <div>
              <p className={styles.brandName}>ClipFactory</p>
              <p className={styles.previewLabel}>
                {lab
                  ? "Product journey · state lab"
                  : "Guided customer journey"}
              </p>
            </div>
          </div>

          <div className={styles.topbarActions}>
            {lab ? (
              <>
                <span className={styles.localBadge}>
                  <LockKeyhole aria-hidden="true" />
                  State lab · no API
                </span>
                <label className={styles.statePicker}>
                  <span>Fixture state</span>
                  <select
                    value={fixtureState}
                    onChange={(event) =>
                      setFixtureState(event.target.value as JourneyFixtureState)
                    }
                    aria-label="Fixture state"
                  >
                    {FIXTURE_STATES.map((state) => (
                      <option key={state.id} value={state.id}>
                        {state.label}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : (
              <span className={styles.localBadge}>
                <LockKeyhole aria-hidden="true" />
                Local preview · no charge
              </span>
            )}
            <button
              type="button"
              className={styles.resetButton}
              onClick={() => navigate("login")}
              aria-label="Reset journey preview"
            >
              <RefreshCcw aria-hidden="true" />
              <span>Reset</span>
            </button>
          </div>
        </header>

        <div className={styles.appBody}>
          {lab ? (
            <aside className={styles.rail} aria-label="Product journey screens">
              <div className={styles.railIntro}>
                <p>Source thread</p>
                <span>
                  One continuous decision trail from input to delivery.
                </span>
              </div>
              <ol className={styles.stepList}>
                {SCREEN_STEPS.map((step, index) => {
                  const active = step.id === screen;
                  const complete = index < currentIndex;
                  return (
                    <li
                      key={step.id}
                      className={styles.stepItem}
                      data-complete={complete || undefined}
                      data-active={active || undefined}
                    >
                      <button
                        type="button"
                        className={styles.stepButton}
                        onClick={() => navigate(step.id)}
                        aria-current={active ? "step" : undefined}
                      >
                        {active ? (
                          <motion.span
                            className={styles.activeStepSurface}
                            layoutId="journey-active-step"
                            transition={INDICATOR_TRANSITION}
                          />
                        ) : null}
                        <span className={styles.stepDot} aria-hidden="true">
                          {complete ? (
                            <Check />
                          ) : (
                            String(index + 1).padStart(2, "0")
                          )}
                        </span>
                        <span className={styles.stepCopy}>
                          <strong>{step.label}</strong>
                          <span>{step.detail}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
              <p className={styles.railFootnote}>
                Illustrative data. No account, payment, upload, job, or export
                is created from this route.
              </p>
            </aside>
          ) : null}

          <main
            id="main-content"
            className={styles.viewport}
            data-guided={!lab || undefined}
          >
            <div className={styles.viewportGlow} aria-hidden="true" />
            {!lab ? (
              <nav
                className={styles.customerProgress}
                aria-label="Customer journey progress"
              >
                <ol>
                  {SCREEN_STEPS.map((step, index) => {
                    const active = step.id === screen;
                    const complete = index < currentIndex;
                    return (
                      <li
                        key={step.id}
                        data-active={active || undefined}
                        data-complete={complete || undefined}
                      >
                        <button
                          type="button"
                          disabled={index > currentIndex}
                          onClick={() =>
                            index <= currentIndex && navigate(step.id)
                          }
                          aria-current={active ? "step" : undefined}
                        >
                          <span>
                            {complete ? (
                              <Check aria-hidden="true" />
                            ) : (
                              String(index + 1).padStart(2, "0")
                            )}
                          </span>
                          <strong>{step.label}</strong>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              </nav>
            ) : null}
            <div className={styles.screenViewport}>
              <AnimatePresence mode="wait" initial={false}>
                <motion.section
                  key={`${screen}:${fixtureState}`}
                  className={styles.screen}
                  initial={{
                    opacity: 0,
                    transform: reduceMotion
                      ? "translateX(0)"
                      : `translateX(${direction * 18}px)`,
                  }}
                  animate={{ opacity: 1, transform: "translateX(0)" }}
                  exit={{
                    opacity: 0,
                    transform: reduceMotion
                      ? "translateX(0)"
                      : `translateX(${direction * -12}px)`,
                  }}
                  transition={
                    reduceMotion
                      ? { duration: 0.16, ease: "easeOut" }
                      : SCREEN_TRANSITION
                  }
                >
                  <JourneyScreenContent
                    screen={screen}
                    fixtureState={fixtureState}
                    navigate={navigate}
                    setFixtureState={setFixtureState}
                  />
                </motion.section>
              </AnimatePresence>
            </div>

            {lab ? (
              <nav
                className={styles.previewControls}
                aria-label="Preview navigation"
              >
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className={styles.actionButton}
                  disabled={!previousScreen}
                  onClick={() => previousScreen && navigate(previousScreen)}
                >
                  <ArrowLeft aria-hidden="true" />
                  Back
                </Button>
                <p>
                  Screen <span>{currentIndex + 1}</span> of{" "}
                  {SCREEN_STEPS.length}
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className={styles.actionButton}
                  disabled={!nextScreen}
                  onClick={() => nextScreen && navigate(nextScreen)}
                >
                  Next screen
                  <ArrowRight aria-hidden="true" />
                </Button>
              </nav>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}

function JourneyScreenContent({
  screen,
  fixtureState,
  navigate,
  setFixtureState,
}: ScreenProps & { screen: JourneyScreen }) {
  const props = { fixtureState, navigate, setFixtureState };
  switch (screen) {
    case "login":
      return <LoginScreen {...props} />;
    case "paywall":
      return <PaywallScreen {...props} />;
    case "brief":
      return <BriefScreen {...props} />;
    case "source":
      return <SourceScreen {...props} />;
    case "processing":
      return <ProcessingScreen {...props} />;
    case "result":
      return <ResultScreen {...props} />;
    case "workspace":
      return <WorkspaceScreen {...props} />;
  }
}

function LoginScreen({ fixtureState, navigate, setFixtureState }: ScreenProps) {
  const [email, setEmail] = React.useState(
    fixtureState === "empty" ? "" : "augustin@studio.example",
  );
  const busy = fixtureState === "loading";

  if (fixtureState === "success") {
    return (
      <div className={styles.authLayout}>
        <ScreenIntro
          index="01"
          eyebrow="Workspace access"
          title="The thread starts with you."
          description="The real product uses a secure sign-in link or Google. This preview keeps everything local."
        />
        <div
          className={`${styles.surface} ${styles.successSurface}`}
          role="status"
        >
          <span className={styles.largeStatusIcon}>
            <Mail aria-hidden="true" />
          </span>
          <p className={styles.kicker}>Preview state · link sent</p>
          <h2>Check your inbox.</h2>
          <p>
            A sign-in link would be sent to <strong>{email}</strong>. No email
            was sent from this static route.
          </p>
          <Button
            type="button"
            className={styles.actionButton}
            onClick={() => navigate("brief")}
          >
            Create the campaign brief
            <ArrowRight aria-hidden="true" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.authLayout}>
      <div className={styles.authStory}>
        <ScreenIntro
          index="01"
          eyebrow="Workspace access"
          title="Give your first clip a direction."
          description="Create an account, define the campaign, then bring the source. The plan only appears when processing is ready to begin."
        />
        <div className={styles.threadStatement}>
          <span aria-hidden="true" />
          <p>
            ClipFactory keeps the editorial reason beside the clip, not buried
            in a separate report.
          </p>
        </div>
      </div>

      <form
        className={`${styles.surface} ${styles.authCard}`}
        onSubmit={(event) => {
          event.preventDefault();
          setFixtureState("success");
        }}
        aria-busy={busy}
      >
        <div className={styles.cardHeading}>
          <div>
            <p className={styles.kicker}>Sign in</p>
            <h2>Open your workspace</h2>
          </div>
          <span className={styles.secureIcon}>
            <LockKeyhole aria-hidden="true" />
          </span>
        </div>

        <StateNotice
          state={fixtureState}
          loadingTitle="Opening the sign-in service"
          loadingDetail="The form remains visible so the next action stays predictable."
          emptyTitle="No email entered yet"
          emptyDetail="Use Google or add the email that should own this workspace."
          errorTitle="Sign-in is unavailable"
          errorDetail="Nothing was lost. Try the link again or continue through the static journey controls."
        />

        <Button
          type="button"
          variant="secondary"
          className={`${styles.actionButton} ${styles.fullButton}`}
          disabled={busy}
          onClick={() => setFixtureState("success")}
        >
          <span className={styles.googleMark} aria-hidden="true">
            G
          </span>
          Continue with Google
        </Button>

        <div className={styles.divider} role="separator" aria-label="or">
          <span />
          <small>or</small>
          <span />
        </div>

        <FieldLabel label="Email" htmlFor="journey-email">
          <Input
            id="journey-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            disabled={busy}
          />
        </FieldLabel>

        <Button
          type="submit"
          className={`${styles.actionButton} ${styles.fullButton}`}
          disabled={busy || email.length === 0}
        >
          {busy ? "Checking the browser…" : "Preview sign-in link"}
          {!busy ? (
            <ArrowRight aria-hidden="true" />
          ) : (
            <LoaderCircle aria-hidden="true" />
          )}
        </Button>
        <p className={styles.formFootnote}>
          Static preview: no account is created and no message is sent.
        </p>
      </form>
    </div>
  );
}

function PaywallScreen({
  fixtureState,
  navigate,
  setFixtureState,
}: ScreenProps) {
  const active = fixtureState === "success";
  const busy = fixtureState === "loading";

  return (
    <div className={styles.paywallLayout}>
      <ScreenIntro
        index="04"
        eyebrow={active ? "Plan active" : "Starter plan"}
        title={
          active
            ? "Processing is unlocked."
            : "Everything is ready. Unlock the cut."
        }
        description="Your campaign brief and source are already in place. Starter unlocks the real analysis, render and download without making you rebuild the setup."
      />

      <div className={styles.planGrid}>
        <article
          className={`${styles.surface} ${styles.planCard} ${
            active ? styles.planCardActive : ""
          }`}
          aria-busy={busy}
        >
          <div className={styles.planTopline}>
            <span className={styles.planBadge}>
              {active ? "Active" : "Starter"}
            </span>
            <CreditCard aria-hidden="true" />
          </div>
          <div className={styles.priceLine}>
            <strong>€29</strong>
            <span>/ month</span>
          </div>
          <p className={styles.planLead}>300 credits each month.</p>

          <StateNotice
            state={fixtureState}
            loadingTitle="Confirming plan status"
            loadingDetail="No payment is made from this preview."
            emptyTitle="No plan selected"
            emptyDetail="Starter is the only plan represented in the current product contract."
            errorTitle="Plan activation was not confirmed"
            errorDetail="The workspace remains unchanged. Retry the preview state when ready."
            successTitle="Starter is active"
            successDetail="The source can now enter the real processing pipeline."
          />

          <ul className={styles.featureList}>
            <Feature>300 credits per month</Feature>
            <Feature>YouTube and Vimeo source URLs</Feature>
            <Feature>Sources up to 30 minutes</Feature>
            <Feature>Request 1–3 clip candidates</Feature>
            <Feature>One active processing job at a time</Feature>
          </ul>

          <Button
            type="button"
            className={`${styles.actionButton} ${styles.fullButton}`}
            disabled={busy}
            onClick={() =>
              active
                ? navigate("result", "success")
                : setFixtureState("success")
            }
          >
            {busy
              ? "Confirming preview…"
              : active
                ? "Open the unlocked result"
                : "Unlock processing with Starter"}
            {!busy ? (
              <ArrowRight aria-hidden="true" />
            ) : (
              <LoaderCircle aria-hidden="true" />
            )}
          </Button>
          <p className={styles.formFootnote}>
            Static preview only. Checkout is not opened and payment details are
            never requested here.
          </p>
        </article>

        <aside className={styles.contractPanel}>
          <p className={styles.kicker}>Ready to process</p>
          <h2>The setup stays attached.</h2>
          <p>
            Founder proof series · YouTube source · three requested clips. The
            paid step unlocks compute; it does not erase the work already done.
          </p>
          <div className={styles.contractFlow} aria-label="Activation flow">
            <span>Brief</span>
            <ChevronRight aria-hidden="true" />
            <span>Source</span>
            <ChevronRight aria-hidden="true" />
            <span>Starter</span>
            <ChevronRight aria-hidden="true" />
            <span>Process</span>
          </div>
        </aside>
      </div>
    </div>
  );
}

function BriefScreen({ fixtureState, navigate, setFixtureState }: ScreenProps) {
  const blank = fixtureState === "empty";
  const busy = fixtureState === "loading";
  const saved = fixtureState === "success";

  if (busy) {
    return (
      <div>
        <ScreenIntro
          index="02"
          eyebrow="Campaign brief"
          title="Give the edit a point of view."
          description="Audience, goal and tone narrow the search before the source is processed."
        />
        <LoadingPanel
          title="Opening the campaign draft"
          detail="The fields and source step will appear in the same place."
          rows={6}
        />
      </div>
    );
  }

  return (
    <div>
      <ScreenIntro
        index="02"
        eyebrow="Campaign brief"
        title="Give the edit a point of view."
        description="The brief is not decoration. It is the filter that keeps a technically strong moment from becoming the wrong clip."
      />

      <form
        className={styles.briefGrid}
        onSubmit={(event) => {
          event.preventDefault();
          if (saved) navigate("source");
          else setFixtureState("success");
        }}
      >
        <div className={`${styles.surface} ${styles.formSurface}`}>
          <StateNotice
            state={fixtureState}
            emptyTitle="Start with a campaign name"
            emptyDetail="The preview intentionally shows the unfilled first-use state."
            errorTitle="The draft could not be saved"
            errorDetail="The entered copy stays visible. Retry without rebuilding the brief."
            successTitle="Campaign brief saved"
            successDetail="The source can now be evaluated against the same intent."
          />
          <div className={styles.formGridTwo}>
            <FieldLabel label="Campaign name" htmlFor="campaign-name">
              <Input
                id="campaign-name"
                required
                maxLength={80}
                defaultValue={blank ? "" : "Founder proof series"}
                placeholder="Founder lessons Q2"
              />
            </FieldLabel>
            <FieldLabel label="Niche" htmlFor="campaign-niche">
              <Input
                id="campaign-niche"
                maxLength={120}
                defaultValue={blank ? "" : "Bootstrapped SaaS"}
                placeholder="Bootstrapped SaaS"
              />
            </FieldLabel>
          </div>
          <FieldLabel label="Target audience" htmlFor="campaign-audience">
            <Input
              id="campaign-audience"
              maxLength={400}
              defaultValue={
                blank ? "" : "Solo SaaS founders validating paid acquisition"
              }
              placeholder="Who should recognize themselves in this clip?"
            />
          </FieldLabel>
          <div className={styles.formGridTwo}>
            <FieldLabel label="Tone" htmlFor="campaign-tone">
              <Input
                id="campaign-tone"
                maxLength={120}
                defaultValue={blank ? "" : "Direct, evidence-led, no hype"}
                placeholder="Direct, no-fluff"
              />
            </FieldLabel>
            <FieldLabel label="Avoid topics" htmlFor="campaign-avoid">
              <Input
                id="campaign-avoid"
                maxLength={400}
                defaultValue={
                  blank ? "" : "Fundraising claims, competitor attacks"
                }
                placeholder="Comma-separated"
              />
            </FieldLabel>
          </div>
          <FieldLabel label="Clip series goal" htmlFor="campaign-goal">
            <textarea
              id="campaign-goal"
              className={styles.textarea}
              rows={3}
              maxLength={400}
              defaultValue={
                blank
                  ? ""
                  : "Show that the product result is visible before the founder explains the promise."
              }
              placeholder="What should this clip make the viewer understand or do?"
            />
          </FieldLabel>
          <FieldLabel label="Example hooks" htmlFor="campaign-hooks">
            <textarea
              id="campaign-hooks"
              className={styles.textarea}
              rows={3}
              defaultValue={
                blank
                  ? ""
                  : "The proof was already on screen.\nWe changed the frame, not the product."
              }
              placeholder="One hook per line"
            />
          </FieldLabel>
          <Button type="submit" className={styles.actionButton}>
            {saved ? "Choose a source" : "Save preview brief"}
            <ArrowRight aria-hidden="true" />
          </Button>
        </div>

        <aside className={`${styles.surface} ${styles.briefSummary}`}>
          <p className={styles.kicker}>What travels forward</p>
          <h2>Intent becomes a visible constraint.</h2>
          <ol className={styles.summaryList}>
            <li>
              <span>01</span>
              <p>
                <strong>Audience</strong>
                <small>Who the moment must resonate with.</small>
              </p>
            </li>
            <li>
              <span>02</span>
              <p>
                <strong>Goal</strong>
                <small>What the clip needs to prove or unlock.</small>
              </p>
            </li>
            <li>
              <span>03</span>
              <p>
                <strong>Tone</strong>
                <small>How the edit should sound, not merely look.</small>
              </p>
            </li>
          </ol>
        </aside>
      </form>
    </div>
  );
}

function SourceScreen({ fixtureState, navigate }: ScreenProps) {
  const [clipCount, setClipCount] = React.useState("3");
  const blank = fixtureState === "empty";
  const busy = fixtureState === "loading";

  return (
    <div>
      <ScreenIntro
        index="03"
        eyebrow="Source intake"
        title="Bring the source, not a guess."
        description="A public YouTube or Vimeo URL enters the same thread as the campaign brief. File upload is outside this version."
      />

      <form
        className={styles.sourceGrid}
        onSubmit={(event) => {
          event.preventDefault();
          navigate("processing");
        }}
        aria-busy={busy}
      >
        <div className={`${styles.surface} ${styles.sourceForm}`}>
          <StateNotice
            state={fixtureState}
            loadingTitle="Checking the source field"
            loadingDetail="The URL remains visible; no remote request is made in this preview."
            emptyTitle="No source URL yet"
            emptyDetail="Paste a public YouTube or Vimeo URL to define the source."
            errorTitle="This URL cannot be used"
            errorDetail="Use a public YouTube or Vimeo URL. The current entry stays in the field for correction."
            successTitle="Source format accepted"
            successDetail="This confirms only the preview state; the source was not fetched."
          />
          <FieldLabel label="YouTube or Vimeo URL" htmlFor="source-url">
            <div className={styles.urlField}>
              <Link2 aria-hidden="true" />
              <Input
                id="source-url"
                type="url"
                required
                disabled={busy}
                defaultValue={
                  blank
                    ? ""
                    : "https://www.youtube.com/watch?v=founder-interview"
                }
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </div>
          </FieldLabel>

          <fieldset className={styles.clipCountFieldset} disabled={busy}>
            <legend>Clip candidates</legend>
            <div className={styles.segmentedControl}>
              {["1", "2", "3"].map((value) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="clip-count"
                    value={value}
                    checked={clipCount === value}
                    onChange={(event) => setClipCount(event.target.value)}
                  />
                  <span>{value}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className={styles.sourceBoundary}>
            <span>
              <CheckCircle2 aria-hidden="true" />
              Public URL
            </span>
            <span>
              <Clock3 aria-hidden="true" />
              Up to 30 minutes
            </span>
            <span>
              <Gauge aria-hidden="true" />
              300 credits available · fixture
            </span>
          </div>

          <Button type="submit" className={styles.actionButton} disabled={busy}>
            {busy ? "Checking preview…" : "Build my first clip"}
            {!busy ? (
              <ArrowRight aria-hidden="true" />
            ) : (
              <LoaderCircle aria-hidden="true" />
            )}
          </Button>
        </div>

        <aside className={styles.sourcePreview}>
          <div className={styles.sourceImage}>
            <Image
              src="/prototypes/founder-frame-1-v2.webp"
              alt="Illustrative founder interview source frame"
              fill
              priority
              sizes="(max-width: 760px) 100vw, 36vw"
            />
            <span className={styles.sourceImageBadge}>Illustrative source</span>
            <span className={styles.playButton} aria-hidden="true">
              <Play />
            </span>
          </div>
          <div className={styles.sourceMetadata}>
            <div>
              <p>Founder interview · product proof</p>
              <span>YouTube URL · preview fixture</span>
            </div>
            <strong>{clipCount} candidates</strong>
          </div>
        </aside>
      </form>
    </div>
  );
}

function ProcessingScreen({
  fixtureState,
  navigate,
  setFixtureState,
}: ScreenProps) {
  if (fixtureState === "empty") {
    return (
      <div>
        <ScreenIntro
          index="04"
          eyebrow="Source processing"
          title="Nothing entered the thread yet."
          description="A job starts only after a campaign brief and a supported source URL are present."
        />
        <EmptyPanel
          icon={Link2}
          title="No source to process"
          detail="Return to source intake and add a public YouTube or Vimeo URL."
          actionLabel="Add a source"
          onAction={() => navigate("source", "empty")}
        />
      </div>
    );
  }

  if (fixtureState === "error") {
    return (
      <div>
        <ScreenIntro
          index="04"
          eyebrow="Source processing"
          title="The thread stopped safely."
          description="A failed stage is named directly so the next action is obvious and no delivery is implied."
        />
        <EmptyPanel
          icon={TriangleAlert}
          tone="danger"
          title="No usable moment passed the source checks"
          detail="No delivery was created in this fixture. Review the URL or campaign brief, then try the preview again."
          actionLabel="Review the source"
          onAction={() => navigate("source", "error")}
        />
      </div>
    );
  }

  const complete = fixtureState === "success";
  const activeIndex = fixtureState === "loading" ? 1 : complete ? 5 : 3;
  const activeLabel = complete
    ? "Delivery prepared"
    : (PROCESS_STEPS[activeIndex]?.[0] ?? "Preparing source");

  return (
    <div>
      <ScreenIntro
        index="04"
        eyebrow={complete ? "Processing complete" : "Source processing"}
        title={
          complete
            ? "Three candidates stayed grounded."
            : "Keep every stage legible."
        }
        description="Progress is shown as discrete work, not a made-up percentage or unconfirmed time estimate."
      />

      <div className={styles.processingGrid} aria-live="polite">
        <section className={styles.processingStage}>
          <div className={styles.processingImage}>
            <Image
              src="/prototypes/founder-frame-3-v2.webp"
              alt="Illustrative interview frame being evaluated"
              fill
              sizes="(max-width: 760px) 100vw, 48vw"
            />
            <div className={styles.frameShade} />
            <div className={styles.frameChrome}>
              <span>9:16 · auto frame</span>
              <span>09:32</span>
            </div>
            <div className={styles.transcriptAnchor}>
              <small>Illustrative transcript anchor</small>
              <p>
                The product was already visible.{" "}
                <mark>The proof arrived before the promise.</mark>
              </p>
            </div>
          </div>
          <div className={styles.waveform} aria-hidden="true">
            {WAVEFORM.map((height, index) => (
              <span key={index} style={{ height: `${height}%` }} />
            ))}
            <i />
          </div>
        </section>

        <section className={`${styles.surface} ${styles.pipelinePanel}`}>
          <div className={styles.cardHeading}>
            <div>
              <p className={styles.kicker}>Live stage · fixture</p>
              <h2>{activeLabel}</h2>
            </div>
            <span className={styles.secureIcon}>
              {complete ? (
                <Check aria-hidden="true" />
              ) : (
                <ScanText aria-hidden="true" />
              )}
            </span>
          </div>
          <ol className={styles.pipelineList}>
            {PROCESS_STEPS.map(([label, detail], index) => {
              const done = complete || index < activeIndex;
              const active = !complete && index === activeIndex;
              return (
                <li
                  key={label}
                  data-done={done || undefined}
                  data-active={active || undefined}
                >
                  <span className={styles.pipelineNode} aria-hidden="true">
                    {done ? <Check /> : String(index + 1).padStart(2, "0")}
                  </span>
                  <p>
                    <strong>{label}</strong>
                    <small>{detail}</small>
                  </p>
                  {active ? <span className={styles.nowBadge}>Now</span> : null}
                </li>
              );
            })}
          </ol>
          <p className={styles.formFootnote}>
            No percentage or completion-time estimate is shown because this is a
            static preview.
          </p>
          <Button
            type="button"
            className={`${styles.actionButton} ${styles.fullButton}`}
            onClick={() =>
              complete ? navigate("result") : setFixtureState("success")
            }
          >
            {complete ? "Review the candidates" : "Finish the preview job"}
            <ArrowRight aria-hidden="true" />
          </Button>
        </section>
      </div>
    </div>
  );
}

function ResultScreen({ fixtureState, navigate }: ScreenProps) {
  const [selectedClip, setSelectedClip] = React.useState<string>(CLIPS[0].id);

  if (fixtureState === "loading") {
    return (
      <div>
        <ScreenIntro
          index="05"
          eyebrow="Candidate review"
          title="Assembling the review surface."
          description="The selected frame, transcript evidence and rationale will arrive together."
        />
        <LoadingPanel
          title="Preparing three candidate views"
          detail="The picker stays reserved so the layout does not jump."
          rows={4}
          media
        />
      </div>
    );
  }

  if (fixtureState === "empty" || fixtureState === "error") {
    return (
      <div>
        <ScreenIntro
          index="05"
          eyebrow="Candidate review"
          title={
            fixtureState === "empty"
              ? "No candidate cleared the checks."
              : "The delivery view is unavailable."
          }
          description="An empty or unavailable result must never masquerade as a successful export."
        />
        <EmptyPanel
          icon={fixtureState === "empty" ? Film : TriangleAlert}
          tone={fixtureState === "error" ? "danger" : "neutral"}
          title={
            fixtureState === "empty"
              ? "No delivery created"
              : "Delivery could not be opened"
          }
          detail={
            fixtureState === "empty"
              ? "Review the campaign brief or use a source with a clearer, self-contained moment."
              : "The result stays untouched. Return to the processing trace and retry from there."
          }
          actionLabel="Review processing"
          onAction={() => navigate("processing", fixtureState)}
        />
      </div>
    );
  }

  const selected = CLIPS.find((clip) => clip.id === selectedClip) ?? CLIPS[0];

  return (
    <div>
      <ScreenIntro
        index="05"
        eyebrow="Candidate review"
        title="Choose with the evidence beside it."
        description="Every candidate keeps its frame, source timing, transcript excerpt and editorial reason in one review surface."
      />

      <Tabs value={selectedClip} onValueChange={setSelectedClip}>
        <div className={styles.resultToolbar}>
          <TabsList
            className={styles.clipTabsList}
            aria-label="Clip candidates"
          >
            {CLIPS.map((clip) => (
              <TabsTrigger
                key={clip.id}
                value={clip.id}
                className={styles.clipTabTrigger}
              >
                {clip.shortLabel}
                <span>{clip.score}</span>
              </TabsTrigger>
            ))}
          </TabsList>
          <span className={styles.illustrativeBadge}>Illustrative result</span>
        </div>

        {CLIPS.map((clip) => (
          <TabsContent
            key={clip.id}
            value={clip.id}
            className={styles.clipTabContent}
          >
            <motion.div
              key={clip.id}
              className={styles.resultGrid}
              initial={{ opacity: 0, transform: "translateY(8px)" }}
              animate={{ opacity: 1, transform: "translateY(0)" }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              <section className={styles.resultMedia}>
                <div className={styles.verticalFrame}>
                  <Image
                    src={clip.image}
                    alt={`Illustrative frame for ${clip.title}`}
                    fill
                    sizes="(max-width: 760px) 88vw, 34vw"
                  />
                  <div className={styles.frameChrome}>
                    <span>9:16 · auto frame</span>
                    <span>{clip.moment.split("–")[0]}</span>
                  </div>
                  <div className={styles.captionCard}>
                    <p>{clip.title}</p>
                    <span>
                      {clip.moment} · {clip.duration}
                    </span>
                  </div>
                </div>
                <div className={styles.resultTimeline}>
                  <span />
                  <i style={{ left: `${28 + CLIPS.indexOf(clip) * 24}%` }} />
                  <small>{clip.moment}</small>
                </div>
              </section>

              <aside className={`${styles.surface} ${styles.inspector}`}>
                <div className={styles.inspectorHeading}>
                  <div>
                    <p className={styles.kicker}>Why this moment</p>
                    <h2>{clip.title}</h2>
                  </div>
                  <strong className={styles.scoreBadge}>{clip.score}</strong>
                </div>
                <p className={styles.rationale}>{clip.rationale}</p>
                <blockquote className={styles.transcriptQuote}>
                  <span>Illustrative source excerpt</span>“{clip.transcript}”
                </blockquote>
                <dl className={styles.metricList}>
                  {clip.metrics.map(([label, value]) => (
                    <div key={label}>
                      <dt>
                        <span>{label}</span>
                        <strong>{value}</strong>
                      </dt>
                      <dd>
                        <span style={{ width: `${value}%` }} />
                      </dd>
                    </div>
                  ))}
                </dl>
                <div className={styles.resultActions}>
                  <Button
                    type="button"
                    variant="secondary"
                    className={styles.actionButton}
                    disabled
                    title="No export is generated by this static preview"
                  >
                    <Download aria-hidden="true" />
                    Export unavailable
                  </Button>
                  <Button
                    type="button"
                    className={styles.actionButton}
                    onClick={() => navigate("workspace")}
                  >
                    Keep in workspace
                    <ArrowRight aria-hidden="true" />
                  </Button>
                </div>
              </aside>
            </motion.div>
          </TabsContent>
        ))}
      </Tabs>
      <span className={styles.srOnly} aria-live="polite">
        Selected clip: {selected.title}
      </span>
    </div>
  );
}

function WorkspaceScreen({ fixtureState, navigate }: ScreenProps) {
  if (fixtureState === "loading") {
    return (
      <div>
        <ScreenIntro
          index="06"
          eyebrow="Workspace"
          title="Opening the work in context."
          description="Campaign, source and candidate history keep their reserved positions while loading."
        />
        <LoadingPanel
          title="Loading the workspace fixture"
          detail="No Supabase or product API is called from this route."
          rows={5}
          media
        />
      </div>
    );
  }

  if (fixtureState === "empty") {
    return (
      <div>
        <ScreenIntro
          index="06"
          eyebrow="Workspace"
          title="A quiet first workspace."
          description="The empty state points to the next meaningful action instead of filling the page with demo metrics."
        />
        <EmptyPanel
          icon={Target}
          title="No campaign yet"
          detail="Create a campaign brief before adding a YouTube or Vimeo source."
          actionLabel="Create the first brief"
          onAction={() => navigate("brief", "empty")}
        />
      </div>
    );
  }

  if (fixtureState === "error") {
    return (
      <div>
        <ScreenIntro
          index="06"
          eyebrow="Workspace"
          title="The workspace did not load."
          description="The error state preserves the route and offers a reversible next step."
        />
        <EmptyPanel
          icon={TriangleAlert}
          tone="danger"
          title="Workspace data is unavailable"
          detail="No campaign was removed. Retry this fixture or inspect the journey through the screen rail."
          actionLabel="Retry preview"
          onAction={() => navigate("workspace")}
        />
      </div>
    );
  }

  return (
    <div>
      <div className={styles.workspaceHeader}>
        <ScreenIntro
          index="06"
          eyebrow="Workspace"
          title="The result stays attached to the reason."
          description="Campaign, source and delivery remain one traceable unit instead of three disconnected dashboards."
        />
        <Button
          type="button"
          className={styles.actionButton}
          onClick={() => navigate("source", "empty")}
        >
          New source
          <ArrowRight aria-hidden="true" />
        </Button>
      </div>

      <div className={styles.workspaceGrid}>
        <section className={`${styles.surface} ${styles.campaignPanel}`}>
          <div className={styles.panelTopline}>
            <span className={styles.statusChip}>
              <span />
              Active campaign
            </span>
            <small>Preview fixture</small>
          </div>
          <h2>Founder proof series</h2>
          <p>
            Show that the product result is visible before the founder explains
            the promise.
          </p>
          <div className={styles.campaignMeta}>
            <span>
              <Target aria-hidden="true" />
              Solo SaaS founders
            </span>
            <span>
              <Link2 aria-hidden="true" />1 source
            </span>
            <span>
              <Clapperboard aria-hidden="true" />3 ready candidates
            </span>
          </div>
          <div className={styles.sourceThreadCard}>
            <div className={styles.threadPoster}>
              <Image
                src="/prototypes/founder-frame-4-v2.webp"
                alt="Illustrative ready clip frame"
                fill
                sizes="160px"
              />
            </div>
            <div>
              <small>Ready · 09:32–09:45</small>
              <h3>The proof arrives before the promise.</h3>
              <p>Score 89 · rationale attached</p>
            </div>
            <button
              type="button"
              onClick={() => navigate("result")}
              aria-label="Open candidate review"
            >
              <ChevronRight aria-hidden="true" />
            </button>
          </div>
        </section>

        <aside className={styles.workspaceSide}>
          <section className={`${styles.surface} ${styles.creditPanel}`}>
            <div className={styles.panelTopline}>
              <span>
                <Gauge aria-hidden="true" />
                Credits
              </span>
              <small>Demo balance</small>
            </div>
            <div className={styles.creditValue}>
              <strong>276</strong>
              <span>/ 300</span>
            </div>
            <div className={styles.creditTrack} aria-hidden="true">
              <span />
            </div>
            <p>Starter · monthly allocation</p>
          </section>

          <section className={`${styles.surface} ${styles.activityPanel}`}>
            <div className={styles.panelTopline}>
              <span>
                <Sparkles aria-hidden="true" />
                Source trail
              </span>
              <small>Today</small>
            </div>
            <ol>
              <li>
                <span>
                  <Check aria-hidden="true" />
                </span>
                <p>
                  <strong>Delivery ready</strong>
                  <small>3 candidates kept their evidence.</small>
                </p>
              </li>
              <li>
                <span>
                  <ScanText aria-hidden="true" />
                </span>
                <p>
                  <strong>Brief matched</strong>
                  <small>Audience and goal were applied.</small>
                </p>
              </li>
              <li>
                <span>
                  <Link2 aria-hidden="true" />
                </span>
                <p>
                  <strong>Source accepted</strong>
                  <small>YouTube URL · fixture.</small>
                </p>
              </li>
            </ol>
          </section>
        </aside>
      </div>
    </div>
  );
}

function ScreenIntro({
  index,
  eyebrow,
  title,
  description,
}: {
  index: string;
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className={styles.screenIntro}>
      <div className={styles.screenIndex} aria-hidden="true">
        <span>{index}</span>
      </div>
      <div>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1>{title}</h1>
        <p className={styles.screenDescription}>{description}</p>
      </div>
    </header>
  );
}

function FieldLabel({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <label className={styles.field} htmlFor={htmlFor}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function Feature({ children }: { children: React.ReactNode }) {
  return (
    <li>
      <span aria-hidden="true">
        <Check />
      </span>
      {children}
    </li>
  );
}

function StateNotice({
  state,
  loadingTitle,
  loadingDetail,
  emptyTitle,
  emptyDetail,
  errorTitle,
  errorDetail,
  successTitle,
  successDetail,
}: {
  state: JourneyFixtureState;
  loadingTitle?: string;
  loadingDetail?: string;
  emptyTitle?: string;
  emptyDetail?: string;
  errorTitle?: string;
  errorDetail?: string;
  successTitle?: string;
  successDetail?: string;
}) {
  if (state === "default") return null;

  const content = {
    loading: {
      title: loadingTitle ?? "Loading this fixture",
      detail:
        loadingDetail ?? "The content will stay in place when it arrives.",
      icon: LoaderCircle,
      className: styles.noticeLoading,
    },
    empty: {
      title: emptyTitle ?? "Nothing here yet",
      detail: emptyDetail ?? "The first meaningful action is available below.",
      icon: Film,
      className: styles.noticeEmpty,
    },
    error: {
      title: errorTitle ?? "This view is unavailable",
      detail: errorDetail ?? "Nothing was changed. Try again when ready.",
      icon: TriangleAlert,
      className: styles.noticeDanger,
    },
    success: {
      title: successTitle ?? "Ready",
      detail: successDetail ?? "The next step is available.",
      icon: CheckCircle2,
      className: styles.noticeSuccess,
    },
  }[state];

  const Icon = content.icon;
  return (
    <div
      className={`${styles.notice} ${content.className}`}
      role={state === "error" ? "alert" : "status"}
    >
      <Icon aria-hidden="true" />
      <p>
        <strong>{content.title}</strong>
        <span>{content.detail}</span>
      </p>
    </div>
  );
}

function LoadingPanel({
  title,
  detail,
  rows,
  media = false,
}: {
  title: string;
  detail: string;
  rows: number;
  media?: boolean;
}) {
  return (
    <div
      className={`${styles.surface} ${styles.loadingPanel}`}
      aria-busy="true"
    >
      <div className={styles.loadingHeading}>
        <span>
          <LoaderCircle aria-hidden="true" />
        </span>
        <p>
          <strong>{title}</strong>
          <small>{detail}</small>
        </p>
      </div>
      <div
        className={media ? styles.loadingSplit : styles.loadingRows}
        aria-hidden="true"
      >
        {media ? <span className={styles.loadingMedia} /> : null}
        <div className={styles.loadingRows}>
          {Array.from({ length: rows }).map((_, index) => (
            <span key={index} style={{ width: `${92 - (index % 3) * 13}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyPanel({
  icon: Icon,
  title,
  detail,
  actionLabel,
  onAction,
  tone = "neutral",
}: {
  icon: typeof Film;
  title: string;
  detail: string;
  actionLabel: string;
  onAction: () => void;
  tone?: "neutral" | "danger";
}) {
  return (
    <div
      className={`${styles.surface} ${styles.emptyPanel} ${
        tone === "danger" ? styles.emptyPanelDanger : ""
      }`}
    >
      <span className={styles.largeStatusIcon}>
        <Icon aria-hidden="true" />
      </span>
      <p className={styles.kicker}>
        {tone === "danger" ? "Action needed" : "First-use state"}
      </p>
      <h2>{title}</h2>
      <p>{detail}</p>
      <Button type="button" className={styles.actionButton} onClick={onAction}>
        {actionLabel}
        <ArrowRight aria-hidden="true" />
      </Button>
    </div>
  );
}
