import Link from "next/link";
import { Container } from "@/components/ui/container";
import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";
import { BreadcrumbJsonLd } from "@/components/marketing/json-ld";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata("/vs/opusclip");

const COMPARISON = [
  {
    topic: "Starting point",
    clipfactory:
      "A saved campaign brief: audience, objective, tone and topics to avoid.",
    opus: "AI clipping with prompts to find specific moments using ClipBasic or ClipAnything.",
    source: "https://help.opus.pro/docs/article/select-keywords",
  },
  {
    topic: "Visual context",
    clipfactory:
      "Visual checks complement the transcript when selecting and reviewing a candidate.",
    opus: "ClipAnything uses visual, audio and sentiment cues to find moments.",
    source: "https://www.opus.pro/clipanything",
  },
  {
    topic: "Editing and publishing",
    clipfactory:
      "Review captioned vertical renders, source timestamps and editorial reasons, then download. Publishing and scheduling are manual in the current pilot.",
    opus: "Its published editor includes caption editing, layouts, reframing and AI B-roll, with publishing and scheduling tools.",
    source: "https://www.opus.pro/ai-video-editor",
  },
];

export default function VsOpusClipPage() {
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: "Home", href: "/" },
          { name: "ClipFactory vs OpusClip", href: "/vs/opusclip" },
        ]}
      />
      <MarketingNav />
      <main id="main-content" className="marketing-page flex-1">
        <Container className="max-w-5xl py-20">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
            Workflow comparison
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight md:text-5xl">
            ClipFactory vs OpusClip
          </h1>
          <p className="mt-6 max-w-3xl text-lg leading-relaxed text-[var(--color-muted-foreground)]">
            Choosing an AI clipping tool starts with the work you need to
            finish. ClipFactory is a pilot built around campaign briefs and
            source-based editorial review. OpusClip describes a broader
            clipping, editing and publishing workflow.
          </p>
          <p className="mt-4 text-sm text-[var(--color-muted-foreground)]">
            Reviewed 6 September 2026. This comparison uses our current pilot
            scope and the linked OpusClip product documentation. It is not a
            performance benchmark. ClipFactory is independent of OpusClip.
          </p>
          <section className="mt-12" aria-labelledby="workflow-comparison">
            <h2 id="workflow-comparison" className="text-2xl font-semibold">
              Compare the workflow you will actually use
            </h2>
            <div
              className="mt-6 overflow-x-auto rounded-xl border border-[var(--color-border)]"
              role="region"
              aria-label="Workflow comparison table"
              tabIndex={0}
            >
              <table className="w-full min-w-[40rem] text-left text-sm leading-relaxed">
                <caption className="sr-only">
                  ClipFactory pilot compared with OpusClip's documented workflow
                </caption>
                <thead className="bg-[var(--color-muted)]">
                  <tr>
                    <th scope="col" className="p-5">
                      Area
                    </th>
                    <th scope="col" className="p-5">
                      ClipFactory
                    </th>
                    <th scope="col" className="p-5">
                      OpusClip
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON.map((row) => (
                    <tr
                      key={row.topic}
                      className="border-t border-[var(--color-border)]"
                    >
                      <th scope="row" className="p-5 align-top font-medium">
                        {row.topic}
                      </th>
                      <td className="p-5 align-top text-[var(--color-muted-foreground)]">
                        {row.clipfactory}
                      </td>
                      <td className="p-5 align-top text-[var(--color-muted-foreground)]">
                        {row.opus}{" "}
                        <a
                          className="text-[var(--color-foreground)] underline underline-offset-4"
                          href={row.source}
                        >
                          Source: OpusClip
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="mt-12 max-w-3xl">
            <h2 className="text-2xl font-semibold">
              When to evaluate ClipFactory
            </h2>
            <p className="mt-5 leading-relaxed text-[var(--color-muted-foreground)]">
              Consider the pilot if you want to keep a campaign brief attached
              to each source and review why a small set of moments was chosen.
              Starter accepts accessible YouTube and Vimeo URLs up to 30
              minutes, with up to three requested clips per job. Quality checks
              can return fewer clips.
            </p>
            <p className="mt-5 leading-relaxed text-[var(--color-muted-foreground)]">
              The current offer does not include direct file upload, team
              workspaces, AI B-roll or automatic social publishing. Check the{" "}
              <Link
                className="text-[var(--color-foreground)] underline underline-offset-4"
                href="/faq"
              >
                pilot FAQ
              </Link>{" "}
              and{" "}
              <Link
                className="text-[var(--color-foreground)] underline underline-offset-4"
                href="/pricing"
              >
                pricing
              </Link>{" "}
              before choosing it for a client workflow.
            </p>
          </section>
          <section className="mt-12 max-w-3xl">
            <h2 className="text-2xl font-semibold">
              When to evaluate OpusClip
            </h2>
            <p className="mt-5 leading-relaxed text-[var(--color-muted-foreground)]">
              Include OpusClip in your evaluation if you need the editing and
              publishing tools described in its product documentation. Feature
              access and source limits can depend on the current plan. Review
              the vendor's live offer rather than assuming that every feature is
              included in every subscription.
            </p>
            <p className="mt-5 leading-relaxed text-[var(--color-muted-foreground)]">
              Visual understanding is not an exclusive ClipFactory feature:
              OpusClip also describes multimodal clipping. Your own source
              footage and review requirements are more useful evaluation
              criteria than a generic claim that one tool produces better clips.
            </p>
          </section>
          <section className="mt-12 max-w-3xl">
            <h2 className="text-2xl font-semibold">
              Run the same editorial test in both tools
            </h2>
            <ol className="mt-6 list-decimal space-y-4 pl-5 leading-relaxed text-[var(--color-muted-foreground)]">
              <li>
                Choose one source you can review against the original recording.
              </li>
              <li>
                Write the same audience, objective and topic boundaries for both
                workflows.
              </li>
              <li>
                Check whether each clip makes sense without the full episode and
                preserves the speaker's meaning.
              </li>
              <li>
                Inspect captions, speaker changes, vertical framing and the
                final ending.
              </li>
              <li>
                Record how many clips you would publish and how much manual
                correction they need.
              </li>
            </ol>
            <p className="mt-6 leading-relaxed text-[var(--color-muted-foreground)]">
              This is an evaluation method, not a claim that we have run a
              comparative benchmark. A selection score does not guarantee views
              or campaign results.
            </p>
            <p className="mt-8">
              <Link
                className="font-medium underline underline-offset-4"
                href="/guides/video-clipping-campaign-brief"
              >
                Write your evaluation brief →
              </Link>
            </p>
          </section>
        </Container>
      </main>
      <MarketingFooter />
    </>
  );
}
