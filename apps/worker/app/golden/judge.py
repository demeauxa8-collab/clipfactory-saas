"""B0 observation rubric, independent of the optional production judge."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from ..pipeline.clip_judge import VideoJudgeProvider, call_native_video_judge

REASONS = {
    "fin_coupee": "Fin coupée",
    "ouverture_sans_contexte": "Ouverture sans contexte",
    "accroche_faible": "Accroche faible",
    "chute_absente": "Chute absente",
    "promesse_non_tenue": "Promesse non tenue",
    "hors_brief": "Hors brief",
    "cadrage": "Cadrage",
    "sous_titres": "Sous-titres",
    "trop_long": "Trop long",
    "trop_court": "Trop court",
    "audio": "Audio",
    "autre": "Autre",
}
SYSTEM = (
    """Watch the entire native vertical video with sound. Review it for the supplied campaign.
Do not change the clip. Reply with exactly one JSON object with these exact keys:
publishable (boolean), reasons (array of rejection reason codes), hook_0_3s (integer 0 to 4),
explanation (one short sentence). 0=no hook, 4=very strong hook in the first 3 seconds.
Reasons must use only: """
    + ", ".join(REASONS)
    + ". No extra keys."
)


def parse_verdict(payload):
    if not isinstance(payload, dict) or set(payload) != {
        "publishable",
        "reasons",
        "hook_0_3s",
        "explanation",
    }:
        raise ValueError("invalid observation verdict fields")
    if type(payload["publishable"]) is not bool or type(payload["hook_0_3s"]) is not int:
        raise ValueError("invalid observation verdict types")
    if not 0 <= payload["hook_0_3s"] <= 4:
        raise ValueError("hook outside 0-4")
    if not isinstance(payload["reasons"], list) or any(
        type(r) is not str or r not in REASONS for r in payload["reasons"]
    ):
        raise ValueError("unknown rejection reason")
    if not isinstance(payload["explanation"], str) or not payload["explanation"].strip():
        raise ValueError("empty explanation")
    return payload


async def judge_clip(path: Path, *, provider: VideoJudgeProvider, model, campaign, transcript):
    # Keep the whole clip/audio native; compress only if the inline media limit
    # would otherwise be exceeded. Delivered media and selection stay untouched.
    original = path
    if path.stat().st_size > 18 * 1024 * 1024:
        path = path.with_suffix(".judge-input.mp4")
        await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(original),
                "-vf",
                "scale=-2:720",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "24",
                "-maxrate",
                "1500k",
                "-bufsize",
                "3000k",
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    if path.stat().st_size > 18 * 1024 * 1024:
        raise ValueError("native video exceeds inline judge limit")
    result = await call_native_video_judge(
        str(path),
        provider=provider,
        model=model,
        system_prompt=SYSTEM,
        user_prompt=json.dumps(
            {"campaign": campaign, "transcript": transcript}, ensure_ascii=False
        ),
    )
    return {
        **parse_verdict(result.payload),
        "model": result.model or model,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "mode": "observation_only",
        "input_media": "original" if path == original else "720p_judge_proxy",
    }
