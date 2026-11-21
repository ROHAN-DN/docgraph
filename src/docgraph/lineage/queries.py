"""Read-only queries used by the API and Streamlit graph explorer."""

import json
from typing import Any

from neo4j import Driver

from docgraph.lineage.suggestions import _canonical_arc


def search_entities(
    driver: Driver, database: str, query: str, limit: int = 25
) -> list[dict[str, Any]]:
    with driver.session(database=database) as session:
        return [
            record.data()
            for record in session.run(
                """MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($search_query)
                   OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) CONTAINS toLower($search_query))
                RETURN e.id AS id, e.name AS name, e.entity_type AS type,
                       e.aliases AS aliases, e.confidence AS confidence
                ORDER BY e.name LIMIT $limit""",
                search_query=query,
                limit=limit,
            )
        ]


def list_datasets(driver: Driver, database: str) -> list[dict[str, Any]]:
    with driver.session(database=database) as session:
        return [
            record.data()
            for record in session.run(
                "MATCH (d:Entity:Dataset) RETURN d.id AS id,d.name AS name "
                "ORDER BY d.name LIMIT 500"
            )
        ]


def dataset_exists(driver: Driver, database: str, dataset_id: str) -> bool:
    with driver.session(database=database) as session:
        record = session.run(
            "MATCH (d:Entity:Dataset {id: $id}) RETURN d.id AS id LIMIT 1", id=dataset_id
        ).single()
    return record is not None


def dataset_lineage(
    driver: Driver,
    database: str,
    dataset_id: str,
    direction: str,
    max_depth: int = 6,
) -> list[dict[str, Any]]:
    """Return directed upstream/downstream routes through jobs and derived datasets."""
    if direction not in {"upstream", "downstream"}:
        raise ValueError("direction must be upstream or downstream")
    if not 1 <= max_depth <= 10:
        raise ValueError("max_depth must be between 1 and 10")
    query = f"""
    MATCH p=(anchor:Entity:Dataset {{id: $id}})-[rels*1..{max_depth}]-(other:Entity:Dataset)
    WHERE other.id <> anchor.id
      AND all(r IN rels WHERE type(r) IN ['READS_FROM','WRITES_TO','PRODUCES','DERIVED_FROM'])
    RETURN nodes(p) AS path_nodes, rels AS path_relationships
    LIMIT 10000
    """
    with driver.session(database=database) as session:
        rows = list(session.run(query, id=dataset_id))
    paths = []
    seen = set()
    for row in rows:
        nodes, relationships = row["path_nodes"], row["path_relationships"]
        node_ids = [str(node.get("id")) for node in nodes]
        if len(node_ids) < 2 or len(relationships) != len(node_ids) - 1:
            continue
        arcs = [_canonical_arc(relationship) for relationship in relationships]
        forward = all(
            arc == (node_ids[index], node_ids[index + 1]) for index, arc in enumerate(arcs)
        )
        reverse = all(
            arc == (node_ids[index + 1], node_ids[index]) for index, arc in enumerate(arcs)
        )
        if direction == "downstream" and not forward:
            continue
        if direction == "upstream" and not reverse:
            continue
        display_nodes = nodes if direction == "downstream" else list(reversed(nodes))
        display_ids = node_ids if direction == "downstream" else list(reversed(node_ids))
        identity = tuple(display_ids)
        if identity in seen:
            continue
        seen.add(identity)
        evidence: list[str] = []
        for relationship in relationships:
            provenance_json = relationship.get("provenance_json", "[]")
            if isinstance(provenance_json, str):
                evidence.extend(item.get("evidence", "") for item in json.loads(provenance_json))
        paths.append(
            {
                "dataset_id": dataset_id,
                "direction": direction,
                "endpoint_id": display_ids[-1],
                "endpoint_name": display_nodes[-1].get("name", display_ids[-1]),
                "steps": [
                    {
                        "id": str(node.get("id")),
                        "name": node.get("name", node.get("entity_type", "entity")),
                        "type": node.get("entity_type", "Dataset"),
                    }
                    for node in display_nodes
                ],
                "evidence": list(dict.fromkeys(evidence))[:10],
            }
        )
    return paths


def list_suggestions(
    driver: Driver, database: str, status: str = "proposed", limit: int = 100
) -> list[dict[str, Any]]:
    with driver.session(database=database) as session:
        return [
            record.data()
            for record in session.run(
                """MATCH (source:Entity:Dataset)-[s:SUGGESTED_LINEAGE]->(target:Entity:Dataset)
                WHERE s.status = $status
                RETURN s.id AS id,source.id AS source_id,source.name AS source_name,
                       target.id AS target_id,target.name AS target_name,s.score AS score,
                       s.rationale AS rationale,s.evidence AS evidence,s.status AS status,
                       s.model_name AS model_name,s.prompt_version AS prompt_version
                ORDER BY s.score DESC LIMIT $limit""",
                status=status,
                limit=limit,
            )
        ]
