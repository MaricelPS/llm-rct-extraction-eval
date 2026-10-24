"""Pydantic schemas for structured extraction of GLP-1 RA randomized controlled trials.

All fields are required (nullable where needed) to stay within structured-output
limits on optional and union-typed parameters. Extraction runs in three calls,
each with its own output model; TrialExtraction is assembled locally.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class CaseInsensitiveEnum(StrEnum):
    """Structured outputs do not guarantee enum casing, so match case-insensitively."""

    @classmethod
    def _missing_(cls, value: object) -> "CaseInsensitiveEnum | None":
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


class SourceLocation(CaseInsensitiveEnum):
    ABSTRACT = "abstract"
    METHODS = "methods"
    RESULTS = "results"
    TABLE = "table"
    OTHER = "other"


class Evidence(BaseModel):
    """Verbatim support for an extracted value."""

    quote: str = Field(description="Exact text span from the article supporting the value.")
    location: SourceLocation
    table_label: str | None = Field(description="e.g. 'Table 2' if location is table, else null.")


class Route(CaseInsensitiveEnum):
    SUBCUTANEOUS = "subcutaneous"
    ORAL = "oral"
    OTHER = "other"
    NOT_REPORTED = "not_reported"


class ArmRole(CaseInsensitiveEnum):
    EXPERIMENTAL = "experimental"
    PLACEBO = "placebo"
    ACTIVE_COMPARATOR = "active_comparator"


class Arm(BaseModel):
    name: str = Field(description="Arm label as written in the article.")
    role: ArmRole
    drug: str | None = Field(description="Drug name as written; null for placebo.")
    dose: str | None = Field(description="Dose as written, e.g. '1.0 mg once weekly'.")
    route: Route
    is_fixed_combination: bool = Field(
        description="True for fixed-ratio combinations (e.g. IDegLira, CagriSema)."
    )
    n_randomized: int | None
    n_analyzed: int | None
    evidence: list[Evidence]


class Population(BaseModel):
    condition: str = Field(description="Target condition, e.g. 'type 2 diabetes', 'obesity'.")
    key_inclusion_criteria: list[str]
    mean_age: float | None
    percent_female: float | None
    evidence: list[Evidence]


class EffectMeasure(CaseInsensitiveEnum):
    MEAN_DIFFERENCE = "mean_difference"
    ESTIMATED_TREATMENT_DIFFERENCE = "estimated_treatment_difference"
    HAZARD_RATIO = "hazard_ratio"
    ODDS_RATIO = "odds_ratio"
    RISK_RATIO = "risk_ratio"
    OTHER = "other"

class Estimand(CaseInsensitiveEnum):
    TREATMENT_POLICY = "treatment_policy"
    HYPOTHETICAL = "hypothetical"  # includes "trial product" estimands (as if all adhered)
    OTHER = "other"
    NOT_REPORTED = "not_reported"

class Outcome(BaseModel):
    name: str = Field(description="Outcome as written, e.g. 'change in HbA1c from baseline'.")
    is_primary: bool
    timepoint: str | None = Field(description="As written, e.g. 'week 26'.")
    comparison: str = Field(description="Format: '<arm name> vs <arm name>', exact arm names.")
    estimand: Estimand = Field(description="Estimand the value refers to, if the article names one.")
    effect_measure: EffectMeasure
    value: float | None
    ci_lower: float | None
    ci_upper: float | None
    ci_level: float | None = Field(description="e.g. 0.95")
    p_value: str | None = Field(description="As written, e.g. '<0.001'.")
    unit: str | None = Field(description="As written, e.g. '%', 'kg', 'mmol/mol'.")
    evidence: list[Evidence]


class AdverseEvent(BaseModel):
    term: str = Field(description="Adverse event term as written in the article.")
    arm_name: str = Field(description="Must exactly match one of the provided arm names.")
    n_patients: int | None
    percent_patients: float | None
    is_serious: bool | None
    evidence: list[Evidence]


# --- Per-call output models (sent to the API) ---


class DesignOutput(BaseModel):
    trial_registration: str | None = Field(description="e.g. NCT number, or null.")
    design_notes: str | None = Field(description="Blinding, phase, duration, as written.")
    population: Population
    arms: list[Arm]


class OutcomesOutput(BaseModel):
    outcomes: list[Outcome]


class AdverseEventsOutput(BaseModel):
    adverse_events: list[AdverseEvent]


# --- Assembled locally (never sent to the API) ---


class TrialExtraction(BaseModel):
    """Top-level extraction output for a single article."""

    pmcid: str
    trial_registration: str | None
    design_notes: str | None
    population: Population
    arms: list[Arm]
    outcomes: list[Outcome]
    adverse_events: list[AdverseEvent]
