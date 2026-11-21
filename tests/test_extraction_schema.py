import pytest
from pydantic import ValidationError

from docgraph.extraction.models import ExtractionPayload


def valid_payload(evidence: str = "The job reads the input table.") -> dict[str, object]:
    return {
        "entities": [
            {
                "type": "Job",
                "name": "LOAD_JOB",
                "aliases": [],
                "description": "",
                "evidence": evidence,
                "confidence": 0.9,
            },
            {
                "type": "Dataset",
                "name": "INPUT_TABLE",
                "aliases": [],
                "description": "",
                "evidence": evidence,
                "confidence": 0.9,
            },
        ],
        "relationships": [
            {
                "source": "LOAD_JOB",
                "type": "READS_FROM",
                "target": "INPUT_TABLE",
                "evidence": evidence,
                "confidence": 0.8,
            }
        ],
    }


def test_schema_rejects_extra_fields() -> None:
    data = valid_payload()
    data["unexpected"] = True
    with pytest.raises(ValidationError):
        ExtractionPayload.model_validate(data)


def test_evidence_guard_rejects_made_up_quote() -> None:
    payload = ExtractionPayload.model_validate(
        valid_payload("The fabricated process writes a new dataset.")
    )
    with pytest.raises(ValueError, match="not found verbatim"):
        payload.require_evidence("The job reads the input table.")


def test_schema_rejects_relationship_endpoint_missing_from_entities() -> None:
    data = valid_payload()
    data["relationships"] = [
        {
            "source": "UNKNOWN_JOB",
            "type": "READS_FROM",
            "target": "INPUT_TABLE",
            "evidence": "The job reads the input table.",
            "confidence": 0.8,
        }
    ]
    with pytest.raises(ValidationError, match="endpoints"):
        ExtractionPayload.model_validate(data)
