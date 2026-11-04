"""Batch C: gold corrections from adjudication of the remaining test differences."""

import csv
import json
from pathlib import Path

ANNOTATIONS = Path("data/gold/annotations")
LOG = Path("data/gold/adjudications.csv")
EVIDENCE = "article checked during adjudication (batch C)"
NO_EVENT = ("statement that no participant had an event counts as 0 in every arm it covers; "
            "term = event as named in the statement (convention, v2 clarification)")
PCT = "percent_patients: not reported in the text (counts only)"
TERM = "term: row label as written in Table 4"

# (pmcid, old name, new name, justification)
RENAMES = [
    ("PMC12577669", "Standard of Care", "Standard Care",
     "name: column header of Table 4 is 'Standard Care'"),
    ("PMC11701190", "Semaglutide plus basal insulin", "Semaglutide",
     "name: column header of Table 2 is 'Semaglutide'"),
    ("PMC11701190", "Multiple daily insulin injections (MDI)", "MDI",
     "name: column header of Table 2 is 'MDI'"),
]

# (pmcid, term, arm, field, old, new, model output, justification)
AE_EDITS = [
    ("PMC13627196", "Gastrointestinal manifestations", "Dulaglutide",
     "percent_patients", 25.0, None, "None", PCT),
    ("PMC13627196", "Gastrointestinal manifestations", "Conventional basal-bolus insulin therapy",
     "percent_patients", 10.0, None, "None", PCT),
    ("PMC13627196", "Hypoglycaemia", "Conventional basal-bolus insulin therapy",
     "percent_patients", 40.0, None, "None", PCT),
    ("PMC11950020", "Any adverse event", "IcoSema", "term",
     "Any adverse event", "AEs", "AEs", TERM),
    ("PMC11950020", "Any adverse event", "Semaglutide 1.0 mg", "term",
     "Any adverse event", "AEs", "AEs", TERM),
    ("PMC11950020", "Serious adverse events", "IcoSema", "term",
     "Serious adverse events", "Serious AEs", "Serious AEs", TERM),
    ("PMC11950020", "Serious adverse events", "Semaglutide 1.0 mg", "term",
     "Serious adverse events", "Serious AEs", "Serious AEs", TERM),
]

# (pmcid, term, arm, n_patients, percent_patients, is_serious, justification)
AE_ADDS = [
    ("PMC10709975", "Serious adverse events", "Exenatide", 0, None, True, NO_EVENT),
    ("PMC10709975", "Serious adverse events", "Control", 0, None, True, NO_EVENT),
    ("PMC10933706", "Adverse events to any medication administered", "liraglutide group",
     0, None, None, NO_EVENT),
    ("PMC10933706", "Adverse events to any medication administered", "control group",
     0, None, None, NO_EVENT),
    ("PMC11822619", "Serious adverse events", "Semaglutide", 0, None, True, NO_EVENT),
    ("PMC11822619", "Serious adverse events", "Placebo", 0, None, True, NO_EVENT),
    ("PMC11822619", "Adverse interactions with alcohol", "Semaglutide", 0, None, None, NO_EVENT),
    ("PMC11822619", "Adverse interactions with alcohol", "Placebo", 0, None, None, NO_EVENT),
    ("PMC11822619", "Treatment-related discontinuations", "Semaglutide", 0, None, None, NO_EVENT),
    ("PMC11822619", "Treatment-related discontinuations", "Placebo", 0, None, None, NO_EVENT),
    ("PMC12992176", "Deaths", "Lixisenatide", 0, None, True, NO_EVENT),
    ("PMC12992176", "Deaths", "Placebo", 0, None, True, NO_EVENT),
    ("PMC12992176", "Serious adverse events related to the drug", "Lixisenatide",
     0, None, True, NO_EVENT + "; statement refers to the lixisenatide group only"),
    ("PMC11950020", "Constipation", "IcoSema", 11, 3.2, None,
     "row present in Table 4 (main safety table), missing in gold"),
    ("PMC11950020", "Constipation", "Semaglutide 1.0 mg", 17, 5.0, None,
     "row present in Table 4 (main safety table), missing in gold"),
]


def _outcome(name: str, value: float, lo: float, hi: float, p: str, unit: str) -> dict:
    return {
        "name": name, "is_primary": True, "timepoint": "32 weeks",
        "comparison": "Semaglutide vs Placebo", "effect_measure": "other",
        "estimand": "not_reported", "value": value, "ci_lower": lo, "ci_upper": hi,
        "ci_level": 0.95, "p_value": p, "unit": unit, "evidence": [],
    }


PRIMARY = "Methods designate 7 primary outcomes (AT quantity by compartment); values from Table 2"
LN_UNIT = "; ln-transformed outcome, unit recorded as ln(<unit>) (ambiguous, v2 clarification)"

