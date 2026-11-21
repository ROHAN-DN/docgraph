# DocGraph

DocGraph turns functional documentation into a provenance-aware knowledge graph and uses it to suggest data lineage links for human review.

> Project status: Phases 1–9 implemented. Reviewer feedback, a FastAPI service, a Streamlit review app, tests, and CI are included. **Evaluation baseline and feedback improvement are not measured yet:** no extraction JSONL output exists in the workspace, so no scores are reported.

## Quickstart

1. Copy `.env.example` to `.env` and change the local Neo4j password if needed.
2. Start Neo4j, the API, and review app with `docker compose up -d --build`.
3. Install the package on the host with `python -m pip install -e .` to use the CLI.
4. Ingest the synthetic corpus with `docgraph ingest data/raw`.
5. Set `LLM_PROVIDER`, `LLM_MODEL`, and the matching API key in `.env`, then run `docgraph extract`.
6. Open Neo4j Browser at <http://localhost:7474>, API docs at <http://localhost:8000/docs>, and the review app at <http://localhost:8501>.

## Architecture

```mermaid
flowchart LR
  D[Functional documents] --> I[Ingest and chunk]
  I --> C[(Neo4j Document and Chunk nodes)]
  C --> X[LLM extraction with evidence checks]
  X --> R[Entity resolution and merge review]
  R --> G[(Neo4j knowledge graph)]
  G --> L[Lineage path and candidate scoring]
  L --> J[LLM judgement with evidence]
  J --> S[Proposed suggestions]
  S --> U[Streamlit review or API feedback]
  U --> F[(SQLite feedback examples)]
  F --> X
  F --> J
  X --> E[Gold-set evaluation]
```

Ingestion supports Markdown, plain text, PDF, and DOCX files. It normalizes whitespace, uses overlapping character chunks, and stores source hashes, full cleaned text, offsets, and chunk text in Neo4j. Re-ingesting a document replaces its chunk set within a transaction. The synthetic source corpus is documented in [data/raw/README.md](data/raw/README.md); the initial hand-labeled subset is in [data/gold/gold_v1.json](data/gold/gold_v1.json).

Extraction prompts are versioned under `prompts/extraction/`. Pydantic validates the response schema and every evidence quote must be an exact substring of the originating chunk. Validated responses are cached in SQLite at `.docgraph/extraction-cache.sqlite3`, written to timestamped JSONL files in `data/processed/`, and token usage is logged to `logs/extraction-usage.jsonl`. Cost estimates are omitted unless both optional per-million-token rates are configured.

See [docs/extraction.md](docs/extraction.md) for provider configuration, retry behavior, and a small-run command.

Entity resolution writes a resolved graph and a pending merge report for review. Run `docgraph resolve data/processed/extractions-<run>.jsonl`, inspect `data/processed/merge_report.json`, then load with `docgraph load data/processed/resolved_graph.json`. Resolution uses OpenAI embeddings by default; `--no-embeddings` enables lexical-only matching. Neo4j constraints and full-text/vector indexes are defined in [schema.cypher](src/docgraph/db/schema.cypher).

Run `docgraph suggest --limit 10` to inspect up to ten graph-derived lineage candidates with the configured LLM. Suggestions use multi-hop paths, shared neighbors, name/embedding similarity, and evidence-grounded LLM judgement. They are stored as `SUGGESTED_LINEAGE` with `status: proposed`; reviewers decide whether to accept or reject them. See [lineage.md](docs/lineage.md).

After running extraction over the full corpus, evaluate those real outputs with `docgraph evaluate data/processed`. The command writes CSV/JSON metrics and an F1 chart under `data/processed/evaluation/`. See [evaluation.md](docs/evaluation.md) for the matching rules and current baseline status.

Reviewer decisions and corrected extractions can be submitted with `docgraph feedback-lineage` and `docgraph feedback-extraction`; recent examples are included by extraction/lineage prompt v2. See [feedback.md](docs/feedback.md). The before/after comparison must be run after collecting actual v1 and v2 extraction outputs.

## Repository layout

```text
data/           Synthetic source documents and labels
docs/           Ontology, extraction, lineage, evaluation, and feedback guides
prompts/        Versioned extraction and lineage prompts
src/docgraph/   CLI, API, Streamlit app, and pipeline modules
tests/          Unit tests with mocked providers
.github/        GitHub Actions CI
```

## API

The FastAPI service exposes entity search, upstream/downstream dataset lineage, suggestion listing, and feedback submission. The Streamlit app uses the same query and feedback modules for an interactive review queue. See [docs/api.md](docs/api.md).

## Tests and CI

Install development tools with `python -m pip install -e ".[dev]"`, then run `pytest -q -m "not integration"`, `ruff check src tests`, and `mypy src/docgraph --ignore-missing-imports`. GitHub Actions runs these checks on each push and pull request and runs a separate graph-loader integration test against Neo4j 5.26. Unit tests use local fixtures and a mocked LLM; they do not require API credentials or Neo4j.

## Known limitations

- No extraction or evaluation run has been measured in this workspace; the README intentionally has no precision, recall, or F1 values.
- The hand-labeled gold set now covers all 16 synthetic documents and still needs human review before metric claims.
- The review UI is a small local tool; authentication and multi-user access control are not implemented.
- PDF ingestion extracts embedded text and does not perform OCR.
- Entity resolution defaults to 1536-dimensional OpenAI embeddings. The lexical-only option works without embeddings.
- The lineage suggestion path search is bounded and heuristic; suggestions still require a human decision.

## Query examples

The project includes more than 10 documented read-only Cypher examples in [docs/queries.md](docs/queries.md). Screenshots are not included yet because the graph and review UI have not been run with measured extraction results.

## Ontology

See [docs/ontology.md](docs/ontology.md) for node labels, relationships, provenance requirements, and design choices.
