"""Export gold-vs-prediction differences as a sheet for adjudication."""

import csv
from pathlib import Path

from pubmed_extraction.evaluate.compare import PaperReport

COLUMNS = [
    "pmcid", "section", "label", "field", "kind", "gold", "pred",
    "categoria",      # model_error | gold_error | ambiguous | equivalente
    "gold_nuevo",     # solo si categoria == gold_error
    "justificacion",  # regla de GUIDELINES.md que aplica
    "evidencia",      # ubicación en el paper (sección / tabla / fila)
]


def _fmt(value) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def write_adjudication_sheet(reports: list[PaperReport], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for report in sorted(reports, key=lambda r: r.pmcid):
            for d in report.records:
                writer.writerow({
                    "pmcid": d.pmcid, "section": d.section, "label": d.label,
                    "field": d.field, "kind": d.kind,
                    "gold": _fmt(d.gold), "pred": _fmt(d.pred),
                })
                rows += 1
    return rows
