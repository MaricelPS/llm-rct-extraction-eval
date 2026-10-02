"""Smoke test: fetch a few GLP-1 RA RCTs from PMC and inspect parser output."""

from pubmed_extraction.extract.router import classify_section
from pubmed_extraction.ingest.jats_parser import parse_jats
from pubmed_extraction.ingest.ncbi_client import NCBIClient

QUERY = (
    "(semaglutide[tiab] OR liraglutide[tiab] OR dulaglutide[tiab] "
    "OR exenatide[tiab] OR lixisenatide[tiab]) "
    'AND "Randomized Controlled Trial"[pt] '
    'AND "pubmed pmc"[sb] '
    'NOT "Retracted Publication"[pt]'
)


def main() -> None:
    client = NCBIClient()
    pmids = client.search_pubmed(QUERY, retmax=10)
    print(f"PMIDs found: {len(pmids)}")

    mapping = client.pmids_to_pmcids(pmids)
    print(f"With PMCID: {len(mapping)}\n")

    for pmid, pmcid in mapping.items():
        article = parse_jats(pmcid, client.fetch_jats(pmcid))
        print(f"=== {pmcid} (PMID {pmid}) ===")
        print(f"Title: {article.title[:100]}")
        print(f"License: {article.license} | Full text: {article.has_full_text}")
        print(f"Retracted: {article.is_retracted}")
        for section in article.sections:
            print(
                f"  [{classify_section(section):8}] sec-type={section.sec_type!s:12} "
                f"{section.title[:60]}"
            )
        for table in article.tables:
            n_rows = table.markdown.count("\n") - 1 if table.markdown else 0
            content = "IMAGE ONLY" if table.is_image_only else f"{n_rows} rows"
            print(f"  TABLE {table.label}: {content} | {table.caption[:60]}")
        print()


if __name__ == "__main__":
    main()
