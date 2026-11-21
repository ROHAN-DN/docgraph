"""SQLite cache for validated extraction responses."""

import hashlib
import sqlite3
from pathlib import Path

from docgraph.extraction.providers import Generation


class ExtractionCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS extraction_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL
                )"""
            )

    @staticmethod
    def key(model: str, prompt_version: str, prompt: str, chunk_id: str, chunk_text: str) -> str:
        material = "\0".join((model, prompt_version, prompt, chunk_id, chunk_text))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Generation | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT response_json,input_tokens,output_tokens FROM extraction_cache WHERE cache_key=?",
                (key,),
            ).fetchone()
        return Generation(str(row[0]), int(row[1]), int(row[2])) if row else None

    def put(self, key: str, generation: Generation) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO extraction_cache VALUES (?,?,?,?)",
                (key, generation.text, generation.input_tokens, generation.output_tokens),
            )
