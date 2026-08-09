from dataclasses import replace

from app.models import Transcript, TranscriptWord
from app.pipeline.editorial_qc import EditorialQCPolicy, evaluate_editorial_qc
from app.pipeline.edl import (
    EditIntentPlan,
    EditShotIntent,
    EffectIntent,
    InclusiveWordRange,
    compile_edit_intent,
)


def _transcript(*words: str) -> Transcript:
    entries = [
        TranscriptWord(word=word, start=index * 0.30, end=index * 0.30 + 0.25)
        for index, word in enumerate(words)
    ]
    return Transcript(text=" ".join(words), words=entries)


def _compiled(
    transcript: Transcript,
    shots: tuple[EditShotIntent, ...],
):
    return compile_edit_intent(
        EditIntentPlan("2.0", "A clear editorial promise.", shots),
        transcript,
        source_duration_ms=10_000,
    )


def _shot(
    shot_id: str,
    role: str,
    start: int,
    end: int,
    *,
    caption_theme: str = "standard_karaoke",
    effects: tuple[EffectIntent, ...] = (),
) -> EditShotIntent:
    return EditShotIntent(
        shot_id=shot_id,
        role=role,  # type: ignore[arg-type]
        from_word_id=start,
        to_word_id=end,
        caption_theme=caption_theme,  # type: ignore[arg-type]
        effects=effects,
    )


def test_passes_a_complete_self_contained_edit() -> None:
    transcript = _transcript("Discover", "the", "result", "because", "it", "works")
    edl = _compiled(
        transcript,
        (
            _shot("hook", "hook", 0, 1),
            _shot("proof", "proof", 2, 3),
            _shot("payoff", "payoff", 4, 5),
        ),
    )

    report = evaluate_editorial_qc(
        edl,
        transcript,
        policy=EditorialQCPolicy(
            required_word_ranges=(InclusiveWordRange(2, 3),),
            protected_word_ranges=(InclusiveWordRange(4, 5),),
        ),
    )

    assert report.status == "pass"
    assert report.caption_occurrences == 6
    assert report.captioned_occurrences == 6
    assert report.caption_coverage == 1.0
    assert report.cut_count == 2


def test_rejects_when_first_beat_is_not_a_hook_proof_or_reaction() -> None:
    transcript = _transcript("Here", "is", "the", "proof")
    edl = _compiled(
        transcript,
        (_shot("setup", "setup", 0, 1), _shot("payoff", "payoff", 2, 3)),
    )

    report = evaluate_editorial_qc(edl, transcript)

    assert report.status == "reject"
    assert [finding.code for finding in report.findings] == ["opening_role"]


def test_final_payoff_or_cta_is_policy_controlled() -> None:
    transcript = _transcript("Start", "with", "proof", "subscribe")
    edl = _compiled(
        transcript,
        (_shot("hook", "hook", 0, 1), _shot("cta", "cta", 2, 3)),
    )

    report = evaluate_editorial_qc(
        edl,
        transcript,
        policy=EditorialQCPolicy(final_roles=frozenset({"payoff"})),
    )

    assert report.status == "reject"
    assert report.findings[0].code == "final_role"


def test_required_and_protected_ranges_are_checked_against_compiled_shots() -> None:
    transcript = _transcript("Hook", "context", "must", "stay", "together", "now")
    edl = _compiled(
        transcript,
        (_shot("hook", "hook", 0, 2), _shot("payoff", "payoff", 3, 5)),
    )

    report = evaluate_editorial_qc(
        edl,
        transcript,
        policy=EditorialQCPolicy(
            required_word_ranges=(InclusiveWordRange(1, 4),),
            protected_word_ranges=(InclusiveWordRange(2, 3),),
        ),
    )

    assert report.status == "reject"
    assert {finding.code for finding in report.findings} == {
        "required_range_missing",
        "protected_range_split",
    }


def test_weak_opening_reference_is_repairable_fallback() -> None:
    transcript = _transcript("This", "is", "the", "answer")
    edl = _compiled(
        transcript,
        (_shot("hook", "hook", 0, 1), _shot("payoff", "payoff", 2, 3)),
    )

    report = evaluate_editorial_qc(edl, transcript)

    assert report.status == "pass_with_fallback"
    assert report.findings[0].code == "weak_opening_reference"
    assert report.findings[0].fallback == "prepend_context_or_choose_a_self_contained_hook"


def test_self_contained_question_is_not_flagged_for_an_internal_pronoun() -> None:
    transcript = _transcript("Est", "ce", "qu'on", "gagne")
    edl = _compiled(
        transcript,
        (_shot("hook", "hook", 0, 2), _shot("payoff", "payoff", 3, 3)),
    )

    report = evaluate_editorial_qc(edl, transcript)

    assert report.status == "pass"
    assert all(finding.code != "weak_opening_reference" for finding in report.findings)


def test_caption_coverage_counts_replayed_word_occurrences() -> None:
    transcript = _transcript("Look", "at", "this", "proof")
    edl = _compiled(
        transcript,
        (
            _shot("hook", "hook", 0, 1),
            _shot("replay", "proof", 0, 1, caption_theme="none"),
            _shot("payoff", "payoff", 2, 3),
        ),
    )

    report = evaluate_editorial_qc(edl, transcript)

    assert report.status == "pass_with_fallback"
    assert report.caption_occurrences == 6
    assert report.captioned_occurrences == 4
    assert report.caption_coverage == 4 / 6
    assert any(finding.code == "caption_coverage" for finding in report.findings)


def test_effect_and_cut_density_return_fallbacks() -> None:
    transcript = _transcript("A", "B", "C", "D", "E", "F")
    effects = (EffectIntent("punch_in", at_word_id=0),)
    edl = _compiled(
        transcript,
        (
            _shot("hook", "hook", 0, 0, effects=effects),
            _shot("proof", "proof", 1, 1),
            _shot("reaction", "reaction", 2, 2),
            _shot("payoff", "payoff", 3, 5),
        ),
    )

    report = evaluate_editorial_qc(
        edl,
        transcript,
        policy=EditorialQCPolicy(max_effects_per_second=0.01, max_cuts_per_second=0.01),
    )

    assert report.status == "pass_with_fallback"
    assert {finding.code for finding in report.findings} == {"effect_density", "cut_density"}


def test_rejects_an_invalid_final_transition_even_if_compiler_was_bypassed() -> None:
    transcript = _transcript("Strong", "proof", "clear", "result")
    edl = _compiled(
        transcript,
        (_shot("hook", "hook", 0, 1), _shot("payoff", "payoff", 2, 3)),
    )
    invalid_final = replace(edl.shots[-1], transition_out="reveal")
    edl = replace(edl, shots=(*edl.shots[:-1], invalid_final))

    report = evaluate_editorial_qc(edl, transcript)

    assert report.status == "reject"
    assert report.findings[0].code == "final_transition"
