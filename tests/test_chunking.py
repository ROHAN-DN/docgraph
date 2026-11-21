from docgraph.ingestion.loader import chunk_text


def test_chunking_respects_size_overlap_and_offsets() -> None:
    text = ("Northstar writes the payment settlement event.\n\n" * 12).strip()

    chunks = chunk_text(text, "DOC-1", chunk_size=120, overlap=24)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 120 for chunk in chunks)
    assert all(text[chunk.start_offset : chunk.end_offset] == chunk.text for chunk in chunks)
    assert all(
        left.end_offset > right.start_offset
        for left, right in zip(chunks, chunks[1:], strict=False)
    )


def test_chunking_rejects_invalid_overlap() -> None:
    try:
        chunk_text("some text", "DOC-1", chunk_size=10, overlap=10)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("invalid overlap should fail")
