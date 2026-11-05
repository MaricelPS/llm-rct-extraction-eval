"""Batch F: corrections verified against the article for the last pending differences."""

import csv
import json
from pathlib import Path

ANNOTATIONS = Path("data/gold/annotations")
LOG = Path("data/gold/adjudications.csv")
EVIDENCE = "article checked during adjudication (batch F)"
NO_DERIVE = ("percent_female: only per-arm values (or only % men) reported; never derive "
             "by subtracting from 100 or combining per-arm values")
ITT = ("n_analyzed: primary analysis is ITT with BOCF imputation (40 per arm), "
       "not the number of completers")

# (pmcid, section, selector, field, old, new, model output, justification)
# selector: None for population, arm name for arms, name prefix for outcomes
EDITS = [
    ("PMC10709975", "population", None, "percent_female", 42.0, None, "None",
     NO_DERIVE + " (text: '58% of the subjects were men'; Table 1 per arm)"),
    ("PMC11417641", "population", None, "percent_female", 39.8, None, "None",
     NO_DERIVE + " (Table 1 per arm only: 16/54 and 27/54)"),
    ("PMC10933706", "outcomes", "change from baseline in peripheral perfu", "effect_measure",
     "mean_difference", "estimated_treatment_difference", "estimated_treatment_difference",
     "effect_measure: article uses 'estimated treatment difference'"),
    ("PMC13627196", "arms", "Dulaglutide", "n_analyzed", 37, 40, "40", ITT),
    ("PMC13627196", "arms", "Conventional basal-bolus insulin therapy", "n_analyzed", 39, 40,
     "40", ITT),
    # ("PMC10709975", "arms", "Exenatide", "n_analyzed", 16, 19, "19",
    #  "n_analyzed: primary outcome analysed in 19 (Table 3)"),
]


def target(data: dict, section: str, selector):
    if section == "population":
        return data["population"], "-"
    if section == "outcomes":
        matches = [o for o in data["outcomes"] if o["name"].lower().startswith(selector.lower())]
        if len(matches) != 1:
            raise SystemExit(f"outcome starting with {selector!r} not found exactly once")
        return matches[0], matches[0]["name"]
    matches = [arm for arm in data["arms"] if arm["name"] == selector]
    if len(matches) != 1:
        raise SystemExit(f"arm {selector!r} not found exactly once")
    return matches[0], selector


def main() -> None:
    files: dict[str, dict] = {}
    rows = []
    for pmcid, section, selector, field, old, new, model, why in EDITS:
        if pmcid not in files:
            files[pmcid] = json.loads((ANNOTATIONS / f"{pmcid}.json").read_text(encoding="utf-8"))
        obj, label = target(files[pmcid], section, selector)
        if obj[field] != old:
            raise SystemExit(f"{pmcid} {section}[{selector}].{field}: expected {old!r}, "
                             f"found {obj[field]!r} (nothing written)")
        obj[field] = new
        rows.append([pmcid, section, label, field, "mismatch", old, new, model, "gold_error",
                     why, EVIDENCE])

    for pmcid, data in files.items():
        path = ANNOTATIONS / f"{pmcid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"{len(rows)} log rows; {len(files)} files written")


if __name__ == "__main__":
    main()
