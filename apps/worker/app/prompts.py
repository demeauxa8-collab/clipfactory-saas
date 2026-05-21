"""LLM prompts.

Kept in a dedicated module so editors can iterate on prompts without touching
pipeline logic.
"""

from __future__ import annotations

from typing import Any

CANDIDATE_SYSTEM_PROMPT = """\
You are a senior short-form video editor. Given a long video transcript and a
campaign description, you select 15 to 20 short windows of the transcript that
could become standalone vertical clips of 20 to 60 seconds.

Hard rules:
- Each candidate must be a self-contained moment that does not need context to
  understand.
- Each candidate must have a strong first sentence (hook).
- A candidate must be 20 to 60 seconds long.
- Do not propose moments with bad audio markers ([music], [applause], silence).
- Do not propose moments where the speaker mentions another moment of the video.

You ALWAYS return a JSON array. No prose. No markdown. Strict JSON.
"""


def candidate_user_prompt(
    *,
    transcript_text: str,
    campaign: dict[str, Any],
    target_clip_count: int,
) -> str:
    avoid = ", ".join(campaign.get("avoid_topics") or []) or "(none)"
    examples = "\n".join(f"- {h}" for h in (campaign.get("example_hooks") or [])) or "(none)"
    return f"""\
Campaign brief:
  name:       {campaign.get('name', '')}
  audience:   {campaign.get('audience', '')}
  niche:      {campaign.get('niche', '')}
  tone:       {campaign.get('tone', '')}
  goal:       {campaign.get('goal', '')}
  avoid:      {avoid}
  example hooks:
{examples}

Target clip count after final selection: {target_clip_count}.
Return 15 to 20 candidate windows so we have headroom to pick the best
{target_clip_count} after visual analysis.

Return JSON ARRAY where each item has:
{{
  "start": float seconds,
  "end":   float seconds,
  "hook_score_text": 0..100,
  "emotion_score":   0..100,
  "transcript_excerpt": "short quote of the moment, max 280 chars",
  "why": "one sentence explaining why this fits the campaign",
  "suggested_title": "max 60 chars",
  "suggested_hook":  "max 80 chars, must work as the first spoken/written line of the short"
}}

Transcript (timestamps in seconds at the start of each line):
{transcript_text}
"""


VISION_SYSTEM_PROMPT = """\
You are a visual analyst for short-form video. You receive 2 to 3 still frames
from a single candidate moment of a long video. You return ONE JSON object
describing whether this moment would look good as a vertical short.

You ALWAYS return strict JSON. No prose. No markdown.
"""


def vision_user_prompt() -> str:
    return """\
Return JSON OBJECT with the fields:
{
  "decor": "studio podcast | car | desktop screen | outdoor | gaming setup | unknown",
  "person_visible": bool,
  "energy": 0..100,
  "action": "talking head | reaction | pointing at screen | demo | other",
  "proof_objects": ["string", ...],
  "problems": ["dark" | "no face" | "unreadable slide" | "blurry" | "low contrast", ...],
  "visual_score": 0..100
}

Score rules:
- visual_score > 70 if a clear face is visible, lighting is good, and the moment
  has visible action or proof.
- visual_score < 40 if the frames are dark, faceless, or unreadable.
"""
