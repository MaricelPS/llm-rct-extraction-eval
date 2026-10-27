"""Route article sections and tables to the extraction context of each call."""

import re

from pubmed_extraction.ingest.jats_parser import ParsedArticle, Section

_METHODS_PATTERN = re.compile(r"method|design|patients|participants|procedures", re.I)
_RESULTS_PATTERN = re.compile(r"result|outcome|efficacy|safety|adverse", re.I)
_EXCLUDED_PATTERN = re.compile(r"reference|acknowledg|funding|conflict|disclosure|author", re.I)


def classify_section(section: Section) -> str:
    """Return 'methods', 'results', 'excluded' or 'other' (sec-type first, then title)."""
    sec_type = (section.sec_type or "").lower()
    if "method" in sec_type:
        return "methods"
    if "result" in sec_type:
        return "results"
    if _EXCLUDED_PATTERN.search(section.title):
        return "excluded"
    if _METHODS_PATTERN.search(section.title):
        return "methods"
    if _RESULTS_PATTERN.search(section.title):
        return "results"
    return "other"


def _assemble(article: ParsedArticle, kind: str) -> str:
    parts = [f"# TITLE\n{article.title}", f"# ABSTRACT\n{article.abstract}"]
    for section in article.sections:
        if classify_section(section) == kind:
            parts.append(f"# {kind.upper()}: {section.title}\n{section.text}")
    for table in article.tables:
        if table.markdown:
            parts.append(f"# {table.label}: {table.caption}\n{table.markdown}")
        elif table.is_image_only:
            parts.append(
                f"# {table.label}: {table.caption}\n"
                "[Table content is only available as an image and was not extracted. "
                "Do not infer its values.]"
            )
    return "\n\n".join(parts)


def build_design_context(article: ParsedArticle) -> str:
    """Context for population and arms: abstract, methods and all tables."""
    return _assemble(article, "methods")


def build_results_context(article: ParsedArticle) -> str:
    """Context for outcomes and adverse events: abstract, results and all tables."""
    return _assemble(article, "results")

def build_context(article: ParsedArticle) -> str:
    """Shared context for all extraction calls: abstract, methods, results and all tables."""
    parts = [f"# TITLE\n{article.title}", f"# ABSTRACT\n{article.abstract}"]
    for kind in ("methods", "results"):
        for section in article.sections:
            if classify_section(section) == kind:
                parts.append(f"# {kind.upper()}: {section.title}\n{section.text}")
    for table in article.tables:
        if table.markdown:
            parts.append(f"# {table.label}: {table.caption}\n{table.markdown}")
        elif table.is_image_only:
            parts.append(
                f"# {table.label}: {table.caption}\n"
                "[Table content is only available as an image and was not extracted. "
                "Do not infer its values.]"
            )
    return "\n\n".join(parts)
