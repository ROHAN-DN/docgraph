"""Find, judge, and persist evidence-backed lineage suggestions."""

import hashlib
import json
import random
import re
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from neo4j import Driver, ManagedTransaction

from docgraph.extraction.providers import LLMProvider
from docgraph.lineage.models import (
    LineageCandidate,
    LineageEvidence,
    LineageJudgement,
    LineageSuggestion,
)
from docgraph.resolution.embeddings import cosine_similarity

PATH_QUERY_BASE = """
MATCH p=(a:Entity:Dataset)-[rels*1..{max_depth}]-(b:Entity:Dataset)
WHERE a.id < b.id
  AND all(r IN rels WHERE type(r) IN ['READS_FROM','WRITES_TO','PRODUCES','DERIVED_FROM'])
  AND NOT EXISTS {{ MATCH (a)-[:DERIVED_FROM]-(b) }}
  AND NOT EXISTS {{ MATCH (a)-[:SUGGESTED_LINEAGE]-(b) }}
RETURN nodes(p) AS path_nodes, rels AS path_relationships
LIMIT 10000
"""


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _similarity(left: list[str], right: list[str]) -> float:
    left_forms = [_norm(value) for value in left if _norm(value)]
    right_forms = [_norm(value) for value in right if _norm(value)]
    if not left_forms or not right_forms:
        return 0.0
    return max(
        SequenceMatcher(None, a, b, autojunk=False).ratio() for a in left_forms for b in right_forms
    )


def _canonical_arc(relationship: Any) -> tuple[str, str] | None:
    rel_type = relationship.type
    start_id = relationship.start_node.get("id")
    end_id = relationship.end_node.get("id")
    if rel_type in {"READS_FROM", "DERIVED_FROM"}:
        return str(end_id), str(start_id)
    if rel_type in {"WRITES_TO", "PRODUCES"}:
        return str(start_id), str(end_id)
    return None


def _provenance_items(properties: dict[str, Any]) -> list[dict[str, Any]]:
    value = properties.get("provenance_json", "[]")
    items = json.loads(value) if isinstance(value, str) else []
    return [dict(item) for item in items if item.get("evidence_id")]


