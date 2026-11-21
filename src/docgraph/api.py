"""FastAPI read/query service and reviewer feedback endpoints."""

from collections.abc import Iterator
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from neo4j import Driver, GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from pydantic import BaseModel, Field

from docgraph.config import settings
from docgraph.feedback.service import review_lineage, save_extraction_correction
from docgraph.feedback.store import FeedbackStore
from docgraph.lineage.queries import (
    dataset_exists,
    dataset_lineage,
    list_suggestions,
    search_entities,
)

app = FastAPI(
    title="DocGraph API",
    version="0.1.0",
    description="Search graph entities, trace lineage, and submit reviewer feedback.",
)


def get_driver() -> Iterator[Driver]:
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        driver.verify_connectivity()
        yield driver
    except (DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j is unavailable: {exc}") from exc
    finally:
        driver.close()


def get_feedback_store() -> FeedbackStore:
    return FeedbackStore(settings.feedback_database_path)


class LineageFeedbackRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    note: str = Field(default="", max_length=1200)
    reviewer: str = Field(default="api-reviewer", min_length=1, max_length=100)


class ExtractionFeedbackRequest(BaseModel):
    source_document: str
    chunk_id: str
    corrected_output: dict[str, Any]
    note: str = Field(default="", max_length=1200)
    reviewer: str = Field(default="api-reviewer", min_length=1, max_length=100)


@app.get("/health")
def health(driver: Driver = Depends(get_driver)) -> dict[str, str]:
    driver.verify_connectivity()
    return {"status": "ok"}


@app.get("/entities")
def entities(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(25, ge=1, le=100),
    driver: Driver = Depends(get_driver),
) -> list[dict[str, Any]]:
    try:
        return search_entities(driver, settings.neo4j_database, q, limit)
    except (DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j query failed: {exc}") from exc


@app.get("/datasets/{dataset_id}/lineage/{direction}")
def lineage(
    dataset_id: str,
    direction: Literal["upstream", "downstream"],
    max_depth: int = Query(6, ge=1, le=10),
    driver: Driver = Depends(get_driver),
) -> list[dict[str, Any]]:
    try:
        if not dataset_exists(driver, settings.neo4j_database, dataset_id):
            raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
        return dataset_lineage(driver, settings.neo4j_database, dataset_id, direction, max_depth)
    except (DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j query failed: {exc}") from exc


@app.get("/suggestions")
def suggestions(
    status: Literal["proposed", "accepted", "rejected"] = "proposed",
    limit: int = Query(100, ge=1, le=500),
    driver: Driver = Depends(get_driver),
) -> list[dict[str, Any]]:
    try:
        return list_suggestions(driver, settings.neo4j_database, status, limit)
    except (DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j query failed: {exc}") from exc


@app.post("/suggestions/{suggestion_id}/feedback")
def submit_lineage_feedback(
    suggestion_id: str,
    request: LineageFeedbackRequest,
    driver: Driver = Depends(get_driver),
    feedback: FeedbackStore = Depends(get_feedback_store),
) -> dict[str, Any]:
    try:
        return review_lineage(
            driver,
            settings.neo4j_database,
            feedback,
            suggestion_id,
            request.decision,
            request.note,
            request.reviewer,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=503, detail=f"Feedback could not be saved: {exc}") from exc


@app.post("/feedback/extractions")
def submit_extraction_feedback(
    request: ExtractionFeedbackRequest,
    driver: Driver = Depends(get_driver),
    feedback: FeedbackStore = Depends(get_feedback_store),
) -> dict[str, str]:
    try:
        save_extraction_correction(
            driver,
            settings.neo4j_database,
            feedback,
            request.source_document,
            request.chunk_id,
            request.corrected_output,
            request.note,
            request.reviewer,
        )
        return {"status": "saved", "chunk_id": request.chunk_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, DriverError, Neo4jError) as exc:
        raise HTTPException(status_code=422, detail=f"Correction was invalid: {exc}") from exc
