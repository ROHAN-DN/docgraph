# Reviewer feedback loop

Phase 8 stores reviewer input in `.docgraph/feedback.sqlite3`. A lineage decision also updates the corresponding Neo4j `SUGGESTED_LINEAGE.status` and review metadata. Extraction corrections are validated against the selected source chunk before being stored. Feedback is append-only, and the latest decision for a suggestion is used as an example.

## Review a suggested link

```powershell
docgraph feedback-lineage <suggestion-id> accepted --note "The shared job path and control documentation support this link."
docgraph feedback-lineage <another-suggestion-id> rejected --note "The names are similar, but there is no direct transformation evidence."
```

Only `accepted` and `rejected` are valid decisions. The reviewer note, rationale, evidence, source/target names, model, and prompt version are stored for future prompt examples.

## Correct an extraction

Create a JSON file with the same `entities` and `relationships` shape as the extraction schema, then submit it:

```powershell
docgraph feedback-extraction DOC-PAY-001 DOC-PAY-001::chunk-0000 .\correction.json --note "The API response is not settlement."
```

Every corrected entity/relationship must cite a quote found verbatim in the selected chunk. Corrections are stored as examples for the next extraction prompt; they do not silently rewrite the current graph.

## Prompt v2 and evaluation

`prompts/extraction/v2.md` and `prompts/lineage/v2.md` contain explicit reviewer-example sections. The CLI inserts up to three recent reviewed examples into those sections. Cache keys include the rendered prompt, so new feedback creates a fresh extraction result rather than reusing an old cache entry.

Run the updated prompt versions explicitly:

```powershell
docgraph extract --prompt-version v2
docgraph suggest --prompt-version v2
```

Run full-corpus v1 and v2 extractions as separate output files, then compare their actual scores with `docgraph evaluate data/processed`. The workspace has no extraction JSONL runs yet, so no baseline or improvement is claimed.
