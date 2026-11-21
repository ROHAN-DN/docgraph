import json

from docgraph.lineage.queries import dataset_lineage
from docgraph.lineage.suggestions import find_candidates


class FakeNode(dict):
    pass


class FakeRelationship(dict):
    def __init__(self, rel_type: str, start_node: FakeNode, end_node: FakeNode) -> None:
        super().__init__(provenance_json="[]")
        self.type = rel_type
        self.start_node = start_node
        self.end_node = end_node


class FakeSession:
    def __init__(self, datasets, paths, query_log) -> None:
        self.datasets = datasets
        self.paths = paths
        self.query_log = query_log

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query: str, **_parameters):
        self.query_log.append(query)
        if "RETURN d.id AS id, properties(d) AS props" in query:
            return [{"id": item["id"], "props": item} for item in self.datasets]
        if "RETURN nodes(p) AS path_nodes" in query:
            return self.paths
        return []


class FakeDriver:
    def __init__(self, datasets, paths) -> None:
        self.datasets = datasets
        self.paths = paths
        self.query_log = []

    def session(self, **_kwargs):
        return FakeSession(self.datasets, self.paths, self.query_log)


def make_graph_driver() -> tuple[FakeDriver, FakeNode, FakeNode, FakeNode]:
    source = FakeNode(
        id="a",
        name="PAYMENT_FACT",
        entity_type="Dataset",
        aliases=[],
        embedding=None,
        provenance_json=json.dumps([]),
    )
    job = FakeNode(id="job", name="LOAD_PAYMENT", entity_type="Job")
    target = FakeNode(
        id="b",
        name="PAYMENT_FACT",
        entity_type="Dataset",
        aliases=[],
        embedding=None,
        provenance_json=json.dumps([]),
    )
    reads = FakeRelationship("READS_FROM", job, source)
    writes = FakeRelationship("WRITES_TO", job, target)
    driver = FakeDriver(
        [source, target],
        [{"path_nodes": [source, job, target], "path_relationships": [reads, writes]}],
    )
    return driver, source, job, target


def test_suggestion_candidate_uses_directed_job_path_and_shared_neighbor() -> None:
    driver, _source, _job, _target = make_graph_driver()

    candidates = find_candidates(driver, "neo4j", max_depth=4)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert (candidate.source_id, candidate.target_id) == ("a", "b")
    assert candidate.shared_neighbors == ["LOAD_PAYMENT"]
    assert candidate.path_support == 1
    assert abs(candidate.heuristic_score - 0.575) < 1e-9
    assert any("rels*1..4" in query for query in driver.query_log)


def test_dataset_lineage_returns_downstream_path_in_data_flow_direction() -> None:
    driver, _source, _job, _target = make_graph_driver()

    paths = dataset_lineage(driver, "neo4j", "a", "downstream", max_depth=3)

    assert len(paths) == 1
    assert paths[0]["endpoint_id"] == "b"
    assert [step["id"] for step in paths[0]["steps"]] == ["a", "job", "b"]
