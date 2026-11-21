import json

from docgraph.extraction.cache import ExtractionCache
from docgraph.extraction.providers import Generation
from docgraph.extraction.service import extract_chunk


class MockProvider:
    provider_name = "mock"
    model = "mock-model"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> Generation:
        self.calls += 1
        return Generation(self.responses.pop(0), input_tokens=10, output_tokens=4)


def test_mock_llm_retries_caches_and_logs_usage(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("docgraph.extraction.service.time.sleep", lambda _: None)
    monkeypatch.setattr("docgraph.extraction.service.random.uniform", lambda _low, _high: 0)
    valid = json.dumps(
        {
            "entities": [
                {
                    "type": "Dataset",
                    "name": "PAYMENT_TABLE",
                    "aliases": [],
                    "description": "",
                    "evidence": "PAYMENT_TABLE stores settled rows.",
                    "confidence": 0.9,
                }
            ],
            "relationships": [],
        }
    )
    provider = MockProvider(["not json", valid])
    cache = ExtractionCache(tmp_path / "cache.sqlite3")
    usage_log = tmp_path / "usage.jsonl"
    arguments = {
        "source_document": "DOC-1",
        "chunk_id": "DOC-1::chunk-0000",
        "chunk_text": "PAYMENT_TABLE stores settled rows.",
        "provider": provider,
        "prompt_template": "Extract from this chunk: {{ chunk_text }}",
        "prompt_version": "v1",
        "cache": cache,
        "max_retries": 1,
        "retry_base_seconds": 0,
        "usage_log": usage_log,
    }

    first = extract_chunk(**arguments)
    second = extract_chunk(**arguments)

    assert provider.calls == 2
    assert first.extraction.entities[0].name == "PAYMENT_TABLE"
    assert first.input_tokens == 20
    assert first.output_tokens == 8
    assert second.cache_hit is True
    assert second.input_tokens == 0
    events = [json.loads(line) for line in usage_log.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["extraction_succeeded", "extraction_succeeded"]
