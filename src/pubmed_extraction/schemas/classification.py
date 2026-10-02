"""Schema for classifying RCT-derived articles by report type."""

from pydantic import BaseModel, Field

from pubmed_extraction.schemas.trial import CaseInsensitiveEnum


class ReportType(CaseInsensitiveEnum):
    PRIMARY_REPORT = "primary_report"
    SECONDARY_ANALYSIS = "secondary_analysis"
    SUBGROUP_ANALYSIS = "subgroup_analysis"
    PROTOCOL_OR_DESIGN = "protocol_or_design"
    OTHER = "other"


class ArticleClassification(BaseModel):
    # rationale comes first so the model reasons before committing to a label
    rationale: str = Field(description="One sentence explaining the classification.")
    report_type: ReportType
    parent_trial: str | None = Field(
        description="Trial name or acronym if stated (e.g. 'SELECT', 'SUSTAIN 6'), else null."
    )
    evidence_quote: str = Field(
        description="Verbatim span from the title or abstract supporting the classification."
    )
