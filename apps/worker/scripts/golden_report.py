import argparse
from pathlib import Path

from app.golden.reporting import recompute_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recompute golden metrics without paid requests")
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--sources-root", type=Path, default=Path.home() / "clipfactory-golden/sources"
    )
    args = parser.parse_args()
    result = recompute_report(args.run, args.sources_root)
    print(f"Measured {result['delivered_clips']} clips; no provider calls")
