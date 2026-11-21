"""Data structures produced by document ingestion."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Chunk(BaseModel):
    """A text segment with offsets into its cleaned source document."""

    model_config = ConfigDict(frozen=True)

    id: str
    document_id: str
    index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)


class IngestedDocument(BaseModel):
    """A parsed source document and its chunks."""

    document_id: str
    path: str
    filename: str
    file_type: Literal["md", "txt", "pdf", "docx"]
    sha256: str
    text: str
    chunks: list[Chunk]
    ingested_at: datetime
