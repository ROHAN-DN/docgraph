"""Resolve repeated entity mentions using aliases, lexical similarity, and embeddings."""

import hashlib
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, cast

from docgraph.extraction.models import EntityType, ExtractionRecord, RelationshipType
from docgraph.resolution.embeddings import EmbeddingProvider, cosine_similarity
from docgraph.resolution.models import (
    MergeCandidate,
    MergeReport,
    Provenance,
    ResolvedEntity,
    ResolvedGraph,
    ResolvedRelationship,
)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]


def read_records(path: Path) -> list[ExtractionRecord]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    records.append(ExtractionRecord.model_validate_json(line))
                except Exception as exc:
                    raise ValueError(
                        f"Invalid extraction JSONL at line {line_number}: {exc}"
                    ) from exc
    return records


def _find(parent: list[int], item: int) -> int:
    if parent[item] != item:
        parent[item] = _find(parent, parent[item])
    return parent[item]


def resolve_records(
    records: list[ExtractionRecord],
    *,
    threshold: float = 0.86,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[ResolvedGraph, MergeReport]:
    """Group same-type mentions, preserve evidence, and return a reviewable merge report."""
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    mentions: list[dict[str, Any]] = []
    local_indexes: list[dict[str, int]] = []
    for record in records:
        local: dict[str, int] = {}
        for entity in record.extraction.entities:
            local[entity.name.casefold()] = len(mentions)
            mentions.append(
                {
                    "type": entity.type,
                    "name": entity.name.strip(),
                    "aliases": sorted({alias.strip() for alias in entity.aliases if alias.strip()}),
                    "description": entity.description.strip(),
                    "provenance": Provenance(
                        evidence_id=_stable_id(record.chunk_id, entity.name, entity.evidence),
                        source_document=record.source_document,
                        chunk_id=record.chunk_id,
                        evidence=entity.evidence,
                        model_name=record.model_name,
                        prompt_version=record.prompt_version,
                        confidence=entity.confidence,
                        extracted_at=record.extracted_at.isoformat(),
                    ),
                }
            )
        local_indexes.append(local)

    forms = [
        {
            _normalize(str(term))
            for term in [item["name"], *item["aliases"]]
            if _normalize(str(term))
        }
        for item in mentions
    ]
    embeddings: dict[str, list[float]] = {}
    embedding_model = None
    if embedding_provider and mentions:
        terms = sorted(
            {
                f"{item['type'].value}: {term}"
                for index, item in enumerate(mentions)
                for term in forms[index]
            }
        )
        vectors = embedding_provider.embed(terms)
        if len(vectors) != len(terms):
            raise ValueError(
                "embedding provider returned a different number of vectors than inputs"
            )
        embeddings = dict(zip(terms, vectors, strict=True))
        embedding_model = embedding_provider.model

    parent = list(range(len(mentions)))
    matched_pairs: list[tuple[int, int, float, set[str]]] = []
    for left in range(len(mentions)):
        for right in range(left + 1, len(mentions)):
            if (
                mentions[left]["type"] != mentions[right]["type"]
                or not forms[left]
                or not forms[right]
            ):
                continue
            exact_alias = bool(forms[left] & forms[right])
            lexical = max(
                SequenceMatcher(None, a, b, autojunk=False).ratio()
                for a in forms[left]
                for b in forms[right]
            )
            semantic = 0.0
            if embeddings:
                prefix = f"{mentions[left]['type'].value}: "
                semantic = max(
                    cosine_similarity(embeddings[prefix + a], embeddings[prefix + b])
                    for a in forms[left]
                    for b in forms[right]
                )
            score = (
                1.0
                if exact_alias
                else (0.55 * lexical + 0.45 * semantic if embeddings else lexical)
            )
            if score >= threshold:
                parent[_find(parent, right)] = _find(parent, left)
                methods = {"alias_or_normalized_exact"} if exact_alias else {"string_similarity"}
                if embeddings and not exact_alias:
                    methods.add("embedding_similarity")
                matched_pairs.append((left, right, score, methods))

    groups: dict[int, list[int]] = {}
    for index in range(len(mentions)):
        groups.setdefault(_find(parent, index), []).append(index)

    entities: list[ResolvedEntity] = []
    mention_to_entity: dict[int, str] = {}
    merge_candidates: list[MergeCandidate] = []
    for members in groups.values():
        counts: Counter[str] = Counter(_normalize(str(mentions[i]["name"])) for i in members)
        original_name: dict[str, str] = {}
        aliases: set[str] = set()
        descriptions: list[str] = []
        provenance: list[Provenance] = []
        for index in members:
            item = mentions[index]
            normalized_name = _normalize(str(item["name"]))
            original_name.setdefault(normalized_name, str(item["name"]))
            aliases.update(str(alias) for alias in item["aliases"])
            if str(item["name"]) != original_name[normalized_name]:
                aliases.add(str(item["name"]))
            if item["description"]:
                descriptions.append(str(item["description"]))
            provenance.append(cast(Provenance, item["provenance"]))
        canonical_normalized = sorted(counts, key=lambda name: (-counts[name], name))[0]
        canonical = original_name[canonical_normalized]
        aliases.discard(canonical)
        entity_type = cast(EntityType, mentions[members[0]]["type"])
        type_name = entity_type.value
        entity_id = _stable_id(type_name, canonical_normalized)
        for index in members:
            mention_to_entity[index] = entity_id
        entities.append(
            ResolvedEntity(
                id=entity_id,
                type=entity_type,
                name=canonical,
                aliases=sorted(aliases, key=str.casefold),
                description=max(descriptions, key=len) if descriptions else "",
                embedding=embeddings.get(f"{type_name}: {canonical_normalized}"),
                provenance=provenance,
            )
        )
        unique_names = sorted({str(mentions[i]["name"]) for i in members}, key=str.casefold)
        if len(unique_names) > 1:
            edges = [pair for pair in matched_pairs if pair[0] in members and pair[1] in members]
            merge_candidates.append(
                MergeCandidate(
                    entity_type=entity_type,
                    canonical_name=canonical,
                    member_names=unique_names,
                    aliases=sorted(aliases, key=str.casefold),
                    similarity_score=min((edge[2] for edge in edges), default=1.0),
                    matched_by=sorted({method for edge in edges for method in edge[3]}),
                )
            )

    relationship_provenance: dict[tuple[str, str, str], list[Provenance]] = {}
    for record_index, record in enumerate(records):
        for relation in record.extraction.relationships:
            source = local_indexes[record_index].get(relation.source.casefold())
            target = local_indexes[record_index].get(relation.target.casefold())
            if source is None or target is None:
                raise ValueError(f"Unresolved relationship endpoint in chunk {record.chunk_id}")
            identity = (mention_to_entity[source], relation.type.value, mention_to_entity[target])
            relationship_provenance.setdefault(identity, []).append(
                Provenance(
                    evidence_id=_stable_id(
                        record.chunk_id,
                        relation.source,
                        relation.type.value,
                        relation.target,
                        relation.evidence,
                    ),
                    source_document=record.source_document,
                    chunk_id=record.chunk_id,
                    evidence=relation.evidence,
                    model_name=record.model_name,
                    prompt_version=record.prompt_version,
                    confidence=relation.confidence,
                    extracted_at=record.extracted_at.isoformat(),
                )
            )

    relationships = [
        ResolvedRelationship(
            id=_stable_id(*identity),
            source_id=identity[0],
            type=RelationshipType(identity[1]),
            target_id=identity[2],
            provenance=provenance,
        )
        for identity, provenance in relationship_provenance.items()
    ]
    return (
        ResolvedGraph(
            embedding_model=embedding_model, entities=entities, relationships=relationships
        ),
        MergeReport(
            threshold=threshold, embedding_model=embedding_model, candidates=merge_candidates
        ),
    )


def write_resolution(
    graph: ResolvedGraph, report: MergeReport, graph_path: Path, report_path: Path
) -> None:
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(graph.model_dump_json(indent=2) + "\n", encoding="utf-8")
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
