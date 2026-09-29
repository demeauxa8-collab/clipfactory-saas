"""Pure assembly boundary for ClipFactory's local context-intelligence loop.

This module joins already validated artefacts.  It does not browse, call a
model, render media, or widen an edit scope.  The output binds one campaign
brief, optional reusable research, one editorial graph, one immutable vault
snapshot, and one bounded editorial question into a replayable bundle.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from .campaign_research import (
    CampaignResearchPack,
    campaign_fingerprint,
    is_reusable_research_pack,
)
from .campaign_research_quality import (
    CampaignResearchQuality,
    CampaignResearchQualityError,
    evaluate_campaign_research_quality,
)
from .editorial_beats import EditorialBeatGraph
from .editorial_context import (
    EDITORIAL_CONTEXT_SCHEMA_VERSION,
    EditorialQuestion,
    MaterializedCampaignResearch,
    SelectedEditorialNote,
    UnifiedEditorialContextPack,
    graph_digest,
    materialize_campaign_research,
)
from .editorial_retrieval import (
    RetrievalPolicy,
    RetrievalResult,
    editorial_question_digest,
    retrieve_editorial_evidence,
)
from .knowledge_ingestion import (
    KnowledgeIngestionError,
    KnowledgeVaultSnapshot,
    compose_vault_snapshot,
    materialize_campaign_brief,
    materialize_editorial_graph,
)
from .knowledge_tenant_authority import IssuedTenantVaultAuthority
from .knowledge_tenant_authority import Verifier as TenantVerifier
from .knowledge_vault import KnowledgeVault
from .research_attestation_authority import (
    IssuedResearchAttestations,
    ResearchAttestationAuthorityError,
    Verifier as ResearchAttestationVerifier,
    verify_research_attestations,
)

CONTEXT_INTELLIGENCE_SCHEMA_VERSION = "1.0"
_DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")


class ContextIntelligenceError(ValueError):
    """The assembled context artefacts do not describe the same authority scope."""


def _canonical_digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PreparedEditorialContext:
    """One replayable local context projection and its immutable vault source."""

    schema_version: Literal["1.0"]
    snapshot: KnowledgeVaultSnapshot
    retrieval: RetrievalResult
    context: UnifiedEditorialContextPack
    research_status: Literal["complete", "partial", "unavailable", "not_requested"]
    research_quality: CampaignResearchQuality | None
    bundle_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_INTELLIGENCE_SCHEMA_VERSION:
            raise ContextIntelligenceError("unsupported context-intelligence schema")
        if not isinstance(self.snapshot, KnowledgeVaultSnapshot):
            raise ContextIntelligenceError("snapshot must be a KnowledgeVaultSnapshot")
        if not isinstance(self.retrieval, RetrievalResult):
            raise ContextIntelligenceError("retrieval must be a RetrievalResult")
        if not isinstance(self.context, UnifiedEditorialContextPack):
            raise ContextIntelligenceError("context must be a UnifiedEditorialContextPack")
        if self.research_status not in {
            "complete",
            "partial",
            "unavailable",
            "not_requested",
        }:
            raise ContextIntelligenceError("research_status is invalid")
        if self.research_quality is not None and not isinstance(
            self.research_quality, CampaignResearchQuality
        ):
            raise ContextIntelligenceError("research_quality must be a CampaignResearchQuality")
        self._validate_bindings()
        object.__setattr__(self, "bundle_digest", _canonical_digest(self.to_payload()))

    def _validate_bindings(self) -> None:
        question = self.context.question
        if self.retrieval.status != "ready":
            raise ContextIntelligenceError("blocked retrieval cannot become editorial context")
        if self.retrieval.question_digest != editorial_question_digest(question):
            raise ContextIntelligenceError("retrieval and context questions do not match")
        if self.retrieval.snapshot_digest != self.snapshot.digest:
            raise ContextIntelligenceError("retrieval and snapshot identities do not match")
        if self.retrieval.graph_digest != self.context.graph_digest:
            raise ContextIntelligenceError("retrieval and context graph identities do not match")
        retrieval_notes = {
            selection.note.note_id: selection.note for selection in self.retrieval.selections
        }
        context_notes = {
            selection.note.note_id: selection.note for selection in self.context.selected_notes
        }
        if retrieval_notes != context_notes:
            raise ContextIntelligenceError(
                "context notes must exactly match the authorised retrieval result"
            )
        if (
            self.snapshot.campaign_id != question.campaign_id
            or self.snapshot.source_id != question.source_id
        ):
            raise ContextIntelligenceError("snapshot and question scopes do not match")
        if self.snapshot.campaign_fingerprint != self.context.campaign_fingerprint:
            raise ContextIntelligenceError("campaign fingerprint binding does not match")
        if self.snapshot.research_digest != self.context.research_digest:
            raise ContextIntelligenceError("research digest binding does not match")
        if self.snapshot.graph_digest != self.context.graph_digest:
            raise ContextIntelligenceError("graph digest binding does not match")
        if self.research_status in {"complete", "partial"}:
            if self.context.research_digest is None:
                raise ContextIntelligenceError("available research requires a bound digest")
            if self.research_quality is not None and (
                self.research_quality.research_digest != self.context.research_digest
                or self.research_quality.status == "blocked"
            ):
                raise ContextIntelligenceError(
                    "research quality audit does not bind the available research"
                )
            if self.research_status == "complete" and (
                self.research_quality is None or self.research_quality.status != "trusted_complete"
            ):
                raise ContextIntelligenceError(
                    "complete research requires a trusted_complete quality audit"
                )
        elif self.context.research_digest is not None:
            raise ContextIntelligenceError("fallback context cannot carry a research digest")
        elif self.research_quality is not None:
            raise ContextIntelligenceError("fallback context cannot carry a research quality audit")
        for selected in self.context.selected_notes:
            version = self.snapshot.note_versions.get(selected.note.note_id)
            if version != selected.note.version:
                raise ContextIntelligenceError(
                    "context note is absent from the snapshot or has another version"
                )

    def to_payload(self) -> dict[str, object]:
        """Return only stable identities; the prompt payload remains on ``context``."""
        return {
            "campaign_id": self.snapshot.campaign_id,
            "context_digest": self.context.context_digest,
            "editorial_policy_version": self.context.editorial_policy_version,
            "graph_digest": self.context.graph_digest,
            "owner_id": self.snapshot.owner_id,
            "research_digest": self.context.research_digest,
            "research_status": self.research_status,
            "research_quality_digest": (
                self.research_quality.audit_digest if self.research_quality is not None else None
            ),
            "research_quality_status": (
                self.research_quality.status if self.research_quality is not None else None
            ),
            "retrieval_policy_digest": self.retrieval.policy_digest,
            "retrieval_result_digest": self.retrieval.result_digest,
            "schema_version": self.schema_version,
            "selected_note_versions": [
                [item.note.note_id, item.note.version] for item in self.context.selected_notes
            ],
            "snapshot_digest": self.snapshot.digest,
            "source_id": self.snapshot.source_id,
        }


def _context_from_retrieval(
    *,
    question: EditorialQuestion,
    retrieval: RetrievalResult,
    campaign_fingerprint_value: str,
    research_digest: str | None,
    editorial_policy_version: str,
) -> UnifiedEditorialContextPack:
    """Project only authorised retrieval selections into the Director context."""
    if retrieval.status != "ready":
        finding_ids = sorted(
            {note_id for finding in retrieval.findings for note_id in finding.note_ids}
        )
        suffix = ",".join(finding_ids) if finding_ids else "unspecified"
        raise ContextIntelligenceError(f"editorial retrieval is blocked: {suffix}")
    selected = tuple(
        SelectedEditorialNote(
            item.note,
            f"retrieval:{item.role};score={item.score};result={retrieval.result_digest[:12]}",
        )
        for item in retrieval.selections
    )
    allowed = tuple(sorted(item.note.note_id for item in selected))
    digest = UnifiedEditorialContextPack.compute_digest(
        schema_version=EDITORIAL_CONTEXT_SCHEMA_VERSION,
        question=question,
        campaign_fingerprint=campaign_fingerprint_value,
        research_digest=research_digest,
        graph_digest=retrieval.graph_digest,
        editorial_policy_version=editorial_policy_version,
        selected_notes=selected,
        allowed_ref_ids=allowed,
    )
    return UnifiedEditorialContextPack(
        schema_version=EDITORIAL_CONTEXT_SCHEMA_VERSION,
        question=question,
        campaign_fingerprint=campaign_fingerprint_value,
        research_digest=research_digest,
        graph_digest=retrieval.graph_digest,
        editorial_policy_version=editorial_policy_version,
        selected_notes=selected,
        allowed_ref_ids=allowed,
        context_digest=digest,
    )


def prepare_editorial_context(
    *,
    base_vault: KnowledgeVault,
    campaign: Mapping[str, Any],
    graph: EditorialBeatGraph,
    question: EditorialQuestion,
    owner_id: str,
    revision: str,
    editorial_policy_version: str,
    as_of: datetime,
    research_pack: CampaignResearchPack | None = None,
    research_attestations: IssuedResearchAttestations | None = None,
    research_attestation_verifier: ResearchAttestationVerifier | None = None,
    retrieval_policy: RetrievalPolicy | None = None,
    tenant_authority: IssuedTenantVaultAuthority | None = None,
    tenant_authority_verifier: TenantVerifier | None = None,
) -> PreparedEditorialContext:
    """Assemble one safe local context, falling back cleanly without research.

    Available research must still be reusable for this exact campaign and its
    own research-policy version at ``as_of``.  ``unavailable`` research is
    treated as an explicit fallback signal and is never materialized.
    """
    if not isinstance(base_vault, KnowledgeVault):
        raise ContextIntelligenceError("base_vault must be a KnowledgeVault")
    if not isinstance(campaign, Mapping):
        raise ContextIntelligenceError("campaign must be a mapping")
    if not isinstance(question, EditorialQuestion):
        raise ContextIntelligenceError("question must be an EditorialQuestion")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ContextIntelligenceError("as_of must be timezone-aware")

    brief = materialize_campaign_brief(campaign, question.campaign_id)
    graph_materialization = materialize_editorial_graph(
        graph,
        question.campaign_id,
        question.source_id,
    )
    expected_graph_digest = graph_digest(graph)
    if graph_materialization.graph_digest != expected_graph_digest:
        raise ContextIntelligenceError("graph materializers disagree on graph identity")

    research: MaterializedCampaignResearch | None = None
    research_status: Literal["complete", "partial", "unavailable", "not_requested"] = (
        "not_requested"
    )
    research_quality: CampaignResearchQuality | None = None
    if research_pack is not None:
        research_status = research_pack.status
        expected_research_fingerprint = campaign_fingerprint(
            campaign,
            research_policy_version=research_pack.research_policy_version,
        )
        if research_pack.campaign_fingerprint != expected_research_fingerprint:
            raise ContextIntelligenceError("research pack belongs to another campaign")
        if research_pack.status != "unavailable":
            if not is_reusable_research_pack(
                research_pack,
                campaign_fingerprint_value=expected_research_fingerprint,
                now=as_of,
                research_policy_version=research_pack.research_policy_version,
            ):
                raise ContextIntelligenceError("research pack is stale or incompatible")
            research = materialize_campaign_research(
                research_pack,
                question.campaign_id,
            )
            if research_attestations is not None and not isinstance(
                research_attestations, IssuedResearchAttestations
            ):
                raise ContextIntelligenceError(
                    "research source classifications require a signed authority envelope"
                )
            try:
                attestation_items = ()
                if research_attestations is not None:
                    if research_attestation_verifier is None:
                        raise ContextIntelligenceError(
                            "research source classifications require an authority verifier"
                        )
                    verified_attestations = verify_research_attestations(
                        research_attestations,
                        research_pack,
                        verifier=research_attestation_verifier,
                        owner_id=owner_id,
                        campaign_id=question.campaign_id,
                        now=as_of,
                    )
                    attestation_items = verified_attestations.attestations
                research_quality = evaluate_campaign_research_quality(
                    research_pack,
                    attestation_items,
                    as_of,
                )
            except (CampaignResearchQualityError, ResearchAttestationAuthorityError) as exc:
                raise ContextIntelligenceError("research quality evaluation failed") from exc
            if research_quality.status == "blocked":
                raise ContextIntelligenceError(
                    "available research cannot have a blocked quality audit"
                )
            if research_pack.status == "complete" and research_quality.status != "trusted_complete":
                raise ContextIntelligenceError(
                    "complete research requires a trusted_complete quality audit"
                )
        elif research_attestations is not None or research_attestation_verifier is not None:
            raise ContextIntelligenceError("unavailable research cannot carry source attestations")
    elif research_attestations is not None or research_attestation_verifier is not None:
        raise ContextIntelligenceError("research attestations require an available research pack")

    try:
        snapshot = compose_vault_snapshot(
            base_vault,
            brief,
            research,
            graph_materialization,
            owner_id=owner_id,
            campaign_id=question.campaign_id,
            source_id=question.source_id,
            revision=revision,
            tenant_authority=tenant_authority,
            tenant_authority_verifier=tenant_authority_verifier,
            authority_now=as_of,
        )
    except KnowledgeIngestionError as exc:
        raise ContextIntelligenceError("tenant vault authority rejected context assembly") from exc
    policy = retrieval_policy or RetrievalPolicy()
    if not isinstance(policy, RetrievalPolicy):
        raise ContextIntelligenceError("retrieval_policy must be a RetrievalPolicy")
    retrieval = retrieve_editorial_evidence(
        question,
        graph,
        snapshot,
        policy,
    )
    context = _context_from_retrieval(
        question=question,
        retrieval=retrieval,
        campaign_fingerprint_value=brief.campaign_fingerprint,
        research_digest=research.research_digest if research is not None else None,
        editorial_policy_version=editorial_policy_version,
    )
    return PreparedEditorialContext(
        CONTEXT_INTELLIGENCE_SCHEMA_VERSION,
        snapshot,
        retrieval,
        context,
        research_status,
        research_quality,
    )
