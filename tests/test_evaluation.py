import json

from docgraph.evaluation.metrics import evaluate


def test_evaluator_scores_entities_and_direction_on_tiny_fixture(tmp_path) -> None:
    gold = {
        "documents": [
            {
                "document_id": "DOC-1",
                "entities": [
                    {"id": "input", "type": "Dataset", "name": "INPUT_TABLE", "aliases": ["INPUT"]},
                    {"id": "output", "type": "Dataset", "name": "OUTPUT_TABLE", "aliases": []},
                ],
                "relationships": [{"source": "input", "type": "WRITES_TO", "target": "output"}],
            }
        ]
    }
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps(gold), encoding="utf-8")
    records = [
        {
            "source_document": "DOC-1",
            "chunk_id": "chunk-1",
            "model_name": "mock:model",
            "prompt_version": "v1",
            "extracted_at": "2026-01-01T00:00:00Z",
            "input_tokens": 10,
            "output_tokens": 4,
            "estimated_cost_usd": None,
            "extraction": {
                "entities": [
                    {
                        "type": "Dataset",
                        "name": "INPUT",
                        "aliases": [],
                        "description": "",
                        "evidence": "INPUT feeds the output.",
                        "confidence": 0.9,
                    },
                    {
                        "type": "Dataset",
                        "name": "OUTPUT_TABLE",
                        "aliases": [],
                        "description": "",
                        "evidence": "OUTPUT_TABLE is derived.",
                        "confidence": 0.9,
                    },
                ],
                "relationships": [
                    {
                        "source": "INPUT",
                        "type": "WRITES_TO",
                        "target": "OUTPUT_TABLE",
                        "evidence": "INPUT feeds the output.",
                        "confidence": 0.8,
                    },
                    {
                        "source": "OUTPUT_TABLE",
                        "type": "WRITES_TO",
                        "target": "INPUT",
                        "evidence": "OUTPUT_TABLE is derived.",
                        "confidence": 0.7,
                    },
                ],
            },
        }
    ]
    predictions = tmp_path / "run-v1.jsonl"
    predictions.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    result = evaluate([predictions], gold_path)[0]

    assert result.evaluated_documents == 1
    assert result.entity.true_positive == 2
    assert result.entity.f1 == 1.0
    assert result.relationship.true_positive == 1
    assert result.relationship.false_positive == 1
    assert result.relationship.false_negative == 0
