"""Rule-based categorization of the adjudication sheet. Never overwrites a filled category."""

import csv
import re
import sys
from pathlib import Path

SHEET = Path("data/gold/adjudication_sheet_test.csv")


def norm_condition(text: str) -> str:
    text = re.sub(r"\([^)]*\)", " ", text.lower())
    text = re.sub(r"\b(mellitus|people with|patients with)\b", " ", text)
    return " ".join(text.split())


# (name, predicate, category, justification)
RULES = [
    ("prefix", lambda r: r["pmcid"] == "PMC11417641" and r["section"] == "adverse_events"
                         and r["field"] == "term",
     "model_error", "omits parent-row prefix (study-/possibly-/not study-related, "
                    "discontinuation); guideline ambiguous when the row also names an event (v2 clarification)"),
    ("arm_cascade", lambda r: r["pmcid"] == "PMC12577669" and r["kind"] in ("missing", "extra"),
     "model_error", "arm named 'Control' instead of table header 'Standard Care'; all objects "
                    "of that arm unmatched (cascade)"),
    ("serious_false", lambda r: r["field"] == "is_serious" and r["gold"] == ""
                                and r["pred"] == "False",
     "model_error", "is_serious must be null unless serious adverse event or death"),
    ("death_serious", lambda r: r["field"] == "is_serious" and r["gold"] == "True"
                                and r["pred"] == "" and r["label"].lower().startswith("death"),
     "model_error", "deaths are serious adverse events (is_serious true)"),
    ("external_lit", lambda r: r["pmcid"] == "PMC10971983" and r["section"] == "adverse_events"
                               and r["kind"] == "extra",
     "model_error", "AEs taken from discussion of external literature, not from this trial"),
    ("crossover_aes", lambda r: r["pmcid"] == "PMC11296502" and r["section"] == "adverse_events"
                                and r["kind"] == "extra",
     "model_error", "symptoms reported grouped and per sequence, without per-arm counts"),
    ("zero_statement", lambda r: r["pmcid"] == "PMC13627196" and r["section"] == "adverse_events"
                                 and r["kind"] == "missing",
     "model_error", "zero-event statement for the insulin arm omitted"),
    ("reworded_term", lambda r: r["pmcid"] == "PMC13627196" and r["field"] == "term",
     "model_error", "row label reworded (term must be copied exactly)"),
    ("condition_form", lambda r: r["field"] == "condition" and r["gold"] and r["pred"]
                                 and norm_condition(r["gold"]) == norm_condition(r["pred"]),
     "equivalente", "same condition; differs only in 'mellitus', abbreviation or 'people with'"),
    ("ln_unit", lambda r: r["pmcid"] == "PMC11417641" and r["field"] == "unit",
     "ambiguous", "gold records ln-transformed outcomes as ln(<unit>); model reports the "
                  "original unit; guideline gap (v2 clarification)"),
    ("middle_dot", lambda r: "·" in r["pred"] and r["field"] in ("p_value", "dose"),
     "equivalente", "same value; middle-dot decimal separator copied from the article"),
    ("combined_dose", lambda r: r["pmcid"] == "PMC11701190" and r["field"] == "dose"
                                and r["label"] == "Semaglutide",
     "ambiguous", "dose of a combined arm not covered by guidelines; model kept GLP-1 RA only"),
    ("drug_code", lambda r: r["pmcid"] == "PMC11987204" and r["field"] == "drug",
     "model_error", "drug must be the active substance only (no code or description)"),
    ("absence_term", lambda r: r["pmcid"] == "PMC10933706" and r["section"] == "adverse_events",
     "ambiguous", "term for zero-event statements not defined in guidelines; model copied "
                  "the whole sentence (convention adopted for gold; v2 clarification)"),
    ("condition_missing", lambda r: r["pmcid"] == "PMC10709975" and r["field"] == "condition",
     "model_error", "omits the second condition required for inclusion"),
    ("condition_qualifier", lambda r: r["pmcid"] == "PMC10971983" and r["field"] == "condition",
     "model_error", "adds a qualifier ('treated with metformin')"),
    ("condition_order", lambda r: r["pmcid"] == "PMC12584062" and r["field"] == "condition",
     "equivalente", "same conditions; different order and no abbreviations"),
    ("condition_chronic", lambda r: r["pmcid"] == "PMC12992176" and r["field"] == "condition",
     "model_error", "drops 'chronic' from the disease name"),
    ("split_outcome", lambda r: r["pmcid"] == "PMC13627196" and r["section"] == "outcomes",
     "model_error", "standardised effect size extracted as a separate outcome; values missing "
                    "from the primary outcome; p-value taken from another result"),
    ("crossover_fas", lambda r: r["pmcid"] == "PMC11296502" and r["field"] == "n_analyzed",
     "model_error", "efficacy analysed in 32 completers of both periods (Table 3); "
                    "model reported randomized/started"),
    ("itt_25", lambda r: r["pmcid"] == "PMC12577669" and r["field"] == "n_analyzed",
     "model_error", "primary analysis population is ITT with 25 per arm (text and Table 1)"),
    ("n_rand_50", lambda r: r["pmcid"] == "PMC10971983" and r["field"] == "n_randomized",
     "model_error", "article reports 50 randomized per arm"),
    ("frc_role", lambda r: r["pmcid"] == "PMC11060164" and r["field"] == "role",
     "ambiguous", "head-to-head of two fixed-ratio combinations; article designates no "
                  "experimental arm (v2 clarification)"),
    ("paired_diff", lambda r: r["pmcid"] == "PMC12003151" and r["field"] == "effect_measure",
     "model_error", "paired difference in means is a mean difference"),
    ("route_unstated", lambda r: r["pmcid"] == "PMC12992176" and r["field"] == "route",
     "model_error", "route not stated in the article; model used outside knowledge"),
    ("aopwv_measure", lambda r: r["pmcid"] == "PMC12992176" and r["field"] == "effect_measure",
     "model_error", "between-group difference in means with CI (Table 2) is a mean difference"),
    ("hypo_missing", lambda r: r["pmcid"] == "PMC12890759" and r["kind"] == "missing",
     "model_error", "hypoglycaemia counts per arm reported in the text were omitted"),
]


def main() -> None:
    with SHEET.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames
        rows = list(reader)

    applied: dict[str, int] = {}
    for row in rows:
        if row["categoria"]:
            continue
        for name, predicate, category, why in RULES:
            if predicate(row):
                row["categoria"], row["justificacion"] = category, why
                applied[name] = applied.get(name, 0) + 1
                break

    with SHEET.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    for name, n in applied.items():
        print(f"  {name:15} {n}")
    pending = [r for r in rows if not r["categoria"]]
    print(f"\nCategorized: {len(rows) - len(pending)} / {len(rows)}; pending: {len(pending)}\n")
    if "--pending" in sys.argv:
        for r in pending:
            print(f'{r["pmcid"]} | {r["section"]}.{r["field"]} | {r["kind"]} | {r["label"][:60]}'
                  f' | gold={r["gold"][:60]!r} | pred={r["pred"][:60]!r}')


if __name__ == "__main__":
    main()
