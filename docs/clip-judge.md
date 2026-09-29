# Clip judge — native-video final selection

Last updated: 2026-06-03.

This doc specs the **final clip judge**: the model that *watches* the candidate
moments (video + audio) and picks the best clips. It is the quality core of
ClipFactory — FFmpeg only executes the timestamps the judge chooses.

## Why a native-video judge (Option B)

Earlier stages already do a lot:

- **Deepgram Nova-3** → transcription with word timestamps.
- **Qwen3-VL-Flash** → cheap coarse video map of the whole source.
- **DeepSeek V4 Flash** (`story_arcs.select_story_arcs`) → *proposes* candidate
  arcs: ordered segments `{start, end}` + a suggested hook.
- **GLM-4.6V** → deep visual-proof scoring on candidate frames.

The weakness of a pure "frame-summary" pipeline: the final pick reads a
**text description of the screen** written by another model. The judge never
sees the real thing.

**Option B** fixes that. On the top candidate zones, the judge (**Gemini 3
Flash**, native video) receives the **actual video + audio** of those moments
plus the transcript and the campaign brief, and decides. It is the difference
between an editor *reading notes* and an editor *watching the rushes*.

## Inputs the judge receives (per candidate)

| Input | Source |
| --- | --- |
| Candidate segments `{start,end}` + suggested hook | `select_story_arcs` (DeepSeek V4 Flash) |
| The real video + audio of those windows | source video, sent natively to Gemini |
| Transcript excerpt of those windows | Deepgram transcript |
| Campaign brief (audience, goal, avoid topics) | user's campaign row |

Output: a ranked list with the 5 scores (`hook`, `emotion`, `visual_proof`,
`audience_fit`, `editing`) + a one-line reason per clip, and the chosen
`target_clip_count` (weak candidates rejected).

## Where it sits in the pipeline

Story path (`runner.run_job`), inserted between arc proposal and the final pick:

```text
... video_map → frame_sampling → vision (Qwen/GLM)
  → select_story_arcs          # DeepSeek proposes candidates  (≤5 arcs)
  → JUDGE  (this doc)          # Gemini 3 Flash watches + ranks + picks
  → verify_arcs                # string-match anti-hallucination (no model)
  → render_montage             # FFmpeg cuts the chosen timestamps
  → retime_captions → upload
```

The judge **replaces the model-judgment part** of `score_and_pick_arcs`. The
existing weighted formula (`score.py` `ARC_WEIGHTS`) stays as the **fallback**
when the judge is disabled or errors, so the pipeline degrades gracefully.

## Implementation

### 1. Settings (`apps/worker/app/settings.py`)

```python
selector_enabled: bool = True
selector_model: str = "gemini-3-flash"        # native video judge
selector_max_candidates: int = 5              # only judge the top arcs
selector_max_clip_seconds: int = 60           # cost guardrail per window
gemini_api_key: str = ""                       # Google AI Studio key (native video)
```

### 2. Provider

Native video is strongest through **Google's Gemini API directly** (upload the
candidate windows via the Files API, or pass the source with clip metadata),
not a text-only proxy. Add `GeminiProvider` alongside `OpenRouterProvider` /
`AnthropicProvider`. If video upload is not wired yet, the OpenRouter route
(`google/gemini-3-flash`) works for image-frame input as a first step, then
upgrade to true native video.

Legal/privacy: Gemini via Google API is an invoiced provider with a DPA — the
**allowed route** per `unit-economics.md`, not a grey-market proxy.

### 3. New step (`apps/worker/app/pipeline/judge.py`)

```python
async def judge_clips(
    ctx: JobContext,
    arcs: list[StoryArc],          # candidates from select_story_arcs
    transcript: Transcript,
    campaign: dict,
    provider: GeminiProvider,
) -> list[JudgedClip]:
    """Watch the top candidate windows and rank/pick the best clips.
    Returns ranked clips with 5 scores + reason. Falls back to score.py
    weighted pick on error (handled by the caller)."""
    top = arcs[: settings.selector_max_candidates]
    media = [extract_window(ctx.source, a, cap=settings.selector_max_clip_seconds)
             for a in top]                          # rough FFmpeg cut, no crossfade
    return await provider.judge(media, top, transcript, campaign, schema=JUDGE_SCHEMA)
```

Prompt shape (structured JSON out): *"You are an editor. For each candidate
clip, watch the video and audio, read the transcript, and score hook / emotion
/ visual_proof / audience_fit / editing 0-100 with one short reason. Pick the
best N for a [audience] series whose goal is [goal]; reject anything off-brief
or visually weak. Return JSON."*

### 4. Wire into `runner.run_job`

```python
arcs = await select_story_arcs(ctx, provider=primary, fallback=fallback, ...)
if settings.selector_enabled and settings.gemini_api_key:
    try:
        picked = await judge_clips(ctx, arcs, transcript, campaign, GeminiProvider())
    except ProviderError:
        picked = score_and_pick_arcs(arcs, vision, campaign)   # formula fallback
else:
    picked = score_and_pick_arcs(arcs, vision, campaign)
# verify_arcs(...) then render_montage(...) on `picked`
```

## Cost & guardrails

Bounded to the top candidate windows, never the full source:

| Guardrail | Value |
| --- | --- |
| Candidates judged | top 5 arcs |
| Window length sent | ≤ 60 s each |
| Native-video cost | ~€0.02 / video (see `unit-economics.md`) |
| Fallback | weighted formula in `score.py`, €0 extra |

This is why the judge improves quality without breaking margin: it only watches
the few moments that already passed the cheap stages.

## Rollout

1. Ship behind `selector_enabled` (default on once the Gemini key is set).
2. A/B: judge vs formula-only on the same arcs; compare kept-clip quality.
3. Log `selector_used` + judge tokens to the finance columns for cost tracking.
4. Keep `verify.py` after the judge — the judge ranks, verify guarantees the
   quoted line really exists before render.

## Related docs

- `pipeline.md` — full step list (story path / simple path).
- `global-video-understanding.md` — why story-first, multi-segment clips.
- `unit-economics.md` — per-stage model prices and the judge's cost line.
