"""Idempotent, batched persistence for resolved entities and relationships."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from neo4j import Driver, ManagedTransaction

from docgraph.resolution.models import ResolvedGraph

DEFAULT_SCHEMA = Path(__file__).with_name("schema.cypher")


def apply_schema(driver: Driver, database: str, schema_path: Path = DEFAULT_SCHEMA) -> None:
    """Apply constraints and indexes from the schema script."""
    statements = [
        line.strip() for line in schema_path.read_text(encoding="utf-8").split(";") if line.strip()
    ]
    with driver.session(database=database) as session:
        for statement in statements:
            session.run(statement).consume()


def _store_entities(tx: ManagedTransaction, /, label: str, rows: list[dict[str, object]]) -> None:
    query = f"""
    UNWIND $rows AS row
    MERGE (e:Entity:{label} {{id: row.id}})
    SET e.entity_type = row.type,
        e.name = row.name,
        e.description = row.description,
        e.embedding = row.embedding,
        e.confidence = row.confidence,
        e.aliases = reduce(acc = coalesce(e.aliases, []) + row.aliases, x IN coalesce(e.aliases, []) + row.aliases |
            CASE WHEN x IN acc THEN acc ELSE acc + [x] END),
        e.provenance_json = row.provenance_json,
        e.source_document_ids = row.source_document_ids
    """
    tx.run(query, rows=rows).consume()


def _store_relationships(
    tx: ManagedTransaction, /, rel_type: str, rows: list[dict[str, object]]
) -> None:
    query = f"""
    UNWIND $rows AS row
    MATCH (source:Entity {{id: row.source_id}})
    MATCH (target:Entity {{id: row.target_id}})
    MERGE (source)-[r:{rel_type} {{id: row.id}}]->(target)
    SET r.provenance_json = row.provenance_json,
        r.source_document_ids = row.source_document_ids,
        r.confidence = row.confidence
    """
    tx.run(query, rows=rows).consume()


def _store_mentions(tx: ManagedTransaction, /, rows: list[dict[str, object]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (c:Chunk {id: row.chunk_id})
        MATCH (e:Entity {id: row.entity_id})
        MERGE (c)-[r:MENTIONS {id: row.id}]->(e)
        SET r.provenance_json = row.provenance_json,
            r.source_document_ids = row.source_document_ids,
            r.confidence = row.confidence
        """,
        rows=rows,
    ).consume()


def _verify_chunks(tx: ManagedTransaction, /, chunk_ids: list[str]) -> list[str]:
    record = tx.run(
        "UNWIND $ids AS id OPTIONAL MATCH (c:Chunk {id: id}) "
        "WITH id,c WHERE c IS NULL RETURN collect(id) AS missing",
        ids=chunk_ids,
    ).single()
    return record["missing"] if record else chunk_ids


def load_graph(driver: Driver, database: str, graph: ResolvedGraph, batch_size: int = 250) -> None:
    """Validate source chunks and load resolved graph facts in bounded transactions."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    apply_schema(driver, database)
    mention_map: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    source_chunk_ids = set()
    for entity in graph.entities:
        for provenance in entity.provenance:
            source_chunk_ids.add(provenance.chunk_id)
            mention_map[(provenance.chunk_id, entity.id)].append(provenance.model_dump())
    for relation in graph.relationships:
        for provenance in relation.provenance:
            source_chunk_ids.add(provenance.chunk_id)
    with driver.session(database=database) as session:
        missing = session.execute_read(_verify_chunks, sorted(source_chunk_ids))
    if missing:
        raise ValueError(f"Source chunks are missing from Neo4j: {', '.join(missing[:10])}")

    entity_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entity in graph.entities:
        entity_groups[entity.type.value].append(
            {
                "id": entity.id,
                "type": entity.type.value,
                "name": entity.name,
                "aliases": entity.aliases,
                "description": entity.description,
                "embedding": entity.embedding,
                "provenance_json": json.dumps([p.model_dump() for p in entity.provenance]),
                "source_document_ids": sorted({p.source_document for p in entity.provenance}),
                "confidence": max((p.confidence for p in entity.provenance), default=0.0),
            }
        )
    relation_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for relation in graph.relationships:
        relation_groups[relation.type.value].append(
            {
                "id": relation.id,
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "provenance_json": json.dumps([p.model_dump() for p in relation.provenance]),
                "source_document_ids": sorted({p.source_document for p in relation.provenance}),
                "confidence": max((p.confidence for p in relation.provenance), default=0.0),
            }
        )
    mention_rows = []
    for (chunk_id, entity_id), mention_provenance in mention_map.items():
        mention_id = hashlib.sha256(f"{chunk_id}\0{entity_id}".encode()).hexdigest()[:24]
        mention_rows.append(
            {
                "id": mention_id,
                "chunk_id": chunk_id,
                "entity_id": entity_id,
                "provenance_json": json.dumps(mention_provenance),
                "source_document_ids": sorted(
                    {str(item["source_document"]) for item in mention_provenance}
                ),
                "confidence": max(
                    (float(item["confidence"]) for item in mention_provenance), default=0.0
                ),
            }
        )

    with driver.session(database=database) as session:
        for label, rows in entity_groups.items():
            for start in range(0, len(rows), batch_size):
                session.execute_write(_store_entities, label, rows[start : start + batch_size])
        for rel_type, rows in relation_groups.items():
            for start in range(0, len(rows), batch_size):
                session.execute_write(
                    _store_relationships, rel_type, rows[start : start + batch_size]
                )
        for start in range(0, len(mention_rows), batch_size):
            session.execute_write(_store_mentions, mention_rows[start : start + batch_size])
