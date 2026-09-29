"""Deterministic editorial quality-control for compiled ClipFactory EDLs.

The EDL compiler validates that an edit is safe to render.  This module answers
the separate editorial question: is the rendered order intelligible, complete
and conservative enough to publish?  It deliberately has no provider, model or
renderer dependency, so a caller can run it before spending render capacity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..models import Transcript
from .edl import CompiledEDL, CompiledShot, InclusiveWordRange, ShotRole

EditorialQCStatus = Literal["pass", "pass_with_fallback", "reject"]
EditorialQCSeverity = Literal["fallback", "reject"]

_NORMALIZE_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)
_LEADING_CONNECTORS = frozenset(
    {"and", "but", "so", "then", "et", "mais", "donc", "alors", "puis"}
)


@dataclass(frozen=True)
class EditorialQCFinding:
    """One stable, machine-readable editorial QC finding."""

    code: str
    severity: EditorialQCSeverity
    message: str
    shot_id: str | None = None
    fallback: str | None = None


@dataclass(frozen=True)
class EditorialQCPolicy:
    """Explicit, account-configurable policy for an otherwise pure QC pass.

    Required ranges must appear in full. Protected ranges may be absent, but a
    shot that intersects one may not cut through it.  Caption coverage counts
    *occurrences*, rather than unique source words, because a replayed word has
    to be captioned each time it appears on the output timeline.
    """

    opening_roles: frozenset[ShotRole] = frozenset({"hook", "proof", "reaction"})
    final_roles: frozenset[ShotRole] = frozenset({"payoff", "cta"})
    required_word_ranges: tuple[InclusiveWordRange, ...] = ()
    protected_word_ranges: tuple[InclusiveWordRange, ...] = ()
    min_caption_coverage: float = 1.0
    max_effects_per_second: float = 0.40
    max_cuts_per_second: float = 1.25
    weak_opening_scan_words: int = 5
    weak_opening_tokens: frozenset[str] = frozenset(
        {
            "c",
            "ce",
            "cet",
            "cette",
            "ces",
            "cela",
            "ca",
            "il",
            "elle",
            "ils",
            "elles",
            "lui",
            "leur",
            "they",
            "them",
            "this",
            "that",
            "it",
            "he",
            "she",
            "these",
            "those",
        }
    )


@dataclass(frozen=True)
class EditorialQCReport:
    """Deterministic outcome and the measurements used to produce it."""

    status: EditorialQCStatus
    findings: tuple[EditorialQCFinding, ...]
    caption_occurrences: int
    captioned_occurrences: int
    caption_coverage: float
    effect_count: int
    effect_density_per_second: float
    cut_count: int
    cut_density_per_second: float

    @property
    def passed(self) -> bool:
        """True when publishing is allowed, possibly after a local fallback."""
        return self.status != "reject"


def _normalized_tokens(text: str) -> tuple[str, ...]:
    return tuple(token for token in _NORMALIZE_TOKEN_RE.sub(" ", text.casefold()).split() if token)


def _policy_range_findings(
    ranges: tuple[InclusiveWordRange, ...],
    *,
    transcript: Transcript,
    label: str,
) -> list[EditorialQCFinding]:
    findings: list[EditorialQCFinding] = []
    for index, word_range in enumerate(ranges):
        if (
            word_range.from_word_id < 0
            or word_range.to_word_id < word_range.from_word_id
            or word_range.to_word_id >= len(transcript.words)
        ):
            findings.append(
                EditorialQCFinding(
                    code=f"invalid_{label}_range",
                    severity="reject",
                    message=(
                        f"{label} range {index} is outside the transcript: "
                        f"{word_range.from_word_id}..{word_range.to_word_id}"
                    ),
                )
            )
    return findings


def _covers_range(shot: CompiledShot, word_range: InclusiveWordRange) -> bool:
    return (
        shot.from_word_id <= word_range.from_word_id
        and shot.to_word_id >= word_range.to_word_id
    )


def _overlaps_range(shot: CompiledShot, word_range: InclusiveWordRange) -> bool:
    return not (
        shot.to_word_id < word_range.from_word_id
        or shot.from_word_id > word_range.to_word_id
    )


def _opening_weak_tokens(
    first_shot: CompiledShot,
    transcript: Transcript,
    *,
    scan_words: int,
    weak_tokens: frozenset[str],
) -> tuple[str, ...]:
    opening_word_ids = tuple(
        occurrence.word_id for occurrence in first_shot.word_occurrences[:scan_words]
    )
    tokens: list[str] = []
    for word_id in opening_word_ids:
        if 0 <= word_id < len(transcript.words):
            tokens.extend(_normalized_tokens(transcript.words[word_id].word))
    # A weak reference is a problem when it *opens* the clip (possibly after a
    # discourse connector), not merely because a complete sentence contains a
    # pronoun later.  For example, "Est-ce qu'on va gagner ?" is self-contained
    # even though its first five ASR words contain "ce".
    first_meaningful = next(
        (token for token in tokens if token not in _LEADING_CONNECTORS),
        None,
    )
    return (
        (first_meaningful,)
        if first_meaningful is not None and first_meaningful in weak_tokens
        else ()
    )


def evaluate_editorial_qc(
    edl: CompiledEDL,
    transcript: Transcript,
    *,
    policy: EditorialQCPolicy | None = None,
) -> EditorialQCReport:
    """Evaluate a compiled edit without mutating it or invoking an LLM.

    Structural and policy violations are rejected.  Correctable presentation
    issues are reported as ``pass_with_fallback`` together with a concrete,
    deterministic fallback action for the caller to apply before rendering.
    """
    active_policy = policy or EditorialQCPolicy()
    findings: list[EditorialQCFinding] = []

    if not edl.shots:
        findings.append(
            EditorialQCFinding(
                code="empty_edl",
                severity="reject",
                message="an editorial QC pass requires at least one compiled shot",
            )
        )
        return _report(edl, findings, active_policy)

    findings.extend(
        _policy_range_findings(
            active_policy.required_word_ranges, transcript=transcript, label="required"
        )
    )
    findings.extend(
        _policy_range_findings(
            active_policy.protected_word_ranges, transcript=transcript, label="protected"
        )
    )

    first_shot = edl.shots[0]
    if first_shot.role not in active_policy.opening_roles:
        findings.append(
            EditorialQCFinding(
                code="opening_role",
                severity="reject",
                message=(
                    f"first beat {first_shot.shot_id!r} has role {first_shot.role!r}; "
                    f"policy requires one of {sorted(active_policy.opening_roles)!r}"
                ),
                shot_id=first_shot.shot_id,
            )
        )

    weak_tokens = _opening_weak_tokens(
        first_shot,
        transcript,
        scan_words=active_policy.weak_opening_scan_words,
        weak_tokens=active_policy.weak_opening_tokens,
    )
    if weak_tokens:
        findings.append(
            EditorialQCFinding(
                code="weak_opening_reference",
                severity="fallback",
                message=(
                    "opening begins with weak contextual references/pronouns: "
                    f"{', '.join(weak_tokens)}"
                ),
                shot_id=first_shot.shot_id,
                fallback="prepend_context_or_choose_a_self_contained_hook",
            )
        )

    final_shot = edl.shots[-1]
    if final_shot.role not in active_policy.final_roles:
        findings.append(
            EditorialQCFinding(
                code="final_role",
                severity="reject",
                message=(
                    f"final beat {final_shot.shot_id!r} has role {final_shot.role!r}; "
                    f"policy requires one of {sorted(active_policy.final_roles)!r}"
                ),
                shot_id=final_shot.shot_id,
            )
        )
    if final_shot.transition_out != "hard_cut":
        findings.append(
            EditorialQCFinding(
                code="final_transition",
                severity="reject",
                message="final beat must end with a hard_cut transition",
                shot_id=final_shot.shot_id,
            )
        )

    for word_range in active_policy.required_word_ranges:
        if not any(_covers_range(shot, word_range) for shot in edl.shots):
            findings.append(
                EditorialQCFinding(
                    code="required_range_missing",
                    severity="reject",
                    message=(
                        "required word range is missing from the compiled edit: "
                        f"{word_range.from_word_id}..{word_range.to_word_id}"
                    ),
                )
            )
    for word_range in active_policy.protected_word_ranges:
        for shot in edl.shots:
            if _overlaps_range(shot, word_range) and not _covers_range(shot, word_range):
                findings.append(
                    EditorialQCFinding(
                        code="protected_range_split",
                        severity="reject",
                        message=(
                            f"shot {shot.shot_id!r} cuts through protected word range "
                            f"{word_range.from_word_id}..{word_range.to_word_id}"
                        ),
                        shot_id=shot.shot_id,
                    )
                )

    return _report(edl, findings, active_policy)


def _report(
    edl: CompiledEDL,
    findings: list[EditorialQCFinding],
    policy: EditorialQCPolicy,
) -> EditorialQCReport:
    """Attach occurrence/density metrics and their policy findings."""
    duration_seconds = edl.duration_ms / 1000 if edl.duration_ms > 0 else 0.0
    caption_occurrences = sum(len(shot.word_occurrences) for shot in edl.shots)
    captioned_occurrences = sum(
        len(shot.word_occurrences) for shot in edl.shots if shot.caption_theme != "none"
    )
    caption_coverage = (
        captioned_occurrences / caption_occurrences if caption_occurrences else 0.0
    )
    effect_count = sum(len(shot.effects) for shot in edl.shots)
    cut_count = max(0, len(edl.shots) - 1)
    effect_density = effect_count / duration_seconds if duration_seconds else 0.0
    cut_density = cut_count / duration_seconds if duration_seconds else 0.0

    if caption_coverage < policy.min_caption_coverage:
        findings.append(
            EditorialQCFinding(
                code="caption_coverage",
                severity="fallback",
                message=(
                    f"caption coverage is {captioned_occurrences}/{caption_occurrences} "
                    f"({caption_coverage:.1%}), below policy {policy.min_caption_coverage:.1%}"
                ),
                fallback="burn_standard_captions_for_uncovered_occurrences",
            )
        )
    if effect_density > policy.max_effects_per_second:
        findings.append(
            EditorialQCFinding(
                code="effect_density",
                severity="fallback",
                message=(
                    f"effect density is {effect_density:.2f}/s, above policy "
                    f"{policy.max_effects_per_second:.2f}/s"
                ),
                fallback="remove_lowest_priority_effects",
            )
        )
    if cut_density > policy.max_cuts_per_second:
        findings.append(
            EditorialQCFinding(
                code="cut_density",
                severity="fallback",
                message=(
                    f"cut density is {cut_density:.2f}/s, above policy "
                    f"{policy.max_cuts_per_second:.2f}/s"
                ),
                fallback="merge_adjacent_beats_or_use_fewer_cuts",
            )
        )

    if any(finding.severity == "reject" for finding in findings):
        status: EditorialQCStatus = "reject"
    elif findings:
        status = "pass_with_fallback"
    else:
        status = "pass"
    return EditorialQCReport(
        status=status,
        findings=tuple(findings),
        caption_occurrences=caption_occurrences,
        captioned_occurrences=captioned_occurrences,
        caption_coverage=caption_coverage,
        effect_count=effect_count,
        effect_density_per_second=effect_density,
        cut_count=cut_count,
        cut_density_per_second=cut_density,
    )
