"""Environment-backed application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read from the environment or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "docgraph-local-password"
    neo4j_database: str = "neo4j"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None
    extraction_max_retries: int = 2
    extraction_retry_base_seconds: float = 1.0
    extraction_input_usd_per_million_tokens: float | None = None
    extraction_output_usd_per_million_tokens: float | None = None
    extraction_cache_path: str = ".docgraph/extraction-cache.sqlite3"
    extraction_usage_log: str = "logs/extraction-usage.jsonl"
    entity_resolution_threshold: float = 0.86
    embedding_model: str = "text-embedding-3-small"
    lineage_suggestion_threshold: float = 0.50
    feedback_database_path: str = ".docgraph/feedback.sqlite3"


settings = Settings()
