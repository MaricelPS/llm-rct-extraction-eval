"""Batch B: gold corrections decided with the paper open after the test run."""

import csv
import json
from pathlib import Path

ANNOTATIONS = Path("data/gold/annotations")
LOG = Path("data/gold/adjudications.csv")
DOSE = "dose: maintenance dose and frequency, without escalation schedules"
EM = "effect_measure: as reported"

# (pmcid, section, selector, field, old, new, model_output, category, justification)
EDITS = [
    ("PMC10971983", "population", None, "condition",
     "type 2 diabetes mellitus at high or exceptionally high cardiovascular risk",
     "type 2 diabetes mellitus", "type 2 diabetes mellitus treated with metformin",
     "gold_error", "condition without qualifiers; cardiovascular risk is a stratification "
                   "criterion, not a disease"),
    ("PMC10709975", "population", None, "condition",
     "type 2 diabetes mellitus and coronary artery disease requiring PCI with drug-eluting "
     "stent implantation",
     "type 2 diabetes mellitus and coronary artery disease", "type 2 diabetes",
     "ambiguous", "PCI with DES is a procedure, not a condition; the article describes the "
                  "population as 'subjects with T2D and coronary artery disease'"),
    ("PMC11701190", "outcomes", 0, "effect_measure", "other", "odds_ratio", "-",
     "gold_error", f"{EM}: odds ratio (OR 2.6, 95% CI 0.7-11.0)"),
    ("PMC11950020", "outcomes", 0, "effect_measure", "other",
     "estimated_treatment_difference", "estimated_treatment_difference",
     "gold_error", f"{EM}: article uses 'estimated treatment difference (ETD)'"),
    ("PMC11987204", "outcomes", 0, "effect_measure", "other", "mean_difference",
     "estimated_treatment_difference",
     "gold_error", f"{EM}: least squares mean difference is a mean difference, not an ETD"),
    ("PMC13627196", "outcomes", 0, "effect_measure", "estimated_treatment_difference",
     "other", "other",
     "gold_error", f"{EM}: estimated standardised effect size, not an ETD"),
    ("PMC13627196", "outcomes", 0, "unit", "other", None, "%",
     "gold_error", "unit: standardised effect size is dimensionless; 'other' is not a unit"),
    ("PMC11822619", "outcomes", 1, "unit", "breath alcohol concentration", None, "None",
     "gold_error", "unit: not reported in text or tables"),
    ("PMC11701190", "arms", "Semaglutide plus basal insulin", "dose",
     "Semaglutide initiated at 0.25 mg once weekly, increased as tolerated to 0.5 mg at Week 4 "
     "and 1 mg at Week 8; insulin degludec once daily",
     "1 mg once weekly + insulin degludec once daily", "1.0 mg once weekly",
     "ambiguous", f"{DOSE}; guideline does not cover combined arms; degludec dose "
                  "individualized, so only frequency recorded"),
    ("PMC11822619", "arms", "Semaglutide", "dose",
     "0.25 mg/week for weeks 1–4, 0.5 mg/week for weeks 5–8, and 1.0 mg at week 9 if "
     "tolerated; the week 9 dose could be maintained at 0.5 mg or deferred for safety or "
     "practical reasons",
     "0.5 mg/week", "0.5 mg once weekly",
     "ambiguous", f"{DOSE}; primary outcome measured during 0.5 mg/week exposure; 1.0 mg "
                  "was conditional and flexible (decision based on the article, not on the prediction)"),
    ("PMC12584062", "arms", "liraglutide", "dose",
     "0.6 mg for the first week, which was increased to 1.2 mg in the second week and "
     "followed by 1.8 mg until day 90",
     "1.8 mg per day", "1.8 mg once daily",
     "gold_error", DOSE),
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
    for pmcid, section, selector, field, old, new, model, category, why in EDITS:
        data = files.setdefault(
            pmcid, json.loads((ANNOTATIONS / f"{pmcid}.json").read_text(encoding="utf-8"))
        )
        obj, label = target(data, section, selector)
        if obj[field] != old:
            raise SystemExit(f"{pmcid} {section}[{selector}].{field}: "
                             f"expected {old!r}, found {obj[field]!r} (nothing written)")
        obj[field] = new
        rows.append([pmcid, section, label, field, "mismatch", old, new, model,
                     category, why, "article checked during adjudication (batch B)"])

    for pmcid, data in files.items():
        path = ANNOTATIONS / f"{pmcid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"{len(rows)} edits applied to {len(files)} files")


if __name__ == "__main__":
    main()
