import argparse
from pathlib import Path

from app.golden.review import generate_review

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a private portable blind review page")
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(generate_review(args.run))
