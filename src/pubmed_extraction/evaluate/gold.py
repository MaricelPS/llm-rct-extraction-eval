"""Gold-set utilities: annotation templates and validation."""

import csv
import json
import re
from pathlib import Path
from typing import Any
from pubmed_extraction.extract.validation import _normalize

from pydantic import ValidationError

from pubmed_extraction.schemas.trial import TrialExtraction

GOLD_DIR = Path("data/gold")
SPLIT_PATH = GOLD_DIR / "split.csv"
ANNOTATIONS_DIR = GOLD_DIR / "annotations"
PLACEHOLDER = "TODO"
VALID_SPLITS = {"dev", "test"}


def load_split(path: Path = SPLIT_PATH) -> dict[str, str]:
    """Return {pmcid: split} from the split file (comma- or semicolon-separated)."""
    text = path.read_text(encoding="utf-8-sig")
    delimiter = ";" if text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    columns = [c.strip().lower() for c in reader.fieldnames or []]
    if columns[:2] != ["pmcid", "split"]:
        raise ValueError(f"{path}: expected header 'pmcid,split', found {reader.fieldnames}")

    split: dict[str, str] = {}
    for row in reader:
        values = list(row.values())
        pmcid, value = values[0].strip(), values[1].strip().lower()
        if not pmcid:
            continue
        if value not in VALID_SPLITS:
            raise ValueError(f"{pmcid}: invalid split '{value}' (expected dev or test)")
        split[pmcid] = value
    return split


def template(pmcid: str) -> dict[str, Any]:
    """Blank annotation following the TrialExtraction schema. TODO marks fields to fill."""
    return {
        "pmcid": pmcid,
        "trial_registration": PLACEHOLDER,
        "design_notes": None,
        "population": {
            "condition": PLACEHOLDER,
            "key_inclusion_criteria": [PLACEHOLDER],
            "mean_age": None,
            "percent_female": None,
            "evidence": [],
        },
        "arms": [
            {
                "name": PLACEHOLDER,
                "role": PLACEHOLDER,
                "drug": PLACEHOLDER,
                "dose": PLACEHOLDER,
                "route": PLACEHOLDER,
                "is_fixed_combination": False,
                "n_randomized": None,
                "n_analyzed": None,
                "evidence": [],
            }
        ],
        "outcomes": [
            {
                "name": PLACEHOLDER,
                "is_primary": True,
                "timepoint": PLACEHOLDER,
                "comparison": f"{PLACEHOLDER} vs {PLACEHOLDER}",
                "effect_measure": PLACEHOLDER,
                "estimand": PLACEHOLDER,
                "value": None,
                "ci_lower": None,
                "ci_upper": None,
                "ci_level": None,
                "p_value": None,
                "unit": None,
                "evidence": [],
            }
        ],
        "adverse_events": [
            {
                "term": PLACEHOLDER,
                "arm_name": PLACEHOLDER,
                "n_patients": None,
                "percent_patients": None,
                "is_serious": None,
                "evidence": [],
            }
        ],
    }


def _find_placeholders(obj: Any, path: str = "") -> list[str]:
    if isinstance(obj, dict):
        return [
            p
            for key, value in obj.items()
            for p in _find_placeholders(value, f"{path}.{key}" if path else key)
        ]
    if isinstance(obj, list):
        return [p for i, value in enumerate(obj) for p in _find_placeholders(value, f"{path}[{i}]")]
    if isinstance(obj, str) and PLACEHOLDER in obj:
        return [path]
    return []


