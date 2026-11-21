"""Persist ingested documents and chunks in Neo4j."""

from typing import Any

from neo4j import Driver, ManagedTransaction

from docgraph.ingestion.models import IngestedDocument


def _replace_document(tx: ManagedTransaction, /, payload: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (d:Document {id: $document_id})
        SET d.filename = $filename,
            d.path = $path,
            d.file_type = $file_type,
            d.sha256 = $sha256,
            d.text = $text,
            d.ingested_at = $ingested_at
        WITH d
        OPTIONAL MATCH (old:Chunk)-[:PART_OF]->(d)
        DETACH DELETE old
        WITH d
        UNWIND $chunks AS item
        MERGE (c:Chunk {id: item.id})
        SET c.document_id = item.document_id,
            c.index = item.index,
            c.text = item.text,
            c.start_offset = item.start_offset,
            c.end_offset = item.end_offset
        MERGE (c)-[:PART_OF]->(d)
        """,
        **payload,
    ).consume()


def store_document(driver: Driver, database: str, document: IngestedDocument) -> None:
    """Replace one document's chunk set atomically, safe to rerun after edits."""
    payload: dict[str, Any] = {
        "document_id": document.document_id,
        "filename": document.filename,
        "path": document.path,
        "file_type": document.file_type,
        "sha256": document.sha256,
        "text": document.text,
        "ingested_at": document.ingested_at.isoformat(),
        "chunks": [chunk.model_dump() for chunk in document.chunks],
    }
    with driver.session(database=database) as session:
        session.execute_write(_replace_document, payload)
