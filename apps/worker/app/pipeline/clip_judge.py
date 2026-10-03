"""Judge a rendered clip by sending it to a model as native video.

Off by default (``CLIP_JUDGE_ENABLED``): one paid call per delivered clip. The
model comes from the ``clip_judge`` stage of models.lock.toml. The verdict is
advisory — the runner logs it with the render outcome, it never blocks delivery.

The answer must be strict JSON with exactly these keys:

    {"publishable": bool, "hook_0_3s": bool, "cut_mid_sentence": bool,
     "framing_ok": bool, "caption_overlap": bool, "reason": str}
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from ..providers.base import LLMCallResult

JUDGE_SYSTEM_PROMPT = """You review a short vertical video clip cut from a longer video.
Watch the whole clip, with sound. Answer with one JSON object and nothing else:
{"publishable": true|false, "hook_0_3s": true|false, "cut_mid_sentence": true|false,
 "framing_ok": true|false, "caption_overlap": true|false, "reason": "<one sentence>"}
- publishable: a social media editor would post this clip as is.
- hook_0_3s: the first 3 seconds give a clear reason to keep watching.
- cut_mid_sentence: the clip starts or ends in the middle of a sentence or word.
- framing_ok: the speaker or subject is fully and correctly framed, no black bars
  or cropped faces.
- caption_overlap: burned-in captions overlap each other, a face, or on-screen text.
- reason: the main reason for the publishable verdict."""

JUDGE_USER_PROMPT = "Judge this clip."

_FIELDS: dict[str, type] = {
    "publishable": bool,
    "hook_0_3s": bool,
    "cut_mid_sentence": bool,
    "framing_ok": bool,
    "caption_overlap": bool,
    "reason": str,
}


class ClipJudgeError(RuntimeError):
    pass


class VideoJudgeProvider(Protocol):
    async def video_json(
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        video_mp4: bytes,
        max_tokens: int = ...,
        temperature: float = ...,
    ) -> LLMCallResult: ...


@dataclass(frozen=True)
class ClipVerdict:
    publishable: bool
    hook_0_3s: bool
    cut_mid_sentence: bool
    framing_ok: bool
    caption_overlap: bool
    reason: str
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_verdict(payload: Any) -> dict[str, Any]:
    """Validate the judge answer strictly: exact keys, exact types."""
    if not isinstance(payload, dict):
        raise ClipJudgeError("judge answer is not a JSON object")
    keys = set(payload)
    if keys != set(_FIELDS):
        missing = sorted(set(_FIELDS) - keys)
        extra = sorted(keys - set(_FIELDS))
        raise ClipJudgeError(f"judge answer keys mismatch: missing={missing} extra={extra}")
    for key, kind in _FIELDS.items():
        # bool is checked exactly: 0/1 or "true" are rejected.
        if type(payload[key]) is not kind:
            raise ClipJudgeError(f"judge field '{key}' must be {kind.__name__}")
    reason = payload["reason"].strip()
    if not reason:
        raise ClipJudgeError("judge reason is empty")
    return {**payload, "reason": reason[:500]}


async def call_native_video_judge(
    clip_path: str,
    *,
    provider: VideoJudgeProvider,
    model: str,
    max_video_mb: float = 18.0,
    system_prompt: str = JUDGE_SYSTEM_PROMPT,
    user_prompt: str = JUDGE_USER_PROMPT,
) -> LLMCallResult:
    """Shared native-video IO for the production and B0 observation rubrics."""
    data = Path(clip_path).read_bytes()
    if not data:
        raise ClipJudgeError("clip file is empty")
    if len(data) > max_video_mb * 1024 * 1024:
        raise ClipJudgeError(f"clip exceeds {max_video_mb} MB judge limit")
    return await provider.video_json(
        model=model,
        system=system_prompt,
        user_text=user_prompt,
        video_mp4=data,
        max_tokens=1024,
        temperature=0.0,
    )


async def judge_clip(
    clip_path: str,
    *,
    provider: VideoJudgeProvider,
    model: str,
    max_video_mb: float = 18.0,
) -> ClipVerdict:
    result = await call_native_video_judge(
        clip_path, provider=provider, model=model, max_video_mb=max_video_mb
    )
    fields = parse_verdict(result.payload)
    return ClipVerdict(
        **fields,
        model=result.model or model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )
