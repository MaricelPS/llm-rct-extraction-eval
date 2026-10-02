"""PubMed queries used by the pipeline."""

GLP1_RCT_QUERY = (
    "(semaglutide[tiab] OR liraglutide[tiab] OR dulaglutide[tiab] "
    "OR exenatide[tiab] OR lixisenatide[tiab]) "
    'AND "Randomized Controlled Trial"[pt] '
    'AND "pubmed pmc"[sb] '
    'NOT "Retracted Publication"[pt]'
)
