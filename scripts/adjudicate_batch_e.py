"""Batch E: corrections verified against the article during adjudication of remaining diffs."""

import csv
import json
from pathlib import Path

ANNOTATIONS = Path("data/gold/annotations")
LOG = Path("data/gold/adjudications.csv")
EVIDENCE = "article checked during adjudication (batch E)"
MDI_DOSE = "insulin degludec once daily + prandial insulin aspart"  # or None

# (pmcid, section, selector, field, old, new, category, justification)
EDITS = [
    ("PMC12003151", "population", None, "mean_age", None, 45.0, "gold_error",
     "mean age of the overall population reported"),
    ("PMC12003151", "population", None, "percent_female", None, 61.0, "gold_error",
     "percent female of the overall population reported (17/28)"),
    ("PMC12003151", "arms", "Placebo", "route", "not_reported", "subcutaneous", "gold_error",
     "route stated in the article (subcutaneous saline)"),
    ("PMC12992176", "outcomes", 0, "ci_lower", None, -0.39, "gold_error",
     "CI reported in Table 2 (Ao-PWV row)"),
    ("PMC12992176", "outcomes", 0, "ci_upper", None, 1.01, "gold_error",
     "CI reported in Table 2 (Ao-PWV row)"),
    ("PMC11701190", "arms", "MDI", "dose",
     "Insulin degludec once daily plus prandial insulin aspart; doses adjusted according to "
     "the study protocol", MDI_DOSE, "ambiguous",
     "dose: titration detail removed; individualized insulin recorded by frequency, as in the "
     "semaglutide arm (guideline gap for combined arms, v2)"),
]

ZERO_CELL = "cell reads '0' (count only): percent_patients null"
# (pmcid, term, arm, field, old, new, justification)
AE_EDITS = [
    ("PMC12003151", "Severe hypoglycemic event", "Semaglutide", "percent_patients", 0.0, None,
     ZERO_CELL),
    ("PMC12003151", "Euglycemic ketosis", "Placebo", "percent_patients", 0.0, None, ZERO_CELL),
    ("PMC12003151", "Diabetic ketoacidosis", "Semaglutide", "percent_patients", 0.0, None,
     ZERO_CELL),
    ("PMC12003151", "Diabetic ketoacidosis", "Placebo", "percent_patients", 0.0, None,
     ZERO_CELL),
]

RETINO = "row of the main safety table (Table 4), participants column; missing in gold"
NO_SEVERE = ("statement that no severe hypoglycaemia occurred counts as 0 in every arm; "
             "'severe' does not imply 'serious'")
# (pmcid, term, arm, n, percent, is_serious, justification)
AE_ADDS = [
    ("PMC12003151", "Progression of diabetic retinopathy: Proliferative", "Placebo",
     1, 4.0, None, RETINO),
    ("PMC12003151", "Progression of diabetic retinopathy: Proliferative", "Semaglutide",
     0, 0.0, None, RETINO),
    ("PMC12003151", "Progression of diabetic retinopathy: Nonproliferative", "Placebo",
     0, 0.0, None, RETINO),
    ("PMC12003151", "Progression of diabetic retinopathy: Nonproliferative", "Semaglutide",
     1, 4.0, None, RETINO),
    ("PMC12890759", "Severe hypoglycaemia", "iGlarLixi", 0, None, None, NO_SEVERE),
    ("PMC12890759", "Severe hypoglycaemia", "MDI", 0, None, None, NO_SEVERE),
]


def load(files: dict, pmcid: str) -> dict:
    if pmcid not in files:
        files[pmcid] = json.loads((ANNOTATIONS / f"{pmcid}.json").read_text(encoding="utf-8"))
    return files[pmcid]


def target(data: dict, section: str, selector):
    if section == "population":
        return data["population"], "-"
    if section == "outcomes":
        obj = data["outcomes"][selector]
        return obj, obj["name"]
    matches = [arm for arm in data["arms"] if arm["name"] == selector]
    if len(matches) != 1:
        raise SystemExit(f"arm {selector!r} not found exactly once (nothing written)")
    return matches[0], selector


def main() -> None:
    files: dict[str, dict] = {}
    rows = []

    for pmcid, section, selector, field, old, new, category, why in EDITS:
        obj, label = target(load(files, pmcid), section, selector)
        if obj[field] != old:
            raise SystemExit(f"{pmcid} {section}[{selector}].{field}: expected {old!r}, "
                             f"found {obj[field]!r} (nothing written)")
        obj[field] = new
        rows.append([pmcid, section, label, field, "mismatch", old, new, "-", category, why,
                     EVIDENCE])

    for pmcid, term, arm, field, old, new, why in AE_EDITS:
        data = load(files, pmcid)
        matches = [ae for ae in data["adverse_events"]
                   if ae["term"] == term and ae["arm_name"] == arm]
        if len(matches) != 1 or matches[0][field] != old:
            raise SystemExit(f"{pmcid} {term!r} / {arm!r}.{field}: not found or not {old!r}")
        matches[0][field] = new
        rows.append([pmcid, "adverse_events", f"{term} / {arm}", field, "mismatch", old, new,
                     "None", "gold_error", why, "Table 4"])

    for pmcid, term, arm, n, pct, serious, why in AE_ADDS:
        data = load(files, pmcid)
        if arm not in {a["name"] for a in data["arms"]}:
            raise SystemExit(f"{pmcid}: unknown arm {arm!r}")
        if any(ae["term"] == term and ae["arm_name"] == arm for ae in data["adverse_events"]):
            raise SystemExit(f"{pmcid}: AE {term!r} / {arm!r} already exists")
        data["adverse_events"].append({
            "term": term, "arm_name": arm, "n_patients": n, "percent_patients": pct,
            "is_serious": serious, "evidence": [],
        })
        rows.append([pmcid, "adverse_events", f"{term} / {arm}", "_object", "missing", "",
                     f"added (n={n})", "-", "gold_error", why, EVIDENCE])

    for pmcid, data in files.items():
        path = ANNOTATIONS / f"{pmcid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"{len(rows)} log rows; {len(files)} files written")


if __name__ == "__main__":
    main()
