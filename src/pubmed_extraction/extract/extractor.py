"""Three-step LLM extraction using Anthropic structured outputs."""

import json
from dataclasses import dataclass, field
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from pubmed_extraction.extract.router import build_design_context, build_results_context
from pubmed_extraction.ingest.jats_parser import ParsedArticle
from pubmed_extraction.schemas.trial import (
    AdverseEventsOutput,
    DesignOutput,
    OutcomesOutput,
    TrialExtraction,
)
from pubmed_extraction.settings import settings

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT = """You extract structured data from randomized controlled trial articles.

Rules:
- Use only information stated in the provided article text. Never infer or use outside knowledge.
- Every evidence quote must be copied verbatim from the article text.
- If a value is not reported, return null. Do not estimate it.
- Report numbers exactly as written. Do not convert units or recompute values.
- When referring to trial arms, use the exact arm names provided."""

DESIGN_INSTRUCTIONS = "Extract the trial registration, design notes, study population and all arms."

OUTCOMES_INSTRUCTIONS = """Extract all efficacy outcomes reported as between-arm comparisons.
Trial arms: {arms}"""

AE_INSTRUCTIONS = """Extract all adverse events reported per arm, including from safety tables.
Trial arms (arm_name must match one exactly): {arms}"""


class ExtractionError(Exception):
    pass


@dataclass
class UsageTracker:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: list[str] = field(default_factory=list)


class TrialExtractor:
    def __init__(self, model: str | None = None) -> None:
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = model or settings.extraction_model

    def _call(
            self, output_model: type[T], instructions: str, context: str, usage: UsageTracker
    ) -> T:
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=settings.extraction_max_tokens,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"{instructions}\n\n<article>\n{context}\n</article>",
                    }
                ],
                output_format=output_model,
            )
        except ValidationError as exc:
            raise ExtractionError(f"{output_model.__name__}: invalid output: {exc}") from exc

        usage.input_tokens += response.usage.input_tokens
        usage.output_tokens += response.usage.output_tokens
        usage.calls.append(output_model.__name__)

        if response.stop_reason in ("refusal", "max_tokens"):
            raise ExtractionError(f"{output_model.__name__}: stop_reason={response.stop_reason}")
        return response.parsed_output

    def extract(self, article: ParsedArticle) -> tuple[TrialExtraction, UsageTracker]:
        usage = UsageTracker()
        design_ctx = build_design_context(article)
        results_ctx = build_results_context(article)

        design = self._call(DesignOutput, DESIGN_INSTRUCTIONS, design_ctx, usage)
        arms = json.dumps([arm.name for arm in design.arms])

        outcomes = self._call(
            OutcomesOutput, OUTCOMES_INSTRUCTIONS.format(arms=arms), results_ctx, usage
        )
        adverse_events = self._call(
            AdverseEventsOutput, AE_INSTRUCTIONS.format(arms=arms), results_ctx, usage
        )

        extraction = TrialExtraction(
            pmcid=article.pmcid,
            trial_registration=design.trial_registration,
            design_notes=design.design_notes,
            population=design.population,
            arms=design.arms,
            outcomes=outcomes.outcomes,
            adverse_events=adverse_events.adverse_events,
        )
        return extraction, usage