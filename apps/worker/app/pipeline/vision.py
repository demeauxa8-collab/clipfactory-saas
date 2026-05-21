from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from ..models import TextCandidate, VisionResult
from ..prompts import VISION_SYSTEM_PROMPT, vision_user_prompt
from ..settings import get_settings
from .ffmpeg import FFmpegError, extract_frame

log = structlog.get_logger()


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        return max(0, min(100, round(float(v))))
    except Exception:
        return default


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _frame_timestamps(candidate: TextCandidate) -> list[float]:
    mid = (candidate.start + candidate.end) / 2.0
    return [
        candidate.start + 0.2,
        mid,
        max(candidate.start + 0.2, candidate.end - 0.2),
    ]


async def extract_candidate_frames(
    *,
    source_path: str,
    candidate: TextCandidate,
    workdir: str,
    idx: int,
) -> list[str]:
    paths: list[str] = []
    for k, ts in enumerate(_frame_timestamps(candidate)):
        out = os.path.join(workdir, f"cand_{idx:02d}_f{k}.jpg")
        try:
            await extract_frame(source_path, ts, out)
            paths.append(out)
        except FFmpegError:
            continue
    return paths


def _frames_as_image_blocks(paths: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for p in paths:
        try:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except FileNotFoundError:
            continue
        blocks.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            }
        )
    return blocks


async def analyze_candidate(
    *,
    candidate: TextCandidate,
    source_path: str,
    workdir: str,
    idx: int,
) -> tuple[VisionResult | None, int, int]:
    """Returns (vision_result_or_None, frames_used, tokens_used)."""
    settings = get_settings()
    frames = await extract_candidate_frames(
        source_path=source_path, candidate=candidate, workdir=workdir, idx=idx
    )
    if not frames:
        return None, 0, 0

    image_blocks = _frames_as_image_blocks(frames)
    if not image_blocks:
        return None, 0, 0

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        msg = await client.messages.create(
            model=settings.anthropic_vision_model,
            max_tokens=512,
            system=VISION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        *image_blocks,
                        {"type": "text", "text": vision_user_prompt()},
                    ],
                }
            ],
        )
    except Exception as exc:
        log.warning("vision.error", err=str(exc))
        return None, len(frames), 0

    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    tokens_used = (msg.usage.input_tokens or 0) + (msg.usage.output_tokens or 0)
    obj = _extract_json_object(raw)
    if not obj:
        return None, len(frames), int(tokens_used)

    return (
        VisionResult(
            decor=str(obj.get("decor", "unknown")),
            person_visible=bool(obj.get("person_visible", False)),
            energy=_coerce_int(obj.get("energy")),
            action=str(obj.get("action", "other")),
            proof_objects=list(obj.get("proof_objects") or []),
            problems=list(obj.get("problems") or []),
            visual_score=_coerce_int(obj.get("visual_score")),
        ),
        len(frames),
        int(tokens_used),
    )
