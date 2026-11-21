import os
import uuid

import pytest
from neo4j import GraphDatabase

from docgraph.db.graph_loader import load_graph
from docgraph.extraction.models import EntityType
from docgraph.resolution.models import Provenance, ResolvedEntity, ResolvedGraph


@pytest.mark.integration
def test_graph_loader_round_trips_provenance_in_neo4j() -> None:
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    suffix = uuid.uuid4().hex[:12]
    document_id = f"IT-DOC-{suffix}"
    chunk_id = f"{document_id}::chunk-0000"
    entity_id = f"it-entity-{suffix}"
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            session.run(
                "MERGE (d:Document {id:$document_id}) "
                "MERGE (c:Chunk {id:$chunk_id})-[:PART_OF]->(d) "
                "SET c.document_id=$document_id,c.index=0,c.text='Synthetic fixture evidence.'",
                document_id=document_id,
                chunk_id=chunk_id,
            ).consume()
        graph = ResolvedGraph(
            entities=[
                ResolvedEntity(
                    id=entity_id,
                    type=EntityType.DATASET,
                    name=f"INTEGRATION_{suffix}",
                    aliases=[],
                    provenance=[
                        Provenance(
                            evidence_id=f"evidence-{suffix}",
                            source_document=document_id,
                            chunk_id=chunk_id,
                            evidence="Synthetic fixture evidence.",
                            model_name="mock:model",
                            prompt_version="test",
                            confidence=0.9,
                            extracted_at="2026-01-01T00:00:00+00:00",
                        )
                    ],
                )
            ],
            relationships=[],
        )

        load_graph(driver, database, graph, batch_size=1)

        with driver.session(database=database) as session:
            record = session.run(
                "MATCH (c:Chunk {id:$chunk_id})-[m:MENTIONS]->(e:Entity:Dataset {id:$entity_id}) "
                "RETURN e.name AS name,m.provenance_json AS provenance",
                chunk_id=chunk_id,
                entity_id=entity_id,
            ).single()
            assert record is not None
            assert record["name"] == f"INTEGRATION_{suffix}"
            assert document_id in record["provenance"]
    finally:
        with driver.session(database=database) as session:
            session.run(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                ids=[document_id, chunk_id, entity_id],
            ).consume()
        driver.close()
