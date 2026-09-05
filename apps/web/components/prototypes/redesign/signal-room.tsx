"use client";

import * as React from "react";
import styles from "./signal-room.module.css";

type SignalKind = "story" | "visual" | "fit";
type SignalFilter = "all" | SignalKind;

type Signal = {
  id: string;
  index: string;
  kind: SignalKind;
  kindLabel: string;
  status: string;
  title: string;
  cue: string;
  sourceTime: string;
  reason: string;
  instruction: string;
  segments: Array<{
    label: string;
    time: string;
    width: string;
  }>;
};

const FILTERS: Array<{ value: SignalFilter; label: string }> = [
  { value: "all", label: "All signals" },
  { value: "story", label: "Story" },
  { value: "visual", label: "Visual" },
  { value: "fit", label: "Campaign fit" },
];

const SIGNALS: Signal[] = [
  {
    id: "promise-before-reveal",
    index: "01",
    kind: "story",
    kindLabel: "Story link",
    status: "Selected",
    title: "Promise before reveal",
    cue: "The opening sets up a result without giving away the answer.",
    sourceTime: "02:14 + 12:47",
    reason:
      "The setup creates an open loop, while the later payoff answers the same question in language that matches the campaign brief.",
    instruction:
      "Open on the unfinished claim. Cut to the result after the pause. Keep the reaction before the final caption.",
    segments: [
      { label: "Setup", time: "02:14", width: "26%" },
      { label: "Bridge", time: "07:08", width: "17%" },
      { label: "Payoff", time: "12:47", width: "36%" },
    ],
  },
  {
    id: "proof-on-screen",
    index: "02",
    kind: "visual",
    kindLabel: "Visual proof",
    status: "Review",
    title: "The receipt enters frame",
    cue: "The claim becomes visible evidence instead of transcript-only copy.",
    sourceTime: "09:32",
    reason:
      "The audience can verify the speaker's claim on screen. That makes this moment useful as proof, not just as a strong sentence.",
    instruction:
      "Hold the frame until the amount is readable. Use the centred crop and keep the source text unobstructed.",
    segments: [
      { label: "Lead in", time: "09:26", width: "19%" },
      { label: "Proof", time: "09:32", width: "43%" },
      { label: "Reaction", time: "09:40", width: "22%" },
    ],
  },
  {
    id: "audience-language",
    index: "03",
    kind: "fit",
    kindLabel: "Campaign fit",
    status: "Strong fit",
    title: "Audience language detected",
    cue: "The speaker names the exact tradeoff in the campaign goal.",
    sourceTime: "16:05",
    reason:
      "This moment speaks directly to founders who need proof before spending. It advances the campaign goal without changing the speaker's tone.",
    instruction:
      "Keep this as a single scene. Lead with the tradeoff, then land on the concrete decision.",
    segments: [
      { label: "Hook", time: "16:05", width: "29%" },
      { label: "Context", time: "16:12", width: "31%" },
      { label: "Decision", time: "16:24", width: "25%" },
    ],
  },
  {
    id: "payoff-with-context",
    index: "04",
    kind: "story",
    kindLabel: "Story link",
    status: "Alternate",
    title: "Payoff needs its setup",
    cue: "The ending is strong, but only after the earlier constraint is restored.",
    sourceTime: "04:18 + 21:03",
    reason:
      "Used alone, the payoff sounds generic. Reconnecting it to the earlier constraint turns it into a complete before-and-after story.",
    instruction:
      "Use the first sentence as setup. Remove the middle explanation. Return for the payoff and final look to camera.",
    segments: [
      { label: "Constraint", time: "04:18", width: "30%" },
      { label: "Payoff", time: "21:03", width: "42%" },
    ],
  },
];

const KIND_LABELS: Record<SignalKind, string> = {
  story: "Story",
  visual: "Visual",
  fit: "Campaign fit",
};

