# pubmed-extraction

Structured data extraction from randomized controlled trials (RCTs) of GLP-1 receptor agonists,
using the full text of PubMed Central articles (JATS XML) and an LLM with structured outputs.
The extraction is evaluated against a hand-annotated gold set, with a frozen protocol, a single
test run and a documented adjudication of every remaining difference.

Portfolio project 2. The focus is less on the extraction itself than on measuring it honestly:
what the model gets right, what it gets wrong, and how much of the apparent error comes from
the gold set.

## What it extracts

For each trial article:

- **Population:** condition, mean age, percent female (overall randomized population).
- **Arms:** name, role, drug, maintenance dose, route, fixed-ratio combination flag,
  n randomized, n analyzed (primary efficacy analysis set).
- **Primary outcomes:** one entry per outcome, comparison and estimand, with timepoint,
  effect measure, value, confidence interval, p-value and unit.
- **Adverse events:** one entry per row of the main safety table and per arm, with term,
  number and percentage of patients, and seriousness.

Every extracted object carries verbatim evidence quotes from the article.

## Pipeline

1. **Ingest:** download the PMC JATS XML and parse it into sections and tables.
2. **Context:** build the article context passed to the model (main text and tables only;
   figures and supplementary material are out of scope).
3. **Extraction:** three structured-output calls per article (design and arms, primary
   outcomes, adverse events), validated against Pydantic schemas.
4. **Evaluation:** field-level comparison against the gold set, with greedy matching of arms,
   outcomes and adverse events, and an export of every difference for adjudication.

Configuration used for all reported results: `claude-sonnet-5`, effort `medium`,
`extraction_max_tokens` 8192 (settings are read from environment variables with prefix `PX_`).

## Evaluation design

- **Gold set:** 25 articles (5 dev, 20 test), annotated by hand from the PMC version of each
  article following [`data/gold/GUIDELINES.md`](data/gold/GUIDELINES.md). The guidelines mirror
  the rules given to the model, so that evaluation measures extraction quality rather than
  differences in criteria.
- **Quality checks:** schema validation (`gold-validate`) and heuristic guideline checks
  (`gold-lint`, with justified exceptions in `data/gold/lint_exceptions.csv`).
- **Blind annotation:** test annotations were final before any test extraction existed
  (verified from file and commit timestamps).
- **Freeze:** prompt, guidelines and gold were frozen after the dev iteration (tag `freeze-v1`).
  The test split was extracted once with that configuration.
- **Adjudication:** after the test run, every difference was reviewed against the article and
  classified as `gold_error`, `model_error`, `ambiguous` (guideline gap) or `equivalente`
  (same content, different form). Gold changes are logged one by one in
  `data/gold/adjudications.csv`; the categorization of the remaining differences is
  rule-based and reproducible (`scripts/categorize_sheet.py`).

## Results

### Dev (5 articles)

Set-level precision and recall of 100% for arms, outcomes and adverse events. Field accuracy
of 100% except `outcomes.estimand` (11/12): in PMC13538791 the estimand is stated only in
Methods, an ambiguous case accepted as an error.

### Test

| Set | Primary, pre-adjudication (19 extracted) | Primary, failure counted as empty (20) | Post-adjudication (19 eligible) |
|---|---|---|---|
| arms | P 95.0% / R 95.0% | R 90.5% | **P 98% / R 98%** |
| outcomes | P 81.5% / R 91.7% | R 88.0% | **P 91% / R 97%** |
| adverse_events | P 66.5% / R 87.5% | R 53.1% | **P 95% / R 96%** |

The bases differ and are reported separately:

- **Primary run** (tag `test-pre`): 19 of 20 test articles. PMC11417641 failed (see below).
  The middle column counts that failure as an empty prediction, which is the most conservative
  figure for the pipeline as frozen.
- **Secondary analysis** (`results/test-secondary-maxtokens`): PMC11417641 re-extracted with a
  higher output limit, everything else unchanged. Documented as a deviation, never as a
  replacement of the primary figures.
- **Post-adjudication** (tag `test-post`): adjudicated gold, 19 eligible articles
  (PMC11527811 excluded), primary-run extractions plus the secondary extraction of PMC11417641.

Field accuracy on matched items:

