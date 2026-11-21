# Extraction behavior

Phase 4 extracts from the `Chunk` nodes created by Phase 3. The CLI reads chunks from Neo4j and writes validated JSONL records to `data/processed/`; it does not create entity or relationship nodes yet. Graph loading is a later phase.

## Provider and settings

Set `LLM_PROVIDER` to `openai` or `anthropic`, set `LLM_MODEL`, and provide the matching API key in `.env`. The provider adapters return response text and reported token counts through the same small interface. To change providers, update configuration; provider SDKs are installed with the project dependencies.

Extraction retries up to `EXTRACTION_MAX_RETRIES` times after provider, JSON/schema, or evidence validation errors, with exponential backoff. The SQLite cache key includes provider/model, prompt version and content, chunk id, and chunk text. Only schema-valid responses with evidence quotes found verbatim in the chunk enter the cache.

## Provenance and cost

Each output record includes source document id, chunk id, provider/model, prompt version, extraction time, token counts, optional cost estimate, and all extracted facts with their evidence and confidence. Usage events are appended to `logs/extraction-usage.jsonl`. Cost is left null unless both `EXTRACTION_INPUT_USD_PER_MILLION_TOKENS` and `EXTRACTION_OUTPUT_USD_PER_MILLION_TOKENS` are set; this avoids embedding volatile provider prices in code. Cache hits log zero incurred tokens and zero estimated cost.

## Run

```powershell
Copy-Item .env.example .env
# Set LLM_PROVIDER, LLM_MODEL, and the matching API key in .env.
python -m pip install -e .
docker compose up -d neo4j
docgraph ingest data/raw
docgraph extract --limit 3
```

`--limit` is useful for a small first run. Remove it to process all chunks. `--prompt-file` can point at another versioned template, and `--prompt-version` is recorded in outputs and cache keys.
