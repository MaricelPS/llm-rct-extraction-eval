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

- The article is the primary results report of a randomized trial. Secondary publications,
  post hoc analyses and substudies of an earlier trial are out of scope.
- The experimental arm must contain a GLP-1 receptor agonist (semaglutide, liraglutide,
  dulaglutide, exenatide or lixisenatide), alone or as part of a fixed-ratio combination.
  Trials where a GLP-1 RA appears only as an active comparator for a different drug class
  (e.g. survodutide, tirzepatide, retatrutide) are out of scope.
- The article must explicitly designate at least one primary outcome. Outcomes are not
  inferred from the study objective.
- The primary outcome must be a clinical efficacy outcome. Pharmacokinetic and
  bioequivalence studies (e.g. Cmax, AUC, geometric mean ratios) are out of scope.
- The article must report at least one between-arm comparison of the primary outcome.
  Articles reporting only within-arm changes are out of scope.
- Excluded articles are listed in data/gold/exclusions.csv with the reason.

## General rules

- Record values as written. Do not convert units, recompute values or derive one value from
  another (e.g. no weighted averages, no 100 minus a percentage).
- If a value is not reported in the main text or tables, use null.
- Numbers use a decimal point and no thousands separators. Percentages are plain numbers
  (12.5, not "12.5%").
- Evidence lists stay empty in the gold set.
- Replace every TODO. `px gold-validate` must report the file as valid.

## Design notes

- design_notes: a short description of the design in the article's words (e.g. "randomised,
  double-blind, placebo-controlled, 26-week phase 3 trial"). Mention crossover designs.
  Not evaluated; null if the article gives no such description.

## Population

- condition: the disease or condition defining the trial population, without qualifiers such
  as glycaemic control, ethnicity or care setting (e.g. "type 2 diabetes"). If participants
  are not selected for a disease (e.g. healthy volunteers), use the article's own short
  description of the population.
- key_inclusion_criteria: 3 to 5 main criteria (diagnosis, age range, HbA1c or BMI thresholds,
  background therapy), worded as in the article.
- mean_age and percent_female: overall randomized population, from the Results text or the
  baseline table.
    - Use null if only per-arm values are reported.
    - Use null if only the median age is reported.
    - Use null if only the percentage of men is reported.

## Arms

- Arms are defined by the randomized intervention. Strata or subgroups (e.g. by insulin
  sensitivity) are not separate arms.
- In crossover trials, arms are the treatment conditions; n_randomized is null (participants are
  randomized to sequences, not conditions) and n_analyzed is the size of the efficacy analysis
  set per condition when the article reports it (often the same number for both conditions).
- name: the arm label used in the column headers of the article's tables; otherwise as written
  in the text. Outcomes and adverse events must reuse these names exactly.
- role: experimental, placebo or active_comparator.
- drug: the active substance only, without route or formulation (e.g. "semaglutide", not
  "oral semaglutide"); the route goes in route.
- dose: maintenance dose and frequency (e.g. "1.0 mg once weekly"), without escalation
  schedules or target-dose details.
- drug and dose are null for placebo arms.
- route: subcutaneous, oral, other or not_reported.
- is_fixed_combination: true for fixed-ratio combination products (e.g. IDegLira, iGlarLixi,
  IcoSema, CagriSema).
- n_randomized: participants randomized to the arm.
- n_analyzed: size of the primary efficacy analysis set as defined by the article (e.g. the
  full analysis set), not the number of completers; null if not stated.

## Outcomes

- Annotate only outcomes the article designates as primary (is_primary: true), including all
  co-primary outcomes.
- One entry per outcome, per comparison, per estimand.
- Annotate an entry only if the text or tables report an effect estimate or a p-value for
  that comparison and estimand. Values shown only in figures are out of scope.
- comparison: exactly "<arm name> vs <arm name>", experimental arm first.
- Record the between-arm comparison only. Within-arm changes from baseline are not annotated.
- effect_measure: estimated_treatment_difference when the article uses that term (ETD);
  mean_difference for other differences in means; odds_ratio, hazard_ratio or risk_ratio as
  reported; other otherwise (e.g. only a between-group p-value).
- estimand: treatment_policy; hypothetical (includes "trial product" estimands); other; or
  not_reported if the article does not name one.
- value, ci_lower, ci_upper: as written, with the sign as reported.
- ci_level: as a decimal (0.95).
- p_value: as written, as text, without a leading "p" or "P =" (e.g. "<0.001"). If both
  non-inferiority and superiority p-values are reported, use the one for the primary
  hypothesis stated in Methods.
- unit: as written ("%-points", "kg", "mmol/mol").

## Adverse events

- Source: the main safety table of the article, meaning the general adverse event table by arm.
  Separate tables (e.g. hypoglycaemia episodes) and adverse events mentioned elsewhere in the
  text are out of scope when a main safety table exists.
- If the article has no safety table, annotate adverse events reported per arm in the Results
  text, when the number or percentage of patients per arm is given. Otherwise leave the list
  empty.
- One entry per event term per arm, including cells reported as 0.
- term: copied exactly from the table row label, without rewording.
- Include summary rows (e.g. any adverse event, serious adverse events, adverse events leading
  to discontinuation) and system organ class category rows, as written.
- Nested rows: when a row label alone does not name an adverse event (e.g. Mild, Level 1,
  Grade 3), prefix it with its parent row label, separated by ": " (e.g. "AEs by severity:
  Mild", "Hypoglycaemic events: Level 1"). Rows that name an event (e.g. Nausea) keep their own
  label even when listed under a section heading. Heading rows without values of their own are
  not annotated. Footnote markers are dropped from terms.
- If the safety table reports both the overall population and subpopulations, annotate only
  the overall population columns.
- n_patients: number of patients with the event. Rows that count events instead of patients
  (e.g. "Number of AEs", "Number of events of ...") are not annotated.
- Symptom scores or ratings (e.g. nausea scales) are not adverse events.
- percent_patients: as written; null if the cell reports only a count (e.g. "0").
- is_serious: true for events reported under serious adverse events and for deaths (fatal
  events meet the serious adverse event definition per ICH E2A); null otherwise. "Severe" does
  not imply "serious".
- A statement that no participant had an event (e.g. "No serious adverse event was reported")
  counts as 0 in every arm the statement covers: n_patients 0, percent_patients null. If the
  statement refers to the whole trial, add an entry for every arm; if it refers to one group,
  only for that arm.
- When a parent row qualifies its rows (e.g. "Serious adverse events", "Leading to treatment
  discontinuation") and a row label depends on it for its meaning (e.g. "Infections" under
  "Serious adverse events"), prefix the row with the parent label (e.g. "Serious adverse events:
  Infections"); such rows under "Serious adverse events" have is_serious true. Rows whose label
  is self-contained (e.g. "TEAEs leading to permanent discontinuation of the drug") keep their
  own label, even when indented: indentation alone does not make a row a subset of its parent.
  Example: in PMC11987204 Table 7, rows indented under "SAEs" ("TEAEs leading to treatment
  interruption", "TEAEs leading to death") are self-contained and keep their own labels; in
  PMC12577669 Table 4, "Cardiac" under "Serious adverse events" becomes "Serious adverse events: Cardiac".
