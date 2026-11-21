from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from docgraph import api


def test_api_query_routes_with_stubbed_driver(monkeypatch) -> None:
    api.app.dependency_overrides[api.get_driver] = lambda: object()
    monkeypatch.setattr(
        api, "search_entities", lambda *_args: [{"id": "1", "name": "PAYMENT_FACT"}]
    )
    monkeypatch.setattr(api, "dataset_exists", lambda *_args: True)
    monkeypatch.setattr(api, "dataset_lineage", lambda *_args: [{"endpoint_name": "PAYMENT_INPUT"}])
    monkeypatch.setattr(api, "list_suggestions", lambda *_args: [{"id": "suggestion-1"}])
    client = TestClient(api.app)
    try:
        assert client.get("/entities", params={"q": "payment"}).json()[0]["name"] == "PAYMENT_FACT"
        assert (
            client.get("/datasets/dataset-1/lineage/upstream").json()[0]["endpoint_name"]
            == "PAYMENT_INPUT"
        )
        assert client.get("/suggestions").json()[0]["id"] == "suggestion-1"
    finally:
        api.app.dependency_overrides.clear()


def test_api_maps_service_unavailable_to_503(monkeypatch) -> None:
    class OfflineDriver:
        closed = False

        def verify_connectivity(self) -> None:
            raise ServiceUnavailable("Neo4j is offline")

        def close(self) -> None:
            self.closed = True

    driver = OfflineDriver()
    monkeypatch.setattr(api.GraphDatabase, "driver", lambda *_args, **_kwargs: driver)
    response = TestClient(api.app).get("/health")

    assert response.status_code == 503
    assert response.json()["detail"].startswith("Neo4j is unavailable")
    assert driver.closed is True


def test_feedback_routes_use_shared_service_functions(monkeypatch) -> None:
    api.app.dependency_overrides[api.get_driver] = lambda: object()
    api.app.dependency_overrides[api.get_feedback_store] = lambda: object()
    monkeypatch.setattr(
        api, "review_lineage", lambda *_args: {"source_name": "INPUT", "target_name": "OUTPUT"}
    )
    monkeypatch.setattr(api, "save_extraction_correction", lambda *_args: None)
    client = TestClient(api.app)
    try:
        reviewed = client.post(
            "/suggestions/suggestion-1/feedback",
            json={"decision": "accepted", "note": "Evidence supports the relation."},
        )
        corrected = client.post(
            "/feedback/extractions",
            json={
                "source_document": "DOC-1",
                "chunk_id": "chunk-1",
                "corrected_output": {"entities": [], "relationships": []},
            },
        )
    finally:
        api.app.dependency_overrides.clear()

    assert reviewed.status_code == 200
    assert reviewed.json()["source_name"] == "INPUT"
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "saved"
