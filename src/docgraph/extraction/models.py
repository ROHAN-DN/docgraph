"""Strict extraction response schemas and provenance envelope."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EntityType(StrEnum):
    SYSTEM = "System"
    APPLICATION = "Application"
    DATASET = "Dataset"
    FIELD = "Field"
    JOB = "Job"
    REPORT = "Report"
    BUSINESS_TERM = "BusinessTerm"
    TEAM = "Team"


class RelationshipType(StrEnum):
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    DERIVED_FROM = "DERIVED_FROM"
    PRODUCES = "PRODUCES"
    DEPENDS_ON = "DEPENDS_ON"
    OWNED_BY = "OWNED_BY"
    DEFINES = "DEFINES"
    MENTIONS = "MENTIONS"
    PART_OF = "PART_OF"


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: EntityType
    name: str = Field(min_length=1, max_length=300)
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ExtractedRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=300)
    type: RelationshipType
    target: str = Field(min_length=1, max_length=300)
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def endpoints_exist(self) -> "ExtractionPayload":
        names = {entity.name.casefold() for entity in self.entities}
        for relation in self.relationships:
            if relation.source.casefold() not in names or relation.target.casefold() not in names:
                raise ValueError("relationship endpoints must match extracted entity names")
        return self

    def require_evidence(self, chunk_text: str) -> "ExtractionPayload":
        """Reject the whole response if any quote is not a literal chunk substring."""
        unsupported = [
            *(item.evidence for item in self.entities if item.evidence not in chunk_text),
            *(item.evidence for item in self.relationships if item.evidence not in chunk_text),
        ]
        if unsupported:
            sample = unsupported[0][:100]
            raise ValueError(f"evidence quote was not found verbatim in chunk: {sample!r}")
        return self


class ExtractionRecord(BaseModel):
    """Validated extraction paired with source and prompt provenance."""

    source_document: str
    chunk_id: str
    model_name: str
    prompt_version: str
    extracted_at: datetime
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    cache_hit: bool = False
    extraction: ExtractionPayload
