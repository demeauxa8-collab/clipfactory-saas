from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_sources(config: Path, selected: str | None = None) -> list[dict]:
    document = tomllib.loads(config.read_text())
    sources = document["sources"]
    ids = [source["id"] for source in sources]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate source IDs")
    for source in sources:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", source["id"]):
            raise ValueError("invalid YouTube ID")
        if not all(source["campaign"].get(key) for key in ("audience", "niche", "tone", "goal")):
            raise ValueError("incomplete campaign brief")
        if len(source["campaign"].get("example_hooks", [])) != 3:
            raise ValueError("three example hooks required")
    if selected:
        requested = selected.split(",")
        if not set(requested) <= set(ids):
            raise ValueError("unknown selected source")
        sources = [source for source in sources if source["id"] in requested]
    return sources


def verify_source(directory: Path) -> dict:
    metadata = json.loads((directory / "meta.json").read_text())
    if sha256(directory / "source.mp4") != metadata["sha256"]:
        raise ValueError("immutable source hash mismatch")
    return metadata


def freeze_source(source: dict, root: Path, *, yt_dlp: str = "yt-dlp") -> dict:
    """Freeze once. An existing complete source is verified and never overwritten."""
    directory = root / source["id"]
    if (directory / "meta.json").exists():
        return verify_source(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    media = directory / "source.mp4"
    if media.exists():
        raise ValueError("incomplete source directory: inspect instead of overwriting")
    url = "https://www.youtube.com/watch?v=" + source["id"]
    raw = subprocess.run(
        [yt_dlp, "--skip-download", "--dump-json", "--no-warnings", url],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    data = json.loads(raw.stdout)
    # Every alternative is capped at 720p. No unrestricted 'best' fallback.
    subprocess.run(
        [
            yt_dlp,
            "-f",
            "bv[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]",
            "--merge-output-format",
            "mp4",
            "--no-playlist",
            "--remote-components",
            "ejs:github",
            "--no-warnings",
            "--quiet",
            "--retries",
            "5",
            "-o",
            str(media),
            url,
        ],
        check=True,
        timeout=1800,
    )
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "json",
            str(media),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if json.loads(probe.stdout)["streams"][0]["height"] > 720:
        raise ValueError("source exceeds 720p")
    metadata = {
        "id": source["id"],
        "title": data["title"],
        "duration": data["duration"],
        "language": data.get("language"),
        "voices": source["voices"],
        "voices_basis": source.get("voices_basis", "provisional; verify during human review"),
        "downloaded_at": datetime.now(UTC).isoformat(),
        "sha256": sha256(media),
        "heatmap_available": bool(data.get("heatmap")),
    }
    (directory / "heatmap.json").write_text(json.dumps({"points": data.get("heatmap")}) + "\n")
    (directory / "meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    for path in directory.iterdir():
        if path.is_file():
            path.chmod(0o400)
    return metadata
