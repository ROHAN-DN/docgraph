"""Lineage path candidates and validated LLM judgement."""

from pydantic import BaseModel, ConfigDict, Field


class LineageEvidence(BaseModel):
    evidence_id: str
    source_document: str
    chunk_id: str
    evidence: str
    model_name: str
    prompt_version: str
    confidence: float
    extracted_at: str


class LineageJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plausible: bool
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=1200)
    evidence: list[str] = Field(min_length=1)

    def require_supplied_evidence(self, supplied: list[str]) -> "LineageJudgement":
        if any(quote not in supplied for quote in self.evidence):
            raise ValueError("LLM cited a quote that was not supplied as graph evidence")
        return self


class LineageCandidate(BaseModel):
    source_id: str
    target_id: str
    source_name: str
    target_name: str
    path_support: int
    shared_neighbors: list[str]
    name_similarity: float
    embedding_similarity: float | None
    heuristic_score: float
    paths: list[str]
    evidence: list[str]
    provenance: list[LineageEvidence]


class LineageSuggestion(BaseModel):
    id: str
    source_id: str
    target_id: str
    score: float = Field(ge=0, le=1)
    rationale: str
    evidence: list[str]
    provenance: list[LineageEvidence]
    status: str = "proposed"
    model_name: str
    prompt_version: str
    created_at: str
    path_support: int
    shared_neighbors: list[str]
    name_similarity: float
    embedding_similarity: float | None
