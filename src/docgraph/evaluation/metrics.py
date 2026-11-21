"""Alias-aware entity and relationship metrics against the hand-labeled gold set."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from docgraph.extraction.models import ExtractionRecord


class MetricCounts(BaseModel):
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None


class EvaluationResult(BaseModel):
    run_id: str
    model_name: str
    prompt_version: str
    evaluated_documents: int
    gold_documents: int
    entity: MetricCounts
    relationship: MetricCounts


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _forms(name: str, aliases: list[str] | None = None) -> set[str]:
    return {form for value in [name, *(aliases or [])] if (form := normalize(value))}


def _matched_pairs(predicted: list[Any], expected: list[Any], matches: Any) -> int:
    """Maximum bipartite matching so one prediction cannot satisfy two gold facts."""
    gold_to_pred: dict[int, int] = {}

    def visit(pred_index: int, seen: set[int]) -> bool:
        for gold_index, gold_item in enumerate(expected):
            if gold_index in seen or not matches(predicted[pred_index], gold_item):
                continue
            seen.add(gold_index)
            if gold_index not in gold_to_pred or visit(gold_to_pred[gold_index], seen):
                gold_to_pred[gold_index] = pred_index
                return True
        return False

    return sum(visit(index, set()) for index in range(len(predicted)))


def _counts(tp: int, predicted: int, expected: int) -> MetricCounts:
    precision = tp / predicted if predicted else None
    recall = tp / expected if expected else None
    f1 = (
        (2 * precision * recall / (precision + recall))
        if precision is not None and recall is not None and precision + recall
        else (0.0 if precision == 0 or recall == 0 else None)
    )
    return MetricCounts(
        true_positive=tp,
        false_positive=predicted - tp,
        false_negative=expected - tp,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _read_gold(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {document["document_id"]: document for document in payload["documents"]}


def _read_predictions(paths: list[Path]) -> list[ExtractionRecord]:
    records = []
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if line.strip():
                    try:
                        records.append(ExtractionRecord.model_validate_json(line))
                    except Exception as exc:
                        raise ValueError(
                            f"Invalid prediction at {path}:{line_number}: {exc}"
                        ) from exc
    return records


def _merge_mentions(mentions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[int, int]]:
    parent = list(range(len(mentions)))

    def find(item: int) -> int:
        if parent[item] != item:
            parent[item] = find(parent[item])
        return parent[item]

    for left in range(len(mentions)):
        for right in range(left + 1, len(mentions)):
            if (
                mentions[left]["type"] == mentions[right]["type"]
                and mentions[left]["forms"] & mentions[right]["forms"]
            ):
                parent[find(right)] = find(left)
    groups: dict[int, dict[str, Any]] = {}
    root_to_group: dict[int, int] = {}
    mapping: dict[int, int] = {}
    for index, mention in enumerate(mentions):
        root = find(index)
        if root not in groups:
            root_to_group[root] = len(groups)
            groups[root] = {"type": mention["type"], "forms": set(), "members": []}
        groups[root]["forms"].update(mention["forms"])
        groups[root]["members"].append(index)
        mapping[index] = root_to_group[root]
    return list(groups.values()), mapping


def _evaluate_group(
    records: list[ExtractionRecord],
    gold_docs: dict[str, dict[str, Any]],
    run_id: str,
    model: str,
    prompt: str,
) -> EvaluationResult:
    by_doc: dict[str, dict[str, list[Any]]] = defaultdict(lambda: {"mentions": [], "relations": []})
    for record in records:
        if record.source_document not in gold_docs:
            continue
        doc = by_doc[record.source_document]
        local: dict[str, int] = {}
        for entity in record.extraction.entities:
            index = len(doc["mentions"])
            local[entity.name.casefold()] = index
            doc["mentions"].append(
                {"type": entity.type.value, "forms": _forms(entity.name, entity.aliases)}
            )
        for relation in record.extraction.relationships:
            doc["relations"].append(
                (
                    relation.type.value,
                    local.get(relation.source.casefold()),
                    local.get(relation.target.casefold()),
                )
            )

    entity_tp = entity_predicted = entity_expected = 0
    relation_tp = relation_predicted = relation_expected = 0
    evaluated = 0
    for document_id, doc in by_doc.items():
        evaluated += 1
        predicted_entities, mention_group = _merge_mentions(doc["mentions"])
        gold = gold_docs[document_id]
        gold_entities = [
            {
                "id": entity["id"],
                "type": entity["type"],
                "forms": _forms(entity["name"], entity.get("aliases", [])),
            }
            for entity in gold["entities"]
        ]

        def entity_matches(pred: dict[str, Any], expected: dict[str, Any]) -> bool:
            return pred["type"] == expected["type"] and bool(pred["forms"] & expected["forms"])

        tp = _matched_pairs(predicted_entities, gold_entities, entity_matches)
        entity_tp += tp
        entity_predicted += len(predicted_entities)
        entity_expected += len(gold_entities)

        gold_by_id = {entity["id"]: entity for entity in gold_entities}
        expected_relations = []
        for relation in gold["relationships"]:
            source_entity = gold_by_id.get(relation["source"])
            target_entity = gold_by_id.get(relation["target"])
            if source_entity and target_entity:
                expected_relations.append(
                    {
                        "type": relation["type"],
                        "source_forms": source_entity["forms"],
                        "target_forms": target_entity["forms"],
                    }
                )
        predicted_relations = []
        seen_relations = set()
        for relation_type, source_index, target_index in doc["relations"]:
            if source_index is None or target_index is None:
                continue
            source_group, target_group = mention_group[source_index], mention_group[target_index]
            identity = (relation_type, source_group, target_group)
            if identity in seen_relations:
                continue
            seen_relations.add(identity)
            predicted_relations.append(
                {
                    "type": relation_type,
                    "source_forms": predicted_entities[source_group]["forms"],
                    "target_forms": predicted_entities[target_group]["forms"],
                }
            )

        def relation_matches(pred: dict[str, Any], expected: dict[str, Any]) -> bool:
            return (
                pred["type"] == expected["type"]
                and bool(pred["source_forms"] & expected["source_forms"])
                and bool(pred["target_forms"] & expected["target_forms"])
            )

        relation_tp += _matched_pairs(predicted_relations, expected_relations, relation_matches)
        relation_predicted += len(predicted_relations)
        relation_expected += len(expected_relations)

    return EvaluationResult(
        run_id=run_id,
        model_name=model,
        prompt_version=prompt,
        evaluated_documents=evaluated,
        gold_documents=len(gold_docs),
        entity=_counts(entity_tp, entity_predicted, entity_expected),
        relationship=_counts(relation_tp, relation_predicted, relation_expected),
    )


def evaluate(paths: list[Path], gold_path: Path) -> list[EvaluationResult]:
    gold_docs = _read_gold(gold_path)
    grouped: dict[tuple[str, str, str], list[ExtractionRecord]] = defaultdict(list)
    for path in paths:
        # Each input file represents one extraction run; never pool separate runs into one score.
        file_records = _read_predictions([path])
        for record in file_records:
            grouped[(path.stem, record.model_name, record.prompt_version)].append(record)
    if not grouped:
        raise ValueError("Prediction files contain no extraction records")
    return [
        _evaluate_group(group, gold_docs, run_id, model, prompt)
        for (run_id, model, prompt), group in sorted(grouped.items())
    ]


def discover_prediction_files(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() == ".jsonl":
        return [source]
    if source.is_dir():
        return sorted(source.rglob("*.jsonl"), key=lambda path: path.as_posix().casefold())
    raise FileNotFoundError(f"Expected an extraction JSONL file or directory: {source}")


def write_results(results: list[EvaluationResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps([item.model_dump() for item in results], indent=2) + "\n", encoding="utf-8"
    )
    fields = [
        "run_id",
        "model_name",
        "prompt_version",
        "evaluated_documents",
        "gold_documents",
        "task",
        "true_positive",
        "false_positive",
        "false_negative",
        "precision",
        "recall",
        "f1",
    ]
    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for task in ("entity", "relationship"):
                metric = getattr(result, task)
                writer.writerow(
                    {
                        "run_id": result.run_id,
                        "model_name": result.model_name,
                        "prompt_version": result.prompt_version,
                        "evaluated_documents": result.evaluated_documents,
                        "gold_documents": result.gold_documents,
                        "task": task,
                        **metric.model_dump(),
                    }
                )
    _write_chart(results, output_dir / "results.png")


def _write_chart(results: list[EvaluationResult], output_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f"{item.model_name}\n{item.prompt_version}\n{item.run_id}" for item in results]
    entity_f1 = [item.entity.f1 if item.entity.f1 is not None else math.nan for item in results]
    relation_f1 = [
        item.relationship.f1 if item.relationship.f1 is not None else math.nan for item in results
    ]
    positions = list(range(len(results)))
    width = 0.36
    figure, axis = plt.subplots(figsize=(max(8, len(results) * 1.5), 5))
    axis.bar([x - width / 2 for x in positions], entity_f1, width, label="Entity F1")
    axis.bar([x + width / 2 for x in positions], relation_f1, width, label="Relationship F1")
    axis.set_ylabel("F1")
    axis.set_ylim(0, 1)
    axis.set_xticks(positions, labels, rotation=20, ha="right")
    axis.set_title("DocGraph extraction evaluation")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)
