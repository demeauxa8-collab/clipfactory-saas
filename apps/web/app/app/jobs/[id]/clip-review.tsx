"use client";

import { Film } from "lucide-react";
import { ProductStatus } from "@/components/product/product-primitives";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ClipActions } from "./clip-actions";
import { RenderedClipPlayer } from "./rendered-clip-player";
import styles from "./clip-review.module.css";

export type ClipSegment = {
  role: "setup" | "transition" | "payoff" | "single";
  start: number;
  end: number;
  transcript_excerpt?: string;
};

export type ClipReviewData = {
  id: string;
  idx: number;
  title: string | null;
  hook_text: string | null;
  rationale: string | null;
  visual_summary: string | null;
  transcript_excerpt: string | null;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
  rendered_duration_seconds: number | null;
  segments: ClipSegment[] | null;
  score_total: number | null;
  score_breakdown: Record<string, number> | null;
};

export function ClipReview({ clips }: { clips: ClipReviewData[] }) {
  return (
    <Tabs defaultValue={clips[0]?.id} className={styles.review}>
      <TabsList className={styles.browser} aria-label="Delivered clips">
        {clips.map((clip) => (
          <TabsTrigger key={clip.id} value={clip.id} className={styles.clipTab}>
            <span className={styles.tabIndex}>
              {String(clip.idx + 1).padStart(2, "0")}
            </span>
            <span className={styles.tabCopy}>
              <strong>{clip.title || `Cut ${clip.idx + 1}`}</strong>
              <small>
                {formatDuration(
                  clip.rendered_duration_seconds ?? clip.duration_seconds,
                )}
              </small>
            </span>
            <span className={styles.tabScore}>{clip.score_total ?? "—"}</span>
          </TabsTrigger>
        ))}
      </TabsList>

      <div className={styles.stage}>
        {clips.map((clip) => (
          <TabsContent key={clip.id} value={clip.id} className={styles.content}>
            <ClipStage clip={clip} />
          </TabsContent>
        ))}
      </div>
    </Tabs>
  );
}

function ClipStage({ clip }: { clip: ClipReviewData }) {
  const segments = clip.segments?.length
    ? clip.segments
    : [
        {
          role: "single" as const,
          start: clip.start_seconds,
          end: clip.end_seconds,
          transcript_excerpt: clip.transcript_excerpt ?? undefined,
        },
      ];
  const breakdown = Object.entries(clip.score_breakdown ?? {});
  const duration = clip.rendered_duration_seconds ?? clip.duration_seconds;

  return (
    <div className={styles.stageGrid}>
      <section
        className={styles.viewerColumn}
        aria-label={`Rendered clip for ${clip.title || `cut ${clip.idx + 1}`}`}
      >
        <div className={styles.viewerShell}>
          <RenderedClipPlayer
            clipId={clip.id}
            title={clip.title || `Cut ${clip.idx + 1}`}
          />
        </div>
      </section>

      <aside className={styles.inspector}>
        <div className={styles.inspectorHead}>
          <div>
            <ProductStatus tone="success">Words verified</ProductStatus>
            <p>Why this cut</p>
            <h3>{clip.title || `Cut ${clip.idx + 1}`}</h3>
          </div>
          <div className={styles.totalScore}>
            <span>Score</span>
            <strong>{clip.score_total ?? "—"}</strong>
          </div>
        </div>

        <p className={styles.rationale}>
          {clip.rationale ||
            "This cut was selected from transcript-anchored candidate moments that matched the campaign brief."}
        </p>
        {clip.visual_summary ? (
          <div className={styles.visualProof}>
            <Film aria-hidden="true" />
            <div>
              <span>Visual proof</span>
              <p>{clip.visual_summary}</p>
            </div>
          </div>
        ) : null}

        {breakdown.length ? (
          <dl className={styles.scores}>
            {breakdown.map(([key, value]) => {
              const normalized = Math.max(0, Math.min(1, Number(value) / 100));
              return (
                <div key={key}>
                  <div>
                    <dt>{shortLabel(key)}</dt>
                    <dd>{value}</dd>
                  </div>
                  <span aria-hidden="true">
                    <i style={{ transform: `scaleX(${normalized})` }} />
                  </span>
                </div>
              );
            })}
          </dl>
        ) : null}

        <ClipActions clipId={clip.id} />
      </aside>

      <section
        className={styles.timeline}
        aria-label="Source segments used in this cut"
      >
        <div className={styles.timelineHead}>
          <span>Source thread</span>
          <strong>{formatDuration(duration)} delivered cut</strong>
        </div>
        <ol className={styles.timelineTrack}>
          {segments.map((segment, index) => (
            <li
              key={`${segment.start}-${segment.end}-${index}`}
              style={{ flexGrow: Math.max(1, segment.end - segment.start) }}
              data-role={segment.role}
            >
              <span>{segment.role}</span>
              <strong>
                {formatTimestamp(segment.start)}–{formatTimestamp(segment.end)}
              </strong>
            </li>
          ))}
        </ol>
        <div className={styles.transcriptLine}>
          <span aria-hidden="true" />
          <p>
            {clip.transcript_excerpt ||
              segments
                .map((segment) => segment.transcript_excerpt)
                .filter(Boolean)
                .join(" ") ||
              "Transcript excerpt remains attached to these source timestamps."}
          </p>
        </div>
      </section>
    </div>
  );
}

function formatTimestamp(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function formatDuration(seconds: number) {
  return `${Number(seconds || 0).toFixed(1)}s`;
}

function shortLabel(key: string) {
  const labels: Record<string, string> = {
    hook: "Hook",
    emotion: "Emotion",
    visual: "Visual proof",
    campaign_fit: "Campaign fit",
    editing_difficulty: "Edit continuity",
    editing_continuity: "Edit continuity",
    payoff_strength: "Payoff",
    setup_clarity: "Setup",
    visual_proof: "Visual proof",
    retention: "Retention",
  };
  return labels[key] ?? key.replaceAll("_", " ");
}