# (pmcid, outcome, category, justification)
OUTCOME_ADDS = [
    ("PMC11417641", _outcome("Total body fat (TBF) quantity", -0.21, -0.33, -0.08, "0.0009",
                             "ln(kg)"), "gold_error", PRIMARY + LN_UNIT),
    ("PMC11417641", _outcome("Limb fat quantity", -0.19, -0.32, -0.05, "0.0065", "ln(kg)"),
     "gold_error", PRIMARY + LN_UNIT),
    ("PMC11417641", _outcome("Trunk fat quantity", -0.24, -0.37, -0.11, "<0.0001", "ln(kg)"),
     "gold_error", PRIMARY + LN_UNIT),
    ("PMC11417641", _outcome("Abdominal total adipose tissue (TAT) quantity", -72.07, -109.88,
                             -34.26, "<0.0001", "cm2"), "gold_error", PRIMARY),
    ("PMC11417641", _outcome("Abdominal subcutaneous adipose tissue (SAT) quantity", -42.01,
                             -75.49, -8.52, "0.0138", "cm2"), "gold_error", PRIMARY),
    ("PMC11417641", _outcome("Pericardial fat quantity", -0.18, -0.41, 0.05, "0.13", "ln(mL)"),
     "gold_error", PRIMARY + LN_UNIT),
]

# Decisions that leave the gold unchanged: (pmcid, section, label, field, category, justification)
DECISIONS = [
    ("PMC11296502", "adverse_events", "-", "_all", "ambiguous",
     "Crossover trial: discontinuations reported per sequence and period; a per-condition count "
     "would require summing reported counts (not allowed). Gold kept empty; v2 clarification."),
    ("PMC10971983", "adverse_events", "-", "_all", "model_error",
     "No safety table or per-arm AE counts in the main text; predicted AEs come from the "
     "discussion of external literature. Gold kept empty."),
]


def load(files: dict, pmcid: str) -> dict:
    if pmcid not in files:
        files[pmcid] = json.loads((ANNOTATIONS / f"{pmcid}.json").read_text(encoding="utf-8"))
    return files[pmcid]


def arm_names(data: dict) -> set[str]:
    return {arm["name"] for arm in data["arms"]}


def main() -> None:
    files: dict[str, dict] = {}
    rows = []

    for pmcid, old, new, why in RENAMES:
        data = load(files, pmcid)
        arms = [arm for arm in data["arms"] if arm["name"] == old]
        if len(arms) != 1:
            raise SystemExit(f"{pmcid}: arm {old!r} not found exactly once (nothing written)")
        arms[0]["name"] = new
        refs = 0
        for outcome in data["outcomes"]:
            sides = outcome["comparison"].split(" vs ")
            if old in sides:
                outcome["comparison"] = " vs ".join(new if s == old else s for s in sides)
                refs += 1
        for ae in data["adverse_events"]:
            if ae["arm_name"] == old:
                ae["arm_name"] = new
                refs += 1
        rows.append([pmcid, "arms", old, "name", "mismatch", old, new, "-", "gold_error",
                     f"{why} (renamed in {refs} outcome/AE references)", EVIDENCE])

    for pmcid, term, arm, field, old, new, model, why in AE_EDITS:
        data = load(files, pmcid)
        matches = [ae for ae in data["adverse_events"]
                   if ae["term"] == term and ae["arm_name"] == arm]
        if len(matches) != 1:
            raise SystemExit(f"{pmcid}: AE {term!r} / {arm!r} not found exactly once")
        if matches[0][field] != old:
            raise SystemExit(f"{pmcid} {term!r} / {arm!r}.{field}: expected {old!r}, "
                             f"found {matches[0][field]!r} (nothing written)")
        matches[0][field] = new
        rows.append([pmcid, "adverse_events", f"{term} / {arm}", field, "mismatch", old, new,
                     model, "gold_error", why, EVIDENCE])

    for pmcid, term, arm, n, pct, serious, why in AE_ADDS:
        data = load(files, pmcid)
        if arm not in arm_names(data):
            raise SystemExit(f"{pmcid}: unknown arm {arm!r}; arms: {sorted(arm_names(data))}")
        if any(ae["term"] == term and ae["arm_name"] == arm for ae in data["adverse_events"]):
            raise SystemExit(f"{pmcid}: AE {term!r} / {arm!r} already exists")
        data["adverse_events"].append({
            "term": term, "arm_name": arm, "n_patients": n, "percent_patients": pct,
            "is_serious": serious, "evidence": [],
        })
        rows.append([pmcid, "adverse_events", f"{term} / {arm}", "_object", "missing", "",
                     f"added (n={n})", "-", "gold_error", why, EVIDENCE])

    for pmcid, outcome, category, why in OUTCOME_ADDS:
        data = load(files, pmcid)
        if any(o["name"] == outcome["name"] for o in data["outcomes"]):
            raise SystemExit(f"{pmcid}: outcome {outcome['name']!r} already exists")
        data["outcomes"].append(outcome)
        rows.append([pmcid, "outcomes", outcome["name"], "_object", "missing", "",
                     f"added (value={outcome['value']}, unit={outcome['unit']})", "-",
                     category, why, "Methods; Table 2"])

    for pmcid, section, label, field, category, why in DECISIONS:
        rows.append([pmcid, section, label, field, "decision", "", "unchanged", "-",
                     category, why, EVIDENCE])

    for pmcid, data in files.items():
        path = ANNOTATIONS / f"{pmcid}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    print(f"{len(rows)} log rows; {len(files)} files written")


if __name__ == "__main__":
    main()
