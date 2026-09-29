#!/usr/bin/env python3
"""One-shot: re-transcribe the bench source with the patched transcribe().

Writes the full Transcript (words + the punctuated sentences we used to throw
away) next to the fixture so every later measurement is free.

    cd /Users/augustindemeaux/clipfactory-saas/apps/worker
    .venv/bin/python /Users/augustindemeaux/clipfactory-data/bench/craft-refs/\
transcribe_with_sentences.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from app.pipeline.transcribe import transcribe  # noqa: E402

SRC = (
    "/Users/augustindemeaux/clipfactory-data/bench/source/"
    "2221f645-ed0e-47b2-8201-417d7c517a39/source.mp4"
)
OUT = Path(
    "/Users/augustindemeaux/clipfactory-data/bench/craft-refs/"
    "transcript_with_sentences.json"
)


async def main() -> int:
    if OUT.is_file():
        print(f"already there: {OUT}")
        return 0
    t = await transcribe(SRC)
    OUT.write_text(json.dumps(asdict(t), ensure_ascii=False), encoding="utf-8")
    print(f"words={len(t.words)} sentences={len(t.sentences)} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
