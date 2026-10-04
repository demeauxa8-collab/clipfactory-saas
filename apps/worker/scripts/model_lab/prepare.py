"""Freeze shared transcripts once; charge new ASR attempts to method A's cap."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tomllib
from dataclasses import asdict
from pathlib import Path

from dotenv import dotenv_values

from app.golden.budget import Budget, duration_context, source_context
from app.golden.sources import read_sources, sha256, verify_source
from app.pipeline.transcribe import _extract_audio, _transcribe_openrouter
from app.settings import Settings, get_settings


async def execute(args):
    credentials = dotenv_values(args.credentials_file)
    if not credentials.get("OPENROUTER_API_KEY"):
        raise ValueError("OpenRouter lab credentials required")
    for field in Settings.model_fields:
        os.environ.pop(field.upper(), None)
    os.environ.update(
        OPENROUTER_API_KEY=credentials["OPENROUTER_API_KEY"],
        OPENAI_API_KEY="unused-offline",
        DATABASE_URL="postgresql://unused",
        R2_ACCOUNT_ID="unused",
        R2_ACCESS_KEY_ID="unused",
        R2_SECRET_ACCESS_KEY="unused",
        R2_ENDPOINT_URL="https://example.com",
        MODELS_LOCK_PATH=str(args.models_lock.resolve()),
        ASR_BACKEND="openrouter",
    )
    get_settings.cache_clear()
    settings = get_settings()
    document = tomllib.loads(args.models_lock.read_text())
    model = document["stages"]["transcription_openrouter"]["model"]
    prior = json.loads(args.prior_ledger.read_text())["requests"] if args.prior_ledger else []
    budget = Budget(
        "0.50",
        args.ledger,
        {model: {"minute": str(document["models"][model]["usd_per_minute"])}},
        prior_entries=prior,
    )
    for source in read_sources(args.config):
        directory = args.shared_root / source["id"]
        meta = verify_source(directory)
        target = directory / "transcript.json"
        if target.exists():
            if sha256(target) != meta.get("transcript_sha256"):
                raise ValueError("frozen transcript hash mismatch")
            continue
        source_context.set(source["id"])
        duration_context.set(meta["duration"])
        audio = await _extract_audio(str(directory / "source.mp4"), settings.ffmpeg_bin)
        try:
            with budget.intercept():
                expected_language = (meta.get("language") or "").split("-")[0]
                transcript = await _transcribe_openrouter(
                    audio, settings, language=expected_language
                )
                if expected_language and transcript.language not in (
                    expected_language,
                    {"fr": "french", "en": "english"}.get(expected_language),
                ):
                    raise ValueError("shared ASR language differs from original source")
        finally:
            Path(audio).unlink(missing_ok=True)
        target.write_text(json.dumps(asdict(transcript), ensure_ascii=False, indent=2))
        target.chmod(0o400)
        meta.update(
            transcript_sha256=sha256(target),
            transcript_provenance="Shared OpenRouter Whisper Large V3 experimental input",
        )
        path = directory / "meta.json"
        path.chmod(0o600)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        path.chmod(0o400)
        print("Shared transcript frozen: " + source["id"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--models-lock", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--prior-ledger", type=Path)
    asyncio.run(execute(parser.parse_args()))


if __name__ == "__main__":
    main()