def validate_annotation(path: Path) -> list[str]:
    """Return the problems found in one annotation file (empty list if valid)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    problems = [f"placeholder left at {p}" for p in _find_placeholders(data)]

    try:
        annotation = TrialExtraction.model_validate(data)
    except ValidationError as exc:
        return problems + [
            f"schema {list(err['loc'])}: {err['msg']} (found: {err.get('input')!r})"
            for err in exc.errors()
        ]

    if annotation.pmcid != path.stem:
        problems.append(f"pmcid '{annotation.pmcid}' does not match file name")

    arm_names = {_normalize(arm.name) for arm in annotation.arms}
    for i, outcome in enumerate(annotation.outcomes):
        if not outcome.is_primary:
            problems.append(f"outcomes[{i}]: gold set only covers primary outcomes")
        sides = [_normalize(side) for side in outcome.comparison.split(" vs ")]
        if len(sides) != 2 or not set(sides) <= arm_names:
            problems.append(f"outcomes[{i}]: comparison must be '<arm> vs <arm>' with arm names")
    for i, ae in enumerate(annotation.adverse_events):
        if _normalize(ae.arm_name) not in arm_names:
            problems.append(f"adverse_events[{i}]: unknown arm '{ae.arm_name}'")
    return problems

QUALIFIER_WORDS = re.compile(
    r"controlled|inadequate|suboptimal|population|chinese|japanese|hospital|outpatient|"
    r"metformin|treated with|on insulin|people with|patients with|without|at high|"
    r"requiring|risk",
    re.I,
)
ROUTE_WORDS = re.compile(r"\boral\b|subcutaneous|injection|tablet", re.I)
DOSE_DETAIL_WORDS = re.compile(
    r"titrat|escalat|target|starting|increment|reduced by|over the first|"
    r"increas|followed by|\bthen\b|\buntil\b|for \d+ (?:day|week|month)s?|for weeks|"
    r"\bweeks? \d|background|if tolerated|as tolerated|maintained at|deferred",
    re.I,
)
DRUG_DETAIL = re.compile(r"[()®™]|reference|biosimilar|product", re.I)
MAX_UNIT_WORDS = 2
SECTION_PREFIX = re.compile(r"^(safety focus areas|most frequent|adverse events by)", re.I)
FOOTNOTE_TAIL = re.compile(r"\s[a-f†‡§*]$")
DEATH_WORDS = re.compile(r"death|fatal|died", re.I)


def lint_annotation(annotation: TrialExtraction) -> list[str]:
    """Heuristic checks against the annotation guidelines. Returns warnings to review."""
    warnings: list[str] = []

    condition = annotation.population.condition
    if QUALIFIER_WORDS.search(condition):
        warnings.append(f"population.condition may contain qualifiers: {condition!r}")

    for arm in annotation.arms:
        tag = f"arms[{arm.name}]"
        if arm.role.value == "placebo" and (arm.drug or arm.dose):
            warnings.append(f"{tag}: drug and dose must be null for placebo")
        if arm.drug and ROUTE_WORDS.search(arm.drug):
            warnings.append(f"{tag}: drug may include route or formulation: {arm.drug!r}")
        if arm.drug and re.search(r"\d", arm.drug):
            warnings.append(f"{tag}: drug contains numbers (dose?): {arm.drug!r}")
        if arm.dose and DOSE_DETAIL_WORDS.search(arm.dose):
            warnings.append(f"{tag}: dose may include escalation or titration details: {arm.dose!r}")
        if arm.drug and DRUG_DETAIL.search(arm.drug):
            warnings.append(f"{tag}: drug may include brand, code or description: {arm.drug!r}")
        if arm.role.value != "placebo" and not arm.drug:
            warnings.append(f"{tag}: drug is null for a non-placebo arm (use substance or class)")
        if arm.dose and not arm.drug:
            warnings.append(f"{tag}: dose without drug: {arm.dose!r}")
        if arm.n_randomized is not None and arm.n_analyzed is not None:
            if arm.n_analyzed > arm.n_randomized:
                warnings.append(f"{tag}: n_analyzed exceeds n_randomized")

    notes = annotation.design_notes or ""
    if re.search(r"cross-?over", notes, re.I):
        for arm in annotation.arms:
            if arm.n_randomized is not None or arm.n_analyzed is not None:
                warnings.append(f"arms[{arm.name}]: crossover design, n values should be null "
                                "unless reported per condition")

    roles = {_normalize(arm.name): arm.role.value for arm in annotation.arms}
    for i, outcome in enumerate(annotation.outcomes):
        tag = f"outcomes[{i}] ({outcome.name[:40]})"
        if outcome.p_value and re.match(r"\s*p", outcome.p_value, re.I):
            warnings.append(f"{tag}: p_value should not start with 'p': {outcome.p_value!r}")
        if outcome.estimand.value == "other":
            warnings.append(f"{tag}: estimand 'other' (trial product estimands are 'hypothetical')")
        if outcome.ci_level is not None and outcome.ci_level > 1:
            warnings.append(f"{tag}: ci_level must be a decimal (0.95): {outcome.ci_level!r}")
        if outcome.unit and (
            outcome.unit.strip().lower() == "other"
            or len(outcome.unit.split()) > MAX_UNIT_WORDS
        ):
            warnings.append(f"{tag}: unit should be a unit, not a description: {outcome.unit!r}")
        if outcome.effect_measure.value == "other" and outcome.value is not None:
            warnings.append(f"{tag}: effect_measure 'other' with an effect estimate "
                            "('other' is for p-value only)")
        first = _normalize(outcome.comparison.split(" vs ")[0])
        if roles.get(first) != "experimental":
            warnings.append(f"{tag}: experimental arm should come first: {outcome.comparison!r}")
        if outcome.value is None and outcome.p_value is None:
            warnings.append(f"{tag}: no effect estimate and no p-value")

    arms_per_term: dict[str, set[str]] = {}
    for i, ae in enumerate(annotation.adverse_events):
        tag = f"adverse_events[{i}] ({ae.term} / {ae.arm_name})"
        arms_per_term.setdefault(ae.term, set()).add(_normalize(ae.arm_name))
        if ae.is_serious is False:
            warnings.append(f"{tag}: is_serious false (use null)")
        if DEATH_WORDS.search(ae.term) and ae.is_serious is not True:
            warnings.append(f"{tag}: deaths must have is_serious true")
        if ae.n_patients is None and ae.percent_patients is None:
            warnings.append(f"{tag}: no patient count or percentage")
        if ae.n_patients == 0 and ae.percent_patients == 0:
            warnings.append(f"{tag}: percent 0.0 is valid only if the cell reads '0 (0.0)'")
        if SECTION_PREFIX.search(ae.term):
            warnings.append(f"{tag}: term prefixed with a section heading")
        if FOOTNOTE_TAIL.search(ae.term):
            warnings.append(f"{tag}: term may end with a footnote marker")

    n_arms = len(annotation.arms)
    for term, arms in arms_per_term.items():
        if len(arms) < n_arms:
            warnings.append(f"adverse_events ({term}): present in {len(arms)} of {n_arms} arms")

    return warnings
