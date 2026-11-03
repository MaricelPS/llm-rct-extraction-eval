"""Batch A: gold errors flagged by gold-lint after the test run (mechanical, guideline-cited)."""

import csv
import json
from pathlib import Path

ANNOTATIONS = Path("data/gold/annotations")
LOG = Path("data/gold/adjudications.csv")
CI = "ci_level: as a decimal (0.95)"
DOSE = "dose: maintenance dose and frequency, without escalation schedules"

# (pmcid, section, selector, field, old, new, model_output, rule)
EDITS = [
    ("PMC11701190", "outcomes", 0, "ci_level", 95.0, 0.95, "-", CI),
    ("PMC11822619", "outcomes", 0, "ci_level", 95.0, 0.95, "0.95", CI),
    ("PMC11822619", "outcomes", 1, "ci_level", 95.0, 0.95, "0.95", CI),
    ("PMC11950020", "outcomes", 0, "ci_level", 95.0, 0.95, "0.95", CI),
    ("PMC11987204", "outcomes", 0, "ci_level", 95.0, 0.95, "0.95", CI),
    ("PMC12992176", "outcomes", 0, "ci_level", 95.0, 0.95, "0.95", CI),
    ("PMC11296502", "arms", "pioglitazone", "dose",
     "15 mg once-daily, increased by 15 mg every other week to 45 mg once-daily",
     "45 mg once-daily", "45mg once-daily", DOSE),
    ("PMC11417641", "arms", "Semaglutide", "dose",
     "0.25 mg weekly for 4 weeks, followed by 0.5 mg weekly for another 4 weeks, "
     "then 1.0 mg weekly for 24 weeks",
     "1.0 mg weekly", "1·0 mg once weekly", DOSE),
    ("PMC11987204", "arms", "LY05008", "dose",
     "1.5 mg once weekly for 24 weeks, with metformin 1.5–2.0 g daily as background therapy",
     "1.5 mg once weekly", "1.5 mg once weekly", DOSE),
    ("PMC11987204", "arms", "Dulaglutide", "dose",
     "1.5 mg once weekly for 24 weeks, with metformin 1.5–2.0 g daily as background therapy",
     "1.5 mg once weekly", "1.5 mg once weekly", DOSE),
    ("PMC12992176", "arms", "Lixisenatide", "dose",
     "10 mcg once daily increased to 20 mcg after 2 weeks",
     "20 mcg once daily", "20 mcg once daily", DOSE),
    ("PMC13627196", "arms", "Dulaglutide", "dose",
     "0.75 mg once weekly for 24 weeks", "0.75 mg once weekly", "0.75 mg once weekly", DOSE),
    ("PMC11987204", "arms", "Dulaglutide", "drug",
     "Dulaglutide (Trulicity), reference product", "dulaglutide", "dulaglutide",
     "drug: active substance only"),
    ("PMC12890759", "arms", "MDI", "drug", None, "insulin", "insulin",
     "drug: class as the article names it (MDI -> insulin)"),
    ("PMC12584062", "arms", "control", "dose",
     "standard treatment according to the guidelines", None, "None",
     "dose: maintenance dose and frequency; standard care is not a dose"),
    ("PMC11060164", "outcomes", 0, "unit",
     "% of time in target glucose range (70–180 mg/dL)", "%", "%", "unit: as written"),
    ("PMC11060164", "outcomes", 1, "unit",
     "% of time below target glucose range (<70 mg/dL)", "%", "%", "unit: as written"),
    ("PMC11296502", "population", None, "condition",
     "type 2 diabetes mellitus without established cardiovascular disease",
     "type 2 diabetes mellitus", "type 2 diabetes", "condition: without qualifiers"),
    ("PMC12890759", "population", None, "condition",
     "people with type 2 diabetes (PwT2D)", "type 2 diabetes", "type 2 diabetes",
     "condition: the disease, without qualifiers"),
]


def target(data: dict, section: str, selector):
    if section == "population":
        return data["population"], "-"
    if section == "outcomes":
        obj = data["outcomes"][selector]
        return obj, obj["name"]
    matches = [arm for arm in data["arms"] if arm["name"] == selector]
    if len(matches) != 1:
        raise SystemExit(f"arm {selector!r} not found exactly once")
    return matches[0], selector


def main() -> None:
    files: dict[str, dict] = {}
    rows = []
    for pmcid, section, selector, field, old, new, model, rule in EDITS:
        data = files.setdefault(
            pmcid, json.loads((ANNOTATIONS / f"{pmcid}.json").read_text(encoding="utf-8"))
        )
        obj, label = target(data, section, selector)
        if obj[field] != old:
            raise SystemExit(f"{pmcid} {section}[{selector}].{field}: "
                             f"expected {old!r}, found {obj[field]!r} (nothing written)")
        obj[field] = new
        rows.append([pmcid, section, label, field, "mismatch", old, new, model,
                     "gold_error", rule, "gold-lint after test run"])

    for pmcid, data in files.items():
        path = ANNOTATIONS / f"{pmcid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"{len(rows)} edits applied to {len(files)} files")


if __name__ == "__main__":
    main()
