"""Command-line interface for the PubMed extraction pipeline."""

import csv
from pathlib import Path

import typer
from rich.progress import track

from pubmed_extraction.extract.classifier import ArticleClassifier
from pubmed_extraction.extract.llm import LLMError, UsageTracker
from pubmed_extraction.extract.validation import quote_in_source
from pubmed_extraction.ingest.jats_parser import parse_jats
from pubmed_extraction.ingest.ncbi_client import NCBIClient
from pubmed_extraction.ingest.queries import GLP1_RCT_QUERY
from pubmed_extraction.settings import settings
from pubmed_extraction.storage.db import (
    connect,
    known_pmcids,
    pending_classification,
    upsert_article,
    upsert_classification,
)

app = typer.Typer(help="PubMed structured extraction pipeline.", no_args_is_help=True)


@app.command()
def ingest(
    retmax: int = typer.Option(200, help="Max PubMed results to consider."),
    query: str = typer.Option(GLP1_RCT_QUERY, help="PubMed query."),
    force: bool = typer.Option(False, help="Re-parse articles already in the database."),
) -> None:
    """Search PubMed, download JATS XML for new articles and store parsed metadata."""
    client = NCBIClient()
    pmids = client.search_pubmed(query, retmax=retmax)
    mapping = client.pmids_to_pmcids(pmids)
    settings.raw_dir.mkdir(parents=True, exist_ok=True)

    with connect() as con:
        known = known_pmcids(con)
        pending = [
            (pmid, pmcid) for pmid, pmcid in mapping.items() if force or pmcid not in known
        ]
        typer.echo(f"PMIDs: {len(pmids)} | With PMCID: {len(mapping)} | New: {len(pending)}")

        failures = 0
        for pmid, pmcid in track(pending, description="Ingesting"):
            raw_path = settings.raw_dir / f"{pmcid}.xml"
            try:
                if not raw_path.exists():
                    raw_path.write_bytes(client.fetch_jats(pmcid))
                article = parse_jats(pmcid, raw_path.read_bytes())
                upsert_article(con, article, pmid, raw_path)
            except Exception as exc:  # keep the batch going; report at the end
                failures += 1
                typer.echo(f"[error] {pmcid}: {exc}", err=True)

    typer.echo(f"Ingested: {len(pending) - failures} | Failed: {failures}")


@app.command()
def classify(
    limit: int | None = typer.Option(None, help="Max articles to classify in this run."),
    retry_ungrounded: bool = typer.Option(
        False, help="Also re-classify articles whose evidence quote failed grounding."
    ),
) -> None:
    """Classify pending articles by report type."""
    classifier = ArticleClassifier()
    total = UsageTracker()
    failures = 0

    with connect() as con:
        pending = pending_classification(con, limit, include_ungrounded=retry_ungrounded)
        typer.echo(f"Pending: {len(pending)}")

        for pmcid, raw_path in track(pending, description="Classifying"):
            article = parse_jats(pmcid, Path(raw_path).read_bytes())
            usage = UsageTracker()
            try:
                result = classifier.classify(article, usage)
            except LLMError as exc:
                failures += 1
                typer.echo(f"[error] {pmcid}: {exc}", err=True)
                continue
            source = f"{article.title}\n{article.abstract}"
            grounded = quote_in_source(result.evidence_quote, source)
            upsert_classification(
                con, pmcid, result, grounded, settings.classification_model, usage
            )
            total.input_tokens += usage.input_tokens
            total.output_tokens += usage.output_tokens

    typer.echo(
        f"Classified: {len(pending) - failures} | Failed: {failures} | "
        f"Input tokens: {total.input_tokens} | Output tokens: {total.output_tokens}"
    )


@app.command()
def stats() -> None:
    """Print corpus and classification summary."""
    with connect() as con:
        n_articles, n_full, n_img = con.execute(
            """
            SELECT COUNT(*), count_if(has_full_text), count_if(n_image_only_tables > 0)
            FROM articles
            """
        ).fetchone()
        typer.echo(f"Articles: {n_articles} | Full text: {n_full} | With image-only tables: {n_img}")

        typer.echo("\nLicenses:")
        for license_, n in con.execute(
            "SELECT COALESCE(license, 'unknown'), COUNT(*) FROM articles GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall():
            typer.echo(f"  {license_:20} {n}")

        typer.echo("\nReport types:")
        for report_type, n, n_grounded in con.execute(
            """
            SELECT report_type, COUNT(*), count_if(is_grounded)
            FROM classifications GROUP BY 1 ORDER BY 2 DESC
            """
        ).fetchall():
            typer.echo(f"  {report_type:20} {n:4} (grounded: {n_grounded})")


@app.command("export-gold-candidates")
def export_gold_candidates(
    out: Path = typer.Option(Path("data/gold/candidates.csv"), help="Output CSV path."),
) -> None:
    """Export grounded primary reports as candidates for gold-set annotation."""
    with connect() as con:
        result = con.execute(
            """
            SELECT a.pmcid, a.pmid, a.title, a.license, a.n_tables,
                   a.n_image_only_tables, c.parent_trial
            FROM articles a
            JOIN classifications c USING (pmcid)
            WHERE c.report_type = 'primary_report' AND c.is_grounded
            ORDER BY a.n_image_only_tables, a.pmcid
            """
        )
        columns = [col[0] for col in result.description]
        rows = result.fetchall()

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    typer.echo(f"Exported {len(rows)} candidates to {out}")


if __name__ == "__main__":
    app()
