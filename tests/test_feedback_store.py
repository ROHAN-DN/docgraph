from docgraph.feedback.store import FeedbackStore


def test_recent_lineage_decision_becomes_a_prompt_example(tmp_path) -> None:
    store = FeedbackStore(tmp_path / "feedback.sqlite3")
    shared = {
        "suggestion_id": "suggestion-1",
        "source_id": "a",
        "target_id": "b",
        "source_name": "PAYMENT_INPUT",
        "target_name": "PAYMENT_FACT",
        "rationale": "They share an enrichment job.",
        "evidence": ["The job reads PAYMENT_INPUT."],
        "reviewer_note": "The cited job writes the fact table.",
        "reviewer": "test-reviewer",
        "model_name": "mock:model",
        "prompt_version": "v1",
    }
    store.record_lineage(decision="rejected", **shared)
    store.record_lineage(decision="accepted", **shared)

    examples = store.examples("lineage")

    assert len(examples) == 1
    assert examples[0]["decision"] == "accepted"
    assert "PAYMENT_FACT" in store.render_examples("lineage")


def test_extraction_correction_is_available_for_few_shot_use(tmp_path) -> None:
    store = FeedbackStore(tmp_path / "feedback.sqlite3")
    store.record_extraction(
        source_document="DOC-1",
        chunk_id="chunk-1",
        source_chunk="The job reads INPUT_TABLE.",
        corrected_json={"entities": [], "relationships": []},
        reviewer_note="Keep the exact table name.",
        reviewer="test-reviewer",
    )

    example = store.examples("extraction")[0]

    assert example["source_chunk"] == "The job reads INPUT_TABLE."
    assert example["corrected_output"] == {"entities": [], "relationships": []}
