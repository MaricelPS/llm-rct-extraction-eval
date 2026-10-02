"""Smoke test: classify a few GLP-1 RA RCT-derived articles by report type."""

from pubmed_extraction.extract.classifier import ArticleClassifier
from pubmed_extraction.extract.llm import UsageTracker
from pubmed_extraction.ingest.jats_parser import parse_jats
from pubmed_extraction.ingest.ncbi_client import NCBIClient
from pubmed_extraction.extract.validation import quote_in_source

QUERY = (
    "(semaglutide[tiab] OR liraglutide[tiab] OR dulaglutide[tiab] "
    "OR exenatide[tiab] OR lixisenatide[tiab]) "
    'AND "Randomized Controlled Trial"[pt] '
    'AND "pubmed pmc"[sb] '
    'NOT "Retracted Publication"[pt]'
)


def main() -> None:
    client = NCBIClient()
    classifier = ArticleClassifier()
    usage = UsageTracker()

    pmids = client.search_pubmed(QUERY, retmax=10)
    mapping = client.pmids_to_pmcids(pmids)

    for pmid, pmcid in mapping.items():
        article = parse_jats(pmcid, client.fetch_jats(pmcid))
        result = classifier.classify(article, usage)
        print(f"=== {pmcid} (PMID {pmid}) ===")
        print(f"Title:     {article.title[:100]}")
        print(f"Type:      {result.report_type.value}")
        print(f"Trial:     {result.parent_trial}")
        print(f"Rationale: {result.rationale}")
        print(f"Evidence:  {result.evidence_quote[:120]}")
        source = f"{article.title}\n{article.abstract}"
        print(f"Grounded:  {quote_in_source(result.evidence_quote, source)}")
        print()

    print(f"Calls: {len(usage.calls)} | Input tokens: {usage.input_tokens} "
          f"| Output tokens: {usage.output_tokens}")


if __name__ == "__main__":
    main()
