"""DocGraph command line interface."""

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from docgraph.config import settings
from docgraph.db.graph_loader import load_graph
from docgraph.evaluation.metrics import discover_prediction_files, write_results
from docgraph.evaluation.metrics import evaluate as evaluate_predictions
from docgraph.extraction.cache import ExtractionCache
from docgraph.extraction.providers import create_provider
from docgraph.extraction.service import ExtractionError, extract_chunk
from docgraph.feedback.service import review_lineage, save_extraction_correction
from docgraph.feedback.store import FeedbackStore
from docgraph.ingestion.loader import DocumentLoadError, discover_documents, load_document
from docgraph.ingestion.neo4j_store import store_document
from docgraph.lineage.suggestions import run_suggestions
from docgraph.resolution.embeddings import OpenAIEmbeddingProvider
from docgraph.resolution.models import ResolvedGraph
from docgraph.resolution.resolver import read_records, resolve_records, write_resolution

app = typer.Typer(help="Build and query the DocGraph knowledge graph.")


@app.command()
def ingest(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="A file or directory of source documents."
    ),
    chunk_size: int = typer.Option(1200, min=1, help="Maximum chunk size in characters."),
    overlap: int = typer.Option(200, min=0, help="Overlap between adjacent chunks in characters."),
) -> None:
    """Load documents, split them into chunks, and store them in Neo4j."""
    if overlap >= chunk_size:
        raise typer.BadParameter("overlap must be smaller than chunk_size")
    try:
        documents = list(discover_documents(source))
        if not documents:
            typer.echo(
                "No supported documents found (.md, .markdown, .txt, .pdf, .docx).", err=True
            )
            raise typer.Exit(code=1)
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            driver.verify_connectivity()
            total_chunks = 0
            for path in documents:
                document = load_document(path, chunk_size=chunk_size, overlap=overlap)
                store_document(driver, settings.neo4j_database, document)
                total_chunks += len(document.chunks)
                typer.echo(f"Ingested {document.document_id}: {len(document.chunks)} chunks")
        typer.echo(f"Done: {len(documents)} document(s), {total_chunks} chunk(s).")
    except (DocumentLoadError, Neo4jError, OSError) as exc:
        typer.echo(f"Ingestion failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def extract(
    prompt_version: str = typer.Option(
        "v1", help="Version label for the prompt and extraction records."
    ),
    prompt_file: Path | None = typer.Option(
        None, help="Prompt template; defaults to prompts/extraction/<version>.md."
    ),
    output: Path | None = typer.Option(
        None, help="JSONL output file; defaults to a timestamped file in data/processed."
    ),
    limit: int | None = typer.Option(
        None, min=1, help="Optional maximum number of chunks to extract."
    ),
) -> None:
    """Extract structured, evidence-checked facts from all ingested chunks."""
    prompt_path = prompt_file or Path("prompts/extraction") / f"{prompt_version}.md"
    if not prompt_path.is_file():
        typer.echo(f"Prompt file not found: {prompt_path}", err=True)
        raise typer.Exit(code=1)
    prompt_template = prompt_path.read_text(encoding="utf-8")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = output or Path("data/processed") / f"extractions-{timestamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache = ExtractionCache(settings.extraction_cache_path)

    try:
        provider = create_provider(
            settings.llm_provider,
            settings.llm_model,
            settings.openai_api_key,
            settings.anthropic_api_key,
            openai_base_url=settings.openai_base_url,
        )
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            driver.verify_connectivity()
            with driver.session(database=settings.neo4j_database) as session:
                result = session.run(
                    "MATCH (c:Chunk)-[:PART_OF]->(d:Document) "
                    "RETURN d.id AS document_id,c.id AS chunk_id,c.text AS text "
                    "ORDER BY d.id,c.index"
                )
                chunks = [record.data() for record in result]
        if limit is not None:
            chunks = chunks[:limit]
        if not chunks:
            typer.echo("No ingested chunks found. Run `docgraph ingest data/raw` first.", err=True)
            raise typer.Exit(code=1)

        success_count = 0
        failure_count = 0
        feedback_examples = FeedbackStore(settings.feedback_database_path).render_examples(
            "extraction"
        )
        with output_path.open("w", encoding="utf-8") as stream:
            for chunk in chunks:
                try:
                    record = extract_chunk(
                        source_document=chunk["document_id"],
                        chunk_id=chunk["chunk_id"],
                        chunk_text=chunk["text"],
                        provider=provider,
                        prompt_template=prompt_template,
                        prompt_version=prompt_version,
                        cache=cache,
                        max_retries=settings.extraction_max_retries,
                        retry_base_seconds=settings.extraction_retry_base_seconds,
                        input_rate=settings.extraction_input_usd_per_million_tokens,
                        output_rate=settings.extraction_output_usd_per_million_tokens,
                        usage_log=settings.extraction_usage_log,
                        feedback_examples=feedback_examples,
                    )
                    stream.write(record.model_dump_json() + "\n")
                    success_count += 1
                    typer.echo(
                        f"Extracted {record.chunk_id} ({'cache' if record.cache_hit else 'LLM'})"
                    )
                except ExtractionError as exc:
                    failure_count += 1
                    typer.echo(str(exc), err=True)
        typer.echo(
            f"Extraction complete: {success_count} succeeded, {failure_count} failed. Output: {output_path}"
        )
        if failure_count:
            raise typer.Exit(code=1)
    except (ValueError, Neo4jError, OSError) as exc:
        typer.echo(f"Extraction run failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def resolve(
    source: Path = typer.Argument(..., exists=True, readable=True, help="Extraction JSONL file."),
    output: Path = typer.Option(
        Path("data/processed/resolved_graph.json"), help="Resolved graph JSON output."
    ),
    report: Path = typer.Option(
        Path("data/processed/merge_report.json"), help="Human review report output."
    ),
    threshold: float | None = typer.Option(
        None, min=0, max=1, help="Similarity threshold from 0 to 1."
    ),
    no_embeddings: bool = typer.Option(
        False, help="Use string similarity only; default uses configured embeddings."
    ),
) -> None:
    """Resolve duplicate entity mentions and write a pending-merge review report."""
    try:
        selected_threshold = (
            settings.entity_resolution_threshold if threshold is None else threshold
        )
        embedding_provider = None
        if not no_embeddings:
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required for embeddings; pass --no-embeddings for lexical-only resolution"
                )
            embedding_provider = OpenAIEmbeddingProvider(
                settings.embedding_model, settings.openai_api_key
            )
        records = read_records(source)
        graph, merge_report = resolve_records(
            records,
            threshold=selected_threshold,
            embedding_provider=embedding_provider,
        )
        write_resolution(graph, merge_report, output, report)
        typer.echo(
            f"Resolved {len(graph.entities)} entities and {len(graph.relationships)} relationships. "
            f"{len(merge_report.candidates)} merge group(s) need review."
        )
        typer.echo(f"Graph: {output}\nMerge report: {report}")
    except (ValueError, OSError) as exc:
        typer.echo(f"Resolution failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def load(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="Resolved graph JSON file."
    ),
    batch_size: int = typer.Option(250, min=1, help="Rows written per Neo4j transaction."),
) -> None:
    """Apply graph constraints/indexes and load resolved facts into Neo4j."""
    try:
        graph = ResolvedGraph.model_validate_json(source.read_text(encoding="utf-8"))
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            driver.verify_connectivity()
            load_graph(driver, settings.neo4j_database, graph, batch_size=batch_size)
        typer.echo(
            f"Loaded {len(graph.entities)} entities and {len(graph.relationships)} relationships."
        )
    except (ValueError, Neo4jError, OSError) as exc:
        typer.echo(f"Graph load failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def suggest(
    prompt_version: str = typer.Option("v1", help="Version label for the judgement prompt."),
    prompt_file: Path | None = typer.Option(
        None, help="Prompt template; defaults to prompts/lineage/<version>.md."
    ),
    limit: int | None = typer.Option(
        None, min=1, help="Maximum candidate links judged by the LLM."
    ),
    score_threshold: float | None = typer.Option(
        None, min=0, max=1, help="Minimum heuristic score before LLM review."
    ),
    max_depth: int = typer.Option(
        6, min=1, max=10, help="Maximum graph path length in relationships."
    ),
) -> None:
    """Suggest missing dataset lineage links for human review."""
    prompt_path = prompt_file or Path("prompts/lineage") / f"{prompt_version}.md"
    if not prompt_path.is_file():
        typer.echo(f"Prompt file not found: {prompt_path}", err=True)
        raise typer.Exit(code=1)
    try:
        if not settings.openai_api_key and settings.llm_provider.casefold() == "openai":
            raise ValueError("OPENAI_API_KEY is required for lineage judgement")
        provider = create_provider(
            settings.llm_provider,
            settings.llm_model,
            settings.openai_api_key,
            settings.anthropic_api_key,
            openai_base_url=settings.openai_base_url,
        )
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            driver.verify_connectivity()
            suggestions = run_suggestions(
                driver=driver,
                database=settings.neo4j_database,
                provider=provider,
                prompt_template=prompt_path.read_text(encoding="utf-8"),
                prompt_version=prompt_version,
                score_threshold=(
                    settings.lineage_suggestion_threshold
                    if score_threshold is None
                    else score_threshold
                ),
                max_depth=max_depth,
                limit=limit,
                feedback_examples=FeedbackStore(settings.feedback_database_path).render_examples(
                    "lineage"
                ),
            )
        typer.echo(
            f"Created {len(suggestions)} proposed lineage suggestion(s). None were auto-accepted."
        )
        for suggestion in suggestions:
            typer.echo(
                f"{suggestion.score:.2f} {suggestion.source_id} -> {suggestion.target_id}: {suggestion.rationale}"
            )
    except (ValueError, Neo4jError, OSError) as exc:
        typer.echo(f"Lineage suggestion failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def evaluate(
    source: Path = typer.Argument(
        ..., exists=True, readable=True, help="Extraction JSONL file or directory of runs."
    ),
    gold: Path = typer.Option(
        Path("data/gold/gold_v1.json"), exists=True, readable=True, help="Gold labels JSON."
    ),
    output_dir: Path = typer.Option(
        Path("data/processed/evaluation"), help="Directory for CSV, JSON, and chart outputs."
    ),
) -> None:
    """Compute alias-aware entity and relationship precision, recall, and F1."""
    try:
        prediction_files = discover_prediction_files(source)
        if not prediction_files:
            raise ValueError(f"No extraction JSONL files found under {source}")
        results = evaluate_predictions(prediction_files, gold)
        write_results(results, output_dir)
        typer.echo("Run / model / prompt | Docs | Entity P / R / F1 | Relationship P / R / F1")

        def fmt(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.3f}"

        for item in results:
            typer.echo(
                f"{item.run_id} / {item.model_name} / {item.prompt_version} | "
                f"{item.evaluated_documents}/{item.gold_documents} | "
                f"{fmt(item.entity.precision)} / {fmt(item.entity.recall)} / {fmt(item.entity.f1)} | "
                f"{fmt(item.relationship.precision)} / {fmt(item.relationship.recall)} / {fmt(item.relationship.f1)}"
            )
        typer.echo(f"Results: {output_dir / 'results.csv'}\nChart: {output_dir / 'results.png'}")
    except (ValueError, OSError) as exc:
        typer.echo(f"Evaluation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("feedback-lineage")
def feedback_lineage(
    suggestion_id: str = typer.Argument(..., help="SUGGESTED_LINEAGE relationship id."),
    decision: str = typer.Argument(..., help="Reviewer decision: accepted or rejected."),
    note: str = typer.Option(
        "", help="Short reason for the decision; used in future prompt examples."
    ),
    reviewer: str = typer.Option("local-reviewer", help="Reviewer label stored with feedback."),
) -> None:
    """Accept or reject a proposed lineage link and save a prompt example."""
    if decision not in {"accepted", "rejected"}:
        typer.echo("Decision must be accepted or rejected.", err=True)
        raise typer.Exit(code=2)
    try:
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            reviewed = review_lineage(
                driver,
                settings.neo4j_database,
                FeedbackStore(settings.feedback_database_path),
                suggestion_id,
                decision,
                note,
                reviewer,
            )
        typer.echo(
            f"Recorded {decision} feedback for {reviewed['source_name']} -> {reviewed['target_name']}."
        )
    except (ValueError, KeyError, Neo4jError, OSError) as exc:
        typer.echo(f"Lineage feedback failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("feedback-extraction")
def feedback_extraction(
    source_document: str = typer.Argument(..., help="Document id containing the reviewed chunk."),
    chunk_id: str = typer.Argument(..., help="Chunk id with the reviewed extraction."),
    correction: Path = typer.Argument(
        ..., exists=True, readable=True, help="JSON file with entities and relationships."
    ),
    note: str = typer.Option("", help="Reviewer note stored with the correction example."),
    reviewer: str = typer.Option("local-reviewer", help="Reviewer label stored with feedback."),
) -> None:
    """Save a corrected, evidence-validated extraction for future prompt examples."""
    try:
        corrected_json = json.loads(correction.read_text(encoding="utf-8"))
        with GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        ) as driver:
            save_extraction_correction(
                driver,
                settings.neo4j_database,
                FeedbackStore(settings.feedback_database_path),
                source_document,
                chunk_id,
                corrected_json,
                note,
                reviewer,
            )
        typer.echo(f"Stored corrected extraction example for {chunk_id}.")
    except (ValueError, KeyError, OSError, Neo4jError) as exc:
        typer.echo(f"Extraction feedback failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
