"""Shared reviewer actions used by the CLI and review interface."""

from datetime import UTC, datetime
from typing import Any

from neo4j import Driver, ManagedTransaction

from docgraph.extraction.models import ExtractionPayload
from docgraph.feedback.store import FeedbackStore


def _update_suggestion(
    tx: ManagedTransaction, /, suggestion_id: str, decision: str, reviewer: str
) -> dict[str, Any] | None:
    record = tx.run(
        """MATCH (source:Entity:Dataset)-[suggestion:SUGGESTED_LINEAGE {id: $id}]->(target:Entity:Dataset)
        SET suggestion.status = $decision, suggestion.reviewed_at = $reviewed_at,
            suggestion.reviewed_by = $reviewer
        RETURN source.id AS source_id, target.id AS target_id, source.name AS source_name,
               target.name AS target_name, properties(suggestion) AS suggestion""",
        id=suggestion_id,
        decision=decision,
        reviewer=reviewer,
        reviewed_at=datetime.now(UTC).isoformat(),
    ).single()
    return record.data() if record else None


def review_lineage(
    driver: Driver,
    database: str,
    feedback: FeedbackStore,
    suggestion_id: str,
    decision: str,
    note: str = "",
    reviewer: str = "local-reviewer",
) -> dict[str, Any]:
    """Update Neo4j review status and save the corresponding SQLite example."""
    if decision not in {"accepted", "rejected"}:
        raise ValueError("decision must be accepted or rejected")
    with driver.session(database=database) as session:
        result = session.execute_write(_update_suggestion, suggestion_id, decision, reviewer)
    if result is None:
        raise KeyError(f"Suggestion not found: {suggestion_id}")
    suggestion = result["suggestion"]
    feedback.record_lineage(
        suggestion_id=suggestion_id,
        decision=decision,
        source_id=result["source_id"],
        target_id=result["target_id"],
        source_name=result["source_name"],
        target_name=result["target_name"],
        rationale=suggestion.get("rationale", ""),
        evidence=suggestion.get("evidence", []),
        reviewer_note=note,
        reviewer=reviewer,
        model_name=suggestion.get("model_name", "unknown"),
        prompt_version=suggestion.get("prompt_version", "unknown"),
    )
    return result


def save_extraction_correction(
    driver: Driver,
    database: str,
    feedback: FeedbackStore,
    source_document: str,
    chunk_id: str,
    corrected_data: dict[str, Any],
    note: str = "",
    reviewer: str = "local-reviewer",
) -> None:
    """Validate a correction against the stored source chunk, then save it."""
    payload = ExtractionPayload.model_validate(corrected_data)
    with driver.session(database=database) as session:
        record = session.run(
            "MATCH (c:Chunk {id: $chunk_id})-[:PART_OF]->(d:Document {id: $document_id}) "
            "RETURN c.text AS text",
            chunk_id=chunk_id,
            document_id=source_document,
        ).single()
    if record is None:
        raise KeyError(f"Chunk {chunk_id} was not found under document {source_document}")
    source_chunk = record["text"]
    payload.require_evidence(source_chunk)
    feedback.record_extraction(
        source_document=source_document,
        chunk_id=chunk_id,
        source_chunk=source_chunk,
        corrected_json=payload.model_dump(mode="json"),
        reviewer_note=note,
        reviewer=reviewer,
    )
