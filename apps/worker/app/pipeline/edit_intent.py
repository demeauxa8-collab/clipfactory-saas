"""LLM contract for ClipFactory's expressive V2 edit timeline.

The model receives transcript words with stable IDs and a closed catalogue of
available operations/assets. It returns editorial intent only. Parsing is
defensive; :mod:`app.pipeline.edl` performs the authoritative semantic and
timeline validation before any renderer sees the plan.
"""

from __future__ import annotations

import json
import math
from typing import Any

from ..models import MontageCandidate, Transcript
from ..providers import LLMProvider, ProviderError
from .edl import (
    CompiledEDL,
    EditIntentPlan,
    EditScope,
    EditShotIntent,
    EDLValidationError,
    EffectIntent,
    FramingIntent,
    InclusiveWordRange,
    MusicIntent,
    SFXCueIntent,
    compile_edit_intent,
    word_id_for_index,
    word_index_from_id,
)

EDIT_INTENT_SYSTEM_PROMPT = """You are ClipFactory's senior short-form editing director.

You can build a genuinely non-linear, multi-shot vertical edit: reorder or reuse
spoken moments, choose exact word boundaries, vary framing, request a small
number of motivated effects, select caption themes, and place licensed music or
SFX from the supplied catalogue.

You do NOT write FFmpeg, file paths, URLs or free-form effect names. You only use
the exact word IDs, shot asset IDs, audio asset IDs and preset values supplied by
the user. List order is final timeline order. Seconds are context only and must
never be emitted as edit boundaries.

Return one JSON object and no markdown. Required shape:
{
  "schema_version": "2.0",
  "editorial_thesis": "one sentence explaining the edit",
  "shots": [
    {
      "shot_id": "unique_safe_id",
      "role": "hook | setup | bridge | proof | payoff | reaction | cta",
      "from_word_id": "w_000000",
      "to_word_id": "w_000010",
      "start_anchor": "exact consecutive words beginning at from_word_id",
      "end_anchor": "exact consecutive words ending at to_word_id",
      "framing": {
        "mode": "source_safe | fit_blur | locked_face | screen_focus",
        "center_x": 0.0,
        "base_scale": 1.0
      },
      "effects": [
        {
          "kind": "punch_in | zoom_out | freeze | flash | shake | blur | color_pop",
          "at_word_id": "w_000004 or null",
          "duration_ms": 50,
          "intensity": 0.0
        }
      ],
      "transition_out": "hard_cut | time_jump | reveal | contrast | hard_impact",
      "caption_theme": "hook_bold | standard_karaoke | proof_clean | reaction_pop | none",
      "speed": 1.0,
      "pre_roll_ms": 0,
      "post_roll_ms": 120
    }
  ],
  "music": [
    {
      "asset_id": "catalogue_id",
      "start_shot_id": "shot_id or null",
      "end_shot_id": "shot_id or null",
      "gain_db": -22,
      "ducking_db": -10,
      "fade_in_ms": 300,
      "fade_out_ms": 600,
      "loop": true
    }
  ],
  "sfx": [
    {
      "asset_id": "catalogue_id",
      "shot_id": "shot_id",
      "at_word_id": "w_000004",
      "gain_db": -10
    }
  ]
}

Editorial rules:
- Start with the strongest scroll-stop, not necessarily the earliest source moment.
- The hook must communicate tension, proof or reaction in the first 1.5 seconds.
- Every spoken boundary must be a supplied word ID plus matching verbatim anchor.
- You may reuse a short reaction/proof range when repetition serves the story.
- Prefer hard cuts. Stylized transitions/effects must have a narrative reason.
- Vary plan scale deliberately; do not add an effect just to simulate activity.
- Keep proof readable: fit_blur or screen_focus for dashboards/objects.
- Use the shot-level speed field for constant speed changes. Do not request
  face tracking, visual inserts or speed ramps until those capabilities are
  explicitly supplied in the job catalogue.
- Music and SFX are optional. Use only supplied asset IDs; an empty list is valid.
- Never remove or separate a negation, number, price, proper name or payoff phrase.
- Maximum 30 shots, 3 effects per shot. The compiler enforces a global effect budget.
"""


