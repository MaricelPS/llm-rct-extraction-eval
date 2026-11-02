"""Three-step LLM extraction using Anthropic structured outputs."""

import json

from pubmed_extraction.extract.llm import UsageTracker, get_client, structured_call
from pubmed_extraction.extract.router import build_context
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
- Provide a single evidence item per extracted object, unless a second one is strictly needed.
- For values taken from a table, quote only the row label, set location to "table" and give the
  table_label. Never copy whole table rows into a quote.
- If a value is not reported, return null. Do not estimate it.
- Report numbers exactly as written. Do not convert units, recompute values, combine per-arm
  values or derive one value from another.
- When referring to trial arms, use the exact arm names provided."""

DESIGN_INSTRUCTIONS = """Extract the trial registration, design notes, study population and all arms.

Population:
- condition: the disease or condition defining the population, without qualifiers such as
  glycaemic control, ethnicity or care setting. If inclusion requires more than one condition,
  keep all of them as the article states them, joined by "and" (e.g. "condition A and
  condition B"). If participants are not selected for a disease (e.g. healthy volunteers), use
  the article's own short description of the population.
- mean_age and percent_female refer to the overall randomized population and may be stated in
  the Results text rather than in the baseline table. Use null if only per-arm values, only the
  median age or only the percentage of men are reported. Never derive percent_female by
  subtracting the percentage of men from 100 or by combining per-arm values. If the trial enrolled
  participants of only one sex by design, percent_female is 0 or 100.

Arms:
- Arms are defined by the randomized intervention. Strata or subgroups (e.g. by insulin
  sensitivity) are not separate arms.
- In crossover trials, arms are the treatment conditions: set n_randomized to null
  (participants are randomized to sequences), set n_analyzed to the size of the efficacy
  analysis set per condition when reported, and mention the crossover design in design_notes.
- name: use the arm label from the column headers of the article's tables when available.
- drug: the active substance only, without route or formulation (e.g. "semaglutide", not
  "oral semaglutide"). If the arm is a regimen described only by drug class (e.g. multiple daily insulin
  injections), use the class name (e.g. "insulin"). If the arm is a regimen described only by drug class, use the class as the article names it
  (e.g. "insulin" for multiple daily insulin injections, "basal insulin"). For drugs given
  separately in the same arm, join the substances with " + "; for fixed-ratio combination
  products, join them with "/".
- dose: maintenance dose and frequency only (e.g. "1.0 mg once weekly"), without escalation
  schedules or target-dose details.
- For placebo arms, drug and dose are null.
- n_analyzed: size of the primary efficacy analysis set defined by the article (e.g. the full
  analysis set), not the number of participants who completed the study."""

PRIMARY_OUTCOMES_INSTRUCTIONS = """Extract only the outcomes the article explicitly designates as
primary (primary outcome or primary endpoint), reported as between-arm comparisons. Set
is_primary to true. If the article designates no primary outcome, return an empty list.
- Report an entry only if the text or tables give an effect estimate or a p-value for that
  comparison and estimand. Values shown only in figures or figure legends are out of scope.
- Report each result once. If the article gives the same result in more than one unit
  (e.g. a percentage and mmol/mol), use the unit in which the outcome is defined in the
  Methods; if the Methods do not specify a unit, use the first unit reported in the Results.
- Record between-arm comparisons only, never within-arm changes from baseline.
- Write each comparison as '<arm name> vs <arm name>', experimental arm first, using the exact
  arm names below.
- If an outcome is reported under more than one estimand, report each estimand as a separate
  entry. Map the article's estimand names: "treatment policy" or "treatment regimen" estimands are
  'treatment_policy'; "trial product", "efficacy" or on-treatment estimands are 'hypothetical'.
  Use 'not_reported' only when the article names no estimand.
- effect_measure: 'estimated_treatment_difference' when the article uses that term; 'other'
  when only a between-group p-value is reported.
- p_value: as written, without a leading "p" or "P =".
Trial arms: {arms}"""

AE_INSTRUCTIONS = """Extract adverse events reported per arm from the main safety table of the
article (the general adverse event table by arm). Separate tables (e.g. hypoglycaemia episodes)
and adverse events mentioned elsewhere in the text are out of scope when a main safety table exists.
- One entry per row per arm, including cells reported as 0.
- term: copy the row label exactly as written, without rewording or shortening.
- Include summary rows (e.g. any adverse event, serious adverse events, adverse events leading to
  discontinuation) and category rows.
- When a row label alone does not name an adverse event (e.g. Mild, Level 1, Grade 3), prefix it
  with its parent row label, separated by ": " (e.g. "AEs by severity: Mild"). Rows that name an
  event (e.g. Nausea, Acute kidney injury) keep their own label; never prefix them with section
  headings such as "Safety focus areas" or "Most frequent AEs". Skip heading rows without
  values. Drop footnote markers. Skip rows that describe the outcome of adverse events rather
  than an event (e.g. "Recovered", "Not recovered", "Unknown").
- If the table reports both the overall population and subpopulations, use only the overall
  population columns.
- Report numbers of patients only. Skip rows that count events instead of patients, and never
  extract symptom scores or ratings.
- If a cell reports only a count, set percent_patients to null.
- is_serious: true for events reported as serious adverse events and for deaths; otherwise null.
  "Severe" does not mean "serious".
- If the article has no safety table, extract adverse events reported per arm in the Results
  text, only when the number or percentage of patients per arm is given. Otherwise return an
  empty list.
- A statement that no participant had an event (e.g. "No serious adverse event was reported")
  counts as 0 in every arm the statement covers: n_patients 0, percent_patients null. If the
  statement refers to the whole trial, add an entry for every arm; if it refers to one group,
  only for that arm.
- When a parent row qualifies its rows (e.g. "Serious adverse events", "Leading to treatment
  discontinuation") and a row label depends on it for its meaning (e.g. "Nervous system disorders"
  under "Serious adverse events"), prefix the row with the parent label (e.g. "Serious adverse
  events: Nervous system disorders"); such rows under "Serious adverse events" have is_serious
  true. Rows whose label is self-contained (e.g. "Adverse events leading to discontinuation")
  keep their own label, even when indented: indentation alone does not make a row a subset of
  its parent.
Trial arms (arm_name must match one exactly): {arms}"""

ALL_OUTCOMES_INSTRUCTIONS = """Extract all efficacy outcomes reported as between-arm comparisons.
Write each comparison as '<arm name> vs <arm name>' using the exact arm names below.
If an outcome is reported under more than one estimand (e.g. treatment policy and trial product),
report each estimand as a separate outcome.
Map the article's estimand names: "treatment policy" or "treatment regimen" estimands are
'treatment_policy'; "trial product", "efficacy" or on-treatment estimands are 'hypothetical'.
Use 'not_reported' only when the article names no estimand.
Values shown only in figures or figure legends are out of scope.
Report each result once. If the article gives the same result in more than one unit
(e.g. a percentage and mmol/mol), use the unit in which the outcome is defined in the
Methods; if the Methods do not specify a unit, use the first unit reported in the Results.
Trial arms: {arms}"""

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
            timeout=settings.extraction_timeout,
        )

    def extract(self, article: ParsedArticle) -> tuple[TrialExtraction, UsageTracker]:
        usage = UsageTracker()
        context = build_context(article)

        design = self._call(DesignOutput, DESIGN_INSTRUCTIONS, context, usage)
        arms = json.dumps([arm.name for arm in design.arms])

        outcomes_template = (
            ALL_OUTCOMES_INSTRUCTIONS
            if settings.extract_secondary_outcomes
            else PRIMARY_OUTCOMES_INSTRUCTIONS
        )
        outcomes = self._call(
            OutcomesOutput, outcomes_template.format(arms=arms), context, usage
        )

        adverse_events = self._call(
            AdverseEventsOutput, AE_INSTRUCTIONS.format(arms=arms), context, usage
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
