"""Parse JATS XML into section-aware text and markdown tables."""

import re

_ALI_NS = "http://www.niso.org/schemas/ali/1.0/"
_XLINK_NS = "http://www.w3.org/1999/xlink"
_CC_URL = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)", re.I)

from dataclasses import dataclass, field

from lxml import etree


@dataclass
class Table:
    label: str
    caption: str
    markdown: str
    is_image_only: bool = False


@dataclass
class Section:
    title: str
    text: str
    sec_type: str | None = None


@dataclass
class ParsedArticle:
    pmcid: str
    title: str
    license: str | None
    is_retracted: bool
    has_full_text: bool
    abstract: str
    sections: list[Section] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)


def _text(node: etree._Element | None) -> str:
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def _table_to_markdown(table: etree._Element) -> str:
    """Flatten an HTML-like JATS table into markdown. Spanning cells are repeated naively."""
    rows = []
    for tr in table.iter("tr"):
        cells = [_text(c).replace("|", "/") for c in tr if c.tag in ("td", "th")]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, *body = rows
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)

def _extract_license(article: etree._Element) -> str | None:
    """Return a normalized license label (e.g. 'cc-by', 'cc0', 'ada-license') or None."""
    permissions = article.find(".//article-meta/permissions")
    if permissions is None:
        return None
    license_node = permissions.find("license")
    candidates = [
        license_node.get("license-type") if license_node is not None else None,
        license_node.get(f"{{{_XLINK_NS}}}href") if license_node is not None else None,
        permissions.findtext(f".//{{{_ALI_NS}}}license_ref"),
        _text(license_node),
    ]
    values = [v for v in candidates if v]
    if not values:
        return None

    for value in values:
        match = _CC_URL.search(value)
        if match:
            kind, code = match.group(1).lower(), match.group(2).lower()
            if kind == "publicdomain":
                return "cc0" if code == "zero" else f"pd-{code}"
            return f"cc-{code}"

    lowered = " ".join(values).lower()
    if "diabetesjournals.org" in lowered:
        return "ada-license"
    if "public domain" in lowered and "government" in lowered:
        return "us-gov-pd"
    if "text mining" in lowered:
        return "pmc-text-mining"

    raw = values[0]
    return raw if len(raw) <= 40 else "other"

def parse_jats(pmcid: str, xml: bytes) -> ParsedArticle:
    root = etree.fromstring(xml)
    article = root.find(".//article")
    if article is None:
        article = root

    license_type = _extract_license(article)

    related = article.xpath(".//related-article/@related-article-type")
    is_retracted = any(r in ("retracted-article", "retraction-forward") for r in related)

    body = article.find("body")
    sections = []
    if body is not None:
        for sec in body.findall("sec"):
            title = _text(sec.find("title"))
            paragraphs = [_text(p) for p in sec.iter("p") if p.getparent().tag != "table-wrap-foot"]
            sections.append(Section(title=title, text="\n".join(paragraphs), sec_type=sec.get("sec-type")))

    tables = []
    for tw in article.iter("table-wrap"):
        table_node = tw.find(".//table")
        tables.append(
            Table(
                label=_text(tw.find("label")),
                caption=_text(tw.find("caption")),
                markdown=_table_to_markdown(table_node) if table_node is not None else "",
                is_image_only=table_node is None and tw.find(".//graphic") is not None,
            )
        )

    return ParsedArticle(
        pmcid=pmcid,
        title=_text(article.find(".//article-meta/title-group/article-title")),
        license=license_type,
        is_retracted=is_retracted,
        has_full_text=body is not None and bool(sections),
        abstract=_text(article.find(".//article-meta/abstract")),
        sections=sections,
        tables=tables,
    )
