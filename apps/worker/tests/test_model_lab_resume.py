"""Resume partial staging without spending before media prerequisites exist."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/model_lab/run.py"
SPEC = importlib.util.spec_from_file_location("lab_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_missing_media_path_is_rejected_before_run_creation(monkeypatch):
    monkeypatch.setenv("PATH", "/definitely-not-a-tools-directory")
    with pytest.raises(ValueError, match="before paid calls: ffmpeg, ffprobe"):
        MODULE.ensure_media_tools()


def test_resume_can_stage_unstarted_second_source_but_rejects_changed_input(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "source.mp4").write_bytes(b"media fixture")
    (shared / "transcript.json").write_text('{"words":[]}')
    meta = {
        "sha256": MODULE.sha256(shared / "source.mp4"),
        "transcript_sha256": MODULE.sha256(shared / "transcript.json"),
    }
    target = tmp_path / "not-yet-started"
    MODULE.stage_source(shared, target, meta, resume=True)
    MODULE.stage_source(shared, target, meta, resume=True)
    assert MODULE.sha256(target / "source.mp4") == meta["sha256"]
    (target / "transcript.json").write_text('{"words":["changed"]}')
    with pytest.raises(ValueError, match="resumed source content changed"):
        MODULE.stage_source(shared, target, meta, resume=True)
