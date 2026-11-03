"""Command-line interface for the PubMed extraction pipeline."""

import csv
from pathlib import Path

import typer
from rich.progress import track

import json
from collections import Counter

from pubmed_extraction.evaluate.adjudication import write_adjudication_sheet
from pubmed_extraction.evaluate.gold import (
    ANNOTATIONS_DIR,
    lint_annotation,
    load_split,
    template,
    validate_annotation,
)
from dataclasses import asdict

from pubmed_extraction.evaluate.compare import compare, summarize
from pubmed_extraction.extract.extractor import TrialExtractor
from pubmed_extraction.extract.router import build_context
from pubmed_extraction.extract.validation import validate
from pubmed_extraction.schemas.trial import TrialExtraction
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
            SELECT a.pmcid,
                  'https://pmc.ncbi.nlm.nih.gov/articles/' || a.pmcid || '/' AS pmc_url,
                   a.pmid, a.title, a.license, a.n_tables,
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

@app.command("gold-template")
def gold_template() -> None:
    """Create blank annotation files for every PMCID in data/gold/split.csv (never overwrites)."""
    split = load_split()
    ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for pmcid in split:
        path = ANNOTATIONS_DIR / f"{pmcid}.json"
        if path.exists():
            continue
        path.write_text(
            json.dumps(template(pmcid), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        created += 1
    typer.echo(f"Created: {created} | Already existing: {len(split) - created}")


@app.command("gold-validate")
def gold_validate(
    pmcid: str | None = typer.Option(None, help="Validate a single PMCID only."),
) -> None:
    """Validate gold annotations listed in data/gold/split.csv."""
    split = load_split()
    if pmcid is not None:
        if pmcid not in split:
            typer.echo(f"{pmcid} is not in split.csv")
            raise typer.Exit(code=1)
        split = {pmcid: split[pmcid]}
    else:
        counts = Counter(split.values())
        typer.echo(f"Split: {counts.get('dev', 0)} dev | {counts.get('test', 0)} test\n")

    n_valid = 0
    for current, subset in sorted(split.items()):
        path = ANNOTATIONS_DIR / f"{current}.json"
        if not path.exists():
            typer.echo(f"[missing] {current} ({subset})")
            continue
        problems = validate_annotation(path)
        if problems:
            typer.echo(f"[invalid] {current} ({subset})")
            for problem in problems:
                typer.echo(f"    - {problem}")
        else:
            typer.echo(f"[valid] {current} ({subset})")
            n_valid += 1
    typer.echo(f"\nValid: {n_valid}/{len(split)}")

EXTRACTIONS_DIR = Path("data/processed/extractions")
EVAL_DIR = Path("data/processed/eval")


@app.command()
def extract(
    split_name: str = typer.Option("dev", "--split", help="dev or test."),
    pmcid: str | None = typer.Option(None, help="Extract a single PMCID only."),
    force: bool = typer.Option(False, help="Re-extract even if a result exists."),
) -> None:
    """Run LLM extraction on the gold-set articles of a split."""
    split = load_split()
    targets = [pmcid] if pmcid else sorted(p for p, s in split.items() if s == split_name)
    if split_name == "test" and not pmcid:
        typer.confirm("Extracting the test split. Guidelines and prompt frozen?", abort=True)

    extractor = TrialExtractor()
    out_dir = EXTRACTIONS_DIR / f"{settings.extraction_model}_{settings.extraction_effort}"
    out_dir.mkdir(parents=True, exist_ok=True)
    total = UsageTracker()

    for current in targets:
        out_path = out_dir / f"{current}.json"
        if out_path.exists() and not force:
            typer.echo(f"[skip] {current} (already extracted)")
            continue
        article = parse_jats(current, (settings.raw_dir / f"{current}.xml").read_bytes())
        try:
            extraction, usage = extractor.extract(article)
        except LLMError as exc:
            typer.echo(f"[error] {current}: {exc}", err=True)
            continue
        context = build_context(article)
        issues = validate(extraction, context)
        payload = {
            "extraction": extraction.model_dump(mode="json"),
            "model": settings.extraction_model,
            "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
            "validation_issues": [asdict(issue) for issue in issues],
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        total.input_tokens += usage.input_tokens
        total.output_tokens += usage.output_tokens
        n_errors = sum(1 for i in issues if i.severity == "error")
        typer.echo(
            f"[done] {current}: {len(extraction.arms)} arms, {len(extraction.outcomes)} outcomes, "
            f"{len(extraction.adverse_events)} AEs | validation errors: {n_errors} | "
            f"tokens in/out: {usage.input_tokens}/{usage.output_tokens}"
        )

    typer.echo(f"\nTotal tokens in/out: {total.input_tokens}/{total.output_tokens}")


@app.command()
def evaluate(
    split_name: str = typer.Option("dev", "--split", help="dev or test."),
    diffs: bool = typer.Option(True, help="Show per-field differences."),
) -> None:
    """Compare extractions with gold annotations, field by field."""
    split = load_split()
    targets = sorted(p for p, s in split.items() if s == split_name)
    config = f"{settings.extraction_model}_{settings.extraction_effort}"
    pred_dir = EXTRACTIONS_DIR / config
    reports = []

    for current in targets:
        pred_path = pred_dir / f"{current}.json"
        if not pred_path.exists():
            typer.echo(f"[missing extraction] {current}")
            continue
        gold = TrialExtraction.model_validate_json(
            (ANNOTATIONS_DIR / f"{current}.json").read_text(encoding="utf-8")
        )
        pred = TrialExtraction.model_validate(
            json.loads(pred_path.read_text(encoding="utf-8"))["extraction"]
        )
        report = compare(gold, pred)
        reports.append(report)
        if diffs:
            typer.echo(f"\n=== {current} ===")
            for section, c in report.sets.items():
                typer.echo(f"  {section}: gold {c['gold']} | pred {c['pred']} | matched {c['matched']}")
            for diff in report.diffs:
                typer.echo(f"  - {diff}")

    summary = summarize(reports)
    diffs_path = EVAL_DIR / f"{config}_{split_name}_diffs.csv"
    n_rows = write_adjudication_sheet(reports, diffs_path)
    typer.echo(f"Saved {n_rows} diffs to {diffs_path}")
    typer.echo(f"\n=== Summary: {split_name} ({len(reports)} papers, {config}) ===")
    typer.echo("\nSets (precision / recall):")
    for section, c in summary["sets"].items():
        p = f"{c['precision']:.0%}" if c["precision"] is not None else "-"
        r = f"{c['recall']:.0%}" if c["recall"] is not None else "-"
        typer.echo(f"  {section:16} P {p:>5} | R {r:>5}  (gold {c['gold']}, pred {c['pred']})")
    typer.echo("\nFields (accuracy on matched items):")
    for key, t in summary["fields"].items():
        typer.echo(f"  {key:34} {t['correct']:4}/{t['total']:<4} ({t['correct'] / t['total']:.0%})")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = EVAL_DIR / f"{settings.extraction_model}_{settings.extraction_effort}_{split_name}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"\nSaved summary to {out}")

@app.command("gold-lint")
def gold_lint(
    pmcid: str | None = typer.Option(None, help="Lint a single PMCID only."),
) -> None:
    """Heuristic guideline checks on gold annotations (warnings to review, not errors)."""
    split = load_split()
    targets = [pmcid] if pmcid else sorted(split)
    exceptions: dict[str, list[str]] = {}
    exceptions_path = Path("data/gold/lint_exceptions.csv")
    if exceptions_path.exists():
        with exceptions_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                exceptions.setdefault(row["pmcid"].strip(), []).append(
                    row["warning_contains"].strip()
                )
    total = 0
    for current in targets:
        path = ANNOTATIONS_DIR / f"{current}.json"
        try:
            annotation = TrialExtraction.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            typer.echo(f"[skip] {current}: run gold-validate first")
            continue
        warnings = [
            w for w in lint_annotation(annotation)
            if not any(fragment in w for fragment in exceptions.get(current, []))
        ]
        if warnings:
            typer.echo(f"\n[{len(warnings)}] {current} ({split.get(current, '?')})")
            for warning in warnings:
                typer.echo(f"    - {warning}")
        total += len(warnings)
    typer.echo(f"\nTotal warnings: {total}")

if __name__ == "__main__":
    app()