| Field | Pre (19 extracted) | Post (19 eligible) |
|---|---|---|
| population.condition | 42% | 53% |
| population.mean_age | 95% | 100% |
| population.percent_female | 89% | 100% |
| arms.role | 97% | 97% |
| arms.drug | 89% | 95% |
| arms.dose | 76% | 92% |
| arms.route | 87% | 90% |
| arms.is_fixed_combination | 100% | 100% |
| arms.n_randomized | 84% | 85% |
| arms.n_analyzed | 87% | 92% |
| outcomes.timepoint | 100% | 100% |
| outcomes.effect_measure | 68% | 87% |
| outcomes.estimand | 95% | 97% |
| outcomes.value | 95% | 97% |
| outcomes.ci_lower / ci_upper | 91% | 97% |
| outcomes.ci_level | 73% | 97% |
| outcomes.p_value | 91% | 87% |
| outcomes.unit | 77% | 80% |
| adverse_events.term | 99% | 67% |
| adverse_events.n_patients | 100% | 100% |
| adverse_events.percent_patients | 97% | 100% |
| adverse_events.is_serious | 96% | 98% |

Field accuracy is computed only on matched objects: a missing arm does not count against its
fields. `adverse_events.term` drops after adjudication because the 166 adverse events of
PMC11417641 enter the evaluation and the model omits their parent-row prefix (see below).

### Adjudication

- **Gold changes:** 89 logged decisions (81 gold errors, 6 guideline decisions, 1 exclusion,
  1 confirmed model error). A logged decision may cover several entries; for example, the
  re-annotation of one safety table replaced 10 entries with 66.
- **Remaining differences:** 265, all categorized: 243 `model_error`, 13 `ambiguous`,
  9 `equivalente`. Two root causes explain 186 of the 243 model errors (77%):
    - omitted parent-row prefixes in a large safety table (156);
    - a control arm named "Control" instead of the table header "Standard Care", which leaves
      every object of that arm unmatched (30).

The adjudication was done by the same person who annotated the gold set, with the model output
visible. Every change was checked against the article and cites a guideline rule, but the
post-adjudication figures may be optimistic. The pre-adjudication figures are the conservative
bound.

## Cost

Estimated at about USD 0.17 per article from the dev runs (three calls per article).

PMC11417641, the article with the largest safety table, used 61,702 input and 26,974 output
tokens in its successful re-extraction, well above the average: cost scales with the size of
the adverse event table.

Measured cost from the Anthropic console (Claude Sonnet 5 only, dates in UTC):

| Date | Cost | Content |
|---|---|---|
| 2026-10-24 | USD 5.03 | dev iteration |
| 2026-10-26 | USD 0.78 | dev iteration |
| 2026-10-27 | USD 3.89 | final dev runs and the first 2 test articles (not separable) |
| 2026-11-02 | USD 2.74 | 17 test articles, the failed attempt and the re-extraction of PMC11417641 |
| **Total** | **USD 12.43** | whole project |

The test split cost about USD 3.1 (USD 2.74 plus an estimated USD 0.35 for the 2 articles
extracted on 2026-10-27), about USD 0.15 per article including the failed call, whose tokens
were not recorded by the pipeline. The dev iteration, with repeated runs on 5 articles, cost
about USD 9.3.

## Findings

### Extraction failure

In the primary run, the adverse event call for PMC11417641 (166 adverse events, 39% of all test
adverse events) produced truncated JSON. The output limit of 8192 tokens is shared with
thinking, and the table could not fit. The failure is not random: it hits the article where
automatic extraction would add the most value. With a higher limit the article is extracted
completely and without validation errors.

Because the structured-output helper validates the response before returning it, a truncated
response raised a validation error before `stop_reason` and token usage were recorded: the
failure was not logged as a `max_tokens` stop, and its tokens are missing from the usage totals.

### Gold-set errors found in test

| Type | Examples |
|---|---|
| Mechanical rule violations | confidence level as a percentage; doses with escalation schedules or durations; descriptive units; brand names in `drug` |
| Prohibited derivations | `percent_female` computed as 100 minus percent male, or by combining per-arm values (2 articles) |
| Analysis population | completers recorded instead of the ITT population |
| Incompleteness | partial safety table; 6 co-primary outcomes omitted; zero-event statements not recorded |
| Arm names | not taken from the table column headers |
| Transcription | a non-standard Unicode space copied into 6 adverse event terms |
| Eligibility | one trial where the GLP-1 RA was background therapy in both arms; the randomized intervention was a digital platform |

Several of these were caught by lint rules added after the test run. The rules detect objective
violations of the frozen guidelines and were applied to all 24 eligible articles, dev included.

### Gold-set errors found in dev

A typo in an adverse event term ("apetite"), a descriptive unit ("% of patients"), the drug of a
combined arm, and a condition with qualifiers. Inconsistent annotation of drug combinations
appeared in 3 of 25 articles.

### Model errors

Besides the two root causes above:

- `is_serious` set to `false` instead of null, and deaths without `is_serious` true;
- outside knowledge: routes of administration not stated in the article, and an
  intention-to-treat analysis mapped to a `treatment_policy` estimand;
