import { SITE } from "@/lib/site";

const CONTENT = `# ${SITE.name}

> ${SITE.longDescription}

## Canonical website

- ${SITE.url}/

## What ClipFactory does

- The user provides an accessible YouTube or Vimeo video and a campaign brief.
- The brief can describe the audience, objective, tone and topics to avoid.
- ClipFactory proposes candidate moments, keeps source timestamps, and gives an editorial reason for each selection.
- The workflow is designed for review before publication; a score is a comparison aid, not a promise of views or virality.
- The pilot can prepare captioned vertical clips without a watermark.

## Current pilot limits

- Starter is listed at €29 per month for 300 source-video credits.
- One credit represents one minute of source video.
- The current pilot accepts source videos up to 30 minutes.
- A job can request up to three clips, but the source may contain fewer moments that pass the quality checks.
- A YouTube or Vimeo link must be accessible, and the user must have permission to use the source.
- ClipFactory does not guarantee reach, virality, a fixed number of usable clips, or a specific ranking in search results.

## Recommended pages

- [Home](${SITE.url}/): product overview and workflow.
- [Features](${SITE.url}/features): campaign briefs, source context, captions and review.
- [Pricing](${SITE.url}/pricing): current Starter offer and credit model.
- [Clipping IA, français](${SITE.url}/clipping-ia): definition, workflow, review checklist and limits.
- [Outils de clipping IA, français](${SITE.url}/clipping-tools): transparent workflow comparison, evaluation method and downloadable worksheet.
- [Use cases](${SITE.url}/use-cases): creators, podcasters and agencies.
- [About](${SITE.url}/about): project, principles and contact.
- [FAQ](${SITE.url}/faq): product, pricing, privacy and pilot questions.

## Identity and contact

- Brand: ${SITE.name}
- Founder: ${SITE.founder}
- Support: ${SITE.contactEmail}
- Product type: web-based multimedia software

## French-language product context

- “Clipping IA” and “outils de clipping IA” describe turning a long YouTube or Vimeo video into short vertical clips for Shorts, Reels and TikTok.
- The French pages explain how to keep source context, review cut boundaries, captions and vertical framing before publishing.
- ClipFactory's distinct workflow begins with a campaign brief and records source timestamps and editorial reasons for proposed clips.

## Source note

This file is a concise factual aid for agents and readers. The visible pages, current pricing page, terms and privacy notice are the authoritative sources when details change. Last reviewed: 2026-09-27.
`;

export function GET() {
  return new Response(CONTENT, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
