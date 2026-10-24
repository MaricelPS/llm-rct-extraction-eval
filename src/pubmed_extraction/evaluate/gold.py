"""Gold-set utilities: annotation templates and validation."""

import csv
import json
from pathlib import Path
from typing import Any

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

    arm_names = {arm.name for arm in annotation.arms}
    for i, outcome in enumerate(annotation.outcomes):
        if not outcome.is_primary:
            problems.append(f"outcomes[{i}]: gold set only covers primary outcomes")
        sides = [side.strip() for side in outcome.comparison.split(" vs ")]
        if len(sides) != 2 or not set(sides) <= arm_names:
            problems.append(f"outcomes[{i}]: comparison must be '<arm> vs <arm>' with arm names")
    for i, ae in enumerate(annotation.adverse_events):
        if ae.arm_name not in arm_names:
            problems.append(f"adverse_events[{i}]: unknown arm '{ae.arm_name}'")
    return problems
