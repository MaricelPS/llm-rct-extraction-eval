"""DuckDB persistence layer for articles and classifications."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from pubmed_extraction.extract.llm import UsageTracker
from pubmed_extraction.ingest.jats_parser import ParsedArticle
from pubmed_extraction.schemas.classification import ArticleClassification
from pubmed_extraction.settings import settings

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS articles (
        pmcid VARCHAR PRIMARY KEY,
        pmid VARCHAR,
        title VARCHAR,
        license VARCHAR,
        is_retracted BOOLEAN,
        has_full_text BOOLEAN,
        n_tables INTEGER,
        n_image_only_tables INTEGER,
        raw_path VARCHAR,
        ingested_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS classifications (
        pmcid VARCHAR PRIMARY KEY,
        report_type VARCHAR,
        parent_trial VARCHAR,
        rationale VARCHAR,
        evidence_quote VARCHAR,
        is_grounded BOOLEAN,
        model VARCHAR,
        input_tokens INTEGER,
        output_tokens INTEGER,
        classified_at TIMESTAMP
    )
    """,
]


def _utc_now() -> datetime:
    """Naive UTC timestamp (DuckDB TIMESTAMP has no time zone)."""
    return datetime.now(UTC).replace(tzinfo=None)


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[duckdb.DuckDBPyConnection]:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        for statement in SCHEMA_STATEMENTS:
            con.execute(statement)
        yield con
    finally:
        con.close()


def known_pmcids(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in con.execute("SELECT pmcid FROM articles").fetchall()}


def upsert_article(
    con: duckdb.DuckDBPyConnection, article: ParsedArticle, pmid: str, raw_path: Path
) -> None:
    con.execute(
        "INSERT OR REPLACE INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            article.pmcid,
            pmid,
            article.title,
            article.license,
            article.is_retracted,
            article.has_full_text,
            len(article.tables),
            sum(1 for t in article.tables if t.is_image_only),
            str(raw_path),
            _utc_now(),
        ],
    )


def pending_classification(
    con: duckdb.DuckDBPyConnection,
    limit: int | None = None,
    include_ungrounded: bool = False,
) -> list[tuple[str, str]]:
    """Articles with full text, not retracted, unclassified (or ungrounded if requested)."""
    query = """
        SELECT a.pmcid, a.raw_path
        FROM articles a
        LEFT JOIN classifications c USING (pmcid)
        WHERE (c.pmcid IS NULL OR (? AND NOT c.is_grounded))
          AND a.has_full_text AND NOT a.is_retracted
        ORDER BY a.pmcid
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    return con.execute(query, [include_ungrounded]).fetchall()


def upsert_classification(
    con: duckdb.DuckDBPyConnection,
    pmcid: str,
    result: ArticleClassification,
    is_grounded: bool,
    model: str,
    usage: UsageTracker,
) -> None:
    con.execute(
        "INSERT OR REPLACE INTO classifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            pmcid,
            result.report_type.value,
            result.parent_trial,
            result.rationale,
            result.evidence_quote,
            is_grounded,
            model,
            usage.input_tokens,
            usage.output_tokens,
            _utc_now(),
        ],
    )
