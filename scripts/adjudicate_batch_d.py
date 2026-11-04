"""Batch D: non-standard spaces in PMC11417641 AE terms; unit of an odds ratio in PMC11701190."""

import csv
import json
from pathlib import Path

ANNOTATIONS = Path("data/gold/annotations")
TABLES = Path("data/gold/tables")
LOG = Path("data/gold/adjudications.csv")
EM_SPACE = "\u2003"


def main() -> None:
    rows = []

    # 1) EM SPACE -> regular space in PMC11417641 (annotation and source table)
    path = ANNOTATIONS / "PMC11417641.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fixed = 0
    for ae in data["adverse_events"]:
        if EM_SPACE in ae["term"]:
            ae["term"] = ae["term"].replace(EM_SPACE, " ")
            fixed += 1
    if fixed != 6:
        raise SystemExit(f"expected 6 terms with EM SPACE, found {fixed} (nothing written)")
    table = TABLES / "PMC11417641.csv"
    table_text = table.read_text(encoding="utf-8")
    if EM_SPACE not in table_text:
        raise SystemExit("EM SPACE not found in the source table (nothing written)")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    table.write_text(table_text.replace(EM_SPACE, " "), encoding="utf-8")
    rows.append(["PMC11417641", "adverse_events", "Not study-related adverse events: Elevated "
                                                  "aspartate aminotransferase (6 entries)", "term", "mismatch",
                 "EM SPACE after ':'", "regular space", "-", "gold_error",
                 "non-standard space copied from the article during transcription; fixed in "
                 "annotation and source table", "gold scan for non-standard spaces (batch D)"])

    # 2) Odds ratio is dimensionless: unit '%' -> null in PMC11701190
    path = ANNOTATIONS / "PMC11701190.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    outcome = data["outcomes"][0]
    if outcome["effect_measure"] != "odds_ratio" or outcome["unit"] != "%":
        raise SystemExit(f"PMC11701190 outcome[0]: unexpected effect_measure/unit "
                         f"{outcome['effect_measure']!r}/{outcome['unit']!r} (nothing written)")
    outcome["unit"] = None
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows.append(["PMC11701190", "outcomes", outcome["name"], "unit", "mismatch", "%", None,
                 "None", "gold_error", "unit: odds ratio is dimensionless",
                 "article checked during adjudication (batch D)"])

    with LOG.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"{len(rows)} log rows; EM SPACE fixed in {fixed} terms")


if __name__ == "__main__":
    main()
