"use client";

import {
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  CirclePlay,
  Clock3,
  FileText,
  Link2,
  LoaderCircle,
} from "lucide-react";
import {
  AnimatePresence,
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import Image from "next/image";
import Link from "next/link";
import type { Route } from "next";
import * as React from "react";

import styles from "./edit-axis-story.module.css";
import { PricingSection } from "@/components/marketing/pricing-section";

export type EditAxisMoment = {
  id: string;
  label: string;
  atSeconds: number;
  score: number;
  frame: string;
  quote: string;
  reason: string;
  breakdown: readonly (readonly [string, number])[];
};

type ProductState = "analyzing" | "ready" | "empty" | "error";

const CAMPAIGNS = [
  {
    id: "launch",
    label: "Product launch",
    eyebrow: "Reveal the proof",
    audience: "Design teams",
    goal: "Conversion",
    tone: "Direct",
    avoid: "Founder biography",
    hook: "Show the result before the promise",
    momentIndex: 1,
  },
  {
    id: "founder",
    label: "Founder story",
    eyebrow: "Earn the tension",
    audience: "Early founders",
    goal: "Trust",
    tone: "Reflective",
    avoid: "Product jargon",
    hook: "Open on the constraint",
    momentIndex: 0,
  },
  {
    id: "authority",
    label: "Point of view",
    eyebrow: "Land the argument",
    audience: "Marketing leads",
    goal: "Authority",
    tone: "Decisive",
    avoid: "Generic advice",
    hook: "Resolve the opening idea",
    momentIndex: 2,
  },
] as const;

const WORKFLOW = [
  {
    id: "brief",
    label: "Aim the series",
    eyebrow: "Campaign brief",
    description:
      "Set the audience, goal, tone and boundaries before a single moment is ranked.",
  },
  {
    id: "map",
    label: "Map the source",
    eyebrow: "Whole-video context",
    description:
      "Read the conversation as a story, then surface moments that can work together.",
  },
  {
    id: "anchor",
    label: "Date the edit",
    eyebrow: "Transcript anchoring",
    description:
      "Candidate words are found in the transcript. Word timestamps define the actual cut.",
  },
  {
    id: "render",
    label: "Render the cut",
    eyebrow: "Vertical delivery",
    description:
      "Reframe each segment, retime captions on the final montage and keep the rationale attached.",
  },
] as const;

const FAQ = [
  {
    question: "Which sources can I use?",
    answer:
      "Starter currently accepts public or accessible YouTube and Vimeo URLs. Direct file upload is not part of the current offer.",
  },
  {
    question: "What does a score mean?",
    answer:
      "It ranks a moment for the campaign brief you supplied. It is a decision aid, not a promise that a clip will go viral.",
  },
  {
    question: "How many clips will I receive?",
    answer:
      "You can request up to three clips per job. Quality checks and deduplication can intentionally return fewer when the source does not support three distinct cuts.",
  },
  {
    question: "How do credits work?",
    answer:
      "Starter includes 300 credits per month for individual videos up to 30 minutes. Pro is planned at 79 euros per month with 1,000 credits and up to five YouTube sources per series, each up to 60 minutes. Pro subscriptions are not open yet.",
  },
  {
    question: "What is included in the export?",
    answer:
      "A vertical render with burned captions, the selected source segments, a campaign-fit rationale and a download without a watermark.",
  },
  {
    question: "What happens when processing fails?",
    answer:
      "A failed analysis is named explicitly and no delivery is implied. If no moment clears the quality floor, ClipFactory tells you instead of padding the result with a weak clip.",
  },
] as const;

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function Wordmark() {
  return (
    <span className={styles.wordmark}>
      <span className={styles.wordmarkIcon} aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      ClipFactory
    </span>
  );
}

function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={
        reduceMotion
          ? false
          : { opacity: 0, transform: "translate3d(0,30px,0)" }
      }
      whileInView={{ opacity: 1, transform: "translate3d(0,0,0)" }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{
        duration: reduceMotion ? 0 : 0.7,
        delay: reduceMotion ? 0 : delay,
        ease: [0.23, 1, 0.32, 1],
      }}
    >
      {children}
    </motion.div>
  );
}

