"""Read supported document formats and produce overlap-aware chunks."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from docx import Document as WordDocument
from pypdf import PdfReader

from docgraph.ingestion.models import Chunk, IngestedDocument

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf", ".docx"}
_DOCUMENT_ID = re.compile(r"(?im)^\s*Document\s+ID\s*:\s*([A-Za-z0-9_.-]+)")


class DocumentLoadError(Exception):
    """Raised when a source file cannot be read or has no usable text."""


def clean_text(text: str) -> str:
    """Normalize line endings and whitespace without removing meaningful wording."""
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"[\t\f\v ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix in {".md", ".markdown", ".txt"}:
            return path.read_text(encoding="utf-8-sig")
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            document = WordDocument(str(path))
            paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
            tables = [
                " | ".join(cell.text.strip() for cell in row.cells)
                for table in document.tables
                for row in table.rows
            ]
            return "\n\n".join([*paragraphs, *tables])
    except Exception as exc:
        raise DocumentLoadError(f"Could not read {path.name}: {exc}") from exc
    raise DocumentLoadError(f"Unsupported file type: {path.suffix}")


def _preferred_boundary(text: str, start: int, end: int) -> int:
    """Prefer a nearby paragraph, line, or sentence end while honoring max size."""
    floor = start + max(1, (end - start) * 3 // 4)
    candidates = [text.rfind(token, floor, end) for token in ("\n\n", "\n", ". ", "; ")]
    boundary = max(candidates)
    if boundary > start:
        return boundary + (2 if text[boundary : boundary + 2] in {"\n\n", ". ", "; "} else 1)
    return end


def chunk_text(
    text: str, document_id: str, chunk_size: int = 1200, overlap: int = 200
) -> list[Chunk]:
    """Split text into bounded chunks; overlap is measured in characters."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    cleaned = clean_text(text)
    if not cleaned:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        if end < len(cleaned):
            end = _preferred_boundary(cleaned, start, end)
        body = cleaned[start:end].strip()
        if body:
            # Offsets are adjusted to exclude whitespace removed from each chunk edge.
            leading = len(cleaned[start:end]) - len(cleaned[start:end].lstrip())
            trailing = len(cleaned[start:end]) - len(cleaned[start:end].rstrip())
            actual_start = start + leading
            actual_end = end - trailing
            index = len(chunks)
            chunks.append(
                Chunk(
                    id=f"{document_id}::chunk-{index:04d}",
                    document_id=document_id,
                    index=index,
                    text=body,
                    start_offset=actual_start,
                    end_offset=actual_end,
                )
            )
        if end >= len(cleaned):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _document_id(path: Path, text: str) -> str:
    match = _DOCUMENT_ID.search(text)
    return match.group(1) if match else path.stem.lower().replace(" ", "-")


def load_document(path: Path, chunk_size: int = 1200, overlap: int = 200) -> IngestedDocument:
    """Load one supported document, hash its bytes, and chunk cleaned content."""
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise DocumentLoadError(f"Unsupported file type: {path.suffix}")
    try:
        raw = _read_file(path)
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise DocumentLoadError(f"Could not access {path.name}: {exc}") from exc
    text = clean_text(raw)
    if not text:
        raise DocumentLoadError(f"No extractable text in {path.name}")
    document_id = _document_id(path, text)
    return IngestedDocument(
        document_id=document_id,
        path=path.as_posix(),
        filename=path.name,
        file_type=cast(
            Literal["md", "txt", "pdf", "docx"],
            "md" if path.suffix.lower() in {".md", ".markdown"} else path.suffix.lower()[1:],
        ),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        text=text,
        chunks=chunk_text(text, document_id, chunk_size, overlap),
        ingested_at=datetime.now(UTC),
    )


def discover_documents(source: Path) -> Iterable[Path]:
    """Yield supported files under a file or directory in stable path order."""
    if source.is_file():
        if source.suffix.lower() in SUPPORTED_SUFFIXES:
            yield source
        return
    if source.is_dir():
        yield from sorted(
            (
                path
                for path in source.rglob("*")
                if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
            ),
            key=lambda path: path.as_posix().casefold(),
        )
        return
    raise FileNotFoundError(f"Source path does not exist: {source}")
