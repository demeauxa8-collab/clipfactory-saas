"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  CircleAlert,
} from "lucide-react";

import { ProductStatus } from "@/components/product/product-primitives";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiFetch } from "@/lib/api";

import styles from "./new-campaign.module.css";

type Campaign = { id: string; name: string };

type CampaignDraft = {
  name: string;
  goal: string;
  audience: string;
  niche: string;
  tone: string;
  avoidTopics: string;
  exampleHooks: string;
};

type DraftField = keyof CampaignDraft;

const initialDraft: CampaignDraft = {
  name: "",
  goal: "",
  audience: "",
  niche: "",
  tone: "",
  avoidTopics: "",
  exampleHooks: "",
};

const chapters = [
  {
    title: "Promise",
    caption: "Name and outcome",
  },
  {
    title: "Audience",
    caption: "People and voice",
  },
  {
    title: "Boundaries",
    caption: "Guardrails and hooks",
  },
] as const;

const panelVariants = {
  enter: (direction: number) => ({
    opacity: 0,
    transform: `translateX(${direction >= 0 ? 24 : -24}px)`,
  }),
  center: {
    opacity: 1,
    transform: "translateX(0)",
  },
  exit: (direction: number) => ({
    opacity: 0,
    transform: `translateX(${direction >= 0 ? -18 : 18}px)`,
  }),
};