function StoryAssembly({ moments }: { moments: readonly EditAxisMoment[] }) {
  const reduceMotion = useReducedMotion();
  const [activeIndex, setActiveIndex] = React.useState(1);
  const active = moments[activeIndex];

  return (
    <section
      id="story"
      className={styles.storySection}
      aria-labelledby="story-title"
    >
      <div className={styles.sectionIntro}>
        <Reveal className={styles.sectionTitle}>
          <p>Story assembly</p>
          <h2 id="story-title">
            Three distant moments.
            <br />
            One inevitable cut.
          </h2>
        </Reveal>
        <Reveal className={styles.sectionLead} delay={0.08}>
          <p>
            A timestamp is not a story role. ClipFactory connects tension, proof
            and payoff before it builds the vertical edit.
          </p>
          <span>Interactive product illustration</span>
        </Reveal>
      </div>

      <Reveal className={styles.assemblyShell} delay={0.04}>
        <div className={styles.assemblyToolbar}>
          <div>
            <span className={styles.statusDot} />
            Product launch
          </div>
          <div className={styles.assemblyMeta}>
            <span>18:42 source</span>
            <span>3 source locks</span>
            <span>Example analysis</span>
          </div>
        </div>

        <div className={styles.assemblyCanvas}>
          <div className={styles.sourceColumn}>
            <div className={styles.columnLabel}>
              <span>Source moments</span>
              <span>Ranked for this brief</span>
            </div>
            <div className={styles.sourceStack}>
              {moments.map((moment, index) => (
                <motion.button
                  key={moment.id}
                  type="button"
                  className={styles.sourceMoment}
                  data-active={activeIndex === index ? "" : undefined}
                  aria-pressed={activeIndex === index}
                  initial={
                    reduceMotion
                      ? false
                      : { opacity: 0, transform: "translateY(18px)" }
                  }
                  whileInView={{ opacity: 1, transform: "translateY(0)" }}
                  viewport={{ once: true, amount: 0.45 }}
                  transition={{
                    duration: reduceMotion ? 0 : 0.55,
                    delay: reduceMotion ? 0 : 0.08 + index * 0.07,
                    ease: [0.23, 1, 0.32, 1],
                  }}
                  onClick={() => setActiveIndex(index)}
                >
                  {activeIndex === index ? (
                    <motion.span
                      className={styles.sourceActive}
                      layoutId="v6-source-active"
                      transition={{
                        type: "spring",
                        stiffness: 430,
                        damping: 38,
                        mass: 0.72,
                      }}
                    />
                  ) : null}
                  <span className={styles.sourceThumb}>
                    <Image
                      src={moment.frame}
                      alt=""
                      fill
                      unoptimized
                      sizes="96px"
                    />
                  </span>
                  <span className={styles.sourceCopy}>
                    <small>{formatTime(moment.atSeconds)}</small>
                    <strong>{moment.label}</strong>
                    <span>{moment.quote}</span>
                  </span>
                  <span className={styles.sourceScore}>{moment.score}</span>
                </motion.button>
              ))}
            </div>
          </div>

          <div className={styles.assemblyBridge} aria-hidden="true">
            <svg viewBox="0 0 210 420" preserveAspectRatio="none">
              <path d="M0 74 C84 74 78 210 210 210" />
              <path d="M0 210 C84 210 92 210 210 210" />
              <path d="M0 346 C84 346 78 210 210 210" />
            </svg>
            <motion.span
              key={active.id}
              initial={
                reduceMotion ? false : { opacity: 0, transform: "scale(0.92)" }
              }
              animate={{ opacity: 1, transform: "scale(1)" }}
              transition={{
                type: "spring",
                stiffness: 430,
                damping: 34,
              }}
            >
              <Check />
            </motion.span>
          </div>

          <div className={styles.outputColumn}>
            <div className={styles.columnLabel}>
              <span>Vertical edit</span>
              <span>00:42</span>
            </div>
            <div className={styles.outputComposition}>
              <div className={styles.outputPhone}>
                <AnimatePresence initial={false} mode="popLayout">
                  <motion.div
                    key={active.id}
                    className={styles.outputImage}
                    initial={
                      reduceMotion
                        ? { opacity: 0 }
                        : {
                            opacity: 0,
                            transform: "scale(1.025) translate3d(0,8px,0)",
                          }
                    }
                    animate={{
                      opacity: 1,
                      transform: "scale(1) translate3d(0,0,0)",
                    }}
                    exit={{ opacity: 0 }}
                    transition={{
                      duration: reduceMotion ? 0.12 : 0.34,
                      ease: [0.23, 1, 0.32, 1],
                    }}
                  >
                    <Image
                      src={active.frame}
                      alt="Example vertical crop from the selected source moment"
                      fill
                      unoptimized
                      sizes="(max-width: 720px) 62vw, 290px"
                    />
                  </motion.div>
                </AnimatePresence>
                <div className={styles.outputShade} />
                <div className={styles.outputTopline}>
                  <span>9:16</span>
                  <span>{formatTime(active.atSeconds)}</span>
                </div>
                <AnimatePresence initial={false} mode="wait">
                  <motion.div
                    key={`${active.id}-caption`}
                    className={styles.outputCaption}
                    initial={{
                      opacity: 0,
                      transform: `translateY(${reduceMotion ? 0 : 8}px)`,
                    }}
                    animate={{ opacity: 1, transform: "translateY(0)" }}
                    exit={{
                      opacity: 0,
                      transform: `translateY(${reduceMotion ? 0 : -5}px)`,
                    }}
                    transition={{ duration: reduceMotion ? 0.1 : 0.2 }}
                  >
                    <strong>{active.quote}</strong>
                    <span>
                      <Check /> Source words located
                    </span>
                  </motion.div>
                </AnimatePresence>
              </div>

              <AnimatePresence initial={false} mode="wait">
                <motion.div
                  key={`${active.id}-reason`}
                  className={styles.decisionNote}
                  initial={
                    reduceMotion
                      ? { opacity: 0, transform: "translateX(0)" }
                      : {
                          opacity: 0,
                          transform: "translateX(10px)",
                          filter: "blur(3px)",
                        }
                  }
                  animate={{
                    opacity: 1,
                    transform: "translateX(0)",
                    filter: "blur(0px)",
                  }}
                  exit={{
                    opacity: 0,
                    transform: `translateX(${reduceMotion ? 0 : -6}px)`,
                    filter: "blur(3px)",
                  }}
                  transition={{ duration: reduceMotion ? 0.1 : 0.24 }}
                >
                  <span>{String(activeIndex + 1).padStart(2, "0")} / 03</span>
                  <small>Why it stays</small>
                  <strong>{active.label}</strong>
                  <p>{active.reason}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div id="assembly-track" className={styles.assemblyTrack}>
          <div className={styles.trackLabel}>
            <span>ASSEMBLY</span>
            <span>Source-grounded cut</span>
          </div>
          <div className={styles.trackSegments}>
            {moments.map((moment, index) => (
              <button
                key={moment.id}
                type="button"
                data-active={activeIndex === index ? "" : undefined}
                onClick={() => setActiveIndex(index)}
              >
                <span
                  style={{
                    backgroundImage: `url(${moment.frame})`,
                  }}
                />
                <small>{moment.label}</small>
              </button>
            ))}
            <div
              className={styles.trackPlayhead}
              aria-hidden="true"
              style={{
                transform: `translate3d(${16 + activeIndex * 34}%, 0, 0)`,
              }}
            >
              <span />
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function CampaignSection({ moments }: { moments: readonly EditAxisMoment[] }) {
  const reduceMotion = useReducedMotion();
  const [campaignIndex, setCampaignIndex] = React.useState(0);
  const campaign = CAMPAIGNS[campaignIndex];
  const moment = moments[campaign.momentIndex];

  return (
    <section
      id="campaign-v6"
      className={styles.campaignSection}
      aria-labelledby="campaign-title"
    >
      <div className={styles.campaignHeading}>
        <Reveal>
          <p>Campaign intelligence</p>
          <h2 id="campaign-title">
            Same source.
            <br />
            Different campaign.
          </h2>
        </Reveal>
        <Reveal delay={0.07}>
          <p>
            Change the audience or goal and the ranking changes with it. The
            brief is part of the edit, not a note added afterwards.
          </p>
        </Reveal>
      </div>

      <Reveal className={styles.campaignInstrument}>
        <div className={styles.campaignRail}>
          <span>Choose the campaign</span>
          {CAMPAIGNS.map((item, index) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={campaignIndex === index}
              data-active={campaignIndex === index ? "" : undefined}
              onClick={() => setCampaignIndex(index)}
            >
              {campaignIndex === index ? (
                <motion.i
                  layoutId="v6-campaign-active"
                  transition={{
                    type: "spring",
                    stiffness: 420,
                    damping: 38,
                  }}
                />
              ) : null}
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item.label}</strong>
              <small>{item.eyebrow}</small>
              <ArrowRight />
            </button>
          ))}
        </div>

        <div className={styles.briefSheet}>
          <div className={styles.briefHeader}>
            <span>Campaign brief</span>
            <span>Live input</span>
          </div>
          <AnimatePresence initial={false} mode="wait">
            <motion.div
              key={campaign.id}
              className={styles.briefFields}
              initial={{
                opacity: 0,
                transform: `translateY(${reduceMotion ? 0 : 9}px)`,
              }}
              animate={{ opacity: 1, transform: "translateY(0)" }}
              exit={{
                opacity: 0,
                transform: `translateY(${reduceMotion ? 0 : -6}px)`,
              }}
              transition={{ duration: reduceMotion ? 0.1 : 0.22 }}
            >
              {[
                ["Audience", campaign.audience],
                ["Goal", campaign.goal],
                ["Tone", campaign.tone],
                ["Avoid", campaign.avoid],
                ["Example hook", campaign.hook],
              ].map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </motion.div>
          </AnimatePresence>
          <div className={styles.briefFooter}>
            <Check /> Ranking uses this brief
          </div>
        </div>

        <div className={styles.rankedOutput}>
          <div className={styles.rankedHeader}>
            <span>Top story role</span>
            <span>Example</span>
          </div>
          <div className={styles.rankedMedia}>
            <AnimatePresence initial={false} mode="popLayout">
              <motion.div
                key={campaign.id}
                initial={{
                  opacity: 0,
                  transform: `scale(${reduceMotion ? 1 : 1.035})`,
                }}
                animate={{ opacity: 1, transform: "scale(1)" }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduceMotion ? 0.1 : 0.3 }}
              >
                <Image
                  src={moment.frame}
                  alt="Example source frame selected for the active campaign"
                  fill
                  unoptimized
                  sizes="(max-width: 900px) 80vw, 320px"
                />
              </motion.div>
            </AnimatePresence>
            <div className={styles.rankedShade} />
            <AnimatePresence initial={false} mode="wait">
              <motion.div
                key={`${campaign.id}-copy`}
                className={styles.rankedCopy}
                initial={{
                  opacity: 0,
                  transform: `translateY(${reduceMotion ? 0 : 10}px)`,
                }}
                animate={{ opacity: 1, transform: "translateY(0)" }}
                exit={{
                  opacity: 0,
                  transform: `translateY(${reduceMotion ? 0 : -5}px)`,
                }}
                transition={{ duration: reduceMotion ? 0.1 : 0.22 }}
              >
                <small>{formatTime(moment.atSeconds)}</small>
                <strong>{moment.label}</strong>
                <p>{moment.quote}</p>
              </motion.div>
            </AnimatePresence>
          </div>
          <div className={styles.rankedReason}>
            <span>Campaign fit</span>
            <p>{campaign.eyebrow}. The source stays the same.</p>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function WorkflowVisual({
  index,
  moments,
}: {
  index: number;
  moments: readonly EditAxisMoment[];
}) {
  const activeMoment = moments[Math.min(index, moments.length - 1)];

  if (index === 0) {
    return (
      <div className={styles.visualBrief}>
        <div>
          <span>Audience</span>
          <strong>Design teams</strong>
        </div>
        <div>
          <span>Goal</span>
          <strong>Product launch</strong>
        </div>
        <div>
          <span>Tone</span>
          <strong>Direct, evidence first</strong>
        </div>
        <div className={styles.visualPrompt}>
          Find moments where the result is visible before the claim.
          <span>Campaign brief ready</span>
        </div>
      </div>
    );
  }

  if (index === 1) {
    return (
      <div className={styles.visualMap}>
        <div className={styles.mapFilmstrip}>
          {moments.map((moment, momentIndex) => (
            <span key={moment.id}>
              <Image src={moment.frame} alt="" fill unoptimized sizes="150px" />
              <i>{String(momentIndex + 1).padStart(2, "0")}</i>
            </span>
          ))}
        </div>
        <div className={styles.mapTimeline}>
          <span />
          {moments.map((moment) => (
            <i
              key={moment.id}
              style={{ left: `${(moment.atSeconds / (18 * 60 + 42)) * 100}%` }}
            />
          ))}
        </div>
        <div className={styles.mapLegend}>
          <span>00:00</span>
          <strong>Story roles connected across 18:42</strong>
          <span>18:42</span>
        </div>
      </div>
    );
  }

  if (index === 2) {
    return (
      <div className={styles.visualTranscript}>
        <div className={styles.transcriptHeader}>
          <FileText />
          <span>Transcript with word timing</span>
          <small>09:31.840</small>
        </div>
        <p>
          We kept looking for the promise, but{" "}
          <mark>the proof arrives before</mark>
          <mark> the promise</mark> when the product is already on screen.
        </p>
        <div className={styles.wordTimes}>
          <span>proof 09:31.920</span>
          <span>arrives 09:32.180</span>
          <span>before 09:32.490</span>
          <span>promise 09:32.830</span>
        </div>
        <div className={styles.anchorResult}>
          <Check /> Candidate located. Cut boundaries use transcript time.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.visualRender}>
      <div className={styles.renderPhone}>
        <Image
          src={activeMoment.frame}
          alt="Example vertical rendered clip"
          fill
          unoptimized
          sizes="230px"
        />
        <div className={styles.renderShade} />
        <strong>{activeMoment.quote}</strong>
      </div>
      <div className={styles.renderDetails}>
        <span>Ready to download</span>
        <strong>clipfactory-proof-01.mp4</strong>
        <div>
          <span>1080 × 1920</span>
          <span>Burned captions</span>
          <span>No watermark</span>
        </div>
        <button type="button">
          Download example <ArrowUpRight />
        </button>
      </div>
    </div>
  );
}

function WorkflowItem({
  item,
  index,
  setActiveIndex,
}: {
  item: (typeof WORKFLOW)[number];
  index: number;
  setActiveIndex: React.Dispatch<React.SetStateAction<number>>;
}) {
  const ref = React.useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 78%", "end 30%"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [24, -18]);

  useMotionValueEvent(scrollYProgress, "change", (progress) => {
    if (progress > 0.28 && progress < 0.82) {
      setActiveIndex((current) => (current === index ? current : index));
    }
  });

  return (
    <motion.article
      ref={ref}
      className={styles.workflowItem}
      style={
        reduceMotion
          ? undefined
          : {
              y,
            }
      }
      data-workflow-index={index}
    >
      <span>{String(index + 1).padStart(2, "0")}</span>
      <div>
        <small>{item.eyebrow}</small>
        <h3>{item.label}</h3>
        <p>{item.description}</p>
      </div>
    </motion.article>
  );
}

function WorkflowSection({ moments }: { moments: readonly EditAxisMoment[] }) {
  const reduceMotion = useReducedMotion();
  const [activeIndex, setActiveIndex] = React.useState(0);

  return (
    <section
      id="workflow"
      className={styles.workflowSection}
      aria-labelledby="workflow-title"
    >
      <div className={styles.workflowHeading}>
        <p>How it works</p>
        <h2 id="workflow-title">From source to a cut you can explain.</h2>
        <p>
          The model chooses candidate words. The transcript dates the edit. The
          final montage is checked again after every adjustment.
        </p>
      </div>

      <div className={styles.workflowDesktop}>
        <div className={styles.workflowSticky}>
          <div className={styles.workflowChrome}>
            <div>
              <span className={styles.statusDot} />
              Interview_master.mov
            </div>
            <span>{WORKFLOW[activeIndex].eyebrow}</span>
          </div>
          <AnimatePresence initial={false} mode="wait">
            <motion.div
              key={WORKFLOW[activeIndex].id}
              className={styles.workflowViewport}
              initial={
                reduceMotion
                  ? { opacity: 0, transform: "translateY(0)" }
                  : {
                      opacity: 0,
                      transform: "translateY(16px)",
                      filter: "blur(4px)",
                    }
              }
              animate={{
                opacity: 1,
                transform: "translateY(0)",
                filter: "blur(0px)",
              }}
              exit={
                reduceMotion
                  ? { opacity: 0, transform: "translateY(0)" }
                  : {
                      opacity: 0,
                      transform: "translateY(-10px)",
                      filter: "blur(4px)",
                    }
              }
              transition={{
                duration: reduceMotion ? 0.1 : 0.34,
                ease: [0.23, 1, 0.32, 1],
              }}
            >
              <WorkflowVisual index={activeIndex} moments={moments} />
            </motion.div>
          </AnimatePresence>
          <div className={styles.workflowProgress}>
            {WORKFLOW.map((item, index) => (
              <span
                key={item.id}
                aria-hidden="true"
                data-active={activeIndex === index ? "" : undefined}
              />
            ))}
          </div>
        </div>

        <div className={styles.workflowCopy}>
          {WORKFLOW.map((item, index) => (
            <WorkflowItem
              key={item.id}
              item={item}
              index={index}
              setActiveIndex={setActiveIndex}
            />
          ))}
        </div>
      </div>

      <div className={styles.workflowMobile}>
        {WORKFLOW.map((item, index) => (
          <article key={item.id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <small>{item.eyebrow}</small>
            <h3>{item.label}</h3>
            <p>{item.description}</p>
            <div className={styles.mobileWorkflowVisual}>
              <WorkflowVisual index={index} moments={moments} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function StateContent({
  state,
  resultHref,
  briefHref,
  sourceHref,
}: {
  state: ProductState;
  resultHref: Route;
  briefHref: Route;
  sourceHref: Route;
}) {
  if (state === "analyzing") {
    return (
      <div className={styles.stateContent} data-state="analyzing">
        <LoaderCircle />
        <div>
          <small>Whole-video context</small>
          <strong>Reading the source before ranking moments</strong>
          <p>
            Transcript, story structure and visual evidence stay in one job.
          </p>
        </div>
        <div
          className={styles.stateProgress}
          aria-label="Example progress: 62%"
        >
          <motion.span
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 0.62 }}
            transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
          />
        </div>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className={styles.stateContent} data-state="empty">
        <CirclePlay />
        <div>
          <small>No qualifying moment</small>
          <strong>The source stays. The weak cut does not ship.</strong>
          <p>Adjust the brief or try a source with clearer evidence.</p>
        </div>
        <Link href={briefHref}>Build another brief</Link>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className={styles.stateContent} data-state="error">
        <AlertCircle />
        <div>
          <small>Audio could not be read</small>
          <strong>Your source remains attached to the campaign.</strong>
          <p>
            Return to the source step to replace the URL or start a new
            analysis.
          </p>
        </div>
        <div className={styles.stateButtons}>
          <Link href={sourceHref}>
            <Link2 /> Back to source
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.stateContent} data-state="ready">
      <Check />
      <div>
        <small>Quality checks passed</small>
        <strong>Three distinct cuts are ready to review</strong>
        <p>Source segments, rationale and captions travel with each render.</p>
      </div>
      <Link href={resultHref}>
        Open results <ArrowUpRight />
      </Link>
    </div>
  );
}

function ReliabilitySection({
  resultHref,
  briefHref,
  sourceHref,
}: {
  resultHref: Route;
  briefHref: Route;
  sourceHref: Route;
}) {
  const reduceMotion = useReducedMotion();
  const [state, setState] = React.useState<ProductState>("ready");

  return (
    <section
      id="reliability"
      className={styles.reliabilitySection}
      aria-labelledby="strict-title"
    >
      <div className={styles.strictStatement}>
        <Reveal>
          <p>Failure-aware by design</p>
          <h2 id="strict-title">Quietly strict where it matters.</h2>
        </Reveal>
        <Reveal delay={0.08}>
          <p>
            Good automation knows when to stop. Weak evidence becomes a clear
            state, not a confident-looking clip.
          </p>
        </Reveal>
      </div>

      <Reveal className={styles.stateConsole}>
        <div
          className={styles.stateRail}
          role="group"
          aria-label="Product state examples"
        >
          {(
            [
              ["analyzing", "Analyzing"],
              ["ready", "Ready"],
              ["empty", "No match"],
              ["error", "Error"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={state === value}
              data-active={state === value ? "" : undefined}
              onClick={() => setState(value)}
            >
              {state === value ? (
                <motion.i
                  layoutId="v6-state-active"
                  transition={{
                    type: "spring",
                    stiffness: 430,
                    damping: 40,
                  }}
                />
              ) : null}
              <span />
              {label}
            </button>
          ))}
        </div>
        <div className={styles.stateViewport} aria-live="polite">
          <AnimatePresence initial={false} mode="wait">
            <motion.div
              key={state}
              initial={{
                opacity: 0,
                transform: `translateY(${reduceMotion ? 0 : 8}px)`,
              }}
              animate={{ opacity: 1, transform: "translateY(0)" }}
              exit={{
                opacity: 0,
                transform: `translateY(${reduceMotion ? 0 : -6}px)`,
              }}
              transition={{ duration: reduceMotion ? 0.1 : 0.2 }}
            >
              <StateContent
                state={state}
                resultHref={resultHref}
                briefHref={briefHref}
                sourceHref={sourceHref}
              />
            </motion.div>
          </AnimatePresence>
        </div>
        <div className={styles.consoleFooter}>
          <span>Example product states</span>
          <span>Nothing weak is padded into the delivery</span>
        </div>
      </Reveal>
    </section>
  );
}


function FaqSection() {
  const [openIndex, setOpenIndex] = React.useState<number | null>(0);

  return (
    <section
      id="faq-v6"
      className={styles.faqSection}
      aria-labelledby="faq-title-v6"
    >
      <div className={styles.faqHeading}>
        <p>Questions</p>
        <h2 id="faq-title-v6">Answers, without the fine print maze.</h2>
      </div>
      <div className={styles.faqList}>
        {FAQ.map((item, index) => (
          <details
            key={item.question}
            name="clipfactory-faq"
            open={openIndex === index}
            onToggle={(event) => {
              const isOpen = event.currentTarget.open;
              setOpenIndex((current) =>
                isOpen ? index : current === index ? null : current,
              );
            }}
          >
            <summary>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item.question}</strong>
              <ChevronDown />
            </summary>
            <p>{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function ClosingSection({
  startHref,
  signInHref,
}: {
  startHref: Route;
  signInHref: Route;
}) {
  return (
    <>
      <section
        id="closing-v6"
        className={styles.closingSection}
        aria-labelledby="closing-title-v6"
      >
        <div className={styles.closingTexture} aria-hidden="true" />
        <div className={styles.closingCopy}>
          <span>ClipFactory for campaign-led editing</span>
          <h2 id="closing-title-v6">Make the cut you can defend.</h2>
        </div>
        <div className={styles.closingAction}>
          <p>
            <strong>€29</strong>
            <span>per month</span>
          </p>
          <Link href={startHref}>
            Build your first clip <ArrowUpRight />
          </Link>
          <small>YouTube or Vimeo. No watermark.</small>
        </div>
      </section>

      <footer className={styles.footer}>
        <Link href="/" aria-label="ClipFactory home">
          <Wordmark />
        </Link>
        <div className={styles.footerNav}>
          <div>
            <span>Product</span>
            <a href="#story">How it works</a>
            <a href="#campaign-v6">Features</a>
            <a href="#pricing">Pricing</a>
          </div>
          <div>
            <span>Support</span>
            <a href="#faq-v6">FAQ</a>
            <Link href="/about">About</Link>
            <Link href={signInHref}>Sign in</Link>
          </div>
          <div>
            <span>Legal</span>
            <Link href="/legal/terms">Terms</Link>
            <Link href="/legal/privacy">Privacy</Link>
          </div>
        </div>
        <div className={styles.footerNote}>
          <Clock3 />
          <span>The whole story, kept in sync.</span>
          <small>© {new Date().getFullYear()} ClipFactory</small>
        </div>
      </footer>
    </>
  );
}

export function EditAxisStory({
  moments,
  startHref,
  signInHref,
}: {
  moments: readonly EditAxisMoment[];
  startHref: Route;
  signInHref: Route;
}) {
  const briefHref = (
    startHref.toString().startsWith("/preview/")
      ? "/preview/journey?screen=brief"
      : startHref
  ) as Route;
  const sourceHref = (
    startHref.toString().startsWith("/preview/")
      ? "/preview/journey?screen=source"
      : "/login?next=/app"
  ) as Route;
  const resultHref = (
    startHref.toString().startsWith("/preview/")
      ? "/preview/journey?screen=result"
      : "/login?next=/app"
  ) as Route;

  return (
    <div className={styles.rest}>
      <StoryAssembly moments={moments} />
      <CampaignSection moments={moments} />
      <WorkflowSection moments={moments} />
      <ReliabilitySection
        resultHref={resultHref}
        briefHref={briefHref}
        sourceHref={sourceHref}
      />
      <PricingSection startHref={startHref} />
      <FaqSection />
      <ClosingSection startHref={startHref} signInHref={signInHref} />
    </div>
  );
}
