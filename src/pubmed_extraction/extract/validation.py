"""Deterministic post-extraction checks. Issues are reported, not silently fixed."""

import unicodedata
import re
from dataclasses import dataclass

from pubmed_extraction.schemas.trial import EffectMeasure, Evidence, TrialExtraction

_RATIO_MEASURES = {EffectMeasure.HAZARD_RATIO, EffectMeasure.ODDS_RATIO, EffectMeasure.RISK_RATIO}


@dataclass
class ValidationIssue:
    path: str
    severity: str  # "error" | "warning"
    message: str


_CHAR_MAP = str.maketrans(
    {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2015": "-",  # horizontal bar
        "\u2212": "-",  # minus sign
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


def _normalize(text: str) -> str:
    """NFKC, unify dashes and quotes, drop table pipes, collapse whitespace, lowercase."""
    text = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP)
    return re.sub(r"\s+", " ", text.replace("|", " ")).strip().lower()


def _check_evidence(evidence: list[Evidence], source: str, path: str) -> list[ValidationIssue]:
    issues = []
    if not evidence:
        issues.append(ValidationIssue(path, "error", "No evidence provided."))
    for i, ev in enumerate(evidence):
        if _normalize(ev.quote) not in source:
            issues.append(
                ValidationIssue(f"{path}.evidence[{i}]", "error", "Quote not found in source text.")
            )
    return issues


def validate(extraction: TrialExtraction, context: str) -> list[ValidationIssue]:
    source = _normalize(context)
    issues: list[ValidationIssue] = []

    issues += _check_evidence(extraction.population.evidence, source, "population")
    if extraction.population.percent_female is not None and not (
            0 <= extraction.population.percent_female <= 100
    ):
        issues.append(ValidationIssue("population.percent_female", "error", "Out of 0-100 range."))

    arm_names = {_normalize(arm.name) for arm in extraction.arms}
    for i, arm in enumerate(extraction.arms):
        path = f"arms[{i}]"
        issues += _check_evidence(arm.evidence, source, path)
        if arm.n_randomized is not None and arm.n_analyzed is not None:
            if arm.n_analyzed > arm.n_randomized:
                issues.append(
                    ValidationIssue(path, "warning", "n_analyzed exceeds n_randomized.")
                )

    for i, outcome in enumerate(extraction.outcomes):
        path = f"outcomes[{i}]"
        issues += _check_evidence(outcome.evidence, source, path)
        values = (outcome.ci_lower, outcome.value, outcome.ci_upper)
        if None not in values and not (values[0] <= values[1] <= values[2]):
            issues.append(ValidationIssue(path, "error", "Value outside its confidence interval."))
        if outcome.effect_measure in _RATIO_MEASURES and any(
                v is not None and v <= 0 for v in values
        ):
            issues.append(ValidationIssue(path, "error", "Ratio measure must be positive."))

    for i, ae in enumerate(extraction.adverse_events):
        path = f"adverse_events[{i}]"
        issues += _check_evidence(ae.evidence, source, path)
        if _normalize(ae.arm_name) not in arm_names:
            issues.append(ValidationIssue(path, "error", f"Unknown arm '{ae.arm_name}'."))
        if ae.percent_patients is not None and not (0 <= ae.percent_patients <= 100):
            issues.append(ValidationIssue(path, "error", "Out of 0-100 range."))
        if ae.n_patients is None and ae.percent_patients is None:
            issues.append(ValidationIssue(path, "warning", "No patient count or percentage."))

    return issues

def quote_in_source(quote: str, source: str) -> bool:
    """Check whether a quote appears verbatim (after whitespace normalization) in the source."""
    return _normalize(quote) in _normalize(source)
