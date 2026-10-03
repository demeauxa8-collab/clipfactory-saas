"""Freeze only user-approved sources from a private TOML configuration."""

import argparse
from pathlib import Path

from app.golden.sources import freeze_source, read_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sources")
    args = parser.parse_args()
    for source in read_sources(args.config, args.sources):
        metadata = freeze_source(source, args.root)
        print(f"Frozen source verified: {source['id']}, {metadata['duration']} seconds", flush=True)


if __name__ == "__main__":
    main()