def find_candidates(driver: Driver, database: str, max_depth: int = 6) -> list[LineageCandidate]:
    """Use directed interpretations of existing Cypher paths to find missing direct links."""
    if not 1 <= max_depth <= 10:
        raise ValueError("max_depth must be between 1 and 10")
    with driver.session(database=database) as session:
        nodes = {
            row["id"]: row
            for row in session.run(
                "MATCH (d:Entity:Dataset) RETURN d.id AS id, properties(d) AS props"
            )
        }
        path_rows = list(session.run(PATH_QUERY_BASE.format(max_depth=max_depth)))

    path_groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in path_rows:
        path_nodes = row["path_nodes"]
        path_rels = row["path_relationships"]
        node_ids = [str(node.get("id")) for node in path_nodes]
        if len(node_ids) < 3 or len(path_rels) != len(node_ids) - 1:
            continue
        arcs = [_canonical_arc(rel) for rel in path_rels]
        if any(arc is None for arc in arcs):
            continue
        forward = all(arcs[i] == (node_ids[i], node_ids[i + 1]) for i in range(len(arcs)))
        reverse = all(arcs[i] == (node_ids[i + 1], node_ids[i]) for i in range(len(arcs)))
        if not forward and not reverse:
            continue
        source_id, target_id = (
            (node_ids[0], node_ids[-1]) if forward else (node_ids[-1], node_ids[0])
        )
        if source_id not in nodes or target_id not in nodes:
            continue
        source_props, target_props = nodes[source_id]["props"], nodes[target_id]["props"]
        path_label = " -> ".join(
            str(node.get("name", node.get("entity_type", "entity"))) for node in path_nodes
        )
        key = (source_id, target_id)
        bucket = path_groups.setdefault(key, {"paths": set(), "neighbors": set(), "provenance": {}})
        bucket["paths"].add(path_label)
        bucket["neighbors"].update(
            str(node.get("name", node.get("id"))) for node in path_nodes[1:-1]
        )
        provenance_items = (
            _provenance_items(source_props)
            + _provenance_items(target_props)
            + [item for rel in path_rels for item in _provenance_items(dict(rel))]
        )
        for item in provenance_items:
            bucket["provenance"][item["evidence_id"]] = item

    candidates = []
    for (source_id, target_id), group in path_groups.items():
        source, target = nodes[source_id]["props"], nodes[target_id]["props"]
        source_name, target_name = (
            str(source.get("name", source_id)),
            str(target.get("name", target_id)),
        )
        source_aliases = [str(value) for value in source.get("aliases", [])]
        target_aliases = [str(value) for value in target.get("aliases", [])]
        name_score = _similarity([source_name, *source_aliases], [target_name, *target_aliases])
        source_embedding, target_embedding = source.get("embedding"), target.get("embedding")
        embedding_score = (
            cosine_similarity(list(source_embedding), list(target_embedding))
            if source_embedding and target_embedding
            else None
        )
        path_count = len(group["paths"])
        neighbor_count = len(group["neighbors"])
        path_score = min(path_count / 3, 1.0)
        neighbor_score = min(neighbor_count / 2, 1.0)
        if embedding_score is None:
            heuristic = 0.45 * path_score + 0.25 * neighbor_score + 0.30 * name_score
        else:
            heuristic = (
                0.30 * path_score
                + 0.15 * neighbor_score
                + 0.20 * name_score
                + 0.35 * embedding_score
            )
        provenance = [LineageEvidence.model_validate(item) for item in group["provenance"].values()]
        evidence = sorted({item.evidence for item in provenance})[:20]
        provenance = [item for item in provenance if item.evidence in evidence][:40]
        candidates.append(
            LineageCandidate(
                source_id=source_id,
                target_id=target_id,
                source_name=source_name,
                target_name=target_name,
                path_support=path_count,
                shared_neighbors=sorted(group["neighbors"], key=str.casefold),
                name_similarity=name_score,
                embedding_similarity=embedding_score,
                heuristic_score=heuristic,
                paths=sorted(group["paths"]),
                evidence=evidence,
                provenance=provenance,
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.heuristic_score, candidate.source_name.casefold()),
    )


def _render_prompt(template: str, candidate: LineageCandidate, feedback_examples: str = "") -> str:
    replacements = {
        "source_name": candidate.source_name,
        "target_name": candidate.target_name,
        "paths": json.dumps(candidate.paths, ensure_ascii=False),
        "shared_neighbors": json.dumps(candidate.shared_neighbors, ensure_ascii=False),
        "name_similarity": f"{candidate.name_similarity:.3f}",
        "embedding_similarity": "unavailable"
        if candidate.embedding_similarity is None
        else f"{candidate.embedding_similarity:.3f}",
        "evidence_quotes": json.dumps(candidate.evidence, ensure_ascii=False),
    }
    replacements["feedback_examples"] = feedback_examples or "No reviewed examples yet."
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def judge_candidate(
    candidate: LineageCandidate,
    *,
    provider: LLMProvider,
    prompt_template: str,
    prompt_version: str = "v1",
    max_retries: int = 2,
    feedback_examples: str = "",
) -> tuple[LineageJudgement, int, int]:
    """Get LLM judgement and reject citations not present in graph evidence."""
    prompt = _render_prompt(prompt_template, candidate, feedback_examples)
    last_error: Exception | None = None
    input_tokens = output_tokens = 0
    for attempt in range(max_retries + 1):
        try:
            response = provider.generate(prompt)
            input_tokens += response.input_tokens
            output_tokens += response.output_tokens
            judgement = LineageJudgement.model_validate_json(response.text)
            return (
                judgement.require_supplied_evidence(candidate.evidence),
                input_tokens,
                output_tokens,
            )
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                prompt += (
                    "\n\nYour previous response failed JSON or evidence validation. Return corrected JSON only."
                    f" Validation issue: {str(exc)[:400]}"
                )
                time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.2))
    raise ValueError(
        f"LLM judgement failed for {candidate.source_name} -> {candidate.target_name}: {last_error}"
    ) from last_error


