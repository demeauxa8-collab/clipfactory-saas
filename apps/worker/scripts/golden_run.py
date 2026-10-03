"""Run a private reference through the unchanged real worker. Never deploys."""

import argparse
from pathlib import Path

from app.golden.harness import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "clipfactory-golden")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sources")
    parser.add_argument("--budget", default="3.00")
    parser.add_argument("--target-clips", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--asr-backend", choices=("openai", "openrouter"), default="openai")
    parser.add_argument(
        "--reuse-transcripts",
        action="store_true",
        help="Use hash-verified frozen transcripts as shared experimental inputs",
    )
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument(
        "--models-lock",
        type=Path,
        help="Alternative lock (e.g. models.premium.lock.toml); default models.lock.toml",
    )
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument(
        "--prior-ledger",
        type=Path,
        help="Carry earlier interrupted attempts into the same mission cap",
    )
    parser.add_argument("--pg-bin", type=Path, default=Path("/opt/homebrew/opt/postgresql@17/bin"))
    parser.add_argument("--judge", action=argparse.BooleanOptionalAction, default=True)
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
