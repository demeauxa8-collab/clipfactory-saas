export type Guide = {
  slug: string;
  title: string;
  description: string;
  updatedAt: string;
  category: string;
  intro: string;
  sections: { title: string; paragraphs: string[]; checklist?: string[] }[];
  related: { label: string; href: string }[];
};

export const GUIDES: Guide[] = [
  {
    slug: "youtube-video-to-shorts",
    title: "How to turn a YouTube video into Shorts",
    description:
      "A practical workflow for choosing complete moments from a long YouTube video, checking the vertical crop, reviewing captions and preparing a short clip series.",
    updatedAt: "2026-09-06",
    category: "Source to short",
    intro:
      "Start with a moment that makes sense to someone who has never seen your channel. A useful Short answers one question or delivers one complete idea. The job is to keep that idea intact as you shorten the source and change the frame.",
    sections: [
      {
        title: "Choose the audience before the timestamp",
        paragraphs: [
          "Write down who should watch the clip and what they should understand by the end. An interview about starting a business could produce a lesson for first-time founders, a product demonstration for buyers or a story about a difficult decision. Those are different briefs, even when the source is the same.",
          "For example: ‘Help first-time founders understand why the first launch failed. Keep the tone direct. Show the specific mistake and what changed. Leave out fundraising advice.’ This gives you a way to reject an entertaining moment that does not serve the series.",
        ],
      },
      {
        title: "Find a beginning and an ending that belong together",
        paragraphs: [
          "Look for a concrete question, an unexpected observation or a visible action. Then find the sentence or image that resolves it. Read the candidate excerpt without the previous minute: pronouns such as ‘this’ and ‘they’ often reveal missing context.",
          "A continuous excerpt is easiest to review. If the explanation and its supporting example are separated, a multi-moment edit may help, provided that the connection preserves what the speaker meant. Do not join a question to an unrelated answer just because the result sounds more dramatic.",
        ],
      },
      {
        title: "Check the image before you commit to a vertical cut",
        paragraphs: [
          "A strong transcript is only half the decision. Inspect what the audience needs to see: a second speaker, a slide, a product or a hand gesture. A vertical crop can remove the very detail that makes the statement convincing.",
          "Watch each candidate on a phone-sized screen. If a key demonstration becomes unreadable, choose another moment or finish that section in an editor that can preserve the wider view. Treat automatic framing as something to review.",
        ],
      },
      {
        title: "Review captions against the source",
        paragraphs: [
          "Listen to the clip while reading every caption. Pay particular attention to names, numbers, technical terms and negation. A missed ‘not’ can reverse the meaning even when the rest of the text looks correct.",
          "Check the final edit, not only the transcript. When source moments are joined, the captions need to follow the new sequence. Leave enough space around the text for the platform interface and make sure it does not cover the face or demonstration.",
        ],
      },
      {
        title: "Use ClipFactory for candidate selection and review",
        paragraphs: [
          "In the ClipFactory pilot, create a campaign brief and provide an accessible YouTube or Vimeo URL. Starter supports sources up to 30 minutes and lets you request up to three clips per job. The selection process can return fewer clips when the source does not support enough distinct, verified moments.",
          "Review the delivered preview, selected source timestamps and explanation before downloading. A selection score helps compare candidates for your brief; it does not predict views. Publishing and scheduling remain manual in the current offer.",
        ],
      },
      {
        title: "Give every clip one final editorial check",
        paragraphs: [
          "Before posting, watch the short once with sound and once without. Keep the clip only if the opening is understandable, the ending delivers what the opening promises, and the image and captions support the same idea.",
        ],
        checklist: [
          "The first sentence makes sense without the original episode.",
          "The edit preserves the speaker's meaning.",
          "The vertical frame retains the essential visual evidence.",
          "Names, numbers and caption timing have been checked.",
          "The clip has a distinct purpose within the series.",
        ],
      },
    ],
    related: [
      { label: "Clipping for creators", href: "/use-cases/creators" },
      {
        label: "Write a campaign brief",
        href: "/guides/video-clipping-campaign-brief",
      },
      { label: "Source limits and pricing", href: "/pricing" },
    ],
  },
  {
    slug: "podcast-clips-for-social-media",
    title: "How to choose podcast clips for social media",
    description:
      "Build a podcast clip series with distinct ideas, enough context and a clear ending. Use a practical selection checklist for interviews and video podcasts.",
    updatedAt: "2026-09-06",
    category: "Editorial selection",
    intro:
      "An episode can contain several useful short clips without every clip repeating its biggest quote. Plan a small series in which each moment does a different job: introduce a problem, show an example or explain a decision.",
    sections: [
      {
        title: "Build a short list around complete ideas",
        paragraphs: [
          "While reviewing the episode, note candidate questions and answers rather than collecting isolated punchlines. A listener arriving from a feed needs enough context to understand who is speaking, what is at stake and why the answer matters.",
          "For a founder interview, one candidate might explain an early mistake, another might demonstrate the workaround, and a third might challenge a common assumption. Label them by the idea they deliver. If two labels say essentially the same thing, you probably have duplicates.",
        ],
      },
      {
        title: "Use the question when the answer needs it",
        paragraphs: [
          "Some answers are self-contained. Others begin with ‘exactly’, ‘because of that’ or ‘three years later’. Removing the question can make the clip shorter while making it harder to understand. Keep a brief piece of the question or select a different opening from the answer.",
          "Read the first two sentences to someone unfamiliar with the episode. If you need to explain the missing premise, the opening still needs work. Do not repair it with an invented quote or a caption that changes the guest's position.",
        ],
      },
      {
        title: "Distinguish tension from exaggeration",
        paragraphs: [
          "A useful opening can be specific without being sensational. ‘We lost our first customer after the handover’ creates a question the rest of the clip can answer. A title claiming the whole business collapsed would introduce a claim the source may not support.",
          "Keep uncertainty and qualifications when they change the meaning. ‘This helped in our test’ is different from ‘this works for everyone’. The strongest candidate is one whose evidence survives the shorter edit.",
        ],
      },
      {
        title: "Watch speaker changes and reactions",
        paragraphs: [
          "A two-person video podcast can switch between close-ups, a wide shot and the listener's reaction. Check whether the proposed vertical crop keeps the active speaker visible. A reaction can support the story, but a random reaction shot can create a misleading impression.",
          "Keep a deliberate ending: a resolved example, a clear takeaway or a completed answer. If the source ends mid-thought, extend the candidate or reject it. Avoid filling a target duration with unrelated material.",
        ],
      },
      {
        title: "Turn your candidates into a coherent series",
        paragraphs: [
          "Give each selected clip a one-sentence purpose and compare them side by side. One can explain the problem, one can show the practical method, and one can cover a limitation. Each should stand alone, since viewers may encounter the clips in any order.",
          "In ClipFactory, use the campaign brief to specify the audience, tone, objective and topics to avoid. Supply the video podcast through an accessible YouTube or Vimeo URL. Direct audio-file upload is outside the current offer; the pilot accepts video sources up to 30 minutes.",
        ],
      },
      {
        title: "Review the series before publishing",
        paragraphs: [
          "ClipFactory returns candidate clips with source timestamps and editorial reasons. Use them as the starting point for your own review. A high score is not a guarantee of reach, and requesting three clips does not guarantee that three distinct moments will pass the checks.",
        ],
        checklist: [
          "Each clip delivers a different complete idea.",
          "The guest's qualifications and context remain intact.",
          "The opening does not depend on an unseen question.",
          "Speaker changes and caption timing work in the final frame.",
          "Titles describe what the clip actually contains.",
          "Publishing order is useful, but each clip also stands alone.",
        ],
      },
    ],
    related: [
      { label: "Creator and podcast workflow", href: "/use-cases/creators" },
      {
        label: "Turn YouTube videos into Shorts",
        href: "/guides/youtube-video-to-shorts",
      },
      { label: "How clip selection works", href: "/features" },
    ],
  },
  {
    slug: "video-clipping-campaign-brief",
    title: "How to write a brief for AI video clipping",
    description:
      "Use a concrete campaign brief to guide AI clip selection. Define your audience, objective, tone and boundaries, with an example you can adapt to your next video.",
    updatedAt: "2026-09-06",
    category: "Campaign planning",
    intro:
      "‘Find the best clips’ leaves the most important decision unanswered: best for whom? A campaign brief makes the selection criteria explicit so that you can judge the output against the same objective you gave the tool.",
    sections: [
      {
        title: "Name a specific audience and its starting point",
        paragraphs: [
          "Choose the viewer's situation, not just a demographic. ‘People interested in business’ is broad. ‘Solo founders preparing their first customer demo’ tells you what knowledge the clip can assume and which problems deserve attention.",
          "Include what the audience already knows. A specialist audience may understand an acronym that would lose a first-time viewer. This helps you decide whether a technically strong passage is ready to stand alone or needs too much explanation for a short.",
        ],
      },
      {
        title: "Give the series one primary objective",
        paragraphs: [
          "Choose what the series should help the viewer do or understand. Useful objectives include explaining a product decision, showing a specific method or answering a recurring objection. ‘Get views’ describes an outcome, but it does not explain which source moments belong in the series.",
          "For example, a webinar may contain a product tour and a long discussion of the market. If the objective is to show how the product solves one workflow problem, a compelling market quote can still be the wrong clip.",
        ],
      },
      {
        title: "Describe tone through choices",
        paragraphs: [
          "Words such as ‘engaging’ and ‘professional’ are difficult to evaluate. Translate tone into instructions: keep the speaker's plain language, prefer a concrete example over a slogan, retain relevant uncertainty, and avoid an alarmist headline.",
          "A hook example should describe a pattern you want to find in the source. ‘Open on the constraint, then show the workaround’ gives editorial direction. It does not authorize a tool to invent a sentence the speaker never said.",
        ],
      },
      {
        title: "Set boundaries that can reject a candidate",
        paragraphs: [
          "List subjects, claims or details that should stay out of the series. For a product campaign, that might include internal revenue figures, a roadmap announcement or a customer name. Review the source yourself when those boundaries matter; an automated check can miss context.",
          "Also define what makes a candidate incomplete: an answer without its question, a demonstration whose evidence falls outside the crop, or an ending that stops before the result. A useful brief provides reasons to say no.",
        ],
      },
      {
        title: "An example brief to adapt",
        paragraphs: [
          "Audience: solo founders preparing a first product demo. Objective: help them understand why showing one complete workflow is more useful than listing features. Tone: direct and practical, keeping the speaker's qualifications. Prefer: a mistake followed by the concrete change. Avoid: fundraising advice, revenue numbers and claims of guaranteed conversion.",
          "Hook direction: begin with the problem the speaker actually encountered, then show the evidence for the decision. Each clip should deliver one complete lesson and make sense to someone who has not watched the full interview.",
          "This is an illustrative brief, not a claim about a particular video or a measured campaign result. Adapt it to what your source actually contains.",
        ],
      },
      {
        title: "Evaluate the output against the brief",
        paragraphs: [
          "In ClipFactory, the campaign keeps the audience, objective, tone and boundaries attached to the source. Review the selected words, timestamps and reason for each delivered clip. Ask whether the result follows the brief and remains faithful to the source.",
          "A recorded thumbs-up or thumbs-down is feedback for review. It does not silently retrain the system. If the output misses the objective, revise the brief explicitly before the next source or job.",
        ],
        checklist: [
          "The intended viewer is specific.",
          "The objective can guide a real editorial choice.",
          "Tone instructions describe observable choices.",
          "The brief includes topics and claims to avoid.",
          "The hook pattern can be found in the source.",
          "Each candidate can be accepted or rejected against these criteria.",
        ],
      },
    ],
    related: [
      { label: "Campaign clipping features", href: "/features" },
      { label: "Clipping for agencies", href: "/use-cases/agencies" },
      {
        label: "Choose podcast moments",
        href: "/guides/podcast-clips-for-social-media",
      },
    ],
  },
];
