"""Three-step LLM extraction using Anthropic structured outputs."""

import json

from pubmed_extraction.extract.llm import UsageTracker, get_client, structured_call
from pubmed_extraction.extract.router import build_design_context, build_results_context
from pubmed_extraction.ingest.jats_parser import ParsedArticle
from pubmed_extraction.schemas.trial import (
    AdverseEventsOutput,
    DesignOutput,
    OutcomesOutput,
    TrialExtraction,
)
from pubmed_extraction.settings import settings

SYSTEM_PROMPT = """You extract structured data from randomized controlled trial articles.

Rules:
- Use only information stated in the provided article text. Never infer or use outside knowledge.
- Every evidence quote must be a single contiguous span copied verbatim from the article text.
  Never use ellipses or join separate fragments; use several evidence items instead.
- If a value is not reported, return null. Do not estimate it.
- Report numbers exactly as written. Do not convert units or recompute values.
- When referring to trial arms, use the exact arm names provided.
- Provide a single evidence item per extracted object, unless a second one is strictly needed."""

DESIGN_INSTRUCTIONS = """Extract the trial registration, design notes, study population and all arms.
For placebo arms, drug and dose are null."""

OUTCOMES_INSTRUCTIONS = """Extract all efficacy outcomes reported as between-arm comparisons.
Write each comparison as '<arm name> vs <arm name>' using the exact arm names below.
If an outcome is reported under more than one estimand (e.g. treatment policy and trial product),
report each estimand as a separate outcome.
Trial arms: {arms}"""

AE_INSTRUCTIONS = """Extract all adverse events reported per arm, including from safety tables.
Set is_serious to true for events reported as serious adverse events and for deaths; otherwise null.
Trial arms (arm_name must match one exactly): {arms}."""


class TrialExtractor:
    def __init__(self, model: str | None = None) -> None:
        self._client = get_client()
        self._model = model or settings.extraction_model

    def _call(self, output_model, instructions: str, context: str, usage: UsageTracker):
        return structured_call(
            self._client,
            model=self._model,
            max_tokens=settings.extraction_max_tokens,
            system=SYSTEM_PROMPT,
            user_content=f"{instructions}\n\n<article>\n{context}\n</article>",
            output_model=output_model,
            usage=usage,
            effort=settings.extraction_effort,
        )

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
