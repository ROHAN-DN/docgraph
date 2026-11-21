"""Resolved graph output and auditable merge suggestions."""

from pydantic import BaseModel, ConfigDict, Field

from docgraph.extraction.models import EntityType, RelationshipType


class Provenance(BaseModel):
    evidence_id: str
    source_document: str
    chunk_id: str
    evidence: str
    model_name: str
    prompt_version: str
    confidence: float = Field(ge=0, le=1)
    extracted_at: str


class ResolvedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: EntityType
    name: str
    aliases: list[str]
    description: str = ""
    embedding: list[float] | None = None
    provenance: list[Provenance]


class ResolvedRelationship(BaseModel):
    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    provenance: list[Provenance]


class ResolvedGraph(BaseModel):
    schema_version: str = "1.0"
    embedding_model: str | None = None
    entities: list[ResolvedEntity]
    relationships: list[ResolvedRelationship]


class MergeCandidate(BaseModel):
    entity_type: EntityType
    canonical_name: str
    member_names: list[str]
    aliases: list[str]
    similarity_score: float
    matched_by: list[str]
    review_status: str = "pending"


class MergeReport(BaseModel):
    schema_version: str = "1.0"
    threshold: float
    embedding_model: str | None = None
    candidates: list[MergeCandidate]