def make_suggestion(
    candidate: LineageCandidate,
    judgement: LineageJudgement,
    provider: LLMProvider,
    prompt_version: str = "v1",
) -> LineageSuggestion:
    identity = f"{candidate.source_id}\0{candidate.target_id}"
    suggestion_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
    score = 0.55 * candidate.heuristic_score + 0.45 * judgement.confidence
    return LineageSuggestion(
        id=suggestion_id,
        source_id=candidate.source_id,
        target_id=candidate.target_id,
        score=score,
        rationale=judgement.rationale,
        evidence=judgement.evidence,
        provenance=[item for item in candidate.provenance if item.evidence in judgement.evidence],
        model_name=f"{provider.provider_name}:{provider.model}",
        prompt_version=prompt_version,
        created_at=datetime.now(UTC).isoformat(),
        path_support=candidate.path_support,
        shared_neighbors=candidate.shared_neighbors,
        name_similarity=candidate.name_similarity,
        embedding_similarity=candidate.embedding_similarity,
    )


def _store_suggestions(tx: ManagedTransaction, /, rows: list[dict[str, object]]) -> None:
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (source:Entity:Dataset {id: row.source_id})
        MATCH (target:Entity:Dataset {id: row.target_id})
        MERGE (source)-[s:SUGGESTED_LINEAGE {id: row.id}]->(target)
        ON CREATE SET s.status = 'proposed', s.created_at = row.created_at
        SET s.score = row.score, s.rationale = row.rationale, s.evidence = row.evidence,
            s.provenance_json = row.provenance_json,
            s.model_name = row.model_name, s.prompt_version = row.prompt_version,
            s.path_support = row.path_support, s.shared_neighbors = row.shared_neighbors,
            s.name_similarity = row.name_similarity, s.embedding_similarity = row.embedding_similarity
        """,
        rows=rows,
    ).consume()


def store_suggestions(
    driver: Driver, database: str, suggestions: list[LineageSuggestion], batch_size: int = 250
) -> None:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    rows = []
    for suggestion in suggestions:
        row = suggestion.model_dump(exclude={"provenance"})
        row["provenance_json"] = json.dumps([item.model_dump() for item in suggestion.provenance])
        rows.append(row)
    with driver.session(database=database) as session:
        for start in range(0, len(rows), batch_size):
            session.execute_write(_store_suggestions, rows[start : start + batch_size])


def run_suggestions(
    *,
    driver: Driver,
    database: str,
    provider: LLMProvider,
    prompt_template: str,
    prompt_version: str = "v1",
    score_threshold: float = 0.50,
    max_depth: int = 6,
    limit: int | None = None,
    usage_log: str | Path = "logs/lineage-usage.jsonl",
    feedback_examples: str = "",
) -> list[LineageSuggestion]:
    """Find and judge candidates, then persist plausible links as proposed only."""
    if not 0 <= score_threshold <= 1:
        raise ValueError("score_threshold must be between 0 and 1")
    candidates = find_candidates(driver, database, max_depth=max_depth)
    selected = [
        candidate for candidate in candidates if candidate.heuristic_score >= score_threshold
    ]
    if limit is not None:
        selected = selected[:limit]
    suggestions: list[LineageSuggestion] = []
    usage_path = Path(usage_log)
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in selected:
        try:
            judgement, input_tokens, output_tokens = judge_candidate(
                candidate,
                provider=provider,
                prompt_template=prompt_template,
                prompt_version=prompt_version,
                feedback_examples=feedback_examples,
            )
            event = {
                "event": "lineage_judgement",
                "source_id": candidate.source_id,
                "target_id": candidate.target_id,
                "model_name": f"{provider.provider_name}:{provider.model}",
                "prompt_version": prompt_version,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "plausible": judgement.plausible,
            }
            with usage_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event) + "\n")
            if judgement.plausible:
                suggestions.append(make_suggestion(candidate, judgement, provider, prompt_version))
        except Exception as exc:
            with usage_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "event": "lineage_judgement_failed",
                            "source_id": candidate.source_id,
                            "target_id": candidate.target_id,
                            "error": str(exc),
                        }
                    )
                    + "\n"
                )
    store_suggestions(driver, database, suggestions)
    return suggestions
