# API and review app

The API is served by Uvicorn at `http://localhost:8000`; OpenAPI docs are available at `/docs`. The Streamlit reviewer is at `http://localhost:8501`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check Neo4j connectivity |
| `GET` | `/entities?q=payment` | Search entity names and aliases |
| `GET` | `/datasets/{id}/lineage/upstream` | Trace upstream dataset paths |
| `GET` | `/datasets/{id}/lineage/downstream` | Trace downstream impact paths |
| `GET` | `/suggestions?status=proposed` | List the review queue |
| `POST` | `/suggestions/{id}/feedback` | Accept or reject a proposed link |
| `POST` | `/feedback/extractions` | Submit an evidence-validated correction |

Start all local services with `docker compose up -d --build`. The API and Streamlit app share the `.docgraph` volume for SQLite feedback and connect to Neo4j on the Compose network. Set the host-side `NEO4J_URI` in `.env` to `bolt://localhost:7687` for CLI use; Compose overrides it to `bolt://neo4j:7687` inside containers.

The app is intended for a trusted local portfolio demo. It has no login, role management, or public deployment hardening.
