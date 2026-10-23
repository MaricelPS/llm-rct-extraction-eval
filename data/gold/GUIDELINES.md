# Gold-Set Annotation Guidelines

These guidelines define how gold annotations are produced. They mirror the rules given to the
extraction model, so that evaluation measures extraction quality rather than differences in
criteria.

## Source and scope

- Annotate from the PMC version of the article (https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/),
  which is rendered from the same JATS XML the pipeline processes.
- Use only the main text and its tables. Supplementary material, figures and tables available
  only as images are out of scope, because the model does not receive them.
- Annotate blind: never look at model outputs for test-set articles before annotation is final.

## Eligible trials

- The experimental arm must contain a GLP-1 receptor agonist (semaglutide, liraglutide,
  dulaglutide, exenatide or lixisenatide), alone or as part of a fixed-ratio combination.
- Trials where a GLP-1 RA appears only as an active comparator for a different drug class
  (e.g. dual or triple incretin agonists such as survodutide, tirzepatide or retatrutide)
  are out of scope. Excluded articles are listed in data/gold/exclusions.csv.
- The primary outcome must be a clinical efficacy outcome. Pharmacokinetic and
  bioequivalence studies (e.g. Cmax, AUC, geometric mean ratios) are out of scope.
-
## General rules

- Record values as written. Do not convert units, recompute values or derive one value from
  another.
- If a value is not reported in the main text or tables, use null.
- Numbers use a decimal point and no thousands separators. Percentages are plain numbers
  (12.5, not "12.5%").
- Evidence lists stay empty in the gold set.
- Replace every TODO. `px gold-validate` must report the file as valid.

## Population

- condition: the condition defining the trial population, as named in the article.
- key_inclusion_criteria: 3 to 5 main criteria (diagnosis, age range, HbA1c or BMI thresholds,
  background therapy), worded as in the article.
- mean_age and percent_female: overall randomized population, from the baseline table.
    - Use null if only per-arm values are reported (no weighted averages).
    - Use null if only the median age is reported.
    - Use null if only the percentage of men is reported.

## Arms

- name: arm label as written in the article. Outcomes and adverse events must reuse these names
  exactly.
- role: experimental, placebo or active_comparator.
- drug and dose: as written; drug is null for placebo arms.
- route: subcutaneous, oral, other or not_reported.
- is_fixed_combination: true for fixed-ratio combination products (e.g. IDegLira, iGlarLixi,
  IcoSema, CagriSema).
- n_randomized: participants randomized to the arm.
- n_analyzed: participants in the primary efficacy analysis set, if stated; otherwise null.

## Outcomes

- Annotate primary outcomes only (is_primary: true). Include all co-primary outcomes.
- One entry per outcome, per comparison, per estimand. A three-arm trial with one primary
  outcome and two estimands yields four entries.
- comparison: exactly "<arm name> vs <arm name>", experimental arm first.
- Record the between-arm effect only. Within-arm changes from baseline are not annotated.
- effect_measure: estimated_treatment_difference when the article uses that term (ETD);
  mean_difference for other differences in means; odds_ratio, hazard_ratio or risk_ratio as
  reported; other otherwise.
- estimand: treatment_policy; hypothetical (includes "trial product" estimands); other; or
  not_reported if the article does not name one.
- value, ci_lower, ci_upper: as written, with the sign as reported.
- ci_level: as a decimal (0.95).
- p_value: as written, as text ("<0.001"). If both non-inferiority and superiority p-values
  are reported, use the one for the primary hypothesis stated in Methods.
- unit: as written ("%-points", "kg", "mmol/mol").

## Adverse events

- Source: the main safety table of the article.
- One entry per event term per arm, with the term as written in the table row.
- Include summary rows (e.g. any adverse event, serious adverse events, adverse events leading
  to discontinuation) as written.
- n_patients and percent_patients: as written; null if the table reports only one of them.
- is_serious: true for events reported under serious adverse events and for deaths (fatal
  events meet the serious adverse event definition per ICH E2A); null otherwise.
