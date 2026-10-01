"""Parse JATS XML into section-aware text and markdown tables."""

from dataclasses import dataclass, field

from lxml import etree


@dataclass
class Table:
    label: str
    caption: str
    markdown: str


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


def parse_jats(pmcid: str, xml: bytes) -> ParsedArticle:
    root = etree.fromstring(xml)
    article = root.find(".//article")
    if article is None:
        article = root

    license_node = article.find(".//article-meta/permissions/license")
    license_type = license_node.get("license-type") if license_node is not None else None

    related = article.xpath(".//related-article/@related-article-type")
    is_retracted = any(r in ("retracted-article", "retraction-forward") for r in related)

    body = article.find("body")
    sections = []
    if body is not None:
        for sec in body.findall("sec"):
            title = _text(sec.find("title"))
            paragraphs = [_text(p) for p in sec.iter("p") if p.getparent().tag != "table-wrap-foot"]
            sections.append(Section(title=title, text="\n".join(paragraphs), sec_type=sec.get("sec-type")))

    tables = [
        Table(
            label=_text(tw.find("label")),
            caption=_text(tw.find("caption")),
            markdown=_table_to_markdown(tw.find(".//table")) if tw.find(".//table") is not None else "",
        )
        for tw in article.iter("table-wrap")
    ]

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