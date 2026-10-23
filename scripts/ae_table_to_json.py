"""Convert a transcribed adverse event table (CSV) into a gold annotation's adverse_events.

Usage:
    python scripts/ae_table_to_json.py PMCID path/to/table.csv

CSV layout: a "term" column; one column per arm, headed with the exact arm name used in the
annotation; an optional "is_serious" column (true or blank). Cells as written in the article,
e.g. "234 (64.8)" or "0". Empty cells are skipped.
"""

import csv
import json
import re
import sys
from pathlib import Path

CELL = re.compile(r"^\s*(\d+)\s*(?:\(\s*(\d+(?:\.\d+)?)\s*%?\s*\))?\s*$")
RESERVED = {"term", "is_serious"}


def parse_cell(text: str) -> tuple[int, float | None] | None:
    text = text.strip()
    if not text:
        return None
    match = CELL.match(text)
    if not match:
        raise ValueError(f"cannot parse cell {text!r}")
    n, pct = match.groups()
    return int(n), (float(pct) if pct is not None else None)


def main(pmcid: str, csv_path: Path) -> None:
    ann_path = Path("data/gold/annotations") / f"{pmcid}.json"
    annotation = json.loads(ann_path.read_text(encoding="utf-8"))
    arm_names = {arm["name"] for arm in annotation["arms"]}

    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
    reader = csv.DictReader(lines, delimiter=delimiter, restkey="__extra__")
    rows = []
    for line_no, row in enumerate(reader, start=2):
        extra = row.pop("__extra__", None) or []
        if any(str(value).strip() for value in extra):
            sys.exit(
                f"Line {line_no}: more values than header columns: {extra}\n"
                f"Check for a '{delimiter}' inside a term, or leftover cells in that row."
            )
        rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})

    arm_columns = [c.strip() for c in reader.fieldnames if c.strip() not in RESERVED]
    unknown = [c for c in arm_columns if c not in arm_names]
    if unknown:
        sys.exit(f"Columns not matching any arm name: {unknown}\nArms: {sorted(arm_names)}")

    events = []
    for row in rows:
        term = row.get("term", "")
        if not term:
            continue
        serious = row.get("is_serious", "").lower() in ("true", "yes", "1")
        for arm in arm_columns:
            try:
                parsed = parse_cell(row.get(arm, ""))
            except ValueError as exc:
                sys.exit(f"Row '{term}', arm '{arm}': {exc}")
            if parsed is None:
                continue
            n, pct = parsed
            events.append(
                {
                    "term": term,
                    "arm_name": arm,
                    "n_patients": n,
                    "percent_patients": pct,
                    "is_serious": True if serious else None,
                    "evidence": [],
                }
            )

    annotation["adverse_events"] = events
    ann_path.write_text(json.dumps(annotation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{pmcid}: wrote {len(events)} adverse events from {len(rows)} rows x {len(arm_columns)} arms")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], Path(sys.argv[2]))