def transcript_to_word_id_lines(
    transcript: Transcript,
    *,
    words_per_line: int = 10,
    allowed_word_ranges: tuple[InclusiveWordRange, ...] | None = None,
) -> str:
    """Compact word-ID view used by the editing model.

    IDs are deterministic indices assigned after transcription normalization.
    The timestamps help the model understand source distance, but only IDs may
    be returned as boundaries.
    """
    words_per_line = max(1, words_per_line)
    allowed_ids = (
        None
        if allowed_word_ranges is None
        else {
            index
            for word_range in allowed_word_ranges
            for index in range(word_range.from_word_id, word_range.to_word_id + 1)
        }
    )
    entries = [
        f"{word_id_for_index(index)}@{word.start:.3f}={word.word}"
        for index, word in enumerate(transcript.words)
        if allowed_ids is None or index in allowed_ids
    ]
    return "\n".join(
        " | ".join(entries[start : start + words_per_line])
        for start in range(0, len(entries), words_per_line)
    )


def candidate_edit_scope(
    candidate: MontageCandidate,
    transcript: Transcript,
) -> EditScope:
    """Resolve candidate time windows to an explicit word-ID authority scope."""
    ranges: list[InclusiveWordRange] = []
    for segment in candidate.segments:
        matching = [
            index
            for index, word in enumerate(transcript.words)
            if word.end > segment.start and word.start < segment.end
        ]
        if matching:
            ranges.append(InclusiveWordRange(matching[0], matching[-1]))
    if not ranges:
        raise EDLValidationError("candidate does not overlap any transcript words")

    merged: list[InclusiveWordRange] = []
    for word_range in sorted(ranges, key=lambda item: item.from_word_id):
        if merged and word_range.from_word_id <= merged[-1].to_word_id + 1:
            previous = merged[-1]
            merged[-1] = InclusiveWordRange(
                previous.from_word_id,
                max(previous.to_word_id, word_range.to_word_id),
            )
        else:
            merged.append(word_range)
    return EditScope(allowed_word_ranges=tuple(merged))


def edit_intent_user_prompt(
    *,
    transcript: Transcript,
    candidate: MontageCandidate,
    target_duration_seconds: int,
    shot_assets: list[dict[str, Any]] | None = None,
    audio_assets: list[dict[str, Any]] | None = None,
    audio_edit_hints: list[dict[str, Any]] | None = None,
    edit_scope: EditScope | None = None,
) -> str:
    scope = edit_scope or candidate_edit_scope(candidate, transcript)
    candidate_ranges = [
        {
            "role": segment.role,
            "coarse_start": round(segment.start, 3),
            "coarse_end": round(segment.end, 3),
            "transcript_excerpt": segment.transcript_excerpt,
        }
        for segment in candidate.segments
    ]
    return f"""Build one expressive final edit plan.

TARGET DURATION: {target_duration_seconds}s (the compiler validates the result)
CURRENT CANDIDATE: {json.dumps({
        "title": candidate.title,
        "hook": candidate.hook,
        "rationale": candidate.rationale,
        "arc_type": candidate.arc_type,
        "ranges": candidate_ranges,
    }, ensure_ascii=False)}

DETECTED VISUAL SHOT ASSETS (IDs only):
{json.dumps(shot_assets or [], ensure_ascii=False)}

LICENSED AUDIO CATALOGUE (IDs only; empty means no music/SFX):
{json.dumps(audio_assets or [], ensure_ascii=False)}

MEASURED AUDIO PACING HINTS (evidence only; cuts still use word IDs):
{json.dumps(audio_edit_hints or [], ensure_ascii=False)}

WORD-ID TRANSCRIPT:
{transcript_to_word_id_lines(transcript, allowed_word_ranges=scope.allowed_word_ranges)}

Return the JSON plan now. Use exact consecutive transcript words for every
start_anchor/end_anchor and the matching first/last word IDs. Do not emit source
or timeline seconds as edit boundaries.
"""


