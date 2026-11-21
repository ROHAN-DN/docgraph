from datetime import UTC, datetime

from docgraph.extraction.models import (
    EntityType,
    ExtractedEntity,
    ExtractionPayload,
    ExtractionRecord,
)
from docgraph.resolution.resolver import resolve_records


def record(chunk_id: str, entities: list[ExtractedEntity]) -> ExtractionRecord:
    return ExtractionRecord(
        source_document="DOC-CUSTOMER",
        chunk_id=chunk_id,
        model_name="mock:model",
        prompt_version="v1",
        extracted_at=datetime.now(UTC),
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=None,
        extraction=ExtractionPayload(entities=entities, relationships=[]),
    )


def test_resolver_merges_explicit_aliases_but_keeps_types_separate() -> None:
    customer_identity = ExtractedEntity(
        type=EntityType.APPLICATION,
        name="Customer Identity Management",
        aliases=["CIM", "PartyHub"],
        evidence="CIM, also called PartyHub, maintains the party record.",
        confidence=0.9,
    )
    party_hub = ExtractedEntity(
        type=EntityType.APPLICATION,
        name="PartyHub",
        aliases=[],
        description="",
        evidence="PartyHub maintains the mastered party record.",
        confidence=0.85,
    )
    dataset_named_party_hub = ExtractedEntity(
        type=EntityType.DATASET,
        name="PartyHub",
        aliases=[],
        description="",
        evidence="The PartyHub table is a legacy extract.",
        confidence=0.7,
    )
    graph, report = resolve_records(
        [
            record("chunk-1", [customer_identity]),
            record("chunk-2", [party_hub, dataset_named_party_hub]),
        ],
        threshold=0.99,
    )

    applications = [entity for entity in graph.entities if entity.type == EntityType.APPLICATION]
    datasets = [entity for entity in graph.entities if entity.type == EntityType.DATASET]
    assert len(applications) == 1
    assert "PartyHub" in applications[0].aliases
    assert len(applications[0].provenance) == 2
    assert len(datasets) == 1
    assert len(report.candidates) == 1
    assert report.candidates[0].review_status == "pending"
