# Cypher query cookbook

Run these examples in Neo4j Browser after ingestion and graph loading. Queries use the canonical `Entity` label plus the specific ontology label. Replace example IDs or names with values in your graph.

## 1. Search by entity name or alias

```cypher
MATCH (e:Entity)
WHERE toLower(e.name) CONTAINS toLower('payment')
   OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) CONTAINS toLower('payment'))
RETURN e.entity_type, e.name, e.aliases, e.confidence
ORDER BY e.name;
```

## 2. Inspect a dataset and its provenance

```cypher
MATCH (d:Entity:Dataset {name: 'RISK_CURATED.PAYMENT_FACT'})
RETURN d.name, d.aliases, d.source_document_ids, d.confidence, d.provenance_json;
```

## 3. Find direct inputs to a job

```cypher
MATCH (job:Entity:Job {name: 'RISK_PAYMENT_ENRICH'})-[:READS_FROM]->(input:Entity:Dataset)
RETURN job.name, input.name
ORDER BY input.name;
```

## 4. Find direct outputs from a job

```cypher
MATCH (job:Entity:Job {name: 'RISK_PAYMENT_ENRICH'})-[:WRITES_TO|PRODUCES]->(output:Entity)
RETURN job.name, labels(output), output.name
ORDER BY output.name;
```

## 5. Direct downstream impact of a dataset

```cypher
MATCH (source:Entity:Dataset {name: 'PAYMENT_STAGE.SETTLEMENT_EVENT'})
      <-[:READS_FROM]-(job:Entity:Job)-[:WRITES_TO|PRODUCES]->(output:Entity)
RETURN source.name, job.name, output.name, output.entity_type
ORDER BY job.name, output.name;
```

## 6. Direct upstream inputs to a dataset

```cypher
MATCH (input:Entity:Dataset)<-[:READS_FROM]-(job:Entity:Job)
      -[:WRITES_TO|PRODUCES]->(target:Entity:Dataset {name: 'RISK_CURATED.PAYMENT_FACT'})
RETURN input.name, job.name, target.name
ORDER BY job.name, input.name;
```

## 7. Follow explicit dataset derivation upstream

`DERIVED_FROM` points from the derived dataset to its upstream source.

```cypher
MATCH p=(derived:Entity:Dataset {name: 'RISK_CURATED.PAYMENT_FACT'})
         -[:DERIVED_FROM*1..5]->(upstream:Entity:Dataset)
RETURN [node IN nodes(p) | node.name] AS derivation_chain
ORDER BY length(p);
```

## 8. Find downstream derived datasets

```cypher
MATCH p=(downstream:Entity:Dataset)-[:DERIVED_FROM*1..5]->
         (source:Entity:Dataset {name: 'PAYMENT_STAGE.SETTLEMENT_EVENT'})
RETURN [node IN reverse(nodes(p)) | node.name] AS downstream_chain
ORDER BY length(p);
```

## 9. Find datasets without a job or derivation connection

```cypher
MATCH (d:Entity:Dataset)
WHERE NOT EXISTS { MATCH (:Entity:Job)-[:READS_FROM]->(d) }
  AND NOT EXISTS { MATCH (:Entity:Job)-[:WRITES_TO|PRODUCES]->(d) }
  AND NOT EXISTS { MATCH (d)-[:DERIVED_FROM]-(:Entity:Dataset) }
RETURN d.name, d.source_document_ids
ORDER BY d.name;
```

## 10. Find jobs with no recorded input

```cypher
MATCH (job:Entity:Job)
WHERE NOT EXISTS { MATCH (job)-[:READS_FROM]->(:Entity:Dataset) }
RETURN job.name, job.source_document_ids
ORDER BY job.name;
```

## 11. Find jobs with no recorded output

```cypher
MATCH (job:Entity:Job)
WHERE NOT EXISTS { MATCH (job)-[:WRITES_TO|PRODUCES]->(:Entity) }
RETURN job.name, job.source_document_ids
ORDER BY job.name;
```

## 12. Find datasets without an owner

```cypher
MATCH (d:Entity:Dataset)
WHERE NOT EXISTS { MATCH (d)-[:OWNED_BY]->(:Entity:Team) }
RETURN d.name, d.source_document_ids
ORDER BY d.name;
```

## 13. Find systems without an owner

```cypher
MATCH (system:Entity:System)
WHERE NOT EXISTS { MATCH (system)-[:OWNED_BY]->(:Entity:Team) }
RETURN system.name, system.source_document_ids
ORDER BY system.name;
```

## 14. Review proposed lineage links

```cypher
MATCH (source:Entity:Dataset)-[s:SUGGESTED_LINEAGE {status: 'proposed'}]->(target:Entity:Dataset)
RETURN source.name, target.name, s.score, s.rationale, s.evidence, s.provenance_json
ORDER BY s.score DESC;
```

## 15. Count human decisions by status

```cypher
MATCH ()-[s:SUGGESTED_LINEAGE]->()
RETURN s.status AS status, count(*) AS suggestions
ORDER BY status;
```

## 16. Show chunk evidence for an entity

```cypher
MATCH (chunk:Chunk)-[m:MENTIONS]->(entity:Entity {name: 'PAYMENT_SETTLEMENT_EXPORT'})
RETURN chunk.document_id, chunk.id, m.confidence, m.provenance_json
ORDER BY chunk.document_id, chunk.index;
```
