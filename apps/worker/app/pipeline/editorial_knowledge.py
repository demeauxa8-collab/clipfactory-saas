"""Curated, source-audited editorial knowledge for the local Second Brain.

The source catalogue remains outside model prompts. The vault holds short,
reviewed hypotheses paired with their failure cases; neither is a learned
audience-performance rule.
"""

from __future__ import annotations

import json
from pathlib import Path

from .knowledge_vault import KnowledgeVault, load_vault_fixture

_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
_VAULT_FILE = _KNOWLEDGE_DIR / "editorial-retention-v1.json"
_CATALOG_FILE = _KNOWLEDGE_DIR / "editorial-retention-sources-v1.json"


def load_editorial_retention_vault() -> KnowledgeVault:
    """Return validated note and risk pairs, ready for context preparation."""
    vault = load_vault_fixture(_VAULT_FILE)
    catalogue = json.loads(_CATALOG_FILE.read_text(encoding="utf-8"))
    if (
        catalogue.get("schema_version") != "1.0"
        or catalogue.get("pack_id") != "editorial_retention_v1"
    ):
        raise ValueError("unsupported editorial source catalogue")
    source_ids = {item["note_id"] for item in catalogue["sources"]}
    if len(source_ids) != len(catalogue["sources"]):
        raise ValueError("duplicate editorial source IDs")
    vault_sources = {note.id for note in vault.notes if note.status == "raw_source"}
    if source_ids != vault_sources:
        raise ValueError("editorial source catalogue does not cover the vault")
    if any(
        not note.source_refs or any(ref.note_id not in source_ids for ref in note.source_refs)
        for note in vault.notes
        if note.status != "raw_source"
    ):
        raise ValueError("editorial advice lacks catalogue-backed provenance")
    advice = {note.id for note in vault.notes if note.status != "raw_source"}
    by_id = {note.id: note for note in vault.notes}
    paired: set[str] = set()
    for relation in vault.relations:
        if relation.relation != "risks":
            continue
        risk = by_id[relation.source_id]
        principle = by_id[relation.target_id]
        if risk.type not in {"problem", "counterexample"} or principle.type not in {
            "principle",
            "pattern",
        }:
            raise ValueError("editorial risk relation has invalid direction")
        paired.update((risk.id, principle.id))
    if paired != advice:
        raise ValueError("editorial advice must have a paired principle and risk")
    return vault


def load_editorial_retention_sources() -> dict[str, object]:
    """Return review metadata without inserting addresses into model context."""
    load_editorial_retention_vault()
    return json.loads(_CATALOG_FILE.read_text(encoding="utf-8"))
