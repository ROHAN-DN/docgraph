# Evaluation harness

The evaluator compares extraction JSONL files with `data/gold/gold_v1.json`. It reports entity and relationship counts, precision, recall, and F1 for each run/model/prompt version and writes `results.csv`, `results.json`, and `results.png`.

Entity matching is case- and punctuation-insensitive and alias-aware. Repeated mentions with the same type and overlapping normalized aliases are deduplicated within a document. Relationship matching requires the same relationship type and direction, with source and target matched to the corresponding gold entities. Maximum bipartite matching prevents a single prediction from satisfying multiple gold facts. Documents with at least one record are evaluated; coverage is reported against all 16 gold documents. Use a complete extraction run rather than a `--limit` run for a baseline.

```powershell
docgraph evaluate data/processed
```

Each JSONL file is scored as its own run. Runs are never pooled, since combining outputs could conceal variation or inflate recall. Prompt versions can be compared side-by-side after Phase 8, but this harness does not fabricate a before/after result; the metrics are calculated from the files supplied.

## Current baseline

Not measured. At the time this harness was added, `data/processed/` contained no extraction JSONL files. Generate a real full-corpus extraction first, then run the command above. No metric values are claimed here.
