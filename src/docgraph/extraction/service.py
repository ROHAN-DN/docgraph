"""Run evidence-grounded structured extraction with retry and usage logging."""

import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path

from docgraph.extraction.cache import ExtractionCache
from docgraph.extraction.models import ExtractionPayload, ExtractionRecord
from docgraph.extraction.providers import Generation, LLMProvider


class ExtractionError(Exception):
    """Raised when a chunk cannot be extracted after all configured attempts."""


def _with_chunk(template: str, chunk_text: str, feedback_examples: str = "") -> str:
    if "{{ chunk_text }}" not in template:
        raise ValueError("prompt template must contain {{ chunk_text }}")
    return template.replace(
        "{{ feedback_examples }}", feedback_examples or "No reviewed examples yet."
    ).replace("{{ chunk_text }}", chunk_text)


def _cost(
    input_tokens: int, output_tokens: int, input_rate: float | None, output_rate: float | None
) -> float | None:
    if input_rate is None or output_rate is None:
        return None
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def _append_usage(path: str | Path, event: dict[str, object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def extract_chunk(
    *,
    source_document: str,
    chunk_id: str,
    chunk_text: str,
    provider: LLMProvider,
    prompt_template: str,
    prompt_version: str,
    cache: ExtractionCache,
    max_retries: int = 2,
    retry_base_seconds: float = 1.0,
    input_rate: float | None = None,
    output_rate: float | None = None,
    usage_log: str | Path = "logs/extraction-usage.jsonl",
    feedback_examples: str = "",
) -> ExtractionRecord:
    """Extract one chunk; only evidence-checked responses enter the cache."""
    prompt = _with_chunk(prompt_template, chunk_text, feedback_examples)
    model_name = f"{provider.provider_name}:{provider.model}"
    cache_key = cache.key(model_name, prompt_version, prompt, chunk_id, chunk_text)
    generation = cache.get(cache_key)
    cache_hit = generation is not None
    last_error: Exception | None = None
    attempts = 0
    total_input_tokens = 0
    total_output_tokens = 0

    if generation is None:
        for attempt in range(max_retries + 1):
            attempts = attempt + 1
            try:
                generation = provider.generate(prompt)
                total_input_tokens += generation.input_tokens
                total_output_tokens += generation.output_tokens
                payload = ExtractionPayload.model_validate_json(generation.text).require_evidence(
                    chunk_text
                )
                generation = Generation(generation.text, total_input_tokens, total_output_tokens)
                cache.put(cache_key, generation)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                correction = (
                    "\n\nYour previous response failed schema or evidence validation. Correct it and return only the required JSON."
                    f"\nValidation issue: {str(exc)[:500]}"
                )
                prompt += correction
                time.sleep(retry_base_seconds * (2**attempt) + random.uniform(0, 0.25))

    if generation is None or last_error is not None:
        _append_usage(
            usage_log,
            {
                "event": "extraction_failed",
                "source_document": source_document,
                "chunk_id": chunk_id,
                "model_name": model_name,
                "prompt_version": prompt_version,
                "attempts": attempts,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "estimated_cost_usd": _cost(
                    total_input_tokens, total_output_tokens, input_rate, output_rate
                ),
                "error": str(last_error),
            },
        )
        raise ExtractionError(f"Extraction failed for {chunk_id}: {last_error}") from last_error

    payload = ExtractionPayload.model_validate_json(generation.text).require_evidence(chunk_text)
    cost = (
        0.0
        if cache_hit
        else _cost(generation.input_tokens, generation.output_tokens, input_rate, output_rate)
    )
    record = ExtractionRecord(
        source_document=source_document,
        chunk_id=chunk_id,
        model_name=model_name,
        prompt_version=prompt_version,
        extracted_at=datetime.now(UTC),
        input_tokens=0 if cache_hit else generation.input_tokens,
        output_tokens=0 if cache_hit else generation.output_tokens,
        estimated_cost_usd=cost,
        cache_hit=cache_hit,
        extraction=payload,
    )
    _append_usage(
        usage_log,
        {
            "event": "extraction_succeeded",
            "source_document": source_document,
            "chunk_id": chunk_id,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "attempts": attempts,
            "cache_hit": cache_hit,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "estimated_cost_usd": cost,
        },
    )
    return record