export function SignalRoom() {
  const [filter, setFilter] = React.useState<SignalFilter>("all");
  const [selectedId, setSelectedId] = React.useState(SIGNALS[0].id);

  const visibleSignals = React.useMemo(
    () =>
      SIGNALS.filter((signal) => filter === "all" || signal.kind === filter),
    [filter],
  );

  const selected =
    SIGNALS.find((signal) => signal.id === selectedId) ??
    visibleSignals[0] ??
    SIGNALS[0];

  function selectFilter(nextFilter: SignalFilter) {
    setFilter(nextFilter);
    const firstMatch = SIGNALS.find(
      (signal) => nextFilter === "all" || signal.kind === nextFilter,
    );
    if (
      firstMatch &&
      nextFilter !== "all" &&
      firstMatch.kind !== selected.kind
    ) {
      setSelectedId(firstMatch.id);
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.noise} aria-hidden="true" />

      <header className={styles.navShell}>
        <nav className={styles.nav} aria-label="Signal Room prototype">
          <a
            className={styles.brand}
            href="#signal-room-top"
            aria-label="ClipFactory home"
          >
            <span className={styles.brandMark} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <span>ClipFactory</span>
            <span className={styles.brandMode}>Signal Room</span>
          </a>

          <div className={styles.navLinks}>
            <a href="#signal-room-method">Method</a>
            <a href="#signal-room-proof">Proof</a>
            <a href="/pricing">Pricing</a>
          </div>

          <a className={styles.navCta} href="/login">
            Start Starter - €29
          </a>
        </nav>
      </header>

      <main id="main-content">
        <section
          id="signal-room-top"
          className={styles.hero}
          aria-labelledby="signal-room-title"
        >
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span className={styles.liveDot} aria-hidden="true" />
              Campaign intelligence / vertical editing
            </div>

            <h1 id="signal-room-title" className={styles.headline}>
              Give it the campaign. <span>Get the clips that belong.</span>
            </h1>

            <p className={styles.supporting}>
              ClipFactory links distant moments, builds the vertical edit, and
              explains why each clip fits your audience.
            </p>

            <div className={styles.heroActions}>
              <a className={styles.primaryCta} href="/login">
                Start Starter - €29
                <span aria-hidden="true">↗</span>
              </a>
              <a className={styles.secondaryCta} href="#signal-room-proof">
                Watch the proof
                <span aria-hidden="true">↓</span>
              </a>
            </div>

            <div className={styles.heroFootnote} id="signal-room-method">
              <span>One campaign brief</span>
              <span>One long video</span>
              <span>Three clips to review</span>
            </div>
          </div>

          <aside
            className={styles.briefConsole}
            aria-label="Example campaign brief"
          >
            <div className={styles.consoleHeader}>
              <span>CF / CAMPAIGN 014</span>
              <span className={styles.consoleStatus}>
                <i aria-hidden="true" /> Example data
              </span>
            </div>

            <div className={styles.briefTitleRow}>
              <div>
                <span className={styles.fieldLabel}>Series objective</span>
                <strong>Turn product proof into a founder story</strong>
              </div>
              <span className={styles.briefTag}>READY</span>
            </div>

            <dl className={styles.briefFields}>
              <div>
                <dt>Audience</dt>
                <dd>Bootstrapped SaaS founders</dd>
              </div>
              <div>
                <dt>Tone</dt>
                <dd>Direct, specific, no hype</dd>
              </div>
              <div>
                <dt>Avoid</dt>
                <dd>Generic growth advice</dd>
              </div>
            </dl>

            <div
              className={styles.sourceMap}
              aria-label="Source map with four candidate signals"
            >
              <div className={styles.sourceMapHeader}>
                <span>Source map</span>
                <span>24:18</span>
              </div>
              <div className={styles.timeline} aria-hidden="true">
                <span className={styles.timelineBase} />
                <span
                  className={`${styles.timelineSignal} ${styles.signalOne}`}
                />
                <span
                  className={`${styles.timelineSignal} ${styles.signalTwo}`}
                />
                <span
                  className={`${styles.timelineSignal} ${styles.signalThree}`}
                />
                <span
                  className={`${styles.timelineSignal} ${styles.signalFour}`}
                />
              </div>
              <div className={styles.timelineTicks} aria-hidden="true">
                <span>00:00</span>
                <span>08:00</span>
                <span>16:00</span>
                <span>24:18</span>
              </div>
            </div>

            <div className={styles.consoleFooter}>
              <span>4 editorial signals</span>
              <span>2 distant story links</span>
              <span>1 brief bound to every pick</span>
            </div>
          </aside>
        </section>

        <section
          id="signal-room-proof"
          className={styles.proofSection}
          aria-labelledby="signal-room-proof-title"
        >
          <div className={styles.proofIntro}>
            <div>
              <p className={styles.sectionLabel}>
                Interactive proof / example campaign
              </p>
              <h2 id="signal-room-proof-title">
                Inspect the signal before you trust the cut.
              </h2>
            </div>
            <p>
              Filter the pipeline, select a finding, and inspect the editorial
              reason behind the proposed edit.
            </p>
          </div>

          <div
            className={styles.stageRail}
            aria-label="Example ClipFactory workflow"
          >
            {["Brief", "Map", "Select", "Edit plan"].map((stage, index) => (
              <div className={styles.stage} key={stage}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{stage}</strong>
              </div>
            ))}
          </div>

          <div className={styles.workbench}>
            <div className={styles.signalColumn}>
              <div
                className={styles.filterBar}
                aria-label="Filter editorial signals"
              >
                {FILTERS.map((item) => (
                  <button
                    type="button"
                    key={item.value}
                    className={styles.filterButton}
                    aria-pressed={filter === item.value}
                    onClick={() => selectFilter(item.value)}
                  >
                    {item.label}
                    <span>
                      {item.value === "all"
                        ? SIGNALS.length
                        : SIGNALS.filter((signal) => signal.kind === item.value)
                            .length}
                    </span>
                  </button>
                ))}
              </div>

              <div className={styles.listHeader}>
                <span>Candidate signal</span>
                <span>Source</span>
              </div>

              <ul
                className={styles.signalList}
                aria-label="Editorial signal candidates"
              >
                {visibleSignals.map((signal) => {
                  const isSelected = signal.id === selected.id;
                  return (
                    <li key={signal.id}>
                      <button
                        type="button"
                        className={styles.signalButton}
                        data-selected={isSelected ? "true" : "false"}
                        data-kind={signal.kind}
                        aria-pressed={isSelected}
                        onClick={() => setSelectedId(signal.id)}
                      >
                        <span className={styles.signalIndex}>
                          {signal.index}
                        </span>
                        <span className={styles.signalBody}>
                          <span className={styles.signalMeta}>
                            <span>{signal.kindLabel}</span>
                            <i aria-hidden="true" />
                            <span>{signal.status}</span>
                          </span>
                          <strong>{signal.title}</strong>
                          <small>{signal.cue}</small>
                        </span>
                        <span className={styles.signalTime}>
                          {signal.sourceTime}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            <aside
              className={styles.inspector}
              data-kind={selected.kind}
              aria-live="polite"
              aria-label={`Inspector for ${selected.title}`}
            >
              <div className={styles.inspectorTopline}>
                <span>INSPECTOR / {selected.index}</span>
                <span>{KIND_LABELS[selected.kind]}</span>
              </div>

              <div className={styles.inspectorHeading}>
                <div>
                  <span className={styles.fieldLabel}>Selected finding</span>
                  <h3>{selected.title}</h3>
                </div>
                <span className={styles.inspectorStatus}>
                  {selected.status}
                </span>
              </div>

              <div
                className={styles.editTimeline}
                aria-label="Proposed clip segment order"
              >
                {selected.segments.map((segment) => (
                  <div
                    className={styles.editSegment}
                    key={`${selected.id}-${segment.label}`}
                    style={{ flexBasis: segment.width }}
                  >
                    <span>{segment.label}</span>
                    <strong>{segment.time}</strong>
                  </div>
                ))}
              </div>

              <div className={styles.inspectorBlock}>
                <span className={styles.fieldLabel}>Why it belongs</span>
                <p>{selected.reason}</p>
              </div>

              <div className={styles.inspectorBlock}>
                <span className={styles.fieldLabel}>Edit instruction</span>
                <p>{selected.instruction}</p>
              </div>

              <div className={styles.inspectorFooter}>
                <span>Source {selected.sourceTime}</span>
                <span>Bound to example campaign 014</span>
              </div>
            </aside>
          </div>
        </section>
      </main>
    </div>
  );
}
