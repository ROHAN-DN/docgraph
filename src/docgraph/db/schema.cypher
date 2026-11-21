CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT system_id_unique IF NOT EXISTS FOR (n:System) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT application_id_unique IF NOT EXISTS FOR (n:Application) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dataset_id_unique IF NOT EXISTS FOR (n:Dataset) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT field_id_unique IF NOT EXISTS FOR (n:Field) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT job_id_unique IF NOT EXISTS FOR (n:Job) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT report_id_unique IF NOT EXISTS FOR (n:Report) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT business_term_id_unique IF NOT EXISTS FOR (n:BusinessTerm) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT team_id_unique IF NOT EXISTS FOR (n:Team) REQUIRE n.id IS UNIQUE;
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.aliases];
CREATE VECTOR INDEX entity_embedding IF NOT EXISTS FOR (e:Entity) ON (e.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
