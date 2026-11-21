# Entity resolution and graph loading

`docgraph resolve` reads validated extraction JSONL records. It only compares entities with the same ontology type. Explicitly shared aliases are treated as exact matches; other candidates use normalized string similarity and, when enabled, cosine similarity from the configured OpenAI embedding model. The default threshold is configurable with `ENTITY_RESOLUTION_THRESHOLD` or `--threshold`.

The resolver creates stable IDs from canonical type and normalized name, aggregates source spellings as aliases, and retains every evidence/provenance record. It writes both `resolved_graph.json` and `merge_report.json`. Merge report entries have `review_status: pending`, a score, the spellings grouped, and which signals caused the match. Review the report before loading; increase the threshold or use `--no-embeddings` and resolve again if a proposed group looks too broad.

`docgraph load` applies the schema constraints and indexes, checks that every source chunk exists, then writes entity, relationship, and chunk-mention facts in bounded Neo4j transactions. Entity and relationship writes use `MERGE` with stable IDs, so rerunning a load updates the same graph facts and provenance evidence. Provenance is stored as a JSON string property because Neo4j properties cannot contain nested maps; structured data remains in the pipeline JSON files. Entity labels and relationship types come from validated ontology enums before being used in Cypher identifiers.

The vector index is configured for the default `text-embedding-3-small` dimension of 1536. Keep that dimension when changing the embedding model, or update the schema vector dimension to match before loading embeddings from a different-sized model.

```powershell
docgraph resolve data/processed/extractions-<run>.jsonl
# Inspect data/processed/merge_report.json before graph loading.
docgraph load data/processed/resolved_graph.json
```