function splitCommaList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitLineList(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function campaignErrorCopy(error: unknown) {
  if (!(error instanceof ApiError)) {
    return "We couldn’t reach ClipFactory. Check your connection and try again.";
  }

  if (error.code === "not_authenticated" || error.status === 401) {
    return "Your session expired. Sign in again before creating this campaign.";
  }

  if (error.code === "rate_limit_exceeded" || error.status === 429) {
    return "You’ve created several campaigns recently. Wait a moment, then try again.";
  }

  if (error.status === 422) {
    return "One or more details could not be saved. Check the character limits and try again.";
  }

  if (error.status >= 500) {
    return "ClipFactory couldn’t create the campaign right now. Your brief is still here—try again.";
  }

  return "We couldn’t create this campaign. Review the brief and try again.";
}

export function NewCampaignForm() {
  const router = useRouter();
  const prefersReducedMotion = useReducedMotion();
  const nameInputRef = React.useRef<HTMLInputElement>(null);
  const [draft, setDraft] = React.useState<CampaignDraft>(initialDraft);
  const [chapter, setChapter] = React.useState(0);
  const [direction, setDirection] = React.useState(1);
  const [nameError, setNameError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (chapter === 0 && nameError) {
      nameInputRef.current?.focus();
    }
  }, [chapter, nameError]);

  function updateDraft(field: DraftField, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
    setError(null);

    if (field === "name" && value.trim()) {
      setNameError(null);
    }
  }

  function validateName() {
    if (draft.name.trim()) {
      setNameError(null);
      return true;
    }

    setNameError("Give this campaign a name before continuing.");
    return false;
  }

  function goToChapter(nextChapter: number) {
    if (busy || nextChapter === chapter) return;

    if (nextChapter > 0 && !validateName()) {
      if (chapter !== 0) {
        setDirection(-1);
        setChapter(0);
      }
      return;
    }

    setDirection(nextChapter > chapter ? 1 : -1);
    setChapter(nextChapter);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (chapter < chapters.length - 1) {
      goToChapter(chapter + 1);
      return;
    }

    if (!validateName()) {
      if (chapter !== 0) {
        setDirection(-1);
        setChapter(0);
      }
      return;
    }

    setBusy(true);
    setError(null);

    const payload = {
      name: draft.name.trim(),
      audience: draft.audience.trim(),
      niche: draft.niche.trim(),
      tone: draft.tone.trim(),
      goal: draft.goal.trim(),
      avoid_topics: splitCommaList(draft.avoidTopics),
      example_hooks: splitLineList(draft.exampleHooks),
    };

    try {
      const created = await apiFetch<Campaign>("/campaigns", {
        method: "POST",
        json: payload,
      });
      router.push(`/app/campaigns/${created.id}`);
      router.refresh();
    } catch (caughtError) {
      setError(campaignErrorCopy(caughtError));
      setBusy(false);
    }
  }

  const transition = prefersReducedMotion
    ? { duration: 0.01 }
    : {
        type: "spring" as const,
        visualDuration: 0.24,
        bounce: 0,
      };

  return (
    <form className={styles.shell} onSubmit={handleSubmit} noValidate>
      <WizardRail activeChapter={chapter} busy={busy} onSelect={goToChapter} />

      <div className={styles.editor}>
        <p className={styles.mobileProgress} aria-live="polite">
          Step {chapter + 1} of {chapters.length} · {chapters[chapter].title}
        </p>

        <div className={styles.motionViewport}>
          <AnimatePresence mode="wait" initial={false} custom={direction}>
            <motion.div
              key={chapter}
              custom={direction}
              variants={panelVariants}
              initial={prefersReducedMotion ? false : "enter"}
              animate="center"
              exit={prefersReducedMotion ? undefined : "exit"}
              transition={transition}
              role="group"
              aria-labelledby={`campaign-chapter-${chapter}`}
              className={styles.chapter}
            >
              {chapter === 0 ? (
                <PromiseChapter
                  draft={draft}
                  nameError={nameError}
                  nameInputRef={nameInputRef}
                  onChange={updateDraft}
                />
              ) : null}
              {chapter === 1 ? (
                <AudienceChapter draft={draft} onChange={updateDraft} />
              ) : null}
              {chapter === 2 ? (
                <BoundariesChapter draft={draft} onChange={updateDraft} />
              ) : null}
            </motion.div>
          </AnimatePresence>
        </div>

        <details className={styles.mobilePreview}>
          <summary>
            Preview Campaign Lens
            <ChevronDown aria-hidden="true" />
          </summary>
          <CampaignLens draft={draft} compact />
        </details>

        {error ? (
          <div className={styles.apiError} role="alert">
            <CircleAlert aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className={styles.actions}>
          {chapter > 0 ? (
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={() => goToChapter(chapter - 1)}
            >
              <ArrowLeft aria-hidden="true" />
              Back
            </Button>
          ) : (
            <span aria-hidden="true" />
          )}

          {chapter < chapters.length - 1 ? (
            <Button
              type="button"
              disabled={busy}
              onClick={() => goToChapter(chapter + 1)}
            >
              Continue
              <ArrowRight aria-hidden="true" />
            </Button>
          ) : (
            <Button type="submit" disabled={busy}>
              {busy ? "Creating campaign…" : "Create campaign"}
            </Button>
          )}
        </div>
      </div>

      <aside className={styles.preview} aria-label="Live Campaign Lens preview">
        <CampaignLens draft={draft} />
      </aside>
    </form>
  );
}

function WizardRail({
  activeChapter,
  busy,
  onSelect,
}: {
  activeChapter: number;
  busy: boolean;
  onSelect: (chapter: number) => void;
}) {
  return (
    <nav className={styles.rail} aria-label="Campaign setup progress">
      <p className={styles.railLabel}>Brief chapters</p>
      <ol>
        {chapters.map((item, index) => {
          const state =
            index < activeChapter
              ? "complete"
              : index === activeChapter
                ? "current"
                : "upcoming";

          return (
            <li key={item.title} data-state={state}>
              <button
                type="button"
                disabled={busy}
                aria-current={index === activeChapter ? "step" : undefined}
                onClick={() => onSelect(index)}
              >
                <span className={styles.stepIndex} aria-hidden="true">
                  {state === "complete" ? <Check /> : index + 1}
                </span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.caption}</small>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function StepHeader({
  index,
  title,
  description,
}: {
  index: number;
  title: string;
  description: string;
}) {
  return (
    <header className={styles.stepHeader}>
      <p>Chapter {index + 1}</p>
      <h2 id={`campaign-chapter-${index}`}>{title}</h2>
      <span>{description}</span>
    </header>
  );
}

function PromiseChapter({
  draft,
  nameError,
  nameInputRef,
  onChange,
}: {
  draft: CampaignDraft;
  nameError: string | null;
  nameInputRef: React.RefObject<HTMLInputElement | null>;
  onChange: (field: DraftField, value: string) => void;
}) {
  return (
    <>
      <StepHeader
        index={0}
        title="Name the promise."
        description="Start with the result this series should repeatedly deliver. Keep it specific enough to judge every clip against it."
      />
      <div className={styles.fields}>
        <FieldLabel
          htmlFor="name"
          label="Campaign name"
          required
          hint="This is the only required field."
        >
          <Input
            ref={nameInputRef}
            id="name"
            name="name"
            value={draft.name}
            required
            maxLength={80}
            placeholder="Founder lessons · Q2"
            autoComplete="off"
            aria-invalid={Boolean(nameError)}
            aria-describedby={nameError ? "name-hint name-error" : "name-hint"}
            onChange={(event) => onChange("name", event.target.value)}
          />
          {nameError ? (
            <span className={styles.fieldError} id="name-error" role="alert">
              {nameError}
            </span>
          ) : null}
        </FieldLabel>

        <FieldLabel
          htmlFor="goal"
          label="Clip series goal"
          hint="What should viewers understand or do after watching?"
        >
          <textarea
            id="goal"
            name="goal"
            value={draft.goal}
            maxLength={400}
            rows={4}
            aria-describedby="goal-hint"
            placeholder="Make three clips that push viewers to join the newsletter."
            onChange={(event) => onChange("goal", event.target.value)}
          />
        </FieldLabel>
      </div>
    </>
  );
}

function AudienceChapter({
  draft,
  onChange,
}: {
  draft: CampaignDraft;
  onChange: (field: DraftField, value: string) => void;
}) {
  return (
    <>
      <StepHeader
        index={1}
        title="Define who leans in."
        description="Give ClipFactory enough context to distinguish a relevant insight from a merely interesting moment."
      />
      <div className={styles.fields}>
        <FieldLabel
          htmlFor="audience"
          label="Target audience"
          hint="Describe the person, their situation and what they already know."
        >
          <textarea
            id="audience"
            name="audience"
            value={draft.audience}
            maxLength={400}
            rows={4}
            aria-describedby="audience-hint"
            placeholder="Solo SaaS founders learning to run paid acquisition."
            onChange={(event) => onChange("audience", event.target.value)}
          />
        </FieldLabel>

        <div className={styles.fieldPair}>
          <FieldLabel
            htmlFor="niche"
            label="Niche"
            hint="The market shorthand."
          >
            <Input
              id="niche"
              name="niche"
              value={draft.niche}
              maxLength={120}
              aria-describedby="niche-hint"
              placeholder="Bootstrapped SaaS"
              onChange={(event) => onChange("niche", event.target.value)}
            />
          </FieldLabel>
          <FieldLabel
            htmlFor="tone"
            label="Tone"
            hint="How the edit should feel."
          >
            <Input
              id="tone"
              name="tone"
              value={draft.tone}
              maxLength={120}
              aria-describedby="tone-hint"
              placeholder="Direct, useful, no fluff"
              onChange={(event) => onChange("tone", event.target.value)}
            />
          </FieldLabel>
        </div>
      </div>
    </>
  );
}

function BoundariesChapter({
  draft,
  onChange,
}: {
  draft: CampaignDraft;
  onChange: (field: DraftField, value: string) => void;
}) {
  return (
    <>
      <StepHeader
        index={2}
        title="Set the editorial edges."
        description="Mark what never belongs and add a few hook patterns worth recognizing. Both fields are optional."
      />
      <div className={styles.fields}>
        <FieldLabel
          htmlFor="avoid_topics"
          label="Topics to avoid"
          hint="Separate topics with commas."
        >
          <Input
            id="avoid_topics"
            name="avoid_topics"
            value={draft.avoidTopics}
            maxLength={400}
            aria-describedby="avoid_topics-hint"
            placeholder="Politics, religion, crypto pumps"
            onChange={(event) => onChange("avoidTopics", event.target.value)}
          />
        </FieldLabel>

        <FieldLabel
          htmlFor="example_hooks"
          label="Example hooks"
          hint="One hook per line. These are references, not scripts to copy."
        >
          <textarea
            id="example_hooks"
            name="example_hooks"
            value={draft.exampleHooks}
            rows={6}
            aria-describedby="example_hooks-hint"
            placeholder={
              "They said it was impossible. Here is what happened.\nMy biggest mistake in the first year."
            }
            onChange={(event) => onChange("exampleHooks", event.target.value)}
          />
        </FieldLabel>
      </div>
    </>
  );
}

function FieldLabel({
  htmlFor,
  label,
  hint,
  required = false,
  children,
}: {
  htmlFor: string;
  label: string;
  hint: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <label htmlFor={htmlFor}>{label}</label>
        <span>{required ? "Required" : "Optional"}</span>
      </div>
      <p id={`${htmlFor}-hint`}>{hint}</p>
      {children}
    </div>
  );
}

function CampaignLens({
  draft,
  compact = false,
}: {
  draft: CampaignDraft;
  compact?: boolean;
}) {
  const avoidTopics = splitCommaList(draft.avoidTopics);
  const hooks = splitLineList(draft.exampleHooks);
  const audience = [draft.audience.trim(), draft.niche.trim()]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={compact ? styles.lensCompact : styles.lens}>
      <div className={styles.lensTopline}>
        <ProductStatus tone={draft.name.trim() ? "action" : "neutral"}>
          {draft.name.trim() ? "Lens taking shape" : "Draft lens"}
        </ProductStatus>
        <span>Live preview</span>
      </div>

      <div className={styles.lensTitle}>
        <p>Campaign Lens</p>
        <h3>{draft.name.trim() || "Untitled campaign"}</h3>
        <span>
          {draft.goal.trim() ||
            "Add the outcome this series should consistently deliver."}
        </span>
      </div>

      <dl className={styles.lensRows}>
        <div>
          <dt>Audience</dt>
          <dd>{audience || "Open until you narrow it"}</dd>
        </div>
        <div>
          <dt>Voice</dt>
          <dd>{draft.tone.trim() || "No tone constraint"}</dd>
        </div>
        <div>
          <dt>Boundaries</dt>
          <dd>
            {avoidTopics.length
              ? `${avoidTopics.length} topic${avoidTopics.length === 1 ? "" : "s"} excluded`
              : "No exclusions yet"}
          </dd>
        </div>
        <div>
          <dt>Hook signals</dt>
          <dd>
            {hooks.length
              ? `${hooks.length} reference${hooks.length === 1 ? "" : "s"}`
              : "No examples yet"}
          </dd>
        </div>
      </dl>
    </div>
  );
}
