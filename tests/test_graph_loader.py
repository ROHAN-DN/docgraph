from docgraph.db.graph_loader import _store_entities, _store_relationships


class FakeTransaction:
    def __init__(self) -> None:
        self.query = ""
        self.parameters = {}

    def run(self, query: str, **parameters: object):
        self.query = query
        self.parameters = parameters
        return self

    def consume(self) -> None:
        return None


def test_entity_loader_uses_merge_and_native_neo4j_property_values() -> None:
    tx = FakeTransaction()
    _store_entities(
        tx,
        "Dataset",
        [
            {
                "id": "entity-1",
                "type": "Dataset",
                "name": "PAYMENT_FACT",
                "aliases": [],
                "description": "",
                "embedding": None,
                "confidence": 0.9,
                "provenance_json": '[{"source_document":"DOC-1"}]',
                "source_document_ids": ["DOC-1"],
            }
        ],
    )

    assert "MERGE (e:Entity:Dataset" in tx.query
    assert "e.provenance_json = row.provenance_json" in tx.query
    assert isinstance(tx.parameters["rows"][0]["provenance_json"], str)


def test_relationship_loader_merges_stable_identity_and_provenance() -> None:
    tx = FakeTransaction()
    _store_relationships(
        tx,
        "WRITES_TO",
        [
            {
                "id": "relationship-1",
                "source_id": "job-1",
                "target_id": "dataset-1",
                "provenance_json": "[]",
                "source_document_ids": ["DOC-1"],
                "confidence": 0.8,
            }
        ],
    )

    assert "MERGE (source)-[r:WRITES_TO {id: row.id}]->(target)" in tx.query
    assert "r.provenance_json = row.provenance_json" in tx.query
