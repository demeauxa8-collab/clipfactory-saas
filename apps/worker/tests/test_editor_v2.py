import pytest

from app.models import Transcript, TranscriptWord
from app.pipeline.editor_v2 import EditorV2Error, prepare_v2_edit
from app.pipeline.edl import EditIntentPlan, EditShotIntent


def _transcript() -> Transcript:
    return Transcript(
        text="preuve nette voici contexte conclusion maintenant",
        words=[
            TranscriptWord("preuve", 0.00, 0.35),
            TranscriptWord("nette", 0.36, 0.72),
            TranscriptWord("voici", 4.00, 4.30),
            TranscriptWord("contexte", 4.31, 4.75),
            TranscriptWord("conclusion", 8.00, 8.45),
            TranscriptWord("maintenant", 8.46, 8.95),
        ],
    )


def test_prepare_v2_edit_compiles_qcs_and_builds_occurrence_captions() -> None:
    transcript = _transcript()
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Proof, explanation, payoff.",
        shots=(
            EditShotIntent("hook", "proof", 0, 1, caption_theme="hook_bold"),
            EditShotIntent("setup", "setup", 2, 3),
            EditShotIntent("payoff", "payoff", 4, 5, caption_theme="proof_clean"),
        ),
    )

    prepared = prepare_v2_edit(
        plan,
        transcript,
        source_duration_ms=10_000,
    )

    assert prepared.qc.status == "pass"
    assert [shot.shot_id for shot in prepared.edl.shots] == ["hook", "setup", "payoff"]
    assert {cue.shot_id for cue in prepared.captions.cues} == {"hook", "setup", "payoff"}


def test_prepare_v2_edit_fails_closed_on_editorial_rejection() -> None:
    transcript = _transcript()
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Starts with context instead of a hook.",
        shots=(
            EditShotIntent("setup", "setup", 2, 3),
            EditShotIntent("payoff", "payoff", 4, 5),
        ),
    )

    with pytest.raises(EditorV2Error, match="opening_role"):
        prepare_v2_edit(plan, transcript, source_duration_ms=10_000)


def test_prepare_v2_edit_requires_explicit_preview_opt_in_for_fallbacks() -> None:
    transcript = _transcript()
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Valid edit with intentionally disabled captions.",
        shots=(
            EditShotIntent("hook", "proof", 0, 1, caption_theme="none"),
            EditShotIntent("payoff", "payoff", 4, 5, caption_theme="none"),
        ),
    )

    with pytest.raises(EditorV2Error, match="caption_coverage"):
        prepare_v2_edit(plan, transcript, source_duration_ms=10_000)

    preview = prepare_v2_edit(
        plan,
        transcript,
        source_duration_ms=10_000,
        allow_fallback_preview=True,
    )
    assert preview.qc.status == "pass_with_fallback"
    assert preview.captions.cues == ()
