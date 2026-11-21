# Lineage paths and suggestions

## Direction model

The suggestion query considers paths between `Dataset` entities over `READS_FROM`, `WRITES_TO`, `PRODUCES`, and `DERIVED_FROM`. It interprets these edges as data flow: a `READS_FROM` edge is traversed from input dataset to job, `WRITES_TO`/`PRODUCES` from job to output dataset, and `DERIVED_FROM` from upstream dataset to derived dataset. The Cypher path is bounded to six relationships by default and Python checks that every relationship follows this directed interpretation.

Candidates are dataset pairs connected by a multi-hop path and lacking an existing `DERIVED_FROM` or `SUGGESTED_LINEAGE` edge. Shared path neighbors, name similarity, and stored vector similarity contribute to a heuristic score. Candidates below `LINEAGE_SUGGESTION_THRESHOLD` are not sent to the LLM. A versioned prompt asks the configured provider to judge the evidence; each cited quote must exactly match evidence already stored in the graph.

The final score combines the heuristic and LLM confidence. The suggested relationship stores score, rationale, exact evidence, source provenance, model, prompt version, path support, and similarity features. Provenance is stored as a JSON string property to fit Neo4j's property type restrictions. The status is set to `proposed` only when the relationship is first created. Re-running the workflow never changes an existing review status, and suggestions are never auto-accepted.

## Run

```powershell
docgraph suggest --limit 10
```

The `--limit` option caps LLM judgement calls after heuristic filtering. `--score-threshold` overrides the configured threshold; `--max-depth` changes the Cypher path limit. Token usage is appended to `logs/lineage-usage.jsonl`.

The current candidate strategy finds path-connected pairs. It does not claim that a direct transformation exists when the graph only proves a multi-hop route; the suggestion is a review prompt backed by the full path and its evidence.
