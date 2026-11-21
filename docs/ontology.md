# DocGraph ontology

This ontology represents the concepts needed to connect functional documentation to data lineage. It keeps source documents and their chunks in the graph so that extracted facts and later suggestions can be traced to evidence.

## Node labels

| Label | Meaning | Typical identity |
|---|---|---|
| `System` | A business or technical system boundary | normalized system name |
| `Application` | A deployable or user-facing application | normalized application name |
| `Dataset` / `Table` | A logical dataset or physical table | qualified name where available |
| `Field` | A column, attribute, or data element | parent dataset plus normalized field name |
| `Job` / `Process` | A batch, streaming, or manual transformation | normalized process name |
| `Report` | A report, dashboard, or regulatory output | normalized report name |
| `BusinessTerm` | A domain concept with a business definition | normalized term |
| `Team` / `Owner` | An accountable team or owner | normalized owner name |
| `Document` | An ingested source file | stable document id |
| `Chunk` | A bounded text segment used as extraction context | document id plus chunk index |

The pairs `Dataset`/`Table` and `Team`/`Owner` are label aliases for the same ontology concepts. Implementations may use one canonical label (`Dataset`, `Team`) while retaining the source type as a property.

## Relationships

| Relationship | Direction | Meaning |
|---|---|---|
| `READS_FROM` | Job or Process → Dataset | Reads input data |
| `WRITES_TO` | Job or Process → Dataset | Writes output data |
| `DERIVED_FROM` | Dataset or Field → Dataset, Field, or BusinessTerm | Has an upstream derivation |
| `PRODUCES` | Job or Process → Dataset or Report | Creates an output |
| `DEPENDS_ON` | Any operational entity → entity | Requires another entity |
| `OWNED_BY` | Entity → Team or Owner | Identifies accountability |
| `DEFINES` | Document or System → BusinessTerm | Defines a term |
| `MENTIONS` | Document or Chunk → extracted entity | Records a source reference |
| `PART_OF` | Component → containing entity | Indicates containment |
| `SUGGESTED_LINEAGE` | Source data entity → target data entity | Candidate lineage pending human review |

`SUGGESTED_LINEAGE` carries `score`, `rationale`, and `status`. Status starts as `proposed` and may become `accepted` or `rejected`; suggestions are never auto-accepted.

## Provenance requirements

Every extracted node and relationship must retain:

- `source_document`: stable source document id
- `chunk_id`: stable id of the evidence chunk
- `evidence`: exact supporting text span from that chunk
- `model_name`: model/provider identifier, or `deterministic` for rule-based records
- `prompt_version`: version identifier, or `not-applicable` for non-LLM records
- `confidence`: extraction confidence in the inclusive range 0–1
- `extracted_at`: UTC timestamp

The extraction JSONL and resolved graph files keep these as structured fields. Neo4j stores the aggregate in a `provenance_json` string property and exposes `source_document_ids` and maximum `confidence` as query-friendly scalar/list properties, because Neo4j properties cannot hold nested maps.

Document and Chunk nodes also retain source metadata and content hashes. A suggestion stores its own evidence and provenance because it is a derived, reviewable assertion.

## Design notes

- Use stable normalized IDs and uniqueness constraints so rerunning ingestion is idempotent.
- Preserve source spelling and aliases as properties; normalization must not erase evidence or business naming.
- Keep suggestions distinct from asserted lineage. Human feedback changes suggestion status and becomes evaluation/training data.
- Treat evidence validation as a hard guard: an extracted quote must occur in its source chunk before it can be loaded.