def _dict(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EDLValidationError(f"{label} must be an object")
    return value


def _reject_unknown_keys(
    value: dict[str, Any],
    *,
    allowed: frozenset[str],
    label: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise EDLValidationError(f"{label} contains unsupported fields: {unknown}")


def _list(value: Any, *, label: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EDLValidationError(f"{label} must be an array")
    return value


def _text(value: Any, *, label: str, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise EDLValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label=label)


def _number(value: Any, *, label: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise EDLValidationError(f"{label} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EDLValidationError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise EDLValidationError(f"{label} must be a finite number")
    return number


def _integer(value: Any, *, label: str, default: int) -> int:
    number = _number(value, label=label, default=float(default))
    if not number.is_integer():
        raise EDLValidationError(f"{label} must be an integer")
    return int(number)


def _word_ref(value: Any, *, label: str) -> int:
    return word_index_from_id(_text(value, label=label))


def parse_edit_intent(payload: Any) -> EditIntentPlan:
    root = _dict(payload, label="edit plan")
    _reject_unknown_keys(
        root,
        allowed=frozenset(
            {"schema_version", "editorial_thesis", "shots", "music", "sfx"}
        ),
        label="edit plan",
    )
    shots: list[EditShotIntent] = []
    for index, raw_shot in enumerate(_list(root.get("shots"), label="shots")):
        shot = _dict(raw_shot, label=f"shots[{index}]")
        _reject_unknown_keys(
            shot,
            allowed=frozenset(
                {
                    "shot_id",
                    "role",
                    "from_word_id",
                    "to_word_id",
                    "start_anchor",
                    "end_anchor",
                    "framing",
                    "effects",
                    "transition_out",
                    "caption_theme",
                    "speed",
                    "pre_roll_ms",
                    "post_roll_ms",
                }
            ),
            label=f"shots[{index}]",
        )
        framing_raw = _dict(shot.get("framing") or {}, label=f"shots[{index}].framing")
        _reject_unknown_keys(
            framing_raw,
            allowed=frozenset({"mode", "center_x", "base_scale"}),
            label=f"shots[{index}].framing",
        )
        effects: list[EffectIntent] = []
        for effect_index, raw_effect in enumerate(
            _list(shot.get("effects"), label=f"shots[{index}].effects")
        ):
            effect = _dict(
                raw_effect,
                label=f"shots[{index}].effects[{effect_index}]",
            )
            _reject_unknown_keys(
                effect,
                allowed=frozenset(
                    {"kind", "at_word_id", "duration_ms", "intensity"}
                ),
                label=f"shots[{index}].effects[{effect_index}]",
            )
            word_ref = effect.get("at_word_id")
            effects.append(
                EffectIntent(
                    kind=_text(effect.get("kind"), label="effect.kind"),  # type: ignore[arg-type]
                    at_word_id=(
                        _word_ref(word_ref, label="effect.at_word_id")
                        if word_ref is not None
                        else None
                    ),
                    duration_ms=_integer(
                        effect.get("duration_ms"),
                        label="effect.duration_ms",
                        default=350,
                    ),
                    intensity=_number(
                        effect.get("intensity"),
                        label="effect.intensity",
                        default=0.5,
                    ),
                )
            )
        shots.append(
            EditShotIntent(
                shot_id=_text(shot.get("shot_id"), label="shot.shot_id"),
                role=_text(shot.get("role"), label="shot.role"),  # type: ignore[arg-type]
                from_word_id=_word_ref(
                    shot.get("from_word_id"), label="shot.from_word_id"
                ),
                to_word_id=_word_ref(shot.get("to_word_id"), label="shot.to_word_id"),
                start_anchor=_text(
                    shot.get("start_anchor"), label="shot.start_anchor"
                ),
                end_anchor=_text(shot.get("end_anchor"), label="shot.end_anchor"),
                framing=FramingIntent(
                    mode=_text(
                        framing_raw.get("mode") or "source_safe",
                        label="framing.mode",
                    ),  # type: ignore[arg-type]
                    center_x=_number(
                        framing_raw.get("center_x"),
                        label="framing.center_x",
                        default=0.5,
                    ),
                    base_scale=_number(
                        framing_raw.get("base_scale"),
                        label="framing.base_scale",
                        default=1.0,
                    ),
                ),
                effects=tuple(effects),
                transition_out=_text(
                    shot.get("transition_out") or "hard_cut",
                    label="shot.transition_out",
                ),  # type: ignore[arg-type]
                caption_theme=_text(
                    shot.get("caption_theme") or "standard_karaoke",
                    label="shot.caption_theme",
                ),  # type: ignore[arg-type]
                speed=_number(shot.get("speed"), label="shot.speed", default=1.0),
                pre_roll_ms=_integer(
                    shot.get("pre_roll_ms"), label="shot.pre_roll_ms", default=0
                ),
                post_roll_ms=_integer(
                    shot.get("post_roll_ms"), label="shot.post_roll_ms", default=120
                ),
            )
        )

    music: list[MusicIntent] = []
    for index, raw_music in enumerate(_list(root.get("music"), label="music")):
        item = _dict(raw_music, label=f"music[{index}]")
        _reject_unknown_keys(
            item,
            allowed=frozenset(
                {
                    "asset_id",
                    "start_shot_id",
                    "end_shot_id",
                    "gain_db",
                    "ducking_db",
                    "fade_in_ms",
                    "fade_out_ms",
                    "loop",
                }
            ),
            label=f"music[{index}]",
        )
        loop = item.get("loop", True)
        if not isinstance(loop, bool):
            raise EDLValidationError("music.loop must be a boolean")
        music.append(
            MusicIntent(
                asset_id=_text(item.get("asset_id"), label="music.asset_id"),
                start_shot_id=_optional_text(
                    item.get("start_shot_id"), label="music.start_shot_id"
                ),
                end_shot_id=_optional_text(
                    item.get("end_shot_id"), label="music.end_shot_id"
                ),
                gain_db=_number(item.get("gain_db"), label="music.gain_db", default=-22),
                ducking_db=_number(
                    item.get("ducking_db"), label="music.ducking_db", default=-10
                ),
                fade_in_ms=_integer(
                    item.get("fade_in_ms"), label="music.fade_in_ms", default=300
                ),
                fade_out_ms=_integer(
                    item.get("fade_out_ms"), label="music.fade_out_ms", default=600
                ),
                loop=loop,
            )
        )

    sfx: list[SFXCueIntent] = []
    for index, raw_sfx in enumerate(_list(root.get("sfx"), label="sfx")):
        item = _dict(raw_sfx, label=f"sfx[{index}]")
        _reject_unknown_keys(
            item,
            allowed=frozenset({"asset_id", "shot_id", "at_word_id", "gain_db"}),
            label=f"sfx[{index}]",
        )
        sfx.append(
            SFXCueIntent(
                asset_id=_text(item.get("asset_id"), label="sfx.asset_id"),
                shot_id=_text(item.get("shot_id"), label="sfx.shot_id"),
                at_word_id=_word_ref(item.get("at_word_id"), label="sfx.at_word_id"),
                gain_db=_number(item.get("gain_db"), label="sfx.gain_db", default=-10),
            )
        )

    return EditIntentPlan(
        schema_version=_text(
            root.get("schema_version"), label="schema_version"
        ),
        editorial_thesis=_text(
            root.get("editorial_thesis"), label="editorial_thesis"
        ),
        shots=tuple(shots),
        music=tuple(music),
        sfx=tuple(sfx),
    )


async def direct_edit_with_llm(
    *,
    provider: LLMProvider,
    model: str,
    transcript: Transcript,
    candidate: MontageCandidate,
    source_duration_ms: int,
    target_duration_seconds: int,
    shot_assets: list[dict[str, Any]] | None = None,
    audio_assets: list[dict[str, Any]] | None = None,
    audio_edit_hints: list[dict[str, Any]] | None = None,
    edit_scope: EditScope | None = None,
) -> tuple[CompiledEDL, int]:
    """Ask for editorial intent and return only its validated compiled form."""
    scope = edit_scope or candidate_edit_scope(candidate, transcript)
    result = await provider.chat_json(
        model=model,
        system=EDIT_INTENT_SYSTEM_PROMPT,
        user=edit_intent_user_prompt(
            transcript=transcript,
            candidate=candidate,
            target_duration_seconds=target_duration_seconds,
            shot_assets=shot_assets,
            audio_assets=audio_assets,
            audio_edit_hints=audio_edit_hints,
            edit_scope=scope,
        ),
        max_tokens=8192,
        temperature=0.35,
    )
    try:
        plan = parse_edit_intent(result.payload)
        catalogue = audio_assets or []
        allowed_music = {
            str(item["id"])
            for item in catalogue
            if isinstance(item, dict) and item.get("kind") == "music" and "id" in item
        }
        allowed_sfx = {
            str(item["id"])
            for item in catalogue
            if isinstance(item, dict)
            and item.get("kind") in {"sfx", "stinger"}
            and "id" in item
        }
        compiled = compile_edit_intent(
            plan,
            transcript,
            source_duration_ms=source_duration_ms,
            target_duration_seconds=target_duration_seconds,
            allowed_music_asset_ids=allowed_music,
            allowed_sfx_asset_ids=allowed_sfx,
            edit_scope=scope,
        )
    except EDLValidationError as exc:
        raise ProviderError(f"invalid edit intent: {exc}", kind="invalid_json") from exc
    return compiled, result.tokens_total