- adverse events taken from the discussion of external literature, not from the trial;
- the n of the baseline measurement used instead of the follow-up analysis set;
- one primary outcome split in two, with the values attached to the wrong entry.

### Data quality in the articles

- A p-value printed as `00.421` in the table of the primary outcome.
- Decimal separators written as a middle dot (`1·0`), which the evaluator does not normalize.
- Results reported only per sequence and period in a crossover trial, which cannot be assigned
  to a treatment arm without combining counts.

### Run-to-run variability

During the dev iteration, repeated runs with the same prompt produced different outputs. With a
single test run, this variability is not quantified in the test figures.

## Limitations

- Small test set (19 eligible articles) and a single test run.
- Adjudication not blind to the model output, by the same annotator (see above).
- Lint rules were extended after the test run; they only flag objective guideline violations,
  but their detection was triggered by test differences.
- The condition metric uses string similarity: differences such as "mellitus" or abbreviations
  in parentheses count as errors (they are categorized as `equivalente` in the adjudication).
- The prompt does not fully mirror the guidelines: it does not mention `mean_difference`, the
  decimal form of `ci_level` or `route: not_reported`. This explains part of the
  `effect_measure` errors.

## Future work (v2)

Guideline clarifications, from the `ambiguous` cases:

- dose of combined arms and individualized insulin regimens;
- unit of log-transformed outcomes;
- `term` for adverse events derived from zero-event statements;
- adverse events in crossover trials reported per period;
- which analysis to use when several analyses of the primary outcome are reported without
  named estimands;
- role of the arms in head-to-head comparisons of two active treatments;
- parent-row prefix when a row also names an event (prefix required when omitting it would
  produce duplicate terms in an arm);
- eligibility: the GLP-1 RA must be part of the randomized intervention.

Pipeline:

- align the prompt with the guidelines;
- check `stop_reason` and record usage before parsing, so that truncations are logged and paid
  tokens are counted;
- split adverse event extraction by table or by row blocks, and use streaming for long
  requests;
- normalize middle-dot decimals and numeric formats in the evaluator.

## Reproducing

Environment: Python 3.11 with [uv](https://docs.astral.sh/uv/). Requires an Anthropic API key
and an NCBI contact email, read from `.env` with prefix `PX_` (copy `.env.example` to `.env`
and fill it in).

```bash
uv run python -m pubmed_extraction gold-validate
uv run python -m pubmed_extraction gold-lint
uv run python -m pubmed_extraction extract --split test
uv run python -m pubmed_extraction evaluate --split test
```

On Windows, set `PYTHONUTF8=1` when redirecting output to a file.

Frozen results:

| Tag / folder | Content |
|---|---|
| `freeze-v1` | prompt, guidelines and gold frozen after dev |
| `test-pre`, `results/test-primary/` | primary test run, before adjudication |
| `results/test-secondary-maxtokens/` | re-extraction of PMC11417641 |
| `test-post`, `results/test-post-adjudication/` | evaluation with the adjudicated gold |

## Repository layout

```text
data/
  gold/
    GUIDELINES.md                annotation guidelines
    candidates.csv               candidate articles considered for the gold set
    split.csv                    dev/test split
    exclusions.csv               excluded articles with reasons
    annotations/                 gold annotations (one JSON per article)
    excluded/                    annotations of articles excluded from the gold set
    tables/                      transcribed safety tables (CSV) used to build adverse events
    lint_exceptions.csv          justified lint exceptions
    adjudications.csv            log of every gold change after the test run
    adjudication_sheet_test.csv  categorized remaining differences
  raw/                           PMC JATS XML (not versioned)
  processed/                     extractions, evaluation output and DuckDB store (not versioned)
results/
  test-primary/                  primary test run (19/20), before adjudication
  test-secondary-maxtokens/      re-extraction of PMC11417641
  test-post-adjudication/        evaluation with the adjudicated gold
scripts/
  ae_table_to_json.py            builds adverse events from a transcribed table
  adjudicate_batch_[a-f].py      gold corrections, one batch per adjudication round
  categorize_sheet.py            rule-based categorization of remaining differences
  smoke_*.py                     smoke tests for ingest and classification
src/pubmed_extraction/
  ingest/                        NCBI client, search queries, JATS parser
  extract/                       candidate classifier, context router, extractor, LLM calls,
                                 validation
  schemas/                       Pydantic schemas (classification, trial)
  evaluate/                      gold utilities and lint, comparison, adjudication export
  storage/                       DuckDB storage
  cli.py                         command-line entry point
  settings.py                    configuration (environment variables, prefix PX_)
```
