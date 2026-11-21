"""SQLite storage for reviewed suggestions and corrected extractions."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class FeedbackStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lineage_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    suggestion_id TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK (decision IN ('accepted','rejected')),
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    reviewer_note TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS extraction_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_document TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_chunk TEXT NOT NULL,
                    corrected_json TEXT NOT NULL,
                    reviewer_note TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def record_lineage(
        self,
        *,
        suggestion_id: str,
        decision: str,
        source_id: str,
        target_id: str,
        source_name: str,
        target_name: str,
        rationale: str,
        evidence: list[str],
        reviewer_note: str,
        reviewer: str,
        model_name: str,
        prompt_version: str,
    ) -> None:
        if decision not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO lineage_feedback
                (suggestion_id,decision,source_id,target_id,source_name,target_name,rationale,evidence_json,
                 reviewer_note,reviewer,model_name,prompt_version,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    suggestion_id,
                    decision,
                    source_id,
                    target_id,
                    source_name,
                    target_name,
                    rationale,
                    json.dumps(evidence, ensure_ascii=False),
                    reviewer_note,
                    reviewer,
                    model_name,
                    prompt_version,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def record_extraction(
        self,
        *,
        source_document: str,
        chunk_id: str,
        source_chunk: str,
        corrected_json: dict[str, Any],
        reviewer_note: str,
        reviewer: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO extraction_feedback
                (source_document,chunk_id,source_chunk,corrected_json,reviewer_note,reviewer,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    source_document,
                    chunk_id,
                    source_chunk,
                    json.dumps(corrected_json, ensure_ascii=False),
                    reviewer_note,
                    reviewer,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def examples(self, kind: str, limit: int = 3) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        with self._connect() as connection:
            if kind == "lineage":
                rows = connection.execute(
                    """SELECT current.* FROM lineage_feedback AS current
                    WHERE current.id = (
                        SELECT MAX(latest.id) FROM lineage_feedback AS latest
                        WHERE latest.suggestion_id = current.suggestion_id
                    ) ORDER BY current.id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
                return [
                    {
                        "source": row["source_name"],
                        "target": row["target_name"],
                        "decision": row["decision"],
                        "reviewer_note": row["reviewer_note"],
                        "rationale": row["rationale"],
                        "evidence": json.loads(row["evidence_json"]),
                    }
                    for row in rows
                ]
            if kind == "extraction":
                rows = connection.execute(
                    "SELECT * FROM extraction_feedback ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                return [
                    {
                        "source_chunk": row["source_chunk"],
                        "corrected_output": json.loads(row["corrected_json"]),
                        "reviewer_note": row["reviewer_note"],
                    }
                    for row in rows
                ]
        raise ValueError("kind must be extraction or lineage")

    def render_examples(self, kind: str, limit: int = 3) -> str:
        examples = self.examples(kind, limit)
        if not examples:
            return "No reviewed examples yet."
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in examples)
